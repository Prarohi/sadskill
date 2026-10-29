#!/usr/bin/env python3
"""
sadskill Installation Manifest & Transaction Manager (v0.3.0)

Transactional manifest recording, ownership verification, safe restoration,
and uninstallation without data loss.

Invariants enforced here:
  * Manifest files are validated fail-closed: corrupt, tampered, partially
    written, symlinked, or future-version manifests are refused (never reset
    to an empty ledger).
  * Every mutating operation holds an exclusive advisory lock on the manifest
    for its whole duration (``.install-manifest.json.lock`` next to it).
  * A recorded backup is only ever deleted when it is byte-identical to the
    content sadskill itself installed. Backups that may hold user content are
    preserved and surfaced as conflict backups.
  * ``--dry-run`` performs no filesystem writes at all.

Exit codes:
    0  success
    2  usage error / destination outside allowed roots
    3  corrupt or invalid manifest (fail closed)
    6  manifest locked by another process
"""

import argparse
import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from . import sadskill_core as core
except ImportError:
    import sadskill_core as core

MANIFEST_VERSION = "0.3.0"

# Seconds a process waits for a contended manifest lock before failing.
LOCK_WAIT_SECONDS = 10.0

_ENTRY_TYPES = {
    "agent": str,
    "destination": str,
    "backup": str,
    "content_hash": str,
    "content_hash_type": str,
    "target_root": str,
    "backup_hash": str,
    "installed_at": str,
    "restored": bool,
}


class ManifestError(Exception):
    """Manifest file is corrupt, tampered with, or structurally invalid."""


class LockError(Exception):
    """Manifest is locked by another process."""


def compute_sha256(path):
    """Compute SHA-256 digest of a file or directory tree ("" if absent)."""
    if not path.exists():
        return ""
    return core.compute_sha256(path)


def get_allowed_roots(target_dir=None):
    """Return canonical allowed root directories for sadskill installations."""
    home = Path.home().resolve()
    roots = [
        home / ".codex",
        home / ".claude",
        home / ".gemini",
        home / ".agents",
        home / ".sadskill",
    ]
    if target_dir:
        roots.append(Path(target_dir).resolve())
    return roots


_CURSOR_AGENTS = {"cursor_skill", "cursor_rule"}


def _entry_allowed_roots(entry, target_dir, default_roots):
    """Scope Cursor mutations to this invocation's explicit workspace only."""
    if entry.get("agent") in _CURSOR_AGENTS:
        return [Path(target_dir).resolve()] if target_dir else []
    return default_roots


def is_path_contained_in_roots(path: Path, allowed_roots) -> bool:
    """Ensure path is strictly within one of the allowed roots."""
    try:
        resolved = path.resolve()
        for root in allowed_roots:
            try:
                if resolved == root or resolved.is_relative_to(root):
                    return True
            except AttributeError:
                if str(resolved) == str(root) or str(resolved).startswith(str(root) + os.sep):
                    return True

        # Cursor workspace paths are allowed only through an explicit target_dir
        # root above. A destination or target_root stored in the manifest must not
        # expand the current command's deletion boundary.
        return False
    except Exception:
        return False


def _parse_version(version: str):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", version)
    if not match:
        raise ManifestError(f"invalid manifest version: {version!r}")
    return tuple(int(part) for part in match.groups())


