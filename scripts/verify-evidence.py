#!/usr/bin/env python3
"""
sadskill Independent Evidence Verifier (Hardened v0.3.0)
Validates that .sad/evidence/*.json proof records are syntactically valid,
strictly contained within the project repository root, and distinguishes between
agent-reported claims, verified executions via trusted recipes, and CI attestations.
"""

import argparse
import datetime
import json
import os
import re
import shlex
import signal
import subprocess
import sys
from pathlib import Path

# Safe predetermined executables allowed during --retest
ALLOWED_EXECUTABLES = {
    "pytest",
    "python3",
    "python",
    "npm",
    "cargo",
    "go",
}

# Dangerous shell syntax tokens rejected in arguments during safe execution
FORBIDDEN_ARG_TOKENS = {";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r"}

# Dangerous inline code flags rejected in unattended safe retest
DISALLOWED_INLINE_FLAGS = {"-c", "-e", "--eval"}


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


def is_trusted_recipe(argv, project_root: Path):
    """
    Validates that the command adheres to a trusted recipe registry.
    Rejects arbitrary inline code execution (-c, -e, bash -c, arbitrary script files).
    """
    if not argv:
        return False, "Empty argument list"

    executable = Path(argv[0]).name
    if executable not in ALLOWED_EXECUTABLES:
        return (
            False,
            f"Executable '{executable}' is not in authorized verifier allowlist ({', '.join(sorted(ALLOWED_EXECUTABLES))})",
        )

    # Reject inline code evaluation flags (e.g. python -c "...", node -e "...")
    for arg in argv[1:]:
        if arg in DISALLOWED_INLINE_FLAGS:
            return False, f"Inline code evaluation flag '{arg}' prohibited in safe retest recipe"

    # For python/python3, ensure it's either running a project-relative test script or -m unittest/pytest
    if executable in ("python", "python3"):
        if len(argv) > 1 and argv[1] == "-m":
            allowed_modules = {"unittest", "pytest"}
            if len(argv) < 3 or argv[2] not in allowed_modules:
                return False, f"Only trusted test modules ({', '.join(sorted(allowed_modules))}) allowed with -m"
        elif len(argv) > 1:
            script_path = project_root / argv[1]
            try:
                resolved_script = script_path.resolve()
                if not (resolved_script.is_relative_to(project_root) if hasattr(resolved_script, "is_relative_to") else str(resolved_script).startswith(str(project_root))):
                    return False, f"Script path outside project root: {argv[1]}"
            except Exception:
                return False, f"Invalid script path: {argv[1]}"

    # For npm, only allow standard test invocations
    if executable == "npm":
        if len(argv) < 2 or argv[1] not in ("test", "run", "t"):
            return False, f"npm command limited to test scripts: {' '.join(argv)}"

    return True, "Trusted recipe"


