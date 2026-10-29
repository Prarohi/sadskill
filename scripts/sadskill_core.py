#!/usr/bin/env python3
"""Shared safety primitives for sadskill manifest/update tooling (v0.3.0).

Design invariants (see docs/installation-safety.md):
- Manifest loading FAILS CLOSED: a corrupted manifest is an error, never a
  silently-empty fresh manifest (which would lose ownership knowledge).
- All manifest/state writes are atomic (temp file + os.replace) with fsync on
  both the file and its parent directory.
- Cross-process safety: an exclusive advisory lock (flock) guards every
  mutating operation; locks are auto-released when the process dies.
- Content addressing: SHA-256 for every installed/backup artifact.
- Transaction journaling: each update records its steps so an interrupted
  update can be recovered via rollback.

Exit-code conventions shared by callers:
    0 ok / 1 error / 2 usage / 3 corrupt data / 4 integrity violation
    5 conflict (user modification or unresolved restore) / 6 lock contention
"""

import errno
import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
import time
from pathlib import Path

MANIFEST_VERSION = "0.3.0"

_LOCK_WAIT_SECONDS = 10.0
_LOCK_POLL_SECONDS = 0.05


class ManifestError(Exception):
    """Raised when manifest data is missing, malformed, or untrusted."""


class IntegrityError(Exception):
    """Raised when content hashes or archive validation fail."""


class LockError(Exception):
    """Raised when the exclusive manifest lock cannot be acquired in time."""


# ---------------------------------------------------------------------------
# Version handling
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:[-.](?P<pre>[0-9A-Za-z.-]+))?$"
)


def parse_version(text):
    """Parse 'v?MAJOR.MINOR.PATCH[-pre]' into a comparable tuple.

    Returns (major, minor, patch, is_release, pre_tuple). A release beats
    every prerelease of the same numeric version.
    Raises ValueError for anything unparseable.
    """
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    m = _VERSION_RE.match(text.strip())
    if not m:
        raise ValueError(f"invalid version: {text!r}")
    pre_raw = m.group("pre")
    if pre_raw is None:
        pre = tuple()
    else:
        # Each dot-segment: numeric segments compare numerically and always
        # rank BELOW release; non-numeric segments compare as strings.
        pre = tuple(
            (0, "", int(seg)) if seg.isdigit() else (1, seg, 0)
            for seg in pre_raw.split(".")
        )
    return (
        int(m.group("major")),
        int(m.group("minor")),
        int(m.group("patch")),
        not bool(pre),
        pre,
    )


def version_text(t):
    major, minor, patch, _is_release, pre = t
    out = f"{major}.{minor}.{patch}"
    if pre:
        out += "-" + ".".join(seg[1] or str(seg[2]) for seg in pre)
    return out


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------

def compute_sha256(path):
    """SHA-256 of a file or directory tree; raises IntegrityError for unreadable content."""
    path = Path(path)
    if path.is_symlink():
        raise IntegrityError(f"refusing to hash a symlink root: {path}")
    if not path.exists():
        raise IntegrityError(f"path does not exist: {path}")
    digest = hashlib.sha256()
    if path.is_file():
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 512), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise IntegrityError(f"cannot read {path}: {exc}") from exc
    elif path.is_dir():
        digest.update(b"sadskill-tree-sha256-v2\0")
        try:
            def walk_error(exc):
                raise exc

            for root, dirs, files in os.walk(str(path), onerror=walk_error):
                dirs.sort()
                for name in sorted(dirs + files):
                    child = Path(root) / name
                    relative = os.fsencode(child.relative_to(path).as_posix())
                    mode = child.lstat().st_mode
                    if stat.S_ISLNK(mode):
                        kind, payload = b"L", os.fsencode(os.readlink(child))
                    elif stat.S_ISDIR(mode):
                        kind, payload = b"D", b""
                    elif stat.S_ISREG(mode):
                        kind, payload = b"F", bytes.fromhex(compute_sha256(child))
                    else:
                        raise IntegrityError(f"unsupported tree entry: {child}")
                    digest.update(kind)
                    digest.update(len(relative).to_bytes(8, "big"))
                    digest.update(relative)
                    digest.update(len(payload).to_bytes(8, "big"))
                    digest.update(payload)
        except OSError as exc:
            raise IntegrityError(f"cannot walk {path}: {exc}") from exc
    else:
        raise IntegrityError(f"unsupported path type: {path}")
    return digest.hexdigest()


def compute_sha256_of_bytes(data):
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Atomic writes + durability
# ---------------------------------------------------------------------------

