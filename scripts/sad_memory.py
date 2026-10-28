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
            "actor": actor,
            "base_commit": commit_sha,
            "task_id": task_id,
            "type": event_type,
            "payload": payload,
        }

        event_file = events_dir / f"{time_slug}-{event_id[:8]}.json"
        event_file.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

        # Update derived human-readable memory files
        if event_type == "milestone":
            history_file = sad_dir / "history.md"
            title = payload.get("title", f"Milestone {task_id}")
            summary = payload.get("summary", "")
            entry = f"\n### [{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] {title}\n- **Actor**: {actor}\n- **Task**: {task_id}\n"
            if summary:
                entry += f"- **Summary**: {summary}\n"
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(entry)

        elif event_type == "adr":
            decisions_file = sad_dir / "decisions.md"
            title = payload.get("title", f"Decision {task_id}")
            context = payload.get("context", "N/A")
            decision = payload.get("decision", "N/A")
            consequences = payload.get("consequences", "N/A")
            entry = f"\n## ADR: {title}\n- **Date**: {now.strftime('%Y-%m-%d')}\n- **Status**: Accepted\n- **Context**: {context}\n- **Decision**: {decision}\n- **Consequences**: {consequences}\n"
            with open(decisions_file, "a", encoding="utf-8") as f:
                f.write(entry)

        elif event_type == "design_token":
            design_file = sad_dir / "design-memory.md"
            token_name = payload.get("token", "unnamed")
            value = payload.get("value", "")
            note = payload.get("note", "")
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
    for ef in sorted(events_dir.glob("*.json")):
        try:
            records.append(json.loads(ef.read_text(encoding="utf-8")))
        except Exception:
            pass
    return records


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
    root = Path(project_root).resolve()
    events_dir = root / ".sad" / "events"
    lock_path = root / ".sad" / ".lock"

    if not events_dir.exists():
        return 0

    with MemoryLock(lock_path):
        event_files = sorted(events_dir.glob("*.json"))
        if len(event_files) <= keep_latest:
            return 0

        archive_dir = events_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        to_archive = event_files[:-keep_latest]
        archived_count = 0

        now = datetime.datetime.now(datetime.timezone.utc)
        month_slug = now.strftime("%Y-%m")
        archive_file = archive_dir / f"events-{month_slug}.jsonl"

        with open(archive_file, "a", encoding="utf-8") as out_f:
            for ef in to_archive:
                try:
                    data = ef.read_text(encoding="utf-8").strip()
                    # Write as single-line JSONL
                    out_f.write(json.dumps(json.loads(data)) + "\n")
                    ef.unlink()
                    archived_count += 1
                except Exception:
                    pass

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