def validate_manifest(data):
    """Structurally validate manifest data; raise ManifestError when invalid.

    Unknown extra keys on the top level or on entries are preserved (not
    validated) so newer tooling metadata survives round-trips through this
    manager.
    """
    if not isinstance(data, dict):
        raise ManifestError("manifest top-level value must be a JSON object")
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise ManifestError("manifest is missing a valid 'version' string")
    parsed = _parse_version(version)
    if parsed > _parse_version(MANIFEST_VERSION):
        raise ManifestError(
            f"manifest schema version {version} is newer than the supported "
            f"version {MANIFEST_VERSION}; refusing to operate on it"
        )
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ManifestError("manifest 'entries' must be a list")
    seen_destinations = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ManifestError(f"manifest entry #{index} must be a JSON object")
        try:
            core.validate_ownership_metadata(entry)
        except core.ManifestError as exc:
            raise ManifestError(str(exc)) from exc
        destination = entry.get("destination")
        if not isinstance(destination, str) or not destination:
            raise ManifestError(f"manifest entry #{index} has no valid 'destination'")
        if not os.path.isabs(destination):
            raise ManifestError(
                f"manifest entry #{index} destination is not an absolute path: {destination!r}"
            )
        if destination in seen_destinations:
            raise ManifestError(f"manifest has duplicate entries for destination: {destination}")
        seen_destinations.add(destination)
        for field, expected_type in _ENTRY_TYPES.items():
            if field in entry and not isinstance(entry[field], expected_type):
                raise ManifestError(
                    f"manifest entry #{index} field {field!r} must be of type "
                    f"{expected_type.__name__}"
                )
        if entry.get("content_hash_type") not in (None, "file", "tree"):
            raise ManifestError(
                f"manifest entry #{index} content_hash_type must be 'file' or 'tree'"
            )
        target_root = entry.get("target_root")
        if target_root and not os.path.isabs(target_root):
            raise ManifestError(
                f"manifest entry #{index} target_root must be an absolute path"
            )


def load_manifest(manifest_path: Path):
    """Load and validate a manifest. Fails closed on any structural problem."""
    if manifest_path.is_symlink():
        raise ManifestError(f"manifest is a symbolic link, refusing: {manifest_path}")
    if not manifest_path.exists():
        return {"version": MANIFEST_VERSION, "entries": []}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise ManifestError(f"cannot parse manifest {manifest_path}: {exc}") from exc
    validate_manifest(data)
    return data


def _fsync_dir(directory: Path):
    try:
        dir_fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def save_manifest_atomic(manifest_path: Path, data: dict):
    """Write the manifest via write-temp + rename, fsyncing file and directory."""
    validate_manifest(data)
    core.atomic_write_text(manifest_path, json.dumps(data, indent=2) + "\n", mode=0o600)


class LockFile:
    """Exclusive advisory lock next to a manifest, held for a whole operation."""

    def __init__(self, manifest_path: Path):
        self.path = manifest_path.parent / f".{manifest_path.name}.lock"
        self.fd = None
        self.borrowed = False

    def __enter__(self):
        inherited = os.environ.get("SADSKILL_INSTALL_LOCK_FD")
        if inherited:
            try:
                fd = int(inherited)
                actual = os.fstat(fd)
                expected = self.path.lstat()
                if not stat.S_ISREG(expected.st_mode) or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                    raise ValueError("descriptor does not identify the manifest lock")
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.fd = os.dup(fd)
                self.borrowed = True
                return self
            except (OSError, ValueError) as exc:
                raise LockError(f"invalid inherited installer lock: {exc}") from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(self.fd)
                    self.fd = None
                    raise LockError(
                        f"manifest is locked by another process: {self.path}"
                    ) from None
                time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                if not self.borrowed:
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None
        return False


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_owned_destinations(data, target_dir=""):
    """A manifest may name only the artifacts this installer actually owns."""
    home = Path.home().resolve()
    fixed = {
        "claude": home / ".claude/skills/sadskill",
        "codex": home / ".codex/skills/sadskill",
        "gemini": home / ".gemini/skills/sadskill",
        "antigravity": home / ".gemini/antigravity/skills/sadskill",
        "claude_hook": home / ".claude/hooks/git-guardrail.sh",
    }
    command_names = {f"sad-{mode}.md" for mode in ("plan", "design", "backend", "sec", "analyze")}
    for entry in data["entries"]:
        agent = entry["agent"]
        dest = Path(entry["destination"])
        if agent in fixed:
            expected = fixed[agent]
        elif agent in {"claude_command", "codex_prompt"}:
            parent = home / (".claude/commands" if agent == "claude_command" else ".codex/prompts")
            if dest.name not in command_names:
                raise ManifestError(f"not a Sadskill command destination: {dest}")
            expected = parent / dest.name
        elif agent in {"cursor_skill", "cursor_rule"}:
            workspace = Path(entry.get("target_root") or target_dir).resolve()
            expected = workspace / (".cursor/skills/sadskill" if agent == "cursor_skill" else ".cursor/rules/sadskill.mdc")
        else:
            raise ManifestError(f"unsupported installation agent: {agent}")
        if dest != expected or dest.resolve() != expected:
            raise ManifestError(f"destination does not match its canonical Sadskill artifact: {dest}")
        if entry.get("backup"):
            backup = Path(entry["backup"])
            if (backup.parent != dest.parent
                    or not backup.name.startswith(dest.name + ".bak.")
                    or backup.name == dest.name + ".bak."
                    or backup.resolve() != backup or backup.is_symlink()):
                raise ManifestError(f"backup is not a canonical sibling of its destination: {backup}")


