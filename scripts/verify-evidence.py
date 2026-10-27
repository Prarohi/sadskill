#!/usr/bin/env python3
"""
sadskill Independent Evidence Verifier (Hardened)
Validates that .sad/evidence/*.json proof records are syntactically valid,
strictly contained within the project repository root, and distinguishes between
agent-reported claims and verified executions.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

# Safe predetermined executables allowed during --retest
ALLOWED_EXECUTABLES = {
    "pytest",
    "python3",
    "python",
    "npm",
    "npx",
    "node",
    "cargo",
    "go",
    "bash",
    "sh",
}

# Dangerous shell syntax tokens rejected in arguments during safe execution
FORBIDDEN_ARG_TOKENS = {";", "&&", "||", "|", "`", "$(", ">", "<", "\n"}


def detect_project_root(explicit_root=None):
    if explicit_root:
        p = Path(explicit_root).resolve()
        if not p.is_dir():
            raise ValueError(f"Specified project root is not a valid directory: {explicit_root}")
        return p

    # Try git root from current working directory
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return Path(res.stdout.strip()).resolve()
    except Exception:
        pass

    # Fallback: search upward from CWD for .sad or .git or SKILL.md
    curr = Path.cwd().resolve()
    while curr != curr.parent:
        if (curr / ".git").exists() or (curr / ".sad").exists() or (curr / "skills" / "sadskill" / "SKILL.md").exists():
            return curr
        curr = curr.parent

    return Path.cwd().resolve()


def validate_contained_path(project_root: Path, rel_path: str):
    """
    Validates that a declared file path is relative and strictly contained
    within the project root. Rejects path traversal, absolute paths, and external symlinks.
    """
    if not rel_path or not isinstance(rel_path, str):
        return False, "File path must be a non-empty string"

    if rel_path.startswith("/") or rel_path.startswith("\\"):
        return False, f"Absolute paths prohibited in evidence: {rel_path}"

    parts = Path(rel_path).parts
    if ".." in parts:
        return False, f"Path traversal ('..') prohibited in evidence: {rel_path}"

    target = project_root / rel_path
    try:
        resolved = target.resolve()
    except Exception as e:
        return False, f"Failed to resolve path {rel_path}: {e}"

    try:
        if not resolved.is_relative_to(project_root.resolve()):
            return False, f"Path traverses outside project root: {rel_path} -> {resolved}"
    except AttributeError:
        # Python < 3.9 fallback
        if not str(resolved).startswith(str(project_root.resolve())):
            return False, f"Path traverses outside project root: {rel_path} -> {resolved}"

    if not target.exists():
        return False, f"Declared file does not exist: {rel_path}"

    return True, resolved


def execute_safe_command(project_root: Path, cmd_str: str, timeout_seconds=30):
    """
    Safely executes an authorized command without shell=True.
    Validates executable against allowlist, enforces timeout and sanitized environment.
    """
    if not cmd_str or not isinstance(cmd_str, str):
        return False, "Empty or non-string command provided"

    # Reject shell chaining tokens
    for token in FORBIDDEN_ARG_TOKENS:
        if token in cmd_str:
            return False, f"Shell chaining/redirection token '{token}' prohibited in authorized execution"

    try:
        argv = shlex.split(cmd_str)
    except Exception as e:
        return False, f"Failed to parse command arguments: {e}"

    if not argv:
        return False, "Parsed argument vector is empty"

    executable = Path(argv[0]).name
    if executable not in ALLOWED_EXECUTABLES:
        return (
            False,
            f"Executable '{executable}' is not in authorized verifier allowlist ({', '.join(sorted(ALLOWED_EXECUTABLES))})",
        )

    # Sanitize environment: keep minimal necessary paths, drop credentials
    clean_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if "PYTHONPATH" in os.environ:
        clean_env["PYTHONPATH"] = os.environ["PYTHONPATH"]
    if "NODE_PATH" in os.environ:
        clean_env["NODE_PATH"] = os.environ["NODE_PATH"]

    try:
        res = subprocess.run(
            argv,
            shell=False,
            cwd=str(project_root),
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            env=clean_env,
        )
        if res.returncode != 0:
            err_msg = res.stderr.strip()[:300] if res.stderr else f"Exit code {res.returncode}"
            return False, f"Execution failed (code {res.returncode}): {err_msg}"
        return True, "Execution succeeded"
    except subprocess.TimeoutExpired:
        return False, f"Execution timed out after {timeout_seconds}s"
    except Exception as e:
        return False, f"Execution error: {e}"


def verify_evidence(
    project_root=None,
    evidence_dir=None,
    retest=False,
    require_evidence=False,
    timeout=30,
):
    root = detect_project_root(project_root)
    ev_dir = Path(evidence_dir).resolve() if evidence_dir else (root / ".sad" / "evidence")

    print(f"=== sadskill Evidence Verifier ===")
    print(f"  Project Root: {root}")
    print(f"  Evidence Dir: {ev_dir}")

    if not ev_dir.exists():
        if require_evidence:
            print("  [FAIL] Required evidence directory .sad/evidence does not exist.")
            return 1, []
        print("  [INFO] Evidence directory .sad/evidence not found. Clean baseline.")
        return 0, []

    evidence_files = sorted(ev_dir.glob("*.json"))
    if not evidence_files:
        if require_evidence:
            print("  [FAIL] Zero evidence records found when --require-evidence is set.")
            return 1, []
        print("  [INFO] Zero .sad/evidence/*.json logs found (clean baseline).")
        return 0, []

    records = []
    errors = 0
    schema_valid_count = 0
    retested_count = 0

    required_keys = ["timestamp", "task_slug", "command", "exit_code", "summary", "files_touched"]

    for ef in evidence_files:
        print(f"\n-> Inspecting evidence record: {ef.name}")
        try:
            data = json.loads(ef.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"   [FAIL] Invalid JSON syntax: {e}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": f"Invalid JSON: {e}"})
            continue

        missing = [k for k in required_keys if k not in data]
        if missing:
            print(f"   [FAIL] Missing mandatory keys: {missing}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": f"Missing keys: {missing}"})
            continue

        if data["exit_code"] != 0:
            print(f"   [FAIL] Non-zero recorded exit code: {data['exit_code']}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": f"Non-zero exit code: {data['exit_code']}"})
            continue

        # Validate file path containment
        path_error = False
        for touched in data.get("files_touched", []):
            ok, msg = validate_contained_path(root, touched)
            if not ok:
                print(f"   [FAIL] Path containment error: {msg}")
                path_error = True
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": msg})
                break

        if path_error:
            continue

        # If retest requested, safely execute authorized check
        current_status = "SCHEMA_VALID"
        if retest:
            cmd = data.get("command", "")
            print(f"   [INFO] Safe re-test requested for: {cmd}")
            exec_ok, exec_msg = execute_safe_command(root, cmd, timeout_seconds=timeout)
            if not exec_ok:
                print(f"   [FAIL] Re-test failed: {exec_msg}")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": exec_msg})
                continue
            current_status = "RETESTED"
            retested_count += 1
            print(f"   [RETESTED] Authorized check passed successfully: {ef.name}")
        else:
            schema_valid_count += 1
            print(f"   [SCHEMA_VALID] Evidence log {ef.name} format verified (Agent-reported, unexecuted).")

        records.append({"file": ef.name, "status": current_status, "task_slug": data.get("task_slug")})

    print("\n--------------------------------------------------")
    print(
        f"Summary: Total: {len(evidence_files)} | Schema Valid: {schema_valid_count} | Retested: {retested_count} | Errors: {errors}"
    )
    print("--------------------------------------------------")
    return (1 if errors > 0 else 0), records


def main():
    parser = argparse.ArgumentParser(description="sadskill Independent Evidence Verifier")
    parser.add_argument("--project-root", help="Explicit project root directory")
    parser.add_argument("--evidence-dir", help="Explicit evidence directory")
    parser.add_argument("--retest", action="store_true", help="Safely re-execute authorized test commands")
    parser.add_argument(
        "--require-evidence", action="store_true", help="Fail if zero evidence records are present"
    )
    parser.add_argument("--timeout", type=int, default=30, help="Per-command timeout in seconds (default: 30)")
    parser.add_argument("--json", action="store_true", help="Output JSON results")

    args = parser.parse_args()

    exit_code, records = verify_evidence(
        project_root=args.project_root,
        evidence_dir=args.evidence_dir,
        retest=args.retest,
        require_evidence=args.require_evidence,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps({"exit_code": exit_code, "records": records}, indent=2))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
