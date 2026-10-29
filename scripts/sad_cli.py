#!/usr/bin/env python3
"""sadskill Unified Developer CLI (`sad`).
Consolidates initialization, agent diagnostics, benchmark execution,
evidence verification, project memory, and guardrail inspection.
"""

import argparse
import os
from pathlib import Path
import stat
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


def configure_color(enabled: bool) -> None:
    """Refresh cached badges when output color changes after argument parsing."""
    global USE_COLOR, BADGE_PASS, BADGE_FAIL, BADGE_WARN, BADGE_SAFE
    global BADGE_EVID, BADGE_MEM, BADGE_INFO
    USE_COLOR = enabled
    BADGE_PASS = colored("[✓ PASS]", "92;1")
    BADGE_FAIL = colored("[✕ FAIL]", "91;1")
    BADGE_WARN = colored("[! WARN]", "93;1")
    BADGE_SAFE = colored("[🛡️ SAFE]", "96;1")
    BADGE_EVID = colored("[📦 EVIDENCE]", "95;1")
    BADGE_MEM = colored("[🧠 MEMORY]", "94;1")
    BADGE_INFO = colored("[ℹ INFO]", "97;1")


def _safe_directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    if not nofollow or not directory or os.open not in getattr(os, "supports_dir_fd", set()):
        raise OSError("safe initialization is unavailable on this platform")
    return os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0)


def _open_or_create_directory_at(parent_fd: int, basename: str) -> int:
    created = False
    try:
        os.mkdir(basename, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    else:
        created = True
    if created:
        os.fsync(parent_fd)
    try:
        fd = os.open(basename, _safe_directory_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise OSError(f"refusing symlinked or non-directory confidence path: {basename}") from exc
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError(f"refusing non-directory confidence path: {basename}")
    return fd


def _ensure_template_at(parent_fd: int, basename: str, content: str) -> None:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    cloexec = getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(
            basename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow | cloexec,
            0o600,
            dir_fd=parent_fd,
        )
    except FileExistsError:
        try:
            fd = os.open(
                basename,
                os.O_RDONLY | os.O_NONBLOCK | nofollow | cloexec,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise OSError(f"refusing symlinked or unsafe confidence document: {basename}") from exc
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError(f"existing confidence document is not a file (regular file required): {basename}")
        finally:
            os.close(fd)
        return

    try:
        remaining = memoryview(content.encode("utf-8"))
        while remaining:
            written = os.write(fd, remaining)
            if written <= 0:
                raise OSError(f"short write while creating confidence document: {basename}")
            remaining = remaining[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(parent_fd)


def cmd_init(args) -> int:
    """Initialize .sad/ through pinned, no-follow directory descriptors."""
    target_root = Path(args.project_root or Path.cwd()).resolve()
    sad_dir = target_root / ".sad"
    folder_names = ("events", "evidence", "benchmarks")
    templates = {
        "decisions.md": (
            "# Architectural Decision Records (ADRs)\n\n"
            "This document tracks durable architectural choices for the project.\n"
        ),
        "history.md": (
            "# Project Milestones & Execution History\n\n"
            "Chronological milestone log maintained automatically across agent sessions.\n"
        ),
        "design-memory.md": (
            "# Design Tokens & Visual Hierarchy Memory\n\n"
            "Approved tokens and UI styling decisions.\n"
        ),
    }

    opened_fds = []
    try:
        root_fd = os.open(target_root, _safe_directory_flags())
        opened_fds.append(root_fd)
        sad_fd = _open_or_create_directory_at(root_fd, ".sad")
        opened_fds.append(sad_fd)
        for name in folder_names:
            folder_fd = _open_or_create_directory_at(sad_fd, name)
            os.close(folder_fd)
        for basename, content in templates.items():
            _ensure_template_at(sad_fd, basename, content)
    except (OSError, ValueError) as exc:
        print(f"{BADGE_FAIL} Initialization refused: {exc}", file=sys.stderr)
        return 1
    finally:
        for fd in reversed(opened_fds):
            os.close(fd)

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
        configure_color(False)

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
