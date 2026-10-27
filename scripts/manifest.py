#!/usr/bin/env python3
"""
sadskill Installation Manifest & Transaction Manager (v0.3.0)
Provides robust, transactional manifest recording, ownership verification,
safe restoration, and uninstallation without data loss.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 digest of a file or directory tree."""
    if not path.exists():
        return ""
    if path.is_file():
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    elif path.is_dir():
        h = hashlib.sha256()
        for root, dirs, files in os.walk(str(path)):
            dirs.sort()
            for file in sorted(files):
                file_path = Path(root) / file
                rel = file_path.relative_to(path)
                h.update(str(rel).encode("utf-8"))
                try:
                    with open(file_path, "rb") as f:
                        while chunk := f.read(65536):
                            h.update(chunk)
                except Exception:
                    pass
        return h.hexdigest()
    return ""


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

        # Allow Cursor workspace artifacts strictly within a verified .cursor directory
        parts = resolved.parts
        if ".cursor" in parts:
            idx = parts.index(".cursor")
            rel_cursor = parts[idx:]
            # Exact rule file or exact sadskill skill folder within .cursor/skills/
            if rel_cursor == (".cursor", "rules", "sadskill.mdc") or rel_cursor[:3] == (".cursor", "skills", "sadskill"):
                return True
        return False
    except Exception:
        return False


def load_manifest(manifest_path: Path):
    if not manifest_path.exists():
        return {"version": "0.3.0", "entries": []}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"version": "0.3.0", "entries": []}
            data.setdefault("version", "0.3.0")
            data.setdefault("entries", [])
            return data
    except Exception:
        return {"version": "0.3.0", "entries": []}