def _remove_path(path: Path):
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as exc:
        print(f"   [WARN] Could not remove {path}: {exc}")


def record_entry(manifest_path: Path, agent: str, destination: str, backup_path: str = "", target_dir: str = ""):
    allowed_roots = get_allowed_roots(target_dir)
    dest_p = Path(destination).resolve()
    if agent in _CURSOR_AGENTS:
        if not target_dir:
            raise ValueError("Cursor artifacts require an explicit target workspace")
        allowed_roots = [Path(target_dir).resolve()]
        if dest_p == allowed_roots[0]:
            raise ValueError("Cursor artifact destination must be inside the target workspace")
    if not is_path_contained_in_roots(dest_p, allowed_roots):
        raise ValueError(f"Destination path traverses outside allowed roots: {destination}")

    backup_p = Path(backup_path).resolve() if backup_path else None
    if backup_p and not is_path_contained_in_roots(backup_p, allowed_roots):
        raise ValueError(f"Backup path traverses outside allowed roots: {backup_path}")

    data = load_manifest(manifest_path)
    content_hash = compute_sha256(dest_p)
    if not content_hash:
        raise ManifestError("cannot record ownership of an absent destination")
    backup_hash = compute_sha256(backup_p) if backup_p and backup_p.exists() else ""
    timestamp = _now_iso()

    # Record the actual security boundary that owns this destination. The
    # install CLI always passes its Cursor workspace target, even when it is
    # recording an ordinary HOME install, so using target_dir unconditionally
    # both mislabels ownership and can later block safe updater operations.
    matching_roots = []
    for root in allowed_roots:
        try:
            if dest_p == root or dest_p.is_relative_to(root):
                matching_roots.append(root)
        except AttributeError:  # Python < 3.9 compatibility
            try:
                dest_p.relative_to(root)
                matching_roots.append(root)
            except ValueError:
                pass
    if not matching_roots:
        raise ValueError(f"Destination has no recorded allowed root: {destination}")
    recorded_root = max(matching_roots, key=lambda root: len(root.parts))

    entry = {
        "agent": agent,
        "destination": str(dest_p),
        "backup": str(backup_p) if backup_p else "",
        "content_hash": content_hash,
        "content_hash_type": "tree" if dest_p.is_dir() else "file",
        "content_hash_format": "tree-sha256-v2" if dest_p.is_dir() else "sha256",
        "target_root": str(recorded_root),
        "backup_hash": backup_hash,
        "installed_at": timestamp,
        "restored": False,
    }
    validate_owned_destinations({"entries": [entry]}, target_dir)

    existing_idx = None
    for idx, e in enumerate(data["entries"]):
        if e.get("destination") == str(dest_p):
            existing_idx = idx
            break

    if existing_idx is not None:
        existing = dict(data["entries"][existing_idx])
        # Preserve the true pre-sadskill backup reference from the first install.
        entry["backup"] = existing.get("backup", "")
        entry["backup_hash"] = existing.get("backup_hash", "")
        # Carry forward unknown/custom keys (e.g. conflict_backups) so history
        # recorded by newer tooling survives a re-record.
        for key, value in existing.items():
            if key not in entry:
                entry[key] = value

        if backup_p and str(backup_p) != entry["backup"] and backup_p.exists():
            fresh_backup_hash = compute_sha256(backup_p)
            if fresh_backup_hash and fresh_backup_hash == content_hash:
                # Redundant copy of sadskill's own installed content: safe to discard.
                _remove_path(backup_p)
            else:
                # This backup may hold user-modified content. Never discard it;
                # record it so uninstall/restore flows can account for it.
                conflicts = existing.get("conflict_backups")
                if not isinstance(conflicts, list):
                    conflicts = []
                if str(backup_p) not in [c.get("path") for c in conflicts if isinstance(c, dict)]:
                    conflicts.append(
                        {"path": str(backup_p), "hash": fresh_backup_hash, "created_at": timestamp}
                    )
                entry["conflict_backups"] = conflicts
        data["entries"][existing_idx] = entry
    else:
        data["entries"].append(entry)

    save_manifest_atomic(manifest_path, data)
    print(f"   [MANIFEST] Recorded {agent} -> {dest_p}")


