#!/usr/bin/env python3
"""sadskill Persistent Project Memory & Concurrent Event Log (.sad/)
Provides thread-safe and process-safe append-only event recording,
zero-dependency BM25 semantic memory search, and historical compaction.
"""

import argparse
from collections import Counter
from contextlib import contextmanager
import datetime
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised by platform-specific smoke tests
    fcntl = None

_REDACTED = "[REDACTED_SECRET]"
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----",
    re.S,
)
_AUTH_SCHEME = re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/-]+=*", re.I)
_SECRET_ASSIGNMENT = re.compile(
    r"\b(?:aws[_-]?secret[_-]?access[_-]?key|aws[_-]?access[_-]?key(?:[_-]?id)?|"
    r"api[_-]?key|access[_-]?key(?:[_-]?id)?|secret[_-]?access[_-]?key|"
    r"secret[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
    r"client[_-]?secret|password|passwd|authorization|secret)\b"
    r"\s*[:=]\s*[\"']?[^\s,;\"']+",
    re.I,
)
_URL_CREDENTIALS = re.compile(r"(https?://)[^/@\s:]+:[^/@\s]+@", re.I)
_KNOWN_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,})\b"
)
_SECRET_FIELD_SUFFIXES = (
    "password", "passwd", "secret", "api_key", "access_token", "refresh_token",
    "auth_token", "session_token", "credential", "credentials", "private_key",
    "signing_key", "secret_access_key", "secret_key", "access_key_id", "access_key",
    "authorization", "token",
)
_EVENT_BASENAME = re.compile(
    r"^\d{8}-\d{6}-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.json$"
)


def _redact_secret_text(text: str) -> str:
    """Redact recognizable credential formats; this cannot identify every secret."""
    text = _PRIVATE_KEY_BLOCK.sub(_REDACTED, text)
    text = _AUTH_SCHEME.sub(_REDACTED, text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: match.group(0).split("=", 1)[0].split(":", 1)[0] + "=" + _REDACTED, text)
    text = _URL_CREDENTIALS.sub(r"\1" + _REDACTED + "@", text)
    return _KNOWN_TOKEN.sub(_REDACTED, text)


def redact_memory_payload(payload, event_type: str, *, allow_design_token_label: bool = True):
    """Copy a payload while filtering common secret fields and token patterns."""
    if isinstance(payload, dict):
        cleaned = {}
        for key, value in payload.items():
            normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key)).lower()
            normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
            design_label = (
                event_type == "design_token"
                and allow_design_token_label
                and normalized == "token"
                and isinstance(value, str)
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9._/-]{0,63}", value) is not None
            )
            sensitive = not design_label and any(
                normalized == suffix or normalized.endswith("_" + suffix)
                for suffix in _SECRET_FIELD_SUFFIXES
            )
            cleaned[key] = _REDACTED if sensitive else redact_memory_payload(
                value, event_type, allow_design_token_label=False
            )
        return cleaned
    if isinstance(payload, list):
        return [redact_memory_payload(item, event_type, allow_design_token_label=False) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_memory_payload(item, event_type, allow_design_token_label=False) for item in payload)
    if isinstance(payload, str):
        return _redact_secret_text(payload)
    return payload


def find_project_root(start_path: Path = None) -> Path:
    current = (start_path or Path.cwd()).absolute()
    while current != current.parent:
        if (current / ".sad").exists() or (current / "skills" / "sadskill").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return (start_path or Path.cwd()).absolute()


