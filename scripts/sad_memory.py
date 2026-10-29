#!/usr/bin/env python3
"""sadskill Persistent Project Memory & Concurrent Event Log (.sad/)
Provides thread-safe and process-safe append-only event recording,
zero-dependency BM25 semantic memory search, and historical compaction.
"""

import argparse
from collections import Counter
import datetime
import fcntl
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

_REDACTED = "[REDACTED_SECRET]"
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----",
    re.S,
)
_AUTH_SCHEME = re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/-]+=*", re.I)
_SECRET_ASSIGNMENT = re.compile(
    r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
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
    "signing_key", "authorization", "token",
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
    current = (start_path or Path.cwd()).resolve()
    while current != current.parent:
        if (current / ".sad").exists() or (current / "skills" / "sadskill").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return (start_path or Path.cwd()).resolve()


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


class MemoryLock:
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.fd = None

    def __enter__(self):
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.fd = open(self.lock_file, "w")
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                self.fd.close()
            except Exception:
                pass


def append_event(
    project_root: Path,
    event_type: str,
    payload: dict,
    actor: str = "agent",
    task_id: str = "default",
) -> Path:
    """Appends an immutable event record under advisory lock and updates human-readable views."""
    root = Path(project_root).resolve()
    sad_dir = root / ".sad"
    events_dir = sad_dir / "events"
    lock_path = sad_dir / ".lock"
    safe_payload = redact_memory_payload(payload, event_type)
    safe_actor = _redact_secret_text(str(actor))
    safe_task_id = _redact_secret_text(str(task_id))

    with MemoryLock(lock_path):
        events_dir.mkdir(parents=True, exist_ok=True)
        event_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now.isoformat().replace("+00:00", "Z")
        time_slug = now.strftime("%Y%m%d-%H%M%S")

        commit_sha = get_git_commit(root)
        record = {
            "event_id": event_id,
            "timestamp": now_iso,
            "actor": safe_actor,
            "base_commit": commit_sha,
            "task_id": safe_task_id,
            "type": event_type,
            "payload": safe_payload,
        }

        event_file = events_dir / f"{time_slug}-{event_id[:8]}.json"
        event_file.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

        # Update derived human-readable memory files
        if event_type == "milestone":
            history_file = sad_dir / "history.md"
            title = safe_payload.get("title", f"Milestone {safe_task_id}")
            summary = safe_payload.get("summary", "")
            entry = f"\n### [{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] {title}\n- **Actor**: {safe_actor}\n- **Task**: {safe_task_id}\n"
            if summary:
                entry += f"- **Summary**: {summary}\n"
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(entry)

        elif event_type == "adr":
            decisions_file = sad_dir / "decisions.md"
            title = safe_payload.get("title", f"Decision {safe_task_id}")
            context = safe_payload.get("context", "N/A")
            decision = safe_payload.get("decision", "N/A")
            consequences = safe_payload.get("consequences", "N/A")
            entry = f"\n## ADR: {title}\n- **Date**: {now.strftime('%Y-%m-%d')}\n- **Status**: Accepted\n- **Context**: {context}\n- **Decision**: {decision}\n- **Consequences**: {consequences}\n"
            with open(decisions_file, "a", encoding="utf-8") as f:
                f.write(entry)

        elif event_type == "design_token":
            design_file = sad_dir / "design-memory.md"
            token_name = safe_payload.get("token", "unnamed")
            value = safe_payload.get("value", "")
            note = safe_payload.get("note", "")
            entry = f"- `{token_name}`: `{value}` ({note})\n"
            with open(design_file, "a", encoding="utf-8") as f:
                f.write(entry)

        return event_file


def list_events(project_root: Path) -> list:
    root = Path(project_root).resolve()
    events_dir = root / ".sad" / "events"
    if not events_dir.exists():
        return []
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

    for archive in _read_archive_records(events_dir / "archive"):
        add_record(archive)
    for ef in sorted(events_dir.glob("*.json")):
        try:
            add_record(json.loads(ef.read_text(encoding="utf-8")))
        except Exception:
            pass
    records.sort(key=lambda record: (str(record.get("timestamp", "")), str(record.get("event_id", ""))))
    return records


def _read_archive_records(archive_dir: Path) -> list[dict]:
    records = []
    if not archive_dir.is_dir():
        return records
    for archive in sorted(archive_dir.glob("events-*.jsonl")):
        try:
            with open(archive, "r", encoding="utf-8") as archive_file:
                for line in archive_file:
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(record, dict):
                        records.append(record)
        except Exception:
            continue
    return records


def _event_identity(record: dict) -> str:
    event_id = record.get("event_id")
    if event_id:
        return "id:" + str(event_id)
    return "json:" + json.dumps(record, sort_keys=True, separators=(",", ":"))


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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
    root = Path(project_root).resolve()
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

    # 2. Gather ADRs directly from .sad/decisions.md if present
    decisions_file = root / ".sad" / "decisions.md"
    if decisions_file.exists():
        raw_text = decisions_file.read_text(encoding="utf-8")
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
    root = Path(project_root).resolve()
    events_dir = root / ".sad" / "events"
    lock_path = root / ".sad" / ".lock"

    if not events_dir.exists():
        return 0

    with MemoryLock(lock_path):
        event_files = sorted(events_dir.glob("*.json"))
        archive_dir = events_dir / "archive"
        archived_by_id = {}
        for record in _read_archive_records(archive_dir):
            archived_by_id[_event_identity(record)] = record

        to_archive = set(event_files[:-keep_latest] if keep_latest else event_files)
        pending_by_id = {}
        sources_to_remove = []
        for event_file in event_files:
            try:
                record = json.loads(event_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            identity = _event_identity(record)
            existing = archived_by_id.get(identity, pending_by_id.get(identity))
            if existing is not None:
                if existing == record:
                    if identity in archived_by_id or event_file in to_archive:
                        sources_to_remove.append(event_file)
                continue
            if event_file in to_archive:
                pending_by_id[identity] = record
                sources_to_remove.append(event_file)

        archived_count = len(pending_by_id)
        if pending_by_id:
            archive_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.datetime.now(datetime.timezone.utc)
            month_slug = now.strftime("%Y-%m")
            archive_file = archive_dir / f"events-{month_slug}.jsonl"
            with open(archive_file, "a", encoding="utf-8") as out_file:
                for record in pending_by_id.values():
                    out_file.write(json.dumps(record, separators=(",", ":")) + "\n")
                out_file.flush()
                os.fsync(out_file.fileno())
            _fsync_directory(archive_dir)

        removed_any = False
        for event_file in sources_to_remove:
            try:
                event_file.unlink()
                removed_any = True
            except FileNotFoundError:
                continue
        if removed_any:
            _fsync_directory(events_dir)

        return archived_count


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
    root = find_project_root(Path(args.project_root) if args.project_root else None)

    if args.subcommand == "append-event":
        try:
            payload = json.loads(args.payload)
        except Exception as e:
            sys.exit(f"Error parsing JSON payload: {e}")
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


if __name__ == "__main__":
    main()