def _archive_forced_destination(dest_p: Path, entry: dict, manifest_path: Path,
                                data: dict, allowed_roots, dry_run: bool = False):
    """Move modified destination content to a recorded sibling before restore."""
    current_hash = compute_sha256(dest_p)
    installed_hash = entry.get("content_hash", "")
    if installed_hash and current_hash == installed_hash:
        return

    stamp = f"{time.time_ns()}_{os.getpid()}"
    archive = dest_p.with_name(f"{dest_p.name}.bak.{stamp}")
    suffix = 0
    while archive.exists() or archive.is_symlink():
        suffix += 1
        archive = dest_p.with_name(f"{dest_p.name}.bak.{stamp}_{suffix}")
    if not is_path_contained_in_roots(archive, allowed_roots):
        raise ManifestError(f"conflict backup is outside allowed roots: {archive}")
    if dry_run:
        print(f"   [DRY-RUN] Would preserve modified destination at: {archive}")
        return

    # The backup lives beside the destination, so rename preserves its exact
    # bytes/tree atomically and never deletes user data to make room for restore.
    try:
        os.rename(dest_p, archive)
    except OSError as exc:
        raise ManifestError(f"cannot preserve modified destination {dest_p}: {exc}") from exc

    archive_hash = compute_sha256(archive)
    conflicts = entry.get("conflict_backups")
    if not isinstance(conflicts, list):
        conflicts = []
    conflicts.append({"path": str(archive), "hash": archive_hash, "created_at": _now_iso()})
    entry["conflict_backups"] = conflicts
    # Persist provenance before replacing the destination with the older backup.
    # If persistence fails, the user's bytes remain in the sibling archive.
    save_manifest_atomic(manifest_path, data)
    print(f"   [PRESERVE-MODIFIED] Archived user content at: {archive}")
    if not archive_hash or archive_hash != current_hash:
        raise ManifestError(f"conflict backup verification failed for {dest_p}")