def get_git_commit(project_root: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "0" * 40


def _nofollow_flag() -> int:
    flag = getattr(os, "O_NOFOLLOW", 0)
    if not flag or not hasattr(os, "supports_dir_fd"):
        raise OSError("safe project-memory file operations are unavailable on this platform")
    return flag


def _directory_flags() -> int:
    directory = getattr(os, "O_DIRECTORY", 0)
    if not directory or os.open not in os.supports_dir_fd:
        raise OSError("safe project-memory directory operations are unavailable on this platform")
    return os.O_RDONLY | directory | _nofollow_flag() | getattr(os, "O_CLOEXEC", 0)


def _check_basename(name: str) -> None:
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\0" in name:
        raise ValueError("memory path must be a single safe filename")


def _open_directory_at(parent_fd: int, name: str, *, create: bool = False) -> int:
    _check_basename(name)
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        else:
            _fsync_directory_fd(parent_fd)
    fd = os.open(name, _directory_flags(), dir_fd=parent_fd)
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError(f"refusing non-directory project-memory path: {name}")
    return fd


@contextmanager
def _open_sad_directory(project_root: Path, *, create: bool = False):
    """Open the project and .sad directories without following their final symlinks."""
    # Do not resolve the selected project root: doing so follows a symlink
    # before O_NOFOLLOW has any chance to reject it. Resolve only its parent,
    # where legitimate platform aliases (such as macOS /var) may exist.
    chosen = Path(project_root).absolute()
    _check_basename(chosen.name)
    parent = chosen.parent.resolve(strict=True)
    parent_fd = os.open(parent, _directory_flags())
    root_fd = None
    sad_fd = None
    try:
        try:
            root_fd = os.open(chosen.name, _directory_flags(), dir_fd=parent_fd)
        except OSError as exc:
            raise OSError(
                f"refusing symlinked or non-directory project root: {chosen}"
            ) from exc
        root = parent / chosen.name
        sad_fd = _open_directory_at(root_fd, ".sad", create=create)
        yield root, sad_fd
    finally:
        if sad_fd is not None:
            os.close(sad_fd)
        if root_fd is not None:
            os.close(root_fd)
        os.close(parent_fd)


def _open_regular_at(parent_fd: int, name: str, flags: int, mode: int = 0o600) -> int:
    _check_basename(name)
    fd = os.open(
        name,
        flags
        | _nofollow_flag()
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0),
        mode,
        dir_fd=parent_fd,
    )
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        os.close(fd)
        raise OSError(f"refusing non-regular or hard-linked project-memory file: {name}")
    return fd


def _read_text_at(parent_fd: int, name: str, *, encoding: str = "utf-8") -> str:
    fd = _open_regular_at(
        parent_fd,
        name,
        os.O_RDONLY | getattr(os, "O_NONBLOCK", 0),
    )
    with os.fdopen(fd, "r", encoding=encoding) as stream:
        return stream.read()


def _write_all(fd: int, content: bytes) -> None:
    remaining = memoryview(content)
    while remaining:
        written = os.write(fd, remaining)
        if written <= 0:
            raise OSError("short write while recording project memory")
        remaining = remaining[written:]


def _fsync_directory_fd(fd: int) -> None:
    os.fsync(fd)


def _link_no_replace_at(parent_fd: int, source_name: str, destination_name: str) -> None:
    if (
        os.link not in getattr(os, "supports_dir_fd", set())
        or os.link not in getattr(os, "supports_follow_symlinks", set())
    ):
        raise OSError("atomic no-replace project-memory publication is unavailable on this platform")
    os.link(
        source_name,
        destination_name,
        src_dir_fd=parent_fd,
        dst_dir_fd=parent_fd,
        follow_symlinks=False,
    )


