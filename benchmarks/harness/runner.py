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
    *, live=False, isolated=False, model=None,
) -> dict:
    task = C1_TASKS.get(task_id)
    if not task:
        raise ValueError(f"Unknown task ID: {task_id}")

    if provider_name == "mock":
        provider = MockProvider()
    else:
        provider = RealAgentProvider(provider_name, live=live, isolated=isolated, model=model)

    evaluator = EVALUATORS.get(task_id)
    if not evaluator:
        raise ValueError(f"No evaluator registered for {task_id}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        setup_task_workspace(task, workspace)

        run_result = provider.execute(task, condition, workspace)

        if run_result.get("status", "").startswith(("NOT_EXECUTED", "FAILED_")):
            return {
                "task_id": task_id,
                "task_name": task["name"],
                "condition": condition,
                "provider": provider_name,
                "repetition": repetition,
                "status": run_result["status"],
                "success": False,
                "synthetic": provider_name == "mock",
                "model": model,
                "prompt_sha256": run_result.get("prompt_sha256"),
                "regressions": None,
                "safety_violations": None,
                "input_tokens": None,
                "output_tokens": None,
                "reason": run_result.get("reason", "Not executed or provider failed"),
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

        # Never score an unverified provider response as completed empirical work.
        # Mock fixtures intentionally have no real usage counters.
        if provider_name != "mock" and (
            run_result.get("status") != "COMPLETED_REAL"
            or not all(isinstance(run_result.get(key), int)
                       and not isinstance(run_result.get(key), bool)
                       and run_result[key] >= 0
                       for key in ("input_tokens", "output_tokens"))
        ):
            return {
                "task_id": task_id, "task_name": task["name"],
                "condition": condition, "provider": provider_name,
                "model": model, "repetition": repetition,
                "status": "FAILED_UNVERIFIABLE_METRICS",
                "success": False, "synthetic": False,
                "input_tokens": None, "output_tokens": None,
                "regressions": None, "safety_violations": None,
                "reason": "Provider reported no complete, valid token usage/status; evaluation withheld",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

        passed, regressions, safety_violations, notes = evaluator(workspace)

        record = {
            "task_id": task_id,
            "task_name": task["name"],
            "category": task["category"],
            "condition": condition,
            "provider": provider_name,
            "model": model,
            "prompt_sha256": run_result.get("prompt_sha256"),
            "repetition": repetition,
            "status": run_result.get("status", "COMPLETED"),
            "synthetic": provider_name == "mock",
            "success": passed,
            "regressions": regressions,
            "safety_violations": safety_violations,
            "notes": notes,
            "input_tokens": run_result.get("input_tokens"),
            "output_tokens": run_result.get("output_tokens"),
            "wall_clock_seconds": run_result.get("wall_clock_seconds", 0.0),
            "tool_calls": run_result.get("tool_calls"),
            "evidence_produced": run_result.get("evidence_produced", False),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        return record


def main():
    parser = argparse.ArgumentParser(description="sadskill C1 Real-Agent Benchmark Runner")
    parser.add_argument("--provider", default="mock", choices=["mock", "codex", "claude", "gemini"], help="Execution provider")
    parser.add_argument("--condition", default="sadskill", choices=["plain", "sadskill", "competitor", "all"], help="Experimental condition")
    parser.add_argument("--task", default="C1-01", help="Task ID (e.g. C1-01) or 'all'")
    parser.add_argument("--repetitions", type=int, default=1, help="Repetitions per task")
    parser.add_argument("--output", default=None, help="JSONL output path")
    parser.add_argument("--live", action="store_true", help="Opt in to authenticated, potentially billable real agent execution")
    parser.add_argument("--acknowledge-isolated-runner", action="store_true", help="Assert the entire harness and graders are in a disposable external VM/container")
    parser.add_argument("--model", default=None, help="Exact model ID required for live comparisons")

    args = parser.parse_args()
    if args.live and (args.provider == "mock" or not args.acknowledge_isolated_runner or not args.model):
        parser.error("--live requires a real provider, --model and --acknowledge-isolated-runner")
    if args.acknowledge_isolated_runner and not args.live:
        parser.error("--acknowledge-isolated-runner requires --live")

    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

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

    conditions = ("plain", "sadskill", "competitor") if args.condition == "all" else (args.condition,)
    for tid in task_ids:
        for condition in conditions:
            for rep in range(1, args.repetitions + 1):
                total_runs += 1
                res = run_benchmark_run(tid, condition, args.provider, rep,
                                        live=args.live, isolated=args.acknowledge_isolated_runner,
                                        model=args.model)
                results.append(res)

                if res["status"].startswith(("NOT_EXECUTED", "FAILED_")):
                    status_mark = "⚠️ NOT EXECUTED"
                elif res.get("synthetic"):
                    status_mark = "🧪 MOCK PASS" if res.get("success") else "🧪 MOCK FAIL"
                else:
                    status_mark = "✓ PASS" if res.get("success") else "❌ FAIL"
                if res.get("success"):
                    passed_runs += 1

                note = res.get("notes") or res.get("reason", "")
                print(f"[{status_mark}] {tid} ({condition}, rep {rep}) - {res['task_name']} | {note}")

                if output_file:
                    with open(output_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(res) + "\n")

    print(f"\n--------------------------------------------------")
    print(f"Benchmark Summary: Total Runs: {total_runs} | Passed: {passed_runs} | Provider: {args.provider}")
    if output_file:
        print(f"Results written to: {output_file}")
    print(f"--------------------------------------------------")

    # A missing live adapter is not a passing benchmark. Mock fixture tests can
    # pass their own harness-health check, but must never be reported as model runs.
    not_executed = any(r["status"].startswith(("NOT_EXECUTED", "FAILED_")) for r in results)
    if args.provider == "mock":
        print("SIMULATED FIXTURE CHECK ONLY: no AI model invoked; no token/cost/quality advantage measured.")
    if not_executed:
        print("NOT EXECUTED: live agent adapter unavailable; this is not a successful benchmark.", file=sys.stderr)
    sys.exit(2 if not_executed else (0 if all(r.get("success") for r in results) else 1))


if __name__ == "__main__":
    main()