def execute_safe_command(project_root: Path, cmd_str: str, timeout_seconds=30):
    """
    Safely executes an authorized command in an isolated process group without shell=True.
    Validates executable against trusted recipe registry and kills descendants on timeout.
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

    recipe_ok, recipe_msg = is_trusted_recipe(argv, project_root)
    if not recipe_ok:
        return False, f"Untrusted command rejected: {recipe_msg}"

    # Sanitize environment: keep minimal necessary paths, drop credentials.
    # Per V-06, do NOT inherit untrusted external PYTHONPATH or NODE_PATH into subprocess;
    # set PYTHONPATH strictly to the verified project root to prevent module hijacking.
    clean_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "PYTHONPATH": str(project_root),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }

    proc = None
    try:
        # start_new_session=True creates a new process group so timeout kills all child processes
        proc = subprocess.Popen(
            argv,
            shell=False,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=clean_env,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        if proc.returncode != 0:
            err_msg = stderr.strip()[:300] if stderr else f"Exit code {proc.returncode}"
            return False, f"Execution failed (code {proc.returncode}): {err_msg}"
        return True, "Execution succeeded"
    except subprocess.TimeoutExpired:
        if proc:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
        return False, f"Execution timed out after {timeout_seconds}s"
    except Exception as e:
        return False, f"Execution error: {e}"


def is_valid_iso_timestamp(ts: str) -> bool:
    if not isinstance(ts, str):
        return False
    # Validate ISO 8601 format
    iso_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
    return bool(re.match(iso_pattern, ts))


def verify_evidence(
    project_root=None,
    evidence_dir=None,
    retest=False,
    require_evidence=False,
    timeout=30,
    log_stream=sys.stdout,
):
    def log(msg=""):
        print(msg, file=log_stream)

    root = detect_project_root(project_root)
    ev_dir = Path(evidence_dir).resolve() if evidence_dir else (root / ".sad" / "evidence")

    # Security check: evidence dir must be contained within project root unless explicitly permitted
    try:
        if not (ev_dir.is_relative_to(root) if hasattr(ev_dir, "is_relative_to") else str(ev_dir).startswith(str(root))):
            log(f"  [FAIL] Evidence directory outside project root: {ev_dir}")
            return 1, []
    except Exception:
        pass

    log(f"=== sadskill Evidence Verifier ===")
    log(f"  Project Root: {root}")
    log(f"  Evidence Dir: {ev_dir}")

    if not ev_dir.exists():
        if require_evidence:
            log("  [FAIL] Required evidence directory .sad/evidence does not exist.")
            return 1, []
        log("  [INFO] Evidence directory .sad/evidence not found. Clean baseline.")
        return 0, []

    evidence_files = sorted(ev_dir.glob("*.json"))
    if not evidence_files:
        if require_evidence:
            log("  [FAIL] Zero evidence records found when --require-evidence is set.")
            return 1, []
        log("  [INFO] Zero .sad/evidence/*.json logs found (clean baseline).")
        return 0, []

    records = []
    errors = 0
    schema_valid_count = 0
    retested_count = 0

    required_keys = ["timestamp", "task_slug", "command", "exit_code", "summary", "files_touched"]

    for ef in evidence_files:
        log(f"\n-> Inspecting evidence record: {ef.name}")

        # Check if evidence file is a symlink escaping root
        try:
            if ef.is_symlink():
                resolved_ef = ef.resolve()
                if not (resolved_ef.is_relative_to(root) if hasattr(resolved_ef, "is_relative_to") else str(resolved_ef).startswith(str(root))):
                    log("   [FAIL] Evidence symlink escapes project root.")
                    errors += 1
                    records.append({"file": ef.name, "status": "FAILED", "reason": "Symlink escape"})
                    continue
        except Exception as e:
            log(f"   [FAIL] Symlink error: {e}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": str(e)})
            continue

        try:
            data = json.loads(ef.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"   [FAIL] Invalid JSON syntax: {e}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": f"Invalid JSON: {e}"})
            continue

        if not isinstance(data, dict):
            log("   [FAIL] Record is not a JSON object")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "Not a JSON object"})
            continue

        missing = [k for k in required_keys if k not in data]
        if missing:
            log(f"   [FAIL] Missing mandatory keys: {missing}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": f"Missing keys: {missing}"})
            continue

        # Strict type checking (T16, T17)
        # exit_code MUST be strictly integer, not boolean
        if type(data["exit_code"]) is not int:
            log(f"   [FAIL] Invalid exit_code type (must be integer, got {type(data['exit_code']).__name__})")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": f"exit_code not integer"})
            continue

        if data["exit_code"] != 0:
            log(f"   [FAIL] Non-zero recorded exit code: {data['exit_code']}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": f"Non-zero exit code: {data['exit_code']}"})
            continue

        if not isinstance(data.get("files_touched"), list):
            log(f"   [FAIL] Invalid files_touched type (must be list, got {type(data.get('files_touched')).__name__})")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "files_touched not a list"})
            continue

        if not is_valid_iso_timestamp(data.get("timestamp")):
            log(f"   [FAIL] Invalid timestamp format (must be ISO 8601): {data.get('timestamp')}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "Invalid ISO timestamp"})
            continue

        # Validate file path containment
        path_error = False
        for touched in data.get("files_touched", []):
            ok, msg = validate_contained_path(root, touched)
            if not ok:
                log(f"   [FAIL] Path containment error: {msg}")
                path_error = True
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": msg})
                break

        if path_error:
            continue

        # Check CI attestation if present
        ci_attestation = data.get("ci_attestation")
        provenance = "REPORTED"

        # If retest requested, safely execute authorized check
        current_status = "SCHEMA_VALID"
        if retest:
            cmd = data.get("command", "")
            log(f"   [INFO] Safe re-test requested for: {cmd}")
            exec_ok, exec_msg = execute_safe_command(root, cmd, timeout_seconds=timeout)
            if not exec_ok:
                log(f"   [FAIL] Re-test failed: {exec_msg}")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": exec_msg})
                continue
            current_status = "RETESTED"
            provenance = "RETESTED"
            retested_count += 1
            log(f"   [RETESTED] Authorized check passed successfully: {ef.name}")
        elif ci_attestation and isinstance(ci_attestation, dict) and ci_attestation.get("verified"):
            current_status = "CI_ATTESTED"
            provenance = "CI_ATTESTED"
            log(f"   [CI_ATTESTED] Evidence record verified via CI attestation.")
        else:
            schema_valid_count += 1
            provenance = "SCHEMA_VALID"
            log(f"   [SCHEMA_VALID] Evidence log {ef.name} format verified (Agent-reported, unexecuted).")

        records.append({
            "file": ef.name,
            "status": current_status,
            "provenance": provenance,
            "task_slug": data.get("task_slug"),
        })

    log("\n--------------------------------------------------")
    log(
        f"Summary: Total: {len(evidence_files)} | Schema Valid: {schema_valid_count} | Retested: {retested_count} | Errors: {errors}"
    )
    log("--------------------------------------------------")
    return (1 if errors > 0 else 0), records


def main():
    parser = argparse.ArgumentParser(description="sadskill Independent Evidence Verifier")
    parser.add_argument("--project-root", help="Explicit project root directory")
    parser.add_argument("--evidence-dir", help="Explicit evidence directory")
    parser.add_argument("--retest", action="store_true", help="Safely re-execute authorized test commands")
    parser.add_argument(
        "--require-evidence", action="store_true", help="Fail if zero evidence records are present"
    )
    parser.add_argument("--timeout", type=int, default=30, help="Per-command timeout in seconds (default: 30, range 1-300)")
    parser.add_argument("--json", action="store_true", help="Output JSON results")

    args = parser.parse_args()

    # Validate timeout bounds
    if args.timeout < 1 or args.timeout > 300:
        print(f"Error: --timeout must be between 1 and 300 seconds (got {args.timeout})", file=sys.stderr)
        sys.exit(2)

    # When --json is used, send human-readable logs to stderr so stdout is pure JSON
    log_stream = sys.stderr if args.json else sys.stdout

    exit_code, records = verify_evidence(
        project_root=args.project_root,
        evidence_dir=args.evidence_dir,
        retest=args.retest,
        require_evidence=args.require_evidence,
        timeout=args.timeout,
        log_stream=log_stream,
    )

    if args.json:
        print(json.dumps({"exit_code": exit_code, "records": records}, indent=2))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