def fsync_dir(path):
    """Best-effort fsync of a directory so rename() durability is ensured."""
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write_text(path, text, mode=0o644):
    """Write text atomically: temp file in the same dir, fsync, replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.tmp.", dir=str(target.parent)
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(str(tmp), mode)
        os.replace(str(tmp), str(target))
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            raise
    fsync_dir(target.parent)


def atomic_write_bytes(path, data, mode=0o644):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.tmp.", dir=str(target.parent)
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(str(tmp), mode)
        os.replace(str(tmp), str(target))
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            raise
    fsync_dir(target.parent)


# ---------------------------------------------------------------------------
# Manifest validation / IO (fail-closed)
# ---------------------------------------------------------------------------

_ENTRY_TYPES = {
    "agent": str,
    "destination": str,
    "backup": str,
    "content_hash": str,
    "backup_hash": str,
    "content_hash_type": str,
    "target_root": str,
    "installed_at": str,
    "restored": bool,
}


def validate_ownership_metadata(entry):
    """A structurally incomplete ledger cannot grant deletion authority."""
    if not isinstance(entry.get("agent"), str) or not entry["agent"]:
        raise ManifestError("entry requires a non-empty agent")
    content_hash = entry.get("content_hash")
    if not isinstance(content_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", content_hash):
        raise ManifestError("entry requires a valid SHA-256 content_hash")
    if entry.get("backup"):
        backup_hash = entry.get("backup_hash")
        if not isinstance(backup_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", backup_hash):
            raise ManifestError("recorded backup requires a valid SHA-256 backup_hash")


def validate_manifest_data(data):
    """Validate structure; raises ManifestError. Unknown keys are preserved."""
    if not isinstance(data, dict):
        raise ManifestError("manifest top-level value must be an object")
    version = data.get("version")
    if not isinstance(version, str) or not _VERSION_RE.match(version.strip()):
        raise ManifestError(f"manifest version invalid: {version!r}")
    try:
        manifest_ver = parse_version(version)
    except ValueError as exc:
        raise ManifestError(str(exc)) from exc
    if manifest_ver[:3] > parse_version(MANIFEST_VERSION)[:3]:
        raise ManifestError(
            f"manifest version {version} is newer than supported {MANIFEST_VERSION}"
        )
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ManifestError("manifest 'entries' must be a list")
    seen_dest = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ManifestError("each manifest entry must be an object")
        validate_ownership_metadata(entry)
        dest = entry.get("destination")
        if not isinstance(dest, str) or not dest:
            raise ManifestError("entry missing 'destination'")
        if not os.path.isabs(dest):
            raise ManifestError(f"entry destination not absolute: {dest!r}")
        if dest in seen_dest:
            raise ManifestError(f"duplicate destination in manifest: {dest}")
        seen_dest.add(dest)
        for field, expected in _ENTRY_TYPES.items():
            if field in entry and not isinstance(entry[field], expected):
                raise ManifestError(
                    f"entry field {field!r} must be {expected.__name__}"
                )
        if entry.get("content_hash_type") not in (None, "file", "tree"):
            raise ManifestError("entry content_hash_type must be 'file' or 'tree'")
        target_root = entry.get("target_root")
        if target_root and not os.path.isabs(target_root):
            raise ManifestError("entry target_root must be an absolute path")
    return data


def load_manifest_data(path):
    """Load + validate a manifest file. Missing file → fresh manifest.

    Symlinked manifests and any parse/structure error raise ManifestError
    (fail closed — callers must never treat corruption as 'no manifest').
    """
    target = Path(path)
    if target.is_symlink():
        raise ManifestError(f"manifest is a symlink: {target}")
    if not target.exists():
        return {"version": MANIFEST_VERSION, "entries": []}
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise ManifestError(f"cannot read manifest {target}: {exc}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc
    return validate_manifest_data(data)


def save_manifest_data(path, data):
    validate_manifest_data(data)
    atomic_write_text(path, json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Advisory locking
# ---------------------------------------------------------------------------

class LockFile:
    """Exclusive flock on `<manifest-dir>/.<manifest-name>.lock`.

    Non-blocking with bounded wait; auto-released (OS-level) when the process
    dies. Lock acquisition is required for every mutating operation.
    """

    def __init__(self, manifest_path, wait_seconds=None):
        self.lock_path = Path(manifest_path).parent / (
            "." + Path(manifest_path).name + ".lock"
        )
        self.wait_seconds = (
            _LOCK_WAIT_SECONDS if wait_seconds is None else wait_seconds
        )
        self._fd = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    os.close(self._fd)
                    self._fd = None
                    raise
            if time.monotonic() >= deadline:
                os.close(self._fd)
                self._fd = None
                raise LockError(
                    f"another sadskill operation holds {self.lock_path}"
                )
            time.sleep(_LOCK_POLL_SECONDS)

    def __exit__(self, exc_type, exc, tb):
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None
        return False


# ---------------------------------------------------------------------------
# Transaction journal
# ---------------------------------------------------------------------------

class Journal:
    """Crash-recovery journal for update transactions.

    Steps are appended to `<state-dir>/update-journal.json` BEFORE each
    irreversible action. A journal without a terminal state (done/rolled_back)
    means the transaction may be incomplete and rollback is required.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.data = None

    def begin(self, from_version, to_version, stage_dir, repo, channel):
        self.data = {
            "journal_version": 2,
            "action": "update",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "from_version": from_version,
            "to_version": to_version,
            "repo": repo,
            "channel": channel,
            "stage_dir": str(stage_dir),
            "backups_dir": None,
            "steps": [],
            "state": "in_progress",
        }
        self._flush()
        return self.data

    def step(self, name, payload=None):
        self.data["steps"].append(
            {
                "name": name,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "payload": payload or {},
            }
        )
        self._flush()

    def finish(self, state):
        self.data["state"] = state
        self.data["finished_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        self._flush()

    def _flush(self):
        atomic_write_text(self.path, json.dumps(self.data, indent=2) + "\n")

    @classmethod
    def load(cls, path):
        """Load the most recent journal entry; raises ManifestError on garbage."""
        target = Path(path)
        if not target.exists():
            return None
        try:
            data = json.loads(target.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManifestError(f"unreadable update journal: {exc}") from exc
        if not isinstance(data, dict) or "state" not in data:
            raise ManifestError("update journal malformed")
        return data