def save_manifest_atomic(manifest_path: Path, data: dict):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = manifest_path.with_name(f"{manifest_path.name}.tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, manifest_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise e


def record_entry(manifest_path: Path, agent: str, destination: str, backup_path: str = "", target_dir: str = ""):
    allowed_roots = get_allowed_roots(target_dir)
    dest_p = Path(destination).resolve()
    if not is_path_contained_in_roots(dest_p, allowed_roots):
        raise ValueError(f"Destination path traverses outside allowed roots: {destination}")

    backup_p = Path(backup_path).resolve() if backup_path else None
    if backup_p and not is_path_contained_in_roots(backup_p, allowed_roots):
        raise ValueError(f"Backup path traverses outside allowed roots: {backup_path}")

    data = load_manifest(manifest_path)
    content_hash = compute_sha256(dest_p)
    backup_hash = compute_sha256(backup_p) if backup_p and backup_p.exists() else ""

    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = {
        "agent": agent,
        "destination": str(dest_p),
        "backup": str(backup_p) if backup_p else "",
        "content_hash": content_hash,
        "backup_hash": backup_hash,
        "installed_at": timestamp,
        "restored": False,
    }

    # Replace existing active entry for the same destination if present, or append
    existing_idx = None
    for idx, e in enumerate(data["entries"]):
        if e.get("destination") == str(dest_p):
            existing_idx = idx
            break

    if existing_idx is not None:
        data["entries"][existing_idx] = entry
    else:
        data["entries"].append(entry)

    save_manifest_atomic(manifest_path, data)
    print(f"   [MANIFEST] Recorded {agent} -> {dest_p}")


def perform_restore(manifest_path: Path, target_dir: str = "", dry_run: bool = False):
    """Restore backed up files without deleting them afterwards."""
    if not manifest_path.exists():
        print("   [INFO] No manifest found to restore from.")
        return 0

    allowed_roots = get_allowed_roots(target_dir)
    data = load_manifest(manifest_path)
    entries = data.get("entries", [])
    restored_count = 0

    # Process in reverse order so latest installations roll back first
    for entry in reversed(entries):
        dest_str = entry.get("destination")
        bak_str = entry.get("backup")
        if not bak_str or entry.get("restored"):
            continue

        dest_p = Path(dest_str).resolve()
        bak_p = Path(bak_str).resolve()

        if not is_path_contained_in_roots(dest_p, allowed_roots) or not is_path_contained_in_roots(bak_p, allowed_roots):
            print(f"   [WARN] Skipping restore for path outside allowed roots: {dest_p} / {bak_p}")
            continue

        if not bak_p.exists():
            print(f"   [WARN] Backup not found at {bak_p}")
            continue

        print(f"   [RESTORE] Restoring {dest_p} from {bak_p}")
        if not dry_run:
            if dest_p.exists():
                if dest_p.is_dir():
                    shutil.rmtree(dest_p)
                else:
                    dest_p.unlink()
            shutil.move(str(bak_p), str(dest_p))
            entry["restored"] = True
            restored_count += 1

    if not dry_run:
        save_manifest_atomic(manifest_path, data)
    print(f"   [RESTORE] Successfully restored {restored_count} entries.")
    return 0


def perform_uninstall(manifest_path: Path, target_dir: str = "", restore_previous: bool = False, clean_backups: bool = False, dry_run: bool = False):
    """Transactional uninstaller: removes only owned files, preserves restored files."""
    allowed_roots = get_allowed_roots(target_dir)
    data = load_manifest(manifest_path)
    entries = data.get("entries", [])

    # Step 1: If restore_previous requested, perform safe restoration first
    if restore_previous:
        print("-> Performing safe transactional restoration from backups...")
        perform_restore(manifest_path, target_dir=target_dir, dry_run=dry_run)
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

        if not is_path_contained_in_roots(dest_p, allowed_roots):
            print(f"   [WARN] Skipping removal for destination outside allowed roots: {dest_p}")
            continue

        if dest_p.exists():
            print(f"   [REMOVE] Removing sadskill-owned artifact: {dest_p}")
            if not dry_run:
                if dest_p.is_dir():
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
            bak_str = entry.get("backup")
            if not bak_str:
                continue
            bak_p = Path(bak_str).resolve()
            if not is_path_contained_in_roots(bak_p, allowed_roots):
                continue
            if bak_p.exists() and ".bak." in bak_p.name:
                print(f"   [CLEAN-BACKUP] Removing owned backup: {bak_p}")
                if not dry_run:
                    if bak_p.is_dir():
                        shutil.rmtree(bak_p)
                    else:
                        bak_p.unlink()

    if not dry_run and not restore_previous:
        # Clear entries from manifest
        data["entries"] = []
        save_manifest_atomic(manifest_path, data)

    print(f"   [OK] Cleaned {removed_count} installed artifacts.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="sadskill manifest & transaction manager")
    subparsers = parser.add_subparsers(dest="action", required=True)

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
    res.add_argument("--dry-run", action="store_true", help="Dry run")

    # uninstall
    un = subparsers.add_parser("uninstall")
    un.add_argument("--manifest", required=True, help="Path to manifest JSON")
    un.add_argument("--target", default="", help="Explicit target dir")
    un.add_argument("--restore-previous", action="store_true", help="Restore prior backups")
    un.add_argument("--clean-backups", action="store_true", help="Clean only owned backups")
    un.add_argument("--dry-run", action="store_true", help="Dry run")

    args = parser.parse_args()

    manifest_p = Path(args.manifest).resolve()

    if args.action == "record":
        record_entry(
            manifest_path=manifest_p,
            agent=args.agent,
            destination=args.destination,
            backup_path=args.backup,
            target_dir=args.target,
        )
    elif args.action == "restore":
        perform_restore(
            manifest_path=manifest_p,
            target_dir=args.target,
            dry_run=args.dry_run,
        )
    elif args.action == "uninstall":
        perform_uninstall(
            manifest_path=manifest_p,
            target_dir=args.target,
            restore_previous=args.restore_previous,
            clean_backups=args.clean_backups,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