def _ensure_text_file_at(parent_fd: int, name: str, initial_text: str) -> None:
    try:
        fd = _open_regular_at(
            parent_fd,
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        fd = _open_regular_at(parent_fd, name, os.O_RDONLY)
        os.close(fd)
        return
    try:
        _write_all(fd, initial_text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_directory_fd(parent_fd)


def _append_text_at(parent_fd: int, name: str, content: str) -> None:
    fd = _open_regular_at(
        parent_fd,
        name,
        os.O_WRONLY | os.O_APPEND | os.O_CREAT,
        0o600,
    )
    try:
        _write_all(fd, content.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_file_atomically_at(parent_fd: int, basename: str, content: bytes, *, replace: bool) -> None:
    """Durably publish complete file bytes with atomic same-directory operations."""
    if replace and os.rename not in getattr(os, "supports_dir_fd", set()):
        raise OSError("atomic project-memory file publication is unavailable on this platform")
    temporary_name = f".{basename}.{uuid.uuid4().hex}.tmp"
    fd = _open_regular_at(
        parent_fd,
        temporary_name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        try:
            _write_all(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)
        if replace:
            os.rename(temporary_name, basename, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        else:
            # linkat is atomic and fails if the destination exists, so an
            # event published concurrently can never be silently overwritten.
            _link_no_replace_at(parent_fd, temporary_name, basename)
            # Persist both names before removing the staging link. A later
            # reader can recover that two-link state if the process stops here.
            _fsync_directory_fd(parent_fd)
            os.unlink(temporary_name, dir_fd=parent_fd)
        _fsync_directory_fd(parent_fd)
    finally:
        try:
            os.unlink(temporary_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        _fsync_directory_fd(parent_fd)


def _publish_event_atomically(parent_fd: int, event_name: str, content: bytes) -> None:
    """Publish a complete event with one link to its inode, even after a crash."""
    _write_file_atomically_at(parent_fd, event_name, content, replace=False)


def _event_basename_from_temporary(temporary_name: str):
    if not temporary_name.startswith(".") or not temporary_name.endswith(".tmp"):
        return None
    try:
        basename, nonce = temporary_name[1:-4].rsplit(".", 1)
    except ValueError:
        return None
    if not _EVENT_BASENAME.fullmatch(basename) or re.fullmatch(r"[0-9a-f]{32}", nonce) is None:
        return None
    return basename


def _pending_event_link_aliases(events_fd: int) -> dict[str, str]:
    """Map complete events with a crash-left staging hard link to that alias."""
    aliases = {}
    for temporary_name in os.listdir(events_fd):
        basename = _event_basename_from_temporary(temporary_name)
        if basename is None:
            continue
        try:
            temporary_stat = os.stat(temporary_name, dir_fd=events_fd, follow_symlinks=False)
            published_stat = os.stat(basename, dir_fd=events_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if (
            not stat.S_ISREG(temporary_stat.st_mode)
            or not stat.S_ISREG(published_stat.st_mode)
            or temporary_stat.st_nlink != 2
            or published_stat.st_nlink != 2
            or (temporary_stat.st_dev, temporary_stat.st_ino)
            != (published_stat.st_dev, published_stat.st_ino)
        ):
            continue
        aliases[basename] = temporary_name
    return aliases


def _read_event_text_at(events_fd: int, basename: str, pending_alias: str = None) -> str:
    fd = os.open(
        basename,
        os.O_RDONLY | _nofollow_flag() | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0),
        dir_fd=events_fd,
    )
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError(f"refusing non-regular project-memory file: {basename}")
        if metadata.st_nlink != 1:
            if metadata.st_nlink != 2 or pending_alias is None:
                raise OSError(f"refusing non-regular or hard-linked project-memory file: {basename}")
            alias_stat = os.stat(pending_alias, dir_fd=events_fd, follow_symlinks=False)
            if (
                not stat.S_ISREG(alias_stat.st_mode)
                or alias_stat.st_nlink != 2
                or (metadata.st_dev, metadata.st_ino) != (alias_stat.st_dev, alias_stat.st_ino)
            ):
                raise OSError(f"refusing unmatched event staging link: {basename}")
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            fd = -1
            return stream.read()
    finally:
        if fd >= 0:
            os.close(fd)


def _recover_pending_event_links(events_fd: int) -> None:
    """Remove staging links left if a process stopped after event publication."""
    aliases = _pending_event_link_aliases(events_fd)
    for temporary_name in aliases.values():
        os.unlink(temporary_name, dir_fd=events_fd)
    if aliases:
        _fsync_directory_fd(events_fd)


class MemoryLock:
    def __init__(self, sad_directory_fd: int):
        self.sad_directory_fd = sad_directory_fd
        self.fd = None

    def __enter__(self):
        if fcntl is None:
            raise OSError("safe project-memory locking is unavailable on this platform")
        self.fd = _open_regular_at(
            self.sad_directory_fd,
            ".lock",
            os.O_RDWR | os.O_CREAT,
            0o600,
        )
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        except Exception:
            os.close(self.fd)
            self.fd = None
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None


def append_event(
    project_root: Path,
    event_type: str,
    payload: dict,
    actor: str = "agent",
    task_id: str = "default",
) -> Path:
    """Appends an immutable event record under advisory lock and updates human-readable views."""
    root = Path(project_root).absolute()
    if not isinstance(payload, dict):
        raise ValueError("project-memory payload must be a JSON object")
    safe_payload = redact_memory_payload(payload, event_type)
    safe_actor = _redact_secret_text(str(actor))
    safe_task_id = _redact_secret_text(str(task_id))

    with _open_sad_directory(root, create=True) as (root, sad_fd):
        with MemoryLock(sad_fd):
            events_fd = _open_directory_at(sad_fd, "events", create=True)
            try:
                _recover_pending_event_links(events_fd)
                event_id = str(uuid.uuid4())
                now = datetime.datetime.now(datetime.timezone.utc)
                now_iso = now.isoformat().replace("+00:00", "Z")
                time_slug = now.strftime("%Y%m%d-%H%M%S")
                record = {
                    "event_id": event_id,
                    "timestamp": now_iso,
                    "actor": safe_actor,
                    "base_commit": get_git_commit(root),
                    "task_id": safe_task_id,
                    "type": event_type,
                    "payload": safe_payload,
                }

                view = None
                if event_type == "milestone":
                    _ensure_text_file_at(
                        sad_fd,
                        "history.md",
                        "# Project Milestones & Execution History\n\nChronological milestone log maintained automatically across agent sessions.\n",
                    )
                    title = safe_payload.get("title", f"Milestone {safe_task_id}")
                    summary = safe_payload.get("summary", "")
                    entry = f"\n### [{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] {title}\n- **Actor**: {safe_actor}\n- **Task**: {safe_task_id}\n"
                    if summary:
                        entry += f"- **Summary**: {summary}\n"
                    view = ("history.md", entry)
                elif event_type == "adr":
                    _ensure_text_file_at(
                        sad_fd,
                        "decisions.md",
                        "# Architectural Decision Records (ADRs)\n\nThis document tracks durable architectural choices for the project.\n",
                    )
                    title = safe_payload.get("title", f"Decision {safe_task_id}")
                    context = safe_payload.get("context", "N/A")
                    decision = safe_payload.get("decision", "N/A")
                    consequences = safe_payload.get("consequences", "N/A")
                    entry = f"\n## ADR: {title}\n- **Date**: {now.strftime('%Y-%m-%d')}\n- **Status**: Accepted\n- **Context**: {context}\n- **Decision**: {decision}\n- **Consequences**: {consequences}\n"
                    view = ("decisions.md", entry)
                elif event_type == "design_token":
                    _ensure_text_file_at(
                        sad_fd,
                        "design-memory.md",
                        "# Design Tokens & Visual Hierarchy Memory\n\nApproved tokens and UI styling decisions.\n",
                    )
                    token_name = safe_payload.get("token", "unnamed")
                    value = safe_payload.get("value", "")
                    note = safe_payload.get("note", "")
                    view = ("design-memory.md", f"- `{token_name}`: `{value}` ({note})\n")

                event_name = f"{time_slug}-{event_id}.json"
                encoded = (json.dumps(record, indent=2) + "\n").encode("utf-8")
                _publish_event_atomically(events_fd, event_name, encoded)

                if view is not None:
                    _append_text_at(sad_fd, view[0], view[1])
                return root / ".sad" / "events" / event_name
            finally:
                os.close(events_fd)


def list_events(project_root: Path) -> list:
    root = Path(project_root).absolute()
    records = []
    records_by_id = {}

    def add_record(record):
        if not isinstance(record, dict):
            return
        event_id = record.get("event_id")
        if isinstance(event_id, (str, int)) and event_id:
            previous = records_by_id.get(event_id)
            if previous == record:
                return
            records_by_id.setdefault(event_id, record)
        records.append(record)

    try:
        sad_context = _open_sad_directory(root)
        with sad_context as (_, sad_fd):
            try:
                events_fd = _open_directory_at(sad_fd, "events")
            except FileNotFoundError:
                return []
            try:
                pending_aliases = _pending_event_link_aliases(events_fd)
                for archive_record in _read_archive_records(events_fd):
                    add_record(archive_record)
                for name in sorted(os.listdir(events_fd)):
                    if not name.endswith(".json"):
                        continue
                    try:
                        add_record(json.loads(_read_event_text_at(events_fd, name, pending_aliases.get(name))))
                    except (OSError, UnicodeError, ValueError):
                        # Untrusted symlinks, special files and malformed records
                        # are ignored; they are never read through their targets.
                        continue
            finally:
                os.close(events_fd)
    except FileNotFoundError:
        return []
    records.sort(key=lambda record: (str(record.get("timestamp", "")), str(record.get("event_id", ""))))
    return records


def _read_archive_records(events_fd: int, *, strict: bool = False) -> list[dict]:
    records = []
    try:
        archive_fd = _open_directory_at(events_fd, "archive")
    except FileNotFoundError:
        return records
    try:
        for name in sorted(os.listdir(archive_fd)):
            if not name.startswith("events-") or not name.endswith(".jsonl"):
                continue
            try:
                text = _read_text_at(archive_fd, name)
            except (OSError, UnicodeError) as exc:
                if strict:
                    raise OSError(
                        f"refusing compaction: archive {name} is unreadable"
                    ) from exc
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (TypeError, ValueError) as exc:
                    if strict:
                        raise OSError(
                            f"refusing compaction: archive {name} has malformed JSON at line {line_number}"
                        ) from exc
                    continue
                if isinstance(record, dict):
                    records.append(record)
                elif strict:
                    raise OSError(
                        f"refusing compaction: archive {name} has a non-object record at line {line_number}"
                    )
    finally:
        os.close(archive_fd)
    return records


def _validate_archive_append_target(archive_fd: int, archive_name: str) -> tuple[str, bool]:
    """Return validated archive text and whether a final newline is needed."""
    try:
        text = _read_text_at(archive_fd, archive_name)
    except FileNotFoundError:
        return "", False
    if not text:
        return "", False

    lines = text.splitlines(keepends=True)
    needs_separator = not text.endswith("\n")
    for index, line in enumerate(lines):
        payload = line.rstrip("\r\n")
        if not payload:
            continue
        try:
            record = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise OSError(
                f"refusing compaction: archive {archive_name} has malformed JSON at line {index + 1}"
            ) from exc
        if not isinstance(record, dict):
            raise OSError(
                f"refusing compaction: archive {archive_name} has a non-object record at line {index + 1}"
            )
        if index < len(lines) - 1 and not line.endswith(("\n", "\r")):
            raise OSError(
                f"refusing compaction: archive {archive_name} has an incomplete record before line {index + 2}"
            )
    return text, needs_separator


def _event_identity(record: dict) -> str:
    event_id = record.get("event_id")
    if event_id:
        return "id:" + str(event_id)
    return "json:" + json.dumps(record, sort_keys=True, separators=(",", ":"))


def tokenize(text: str) -> list[str]:
    """Extracts lowercase alpha-numeric tokens of length >= 2."""
    return [w for w in re.findall(r"[a-zA-Z0-9_-]+", text.lower()) if len(w) >= 2]


class BM25Ranker:
    """Zero-dependency BM25 ranking algorithm for local project memory."""
    def __init__(self, corpus: list[dict], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.doc_len = [len(doc["tokens"]) for doc in corpus]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 1.0
        self.doc_freqs = Counter()
        self.idf = {}
        self.doc_term_freqs = []

        for doc in corpus:
            tf = Counter(doc["tokens"])
            self.doc_term_freqs.append(tf)
            for term in tf:
                self.doc_freqs[term] += 1

        n_docs = len(corpus)
        for term, freq in self.doc_freqs.items():
            # Robertson-Spärck Jones IDF
            self.idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)

    def score(self, query: str) -> list[tuple[float, dict]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = []
        for idx, doc in enumerate(self.corpus):
            doc_score = 0.0
            doc_len = self.doc_len[idx]
            tf = self.doc_term_freqs[idx]

            for term in query_tokens:
                if term not in tf:
                    continue
                term_freq = tf[term]
                idf = self.idf.get(term, 0.0)
                numerator = term_freq * (self.k1 + 1.0)
                denominator = term_freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                doc_score += idf * (numerator / denominator)

            if doc_score > 0.0:
                scores.append((round(doc_score, 4), doc))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores


def build_corpus(project_root: Path) -> list[dict]:
    root = Path(project_root).absolute()
    corpus = []

    # 1. Gather all structured events from .sad/events/
    events = list_events(root)
    for ev in events:
        ev_type = ev.get("type", "unknown")
        payload = ev.get("payload", {})
        task_id = ev.get("task_id", "")
        title = payload.get("title", f"{ev_type.upper()} ({task_id})")
        context = payload.get("context", "")
        decision = payload.get("decision", "")
        consequences = payload.get("consequences", "")
        summary = payload.get("summary", "")

        text_content = f"{title} {task_id} {summary} {context} {decision} {consequences}"
        corpus.append({
            "id": ev.get("event_id", ""),
            "type": ev_type,
            "title": title,
            "task_id": task_id,
            "summary": summary or decision or context,
            "tokens": tokenize(text_content),
            "raw": ev,
        })

    # 2. Gather ADRs directly from .sad/decisions.md if present. Open relative
    # to a pinned directory descriptor so a project symlink cannot expose a
    # file outside its memory tree.
    try:
        with _open_sad_directory(root) as (_, sad_fd):
            raw_text = _read_text_at(sad_fd, "decisions.md")
    except FileNotFoundError:
        raw_text = None

    if raw_text is not None:
        sections = raw_text.split("## ADR:")
        for s in sections[1:]:
            lines = s.strip().splitlines()
            if not lines:
                continue
            title = lines[0].strip()
            content = "\n".join(lines[1:])
            corpus.append({
                "id": f"adr-{len(corpus)+1}",
                "type": "adr",
                "title": title,
                "task_id": "adr-record",
                "summary": content[:200].strip(),
                "tokens": tokenize(f"{title} {content}"),
                "raw": {"title": title, "content": content},
            })

    return corpus


def search_memory(project_root: Path, query: str, top_k: int = 3) -> list[dict]:
    """Ranks project memory events and ADRs using BM25 and returns top_k matches."""
    corpus = build_corpus(project_root)
    if not corpus:
        return []

    ranker = BM25Ranker(corpus)
    ranked = ranker.score(query)

    results = []
    for score, doc in ranked[:top_k]:
        results.append({
            "score": score,
            "type": doc["type"],
            "title": doc["title"],
            "task_id": doc["task_id"],
            "summary": doc["summary"],
            "raw": doc["raw"],
        })
    return results


def format_memory_context(matches: list[dict]) -> str:
    """Formats top search matches into a compact Markdown context snippet for agent prompt injection."""
    if not matches:
        return ""
    lines = ["### 🧠 Relevant Project Memory & Architectural Decisions (BM25 Matches)"]
    for m in matches:
        score = m.get("score", 0.0)
        m_type = m.get("type", "record").upper()
        title = m.get("title", "Untitled")
        summary = m.get("summary", "").strip()
        lines.append(f"- **[{m_type}] {title}** (BM25: {score}): {summary}")
    return "\n".join(lines)


def compact_memory(project_root: Path, keep_latest: int = 10) -> int:
    """Consolidates older individual event JSON files into monthly archive files."""
    if keep_latest < 0:
        raise ValueError("keep_latest must be zero or greater")
    root = Path(project_root).absolute()
    try:
        sad_context = _open_sad_directory(root)
        with sad_context as (_, sad_fd):
            try:
                events_fd = _open_directory_at(sad_fd, "events")
            except FileNotFoundError:
                return 0

            try:
                with MemoryLock(sad_fd):
                    _recover_pending_event_links(events_fd)
                    event_files = sorted(
                        name for name in os.listdir(events_fd) if name.endswith(".json")
                    )
                    archived_by_id = {}
                    for record in _read_archive_records(events_fd, strict=True):
                        archived_by_id[_event_identity(record)] = record

                    to_archive = set(event_files[:-keep_latest] if keep_latest else event_files)
                    pending_by_id = {}
                    sources_to_remove = []
                    for event_name in event_files:
                        try:
                            record = json.loads(_read_text_at(events_fd, event_name))
                        except (OSError, UnicodeError, ValueError):
                            continue
                        if not isinstance(record, dict):
                            continue
                        identity = _event_identity(record)
                        existing = archived_by_id.get(identity, pending_by_id.get(identity))
                        if existing is not None:
                            if existing == record:
                                if identity in archived_by_id or event_name in to_archive:
                                    sources_to_remove.append(event_name)
                            continue
                        if event_name in to_archive:
                            pending_by_id[identity] = record
                            sources_to_remove.append(event_name)

                    archived_count = len(pending_by_id)
                    if pending_by_id:
                        archive_fd = _open_directory_at(events_fd, "archive", create=True)
                        try:
                            month_slug = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
                            archive_name = f"events-{month_slug}.jsonl"
                            old_text, needs_separator = _validate_archive_append_target(
                                archive_fd, archive_name
                            )
                            appended_text = "".join(
                                json.dumps(record, separators=(",", ":")) + "\n"
                                for record in pending_by_id.values()
                            )
                            combined = old_text + ("\n" if needs_separator else "") + appended_text
                            _write_file_atomically_at(
                                archive_fd,
                                archive_name,
                                combined.encode("utf-8"),
                                replace=True,
                            )
                        finally:
                            os.close(archive_fd)

                    removed_any = False
                    for event_name in sources_to_remove:
                        try:
                            os.unlink(event_name, dir_fd=events_fd)
                            removed_any = True
                        except FileNotFoundError:
                            continue
                    if removed_any:
                        _fsync_directory_fd(events_fd)
                    return archived_count
            finally:
                os.close(events_fd)
    except FileNotFoundError:
        return 0


def main():
    parser = argparse.ArgumentParser(description="sadskill Concurrent Memory & BM25 Search CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    append_parser = subparsers.add_parser("append-event")
    append_parser.add_argument("--type", required=True, choices=["milestone", "adr", "design_token", "checkpoint", "custom"])
    append_parser.add_argument("--task", default="default", help="Task ID or slug")
    append_parser.add_argument("--actor", default="agent", help="Actor name or ID")
    append_parser.add_argument("--payload", required=True, help="JSON payload string")
    append_parser.add_argument("--project-root", default=None, help="Explicit project root")

    list_parser = subparsers.add_parser("list-events")
    list_parser.add_argument("--project-root", default=None, help="Explicit project root")
    list_parser.add_argument("--json", action="store_true", help="Output JSON array")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--query", required=True, help="Search query string")
    search_parser.add_argument("--top-k", type=int, default=3, help="Number of results (default: 3)")
    search_parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    search_parser.add_argument("--project-root", default=None, help="Explicit project root")

    compact_parser = subparsers.add_parser("compact")
    compact_parser.add_argument("--keep-latest", type=int, default=10, help="Number of recent events to keep in events/ root")
    compact_parser.add_argument("--project-root", default=None, help="Explicit project root")

    args = parser.parse_args()
    try:
        root = find_project_root(Path(args.project_root) if args.project_root else None)

        if args.subcommand == "append-event":
            try:
                payload = json.loads(args.payload)
            except Exception as exc:
                parser.error(f"invalid JSON payload: {exc}")
            out_file = append_event(root, args.type, payload, actor=args.actor, task_id=args.task)
            print(f"Event recorded: {out_file.relative_to(root)}")

        elif args.subcommand == "list-events":
            events = list_events(root)
            if args.json:
                print(json.dumps(events, indent=2))
            else:
                print(f"Total events recorded in {root / '.sad' / 'events'}: {len(events)}")
                for ev in events:
                    print(f"  [{ev.get('timestamp')}] ({ev.get('type')}) {ev.get('task_id')}: {ev.get('payload', {}).get('title', '')}")

        elif args.subcommand == "search":
            matches = search_memory(root, args.query, top_k=args.top_k)
            if args.format == "json":
                print(json.dumps(matches, indent=2))
            else:
                md_ctx = format_memory_context(matches)
                if md_ctx:
                    print(md_ctx)
                else:
                    print("No relevant memory records matched query.")

        elif args.subcommand == "compact":
            count = compact_memory(root, keep_latest=args.keep_latest)
            print(f"Compaction complete: {count} events archived to .sad/events/archive/.")
    except (OSError, ValueError) as exc:
        print(f"ERROR: refusing unsafe or unavailable project-memory path: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
