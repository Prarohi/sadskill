#!/usr/bin/env python3
"""sadskill Persistent Project Memory & Concurrent Event Log (.sad/)
Provides thread-safe and process-safe append-only event recording to prevent
silent overwrite hazards when multiple autonomous agents collaborate.
"""

import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
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


def main():
    parser = argparse.ArgumentParser(description="sadskill Concurrent Memory CLI")
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


if __name__ == "__main__":
    main()
