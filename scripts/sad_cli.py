#!/usr/bin/env python3
"""sadskill Unified Developer CLI (`sad`).
Consolidates initialization, agent diagnostics, benchmark execution,
evidence verification, project memory, and guardrail inspection.
"""

import argparse
from pathlib import Path
import subprocess
import sys

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ANSI Color Badges
USE_COLOR = sys.stdout.isatty()


def colored(text: str, color_code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{color_code}m{text}\033[0m"


BADGE_PASS = colored("[✓ PASS]", "92;1")
BADGE_FAIL = colored("[✕ FAIL]", "91;1")
BADGE_WARN = colored("[! WARN]", "93;1")
BADGE_SAFE = colored("[🛡️ SAFE]", "96;1")
BADGE_EVID = colored("[📦 EVIDENCE]", "95;1")
BADGE_MEM = colored("[🧠 MEMORY]", "94;1")
BADGE_INFO = colored("[ℹ INFO]", "97;1")


def cmd_init(args) -> int:
    """Initializes the .sad/ directory structure and templates."""
    target_root = Path(args.project_root or Path.cwd()).resolve()
    sad_dir = target_root / ".sad"

    events_dir = sad_dir / "events"
    evidence_dir = sad_dir / "evidence"
    benchmarks_dir = sad_dir / "benchmarks"

    events_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    benchmarks_dir.mkdir(parents=True, exist_ok=True)

    decisions_file = sad_dir / "decisions.md"
    if not decisions_file.exists():
        decisions_file.write_text(
            "# Architectural Decision Records (ADRs)\n\n"
            "This document tracks durable architectural choices for the project.\n",
            encoding="utf-8",
        )

    history_file = sad_dir / "history.md"
    if not history_file.exists():
        history_file.write_text(
            "# Project Milestones & Execution History\n\n"
            "Chronological milestone log maintained automatically across agent sessions.\n",
            encoding="utf-8",
        )

    design_file = sad_dir / "design-memory.md"
    if not design_file.exists():
        design_file.write_text(
            "# Design Tokens & Visual Hierarchy Memory\n\n"
            "Approved tokens and UI styling decisions.\n",
            encoding="utf-8",
        )

    print(f"{BADGE_PASS} Initialized sadskill project confidence layer at {sad_dir}")
    print(f"  ├── events/       (process-safe append-only memory)")
    print(f"  ├── evidence/     (cryptographic v2 verification records)")
    print(f"  ├── benchmarks/   (paired empirical evaluation artifacts)")
    print(f"  ├── decisions.md  (ADR registry)")
    print(f"  └── history.md    (milestone ledger)")
    return 0


def cmd_doctor(args, extra_args) -> int:
    """Delegates to scripts/doctor.py."""
    doctor_script = REPO_ROOT / "scripts" / "doctor.py"
    cmd = [sys.executable, str(doctor_script)] + extra_args
    return subprocess.run(cmd).returncode


def cmd_bench(args, extra_args) -> int:
    """Runs C1 comparative agent benchmark harness."""
    runner_script = REPO_ROOT / "benchmarks" / "harness" / "runner.py"
    visualize_script = REPO_ROOT / "benchmarks" / "harness" / "visualize.py"

    output_file = Path(args.output) if args.output else REPO_ROOT / ".sad" / "benchmark-latest.jsonl"
    cmd = [
        sys.executable,
        str(runner_script),
        "--provider",
        args.provider,
        "--condition",
        args.condition,
        "--task",
        args.task,
        "--repetitions",
        str(args.repetitions),
        "--output",
        str(output_file),
    ] + extra_args

    print(f"{BADGE_INFO} Running C1 harness (provider={args.provider}; mock runs are SIMULATED, not real-agent performance)...")
    ret = subprocess.run(cmd).returncode

    if ret == 0 and output_file.exists():
        summary_md = REPO_ROOT / ".sad" / "benchmarks" / "c1-summary.md"
        viz_cmd = [
            sys.executable,
            str(visualize_script),
            "--inputs",
            str(output_file),
            "--output-markdown",
            str(summary_md),
        ]
        viz_result = subprocess.run(viz_cmd, capture_output=True, text=True)
        if viz_result.returncode != 0:
            print(f"{BADGE_FAIL} Report generation failed: {viz_result.stderr.strip()}", file=sys.stderr)
            return viz_result.returncode
        if args.provider == "mock":
            print(f"\n{BADGE_INFO} Offline MOCK fixture checks completed (SIMULATED; no model performance measured).")
        else:
            print(f"\n{BADGE_PASS} Live-agent execution completed; inspect independent graders before making performance claims.")
        print(f"  Artifacts saved to: {output_file.relative_to(REPO_ROOT) if output_file.is_relative_to(REPO_ROOT) else output_file}")
        if summary_md.exists():
            print(f"  Summary table:      {summary_md.relative_to(REPO_ROOT) if summary_md.is_relative_to(REPO_ROOT) else summary_md}")

    return ret


def cmd_verify(args, extra_args) -> int:
    """Runs verification checks."""
    if args.all:
        verify_script = REPO_ROOT / "scripts" / "verify.py"
        print(f"{BADGE_INFO} Running full codebase contract verification...")
        return subprocess.run([sys.executable, str(verify_script)] + extra_args).returncode

    verify_ev_script = REPO_ROOT / "scripts" / "verify-evidence.py"
    cmd = [sys.executable, str(verify_ev_script)]
    if args.retest:
        cmd.append("--retest")
    if args.require_evidence:
        cmd.append("--require-evidence")
    if args.emit_slsa:
        cmd.append("--emit-slsa")
    cmd.extend(extra_args)
    return subprocess.run(cmd).returncode


def cmd_memory(args, extra_args) -> int:
    """Delegates to scripts/sad_memory.py."""
    mem_script = REPO_ROOT / "scripts" / "sad_memory.py"
    cmd = [sys.executable, str(mem_script)] + extra_args
    return subprocess.run(cmd).returncode


def cmd_guard(args) -> int:
    """Inspects a shell command or SQL query for destructive patterns."""
    command_str = args.command
    guard_script = REPO_ROOT / "scripts" / "git-guardrail.sh"

    res = subprocess.run(
        ["bash", str(guard_script), command_str],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        print(f"{BADGE_SAFE} No known blocked pattern detected (heuristic only; NOT a security guarantee).")
        return 0
    else:
        print(f"{BADGE_FAIL} BLOCKED: Destructive operation intercepted!")
        if res.stderr.strip():
            print(f"  Reason: {res.stderr.strip()}")
        return res.returncode


def cmd_sandbox(args, extra_args) -> int:
    """Runs a command inside Bubblewrap sandbox."""
    sandbox_script = REPO_ROOT / "scripts" / "sandbox.sh"
    cmd = [str(sandbox_script)]
    if args.offline:
        cmd.append("--offline")
    if args.allow_git:
        cmd.append("--allow-git")
    if args.allow_unsandboxed:
        cmd.append("--allow-unsandboxed")
    cmd.append("--")
    cmd.extend(extra_args)
    return subprocess.run(cmd).returncode


def main():
    parser = argparse.ArgumentParser(
        prog="sad",
        description="sadskill — The Multi-Agent Engineering Confidence Layer",
    )
    parser.add_argument("--version", action="version", version="sadskill 0.5.0")
    parser.add_argument("--no-color", action="store_true", help="Disable colored terminal output")

    subparsers = parser.add_subparsers(dest="subcommand", title="Commands", metavar="<command>")

    # sad init
    init_p = subparsers.add_parser("init", help="Initialize .sad/ project confidence layer")
    init_p.add_argument("--project-root", help="Explicit project directory")

    # sad doctor
    subparsers.add_parser("doctor", help="Inspect multi-agent installation and hook health")

    # sad bench
    bench_p = subparsers.add_parser("bench", help="Run C1 synthetic fixtures; live providers currently fail closed")
    bench_p.add_argument("--provider", choices=["mock", "codex", "claude", "gemini"], default="mock", help="Execution provider; mock is SIMULATED, real adapters are not yet implemented")
    bench_p.add_argument("--condition", choices=["sadskill", "plain", "competitor", "all"], default="sadskill")
    bench_p.add_argument("--task", default="C1-01", help="Task ID or 'all'")
    bench_p.add_argument("--repetitions", type=int, default=1)
    bench_p.add_argument("--output", help="Output JSONL path")

    # sad verify
    verify_p = subparsers.add_parser("verify", help="Verify evidence logs or codebase integrity")
    verify_p.add_argument("--all", action="store_true", help="Run full codebase contract verification (scripts/verify.py)")
    verify_p.add_argument("--retest", action="store_true", help="Safely re-execute authorized test commands")
    verify_p.add_argument("--require-evidence", action="store_true", help="Fail if zero evidence records are present")
    verify_p.add_argument("--emit-slsa", action="store_true", help="Emit in-toto SLSA Provenance v1.0 Statement")

    # sad memory
    subparsers.add_parser("memory", help="Query or append to persistent project memory")

    # sad guard
    guard_p = subparsers.add_parser("guard", help="Check command safety against guardrails")
    guard_p.add_argument("command", help="Command or SQL query string to evaluate")

    # sad sandbox
    sandbox_p = subparsers.add_parser("sandbox", help="Run command inside Bubblewrap OS containment sandbox")
    sandbox_p.add_argument("--offline", action="store_true", help="Unshare network namespace")
    sandbox_p.add_argument("--allow-git", action="store_true", help="Allow write access to .git")
    sandbox_p.add_argument("--allow-unsandboxed", action="store_true", help="Explicitly execute without containment if bwrap is unavailable (unsafe; incompatible with --offline)")

    args, extra = parser.parse_known_args()

    global USE_COLOR
    if args.no_color:
        USE_COLOR = False

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    if args.subcommand == "init":
        sys.exit(cmd_init(args))
    elif args.subcommand == "doctor":
        sys.exit(cmd_doctor(args, extra))
    elif args.subcommand == "bench":
        sys.exit(cmd_bench(args, extra))
    elif args.subcommand == "verify":
        sys.exit(cmd_verify(args, extra))
    elif args.subcommand == "memory":
        sys.exit(cmd_memory(args, extra))
    elif args.subcommand == "guard":
        sys.exit(cmd_guard(args))
    elif args.subcommand == "sandbox":
        sys.exit(cmd_sandbox(args, extra))


if __name__ == "__main__":
    main()
