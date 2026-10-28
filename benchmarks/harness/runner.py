#!/usr/bin/env python3
"""sadskill C1 Real-Agent Benchmark Runner.
Executes and evaluates the 12 C1 benchmark tasks across plain, sadskill, and
competitor conditions with paired metrics and honest provider status reporting.
"""

import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.harness.evaluators import EVALUATORS
from benchmarks.harness.providers import MockProvider, RealAgentProvider
from benchmarks.harness.tasks import C1_TASKS


def setup_task_workspace(task: dict, target_dir: Path):
    """Sets up fixture files in an isolated temporary workspace."""
    target_dir.mkdir(parents=True, exist_ok=True)
    setup_files = task.get("setup_files", {})
    for rel_path, content in setup_files.items():
        dest = target_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def run_benchmark_run(
    task_id: str,
    condition: str,
    provider_name: str,
    repetition: int,
) -> dict:
    task = C1_TASKS.get(task_id)
    if not task:
        raise ValueError(f"Unknown task ID: {task_id}")

    if provider_name == "mock":
        provider = MockProvider()
    else:
        provider = RealAgentProvider(provider_name)

    evaluator = EVALUATORS.get(task_id)
    if not evaluator:
        raise ValueError(f"No evaluator registered for {task_id}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        setup_task_workspace(task, workspace)

        run_result = provider.execute(task, condition, workspace)

        if run_result.get("status") == "NOT_EXECUTED_NO_AUTH":
            return {
                "task_id": task_id,
                "task_name": task["name"],
                "condition": condition,
                "provider": provider_name,
                "repetition": repetition,
                "status": "NOT_EXECUTED_NO_AUTH",
                "success": False,
                "regressions": 0,
                "safety_violations": 0,
                "reason": run_result.get("reason", "No authentication"),
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

        passed, regressions, safety_violations, notes = evaluator(workspace)

        record = {
            "task_id": task_id,
            "task_name": task["name"],
            "category": task["category"],
            "condition": condition,
            "provider": provider_name,
            "repetition": repetition,
            "status": "COMPLETED",
            "success": passed,
            "regressions": regressions,
            "safety_violations": safety_violations,
            "notes": notes,
            "input_tokens": run_result.get("input_tokens", 0),
            "output_tokens": run_result.get("output_tokens", 0),
            "wall_clock_seconds": run_result.get("wall_clock_seconds", 0.0),
            "tool_calls": run_result.get("tool_calls", 0),
            "evidence_produced": run_result.get("evidence_produced", False),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        return record


def main():
    parser = argparse.ArgumentParser(description="sadskill C1 Real-Agent Benchmark Runner")
    parser.add_argument("--provider", default="mock", choices=["mock", "codex", "claude", "gemini"], help="Execution provider")
    parser.add_argument("--condition", default="sadskill", choices=["plain", "sadskill", "competitor"], help="Experimental condition")
    parser.add_argument("--task", default="C1-01", help="Task ID (e.g. C1-01) or 'all'")
    parser.add_argument("--repetitions", type=int, default=1, help="Repetitions per task")
    parser.add_argument("--output", default=None, help="JSONL output path")

    args = parser.parse_args()

    task_ids = list(C1_TASKS.keys()) if args.task.lower() == "all" else [args.task]
    for tid in task_ids:
        if tid not in C1_TASKS:
            sys.exit(f"Invalid task ID '{tid}'. Available tasks: {', '.join(C1_TASKS.keys())}")

    print(f"=== sadskill C1 Real-Agent Benchmark Harness ===")
    print(f"Provider:    {args.provider}")
    print(f"Condition:   {args.condition}")
    print(f"Tasks:       {', '.join(task_ids)}")
    print(f"Repetitions: {args.repetitions}\n")

    results = []
    output_file = Path(args.output) if args.output else None
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        # Empty or create output file
        output_file.write_text("", encoding="utf-8")

    total_runs = 0
    passed_runs = 0

    for tid in task_ids:
        for rep in range(1, args.repetitions + 1):
            total_runs += 1
            res = run_benchmark_run(tid, args.condition, args.provider, rep)
            results.append(res)

            status_mark = "✓ PASS" if res.get("success") else ("⚠️ UNAUTH" if res.get("status") == "NOT_EXECUTED_NO_AUTH" else "❌ FAIL")
            if res.get("success"):
                passed_runs += 1

            note = res.get("notes") or res.get("reason", "")
            print(f"[{status_mark}] {tid} (rep {rep}) - {res['task_name']} | {note}")

            if output_file:
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(res) + "\n")

    print(f"\n--------------------------------------------------")
    print(f"Benchmark Summary: Total Runs: {total_runs} | Passed: {passed_runs} | Provider: {args.provider}")
    if output_file:
        print(f"Results written to: {output_file}")
    print(f"--------------------------------------------------")

    # If all completed runs passed or were cleanly reported unauth
    all_clean = all(r.get("success") or r.get("status") == "NOT_EXECUTED_NO_AUTH" for r in results)
    sys.exit(0 if all_clean else 1)


if __name__ == "__main__":
    main()