def perform_restore(manifest_path: Path, target_dir: str = "", force: bool = False, dry_run: bool = False):
    """Restore backed up files without deleting them afterwards."""
    if not manifest_path.exists():
        print("   [INFO] No manifest found to restore from.")
        return 0

    allowed_roots = get_allowed_roots(target_dir)
    data = load_manifest(manifest_path)
    validate_owned_destinations(data, target_dir)
    entries = data.get("entries", [])
    restored_count = 0
    had_conflict = False

    # Process in reverse order so latest installations roll back first
    for entry in reversed(entries):
        dest_str = entry.get("destination")
        bak_str = entry.get("backup")
        if not bak_str or entry.get("restored"):
            continue

        dest_p = Path(dest_str).resolve()
        bak_p = Path(bak_str).resolve()

        entry_roots = _entry_allowed_roots(entry, target_dir, allowed_roots)
        if not is_path_contained_in_roots(dest_p, entry_roots) or not is_path_contained_in_roots(bak_p, entry_roots):
            print(f"   [WARN] Skipping restore for path outside allowed roots: {dest_p} / {bak_p}")
            continue

        if not bak_p.exists():
            print(f"   [WARN] Backup not found at {bak_p}")
            continue

        if compute_sha256(bak_p) != entry.get("backup_hash"):
            print(f"   [CONFLICT] Backup changed or uses an unverified legacy tree hash: {bak_p}")
            had_conflict = True
            continue

        if dest_p.exists():
            # Safety check: if user modified the installed file since installation, preserve it unless forced
            installed_hash = entry.get("content_hash")
            curr_hash = compute_sha256(dest_p)
            if installed_hash and curr_hash and curr_hash != installed_hash and not force:
                print(f"   [CONFLICT] Destination modified since install: {dest_p}")
                print(f"   [PRESERVE-MODIFIED] Refusing to overwrite modified file without --force. Backup preserved at {bak_p}")
                had_conflict = True
                continue
            if force and (not installed_hash or not curr_hash or curr_hash != installed_hash):
                _archive_forced_destination(
                    dest_p, entry, manifest_path, data, entry_roots, dry_run=dry_run
                )

        print(f"   [RESTORE] Restoring {dest_p} from {bak_p}")
        if not dry_run:
            dest_p.parent.mkdir(parents=True, exist_ok=True)
            if dest_p.exists():
                if dest_p.is_dir() and not dest_p.is_symlink():
                    shutil.rmtree(dest_p)
                else:
                    dest_p.unlink()
            shutil.move(str(bak_p), str(dest_p))
            entry["restored"] = True
            restored_count += 1

    if not dry_run:
        save_manifest_atomic(manifest_path, data)
    print(f"   [RESTORE] Successfully restored {restored_count} entries.")
    if had_conflict:
        print("   [RESTORE] Some destinations were modified and left untouched without --force.")
        return 5
    return 0


def _entry_has_preserved_content(entry: dict) -> bool:
    """True when an entry still references backups holding possible user content."""
    backup = entry.get("backup", "")
    if backup and Path(backup).exists():
        backup_hash = entry.get("backup_hash", "")
        content_hash = entry.get("content_hash", "")
        current_hash = compute_sha256(Path(backup))
        if not (backup_hash and content_hash and current_hash == backup_hash == content_hash):
            return True
    conflicts = entry.get("conflict_backups") or []
    if isinstance(conflicts, list):
        for conflict in conflicts:
            if isinstance(conflict, dict):
                path = conflict.get("path", "")
                if path and Path(path).exists():
                    return True
    return False


def perform_uninstall(manifest_path: Path, target_dir: str = "", restore_previous: bool = False, clean_backups: bool = False, force: bool = False, dry_run: bool = False):
    """Transactional uninstaller: removes only owned files, preserves restored files."""
    if not manifest_path.exists():
        print("   [INFO] No manifest found; nothing to uninstall via manifest.")
        return 0

    allowed_roots = get_allowed_roots(target_dir)
    data = load_manifest(manifest_path)
    validate_owned_destinations(data, target_dir)
    entries = data.get("entries", [])

    # Step 1: If restore_previous requested, perform safe restoration first
    if restore_previous:
        print("-> Performing safe transactional restoration from backups...")
        restore_status = perform_restore(manifest_path, target_dir=target_dir, force=force, dry_run=dry_run)
        # Reload manifest after restore
        data = load_manifest(manifest_path)
        entries = data.get("entries", [])

    removed_count = 0
    # Step 2: Remove installed files that were NOT restored
    for entry in entries:
        if entry.get("restored"):
            # Preserved because it was restored to the user's original version!
            print(f"   [PRESERVE] Keeping restored user file: {entry.get('destination')}")
            continue

        dest_str = entry.get("destination")
        if not dest_str:
            continue
        dest_p = Path(dest_str).resolve()

        entry_roots = _entry_allowed_roots(entry, target_dir, allowed_roots)
        if not is_path_contained_in_roots(dest_p, entry_roots):
            print(f"   [WARN] Skipping removal for destination outside allowed roots: {dest_p}")
            continue

        if dest_p.exists():
            # Safety check: if user modified the installed file since installation, preserve it to prevent data loss
            installed_hash = entry.get("content_hash")
            curr_hash = compute_sha256(dest_p)
            if installed_hash and curr_hash and curr_hash != installed_hash and not force:
                print(f"   [PRESERVE-MODIFIED] Preserving user-modified file: {dest_p} (use --force to remove)")
                continue

            print(f"   [REMOVE] Removing sadskill-owned artifact: {dest_p}")
            if not dry_run:
                if dest_p.is_dir() and not dest_p.is_symlink():
                    shutil.rmtree(dest_p)
                else:
                    dest_p.unlink()
                removed_count += 1
        else:
            print(f"   [INFO] Destination already absent: {dest_p}")

    # Step 3: Clean backups if requested, ONLY cleaning backups recorded in the manifest
    if clean_backups:
        print("-> Cleaning sadskill-recorded backup archives...")
        for entry in entries:
            if entry.get("restored"):
                continue
            bak_str = entry.get("backup")
            if not bak_str:
                continue
            bak_p = Path(bak_str).resolve()
            entry_roots = _entry_allowed_roots(entry, target_dir, allowed_roots)
            if not is_path_contained_in_roots(bak_p, entry_roots):
                continue
            if not bak_p.exists() or ".bak." not in bak_p.name:
                continue
            backup_hash = entry.get("backup_hash", "")
            content_hash = entry.get("content_hash", "")
            current_backup_hash = compute_sha256(bak_p)
            if backup_hash and content_hash and current_backup_hash == backup_hash == content_hash:
                # Backup is byte-identical to what sadskill installed: no user
                # content can be lost by removing it.
                print(f"   [CLEAN-BACKUP] Removing owned backup: {bak_p}")
                if not dry_run:
                    _remove_path(bak_p)
            else:
                print(
                    f"   [PRESERVE-BACKUP] Keeping unresolved backup (may contain user "
                    f"content; restoration was not confirmed): {bak_p}"
                )

    if not dry_run:
        # Prune resolved entries. Entries whose destination is gone but which
        # still reference preserved backups remain recorded so no backup ever
        # becomes an untracked orphan.
        def _resolved(entry):
            if entry.get("restored"):
                return not _entry_has_preserved_content(entry)
            destination = entry.get("destination", "")
            if destination and Path(destination).exists():
                return False
            return not _entry_has_preserved_content(entry)

        data["entries"] = [e for e in entries if not _resolved(e)]
        save_manifest_atomic(manifest_path, data)

    print(f"   [OK] Cleaned {removed_count} installed artifacts.")
    if restore_previous:
        # Truthful signal: restoration was requested but some destinations were
        # user-modified and left untouched. Backups are preserved.
        return restore_status if restore_status else 0
    return 0


# Standard parent directories (relative to $HOME / target) that hold backup
# artifacts created by the installer. Used by adopt-orphans only.
_ORPHAN_PARENTS = (
    (".codex", "skills"),
    (".codex", "prompts"),
    (".claude", "skills"),
    (".claude", "commands"),
    (".claude", "hooks"),
    (".gemini", "skills"),
    (".gemini", "antigravity", "skills"),
)
_CURSOR_ORPHAN_PARENTS = (
    (".cursor", "rules"),
    (".cursor", "skills"),
)
_AGENT_BY_ROOT = {
    ".codex": "codex",
    ".claude": "claude",
    ".gemini": "gemini",
    ".cursor": "cursor",
    ".agents": "agents",
}


def adopt_orphans(manifest_path: Path, target_dir: str = "", dry_run: bool = False):
    """Reference pre-existing ``*.bak.*`` backup artifacts in the manifest.

    For interrupted installs (backup moved, manifest never written) this makes
    the existing backup ledger-manageable without moving or deleting anything.
    Orphan backups are kept exactly where they are; they are only referenced.
    """
    data = load_manifest(manifest_path)
    orphans = data.setdefault("orphan_backups", [])
    if not isinstance(orphans, list):
        raise ManifestError("orphan_backups must be a list")
    home = Path.home().resolve()
    candidates = []
    for parts in _ORPHAN_PARENTS:
        candidates.append((home.joinpath(*parts), _AGENT_BY_ROOT[parts[0]]))
    if target_dir:
        target = Path(target_dir).resolve()
        for parts in _CURSOR_ORPHAN_PARENTS:
            candidates.append((target.joinpath(*parts), _AGENT_BY_ROOT[parts[0]]))

    adopted = 0
    for parent, agent in candidates:
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir()):
            name = child.name
            if ".bak." not in name or name.endswith(".lock"):
                continue
            original_name = name.split(".bak.")[0]
            if not original_name:
                print(f"   [WARN] Cannot derive original name for backup artifact, skipping: {child}")
                continue
            if original_name != "sadskill" and original_name != "git-guardrail.sh" and not re.fullmatch(
                    r"sad-(?:plan|design|backend|sec|analyze)\.md|sadskill\.mdc", original_name):
                continue
            if child.is_symlink() or not is_path_contained_in_roots(child, get_allowed_roots(target_dir)):
                continue
            destination = parent / original_name
            backup_hash = compute_sha256(child)
            timestamp = _now_iso()
            # Discovery is not proof that the current destination is ours.
            # Keep recovery inventory separate from installed ownership entries.
            if not any(isinstance(record, dict) and record.get("path") == str(child) for record in orphans):
                orphans.append({"path": str(child), "hash": backup_hash,
                                "destination": str(destination), "agent": agent,
                                "discovered_at": timestamp})
                adopted += 1
                print(f"   [ADOPT] Inventoried recovery backup without destination ownership: {child}")

    if not dry_run and adopted:
        save_manifest_atomic(manifest_path, data)
    print(f"   [OK] Adopted {adopted} orphan backup artifact(s).")
    return 0


def main():
    parser = argparse.ArgumentParser(description="sadskill manifest & transaction manager")
    subparsers = parser.add_subparsers(dest="action", required=True)

    val = subparsers.add_parser("validate", help="Validate before any installer mutation")
    val.add_argument("--manifest", required=True)
    val.add_argument("--target", default="")
    val.add_argument("--dry-run", action="store_true")
    ins = subparsers.add_parser("install", help="Run installer under its manifest lock")
    ins.add_argument("--manifest", required=True)
    ins.add_argument("--target", default="")
    ins.add_argument("installer_args", nargs=argparse.REMAINDER)

    # record
    rec = subparsers.add_parser("record")
    rec.add_argument("--manifest", required=True, help="Path to manifest JSON")
    rec.add_argument("--agent", required=True, help="Agent type")
    rec.add_argument("--destination", required=True, help="Destination path")
    rec.add_argument("--backup", default="", help="Backup path")
    rec.add_argument("--target", default="", help="Explicit target dir")

    # restore
    res = subparsers.add_parser("restore")
    res.add_argument("--manifest", required=True, help="Path to manifest JSON")
    res.add_argument("--target", default="", help="Explicit target dir")
    res.add_argument("-f", "--force", action="store_true", help="Force overwrite modified destination files")
    res.add_argument("--dry-run", action="store_true", help="Dry run")

    # uninstall
    un = subparsers.add_parser("uninstall")
    un.add_argument("--manifest", required=True, help="Path to manifest JSON")
    un.add_argument("--target", default="", help="Explicit target dir")
    un.add_argument("--restore-previous", action="store_true", help="Restore prior backups")
    un.add_argument("--clean-backups", action="store_true", help="Clean only owned backups")
    un.add_argument("-f", "--force", action="store_true", help="Force removal or restore of modified destination files")
    un.add_argument("--dry-run", action="store_true", help="Dry run")

    # adopt-orphans
    ad = subparsers.add_parser("adopt-orphans")
    ad.add_argument("--manifest", required=True, help="Path to manifest JSON")
    ad.add_argument("--target", default="", help="Explicit target dir")
    ad.add_argument("--dry-run", action="store_true", help="Dry run")

    args = parser.parse_args()

    # Do not resolve symlinks on the manifest path itself: a symlinked manifest
    # must be refused, not silently followed.
    manifest_p = Path(os.path.abspath(args.manifest))

    def _takes_lock(action, dry_run):
        if dry_run:
            return False
        if action == "restore":
            return manifest_p.exists()
        if action == "uninstall":
            return manifest_p.exists()
        return True  # record, adopt-orphans

    try:
        rc = 0
        if args.action == "install":
            with LockFile(manifest_p) as lock:
                validate_owned_destinations(load_manifest(manifest_p), args.target)
                environment = dict(os.environ)
                environment["SADSKILL_INSTALL_LOCK_FD"] = str(lock.fd)
                arguments = args.installer_args
                if arguments[:1] == ["--"]:
                    arguments = arguments[1:]
                rc = subprocess.run(
                    ["bash", str(Path(__file__).resolve().parent.parent / "install.sh"), *arguments],
                    env=environment, pass_fds=(lock.fd,), check=False,
                ).returncode
        elif args.action == "validate":
            if args.dry_run:
                validate_owned_destinations(load_manifest(manifest_p), args.target)
            else:
                with LockFile(manifest_p):
                    validate_owned_destinations(load_manifest(manifest_p), args.target)
        elif args.action == "record":
            with LockFile(manifest_p):
                rc = record_entry(
                    manifest_path=manifest_p,
                    agent=args.agent,
                    destination=args.destination,
                    backup_path=args.backup,
                    target_dir=args.target,
                ) or 0
        elif args.action == "restore":
            if _takes_lock("restore", args.dry_run):
                with LockFile(manifest_p):
                    rc = perform_restore(
                        manifest_path=manifest_p,
                        target_dir=args.target,
                        force=args.force,
                        dry_run=args.dry_run,
                    )
            else:
                rc = perform_restore(
                    manifest_path=manifest_p,
                    target_dir=args.target,
                    force=args.force,
                    dry_run=True,
                )
        elif args.action == "uninstall":
            if _takes_lock("uninstall", args.dry_run):
                with LockFile(manifest_p):
                    rc = perform_uninstall(
                        manifest_path=manifest_p,
                        target_dir=args.target,
                        restore_previous=args.restore_previous,
                        clean_backups=args.clean_backups,
                        force=args.force,
                        dry_run=args.dry_run,
                    )
            else:
                rc = perform_uninstall(
                    manifest_path=manifest_p,
                    target_dir=args.target,
                    restore_previous=args.restore_previous,
                    clean_backups=args.clean_backups,
                    force=args.force,
                    dry_run=True,
                )
        elif args.action == "adopt-orphans":
            if _takes_lock("adopt-orphans", args.dry_run):
                with LockFile(manifest_p):
                    rc = adopt_orphans(
                        manifest_path=manifest_p,
                        target_dir=args.target,
                        dry_run=args.dry_run,
                    ) or 0
            else:
                rc = adopt_orphans(
                    manifest_path=manifest_p,
                    target_dir=args.target,
                    dry_run=True,
                ) or 0
    except ManifestError as exc:
        print(f"   [ERROR] {exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(f"   [ERROR] {exc}", file=sys.stderr)
        return 2
    except LockError as exc:
        print(f"   [ERROR] {exc}", file=sys.stderr)
        return 6
    except (core.IntegrityError, OSError) as exc:
        print(f"   [ERROR] {exc}", file=sys.stderr)
        return 4
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
