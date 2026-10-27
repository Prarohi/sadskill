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


TRUSTED_RECIPES = {
    "repo-verify": [sys.executable, "scripts/verify.py"],
    "repo-benchmarks": [sys.executable, "benchmarks/runner.py"],
    "python-pytest": [sys.executable, "-m", "pytest"],
    "python-unittest": [sys.executable, "-m", "unittest", "discover"],
    "tenant-isolation-grader": [sys.executable, "benchmarks/fixtures/tenant-isolation/grader.py"],
    "real-rls-grader": [sys.executable, "benchmarks/fixtures/real-rls/grader.py"],
    "cargo-test": ["cargo", "test"],
    "go-test": ["go", "test", "./..."],
}


def resolve_retest_argv(data: dict, project_root: Path, allow_custom: bool = False):
    """
    Resolves the execution argv for safe re-testing.
    Prioritizes trusted recipe IDs. If raw command is provided, matches against
    known safe patterns, and strictly rejects arbitrary repository scripts unless
    --allow-custom-retest is explicitly granted.
    """
    check_id = data.get("check_id") or data.get("recipe_id")
    if check_id:
        if check_id in TRUSTED_RECIPES:
            return True, list(TRUSTED_RECIPES[check_id]), f"Trusted recipe: {check_id}"
        return False, [], f"Unknown check_id/recipe_id: {check_id}"

    cmd_str = data.get("command", "")
    if not cmd_str or not isinstance(cmd_str, str):
        return False, [], "Missing or invalid command string"

    for token in FORBIDDEN_ARG_TOKENS:
        if token in cmd_str:
            return False, [], f"Shell chaining/redirection token '{token}' prohibited in authorized execution"

    try:
        argv = shlex.split(cmd_str)
    except Exception as e:
        return False, [], f"Failed to parse command arguments: {e}"

    if not argv:
        return False, [], "Parsed argument vector is empty"

    for arg in argv[1:]:
        if arg in DISALLOWED_INLINE_FLAGS:
            return False, [], f"Inline code evaluation flag '{arg}' prohibited in safe retest recipe"

    # Match raw commands against known trusted recipes
    exe = Path(argv[0]).name
    if exe in ("python", "python3"):
        if len(argv) >= 2 and argv[1] == "scripts/verify.py":
            return True, [sys.executable, "scripts/verify.py"] + argv[2:], "Matched repo-verify recipe"
        if len(argv) >= 2 and argv[1] == "benchmarks/runner.py":
            return True, [sys.executable, "benchmarks/runner.py"] + argv[2:], "Matched repo-benchmarks recipe"
        if len(argv) >= 3 and argv[1] == "-m" and argv[2] in ("unittest", "pytest"):
            return True, [sys.executable] + argv[1:], f"Matched python {argv[2]} recipe"
        if len(argv) >= 2 and "benchmarks/fixtures/tenant-isolation/grader.py" in argv[1]:
            return True, [sys.executable, "benchmarks/fixtures/tenant-isolation/grader.py"], "Matched tenant isolation grader"
        if len(argv) >= 2 and "benchmarks/fixtures/real-rls/grader.py" in argv[1]:
            return True, [sys.executable, "benchmarks/fixtures/real-rls/grader.py"], "Matched real RLS grader"

    if exe == "pytest":
        return True, [sys.executable, "-m", "pytest"] + argv[1:], "Matched pytest recipe"

    if exe == "cargo" and len(argv) >= 2 and argv[1] == "test":
        return True, ["cargo", "test"] + argv[2:], "Matched cargo-test recipe"

    if exe == "go" and len(argv) >= 2 and argv[1] == "test":
        return True, ["go", "test"] + argv[2:], "Matched go-test recipe"

    if not allow_custom:
        return (
            False,
            [],
            f"Arbitrary repository script execution ({exe}) prohibited in unattended retest. Use a registered check_id/recipe_id or pass --allow-custom-retest",
        )

    # If allow_custom is True, validate script containment within project root
    if exe in ("python", "python3") and len(argv) > 1:
        script_path = project_root / argv[1]
        try:
            resolved_script = script_path.resolve()
            if not (resolved_script.is_relative_to(project_root) if hasattr(resolved_script, "is_relative_to") else str(resolved_script).startswith(str(project_root))):
                return False, [], f"Script path outside project root: {argv[1]}"
        except Exception:
            return False, [], f"Invalid script path: {argv[1]}"

    return True, argv, "Custom execution allowed via --allow-custom-retest"


def execute_safe_argv(project_root: Path, argv: list, timeout_seconds=30):
    """
    Safely executes an authorized command argv in an isolated process group without shell=True.
    Kills descendants on timeout and uses clean sanitized environment.
    """
    import tempfile
    clean_env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": tempfile.gettempdir(),
        "PYTHONPATH": str(project_root),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }

    proc = None
    try:
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
    allow_custom_retest=False,
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

    # Check current git commit for freshness binding
    current_head_sha = ""
    try:
        res_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res_sha.returncode == 0:
            current_head_sha = res_sha.stdout.strip()
    except Exception:
        pass

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
        is_skipped = data.get("status") in ("SKIPPED", "SKIPPED_WITH_REASON", "NOT_APPLICABLE", "DOCS_ONLY", "NOT_RUN")
        if is_skipped:
            if data.get("exit_code") is not None and type(data["exit_code"]) is not int:
                log(f"   [FAIL] Invalid exit_code type (must be integer or null for skipped task, got {type(data['exit_code']).__name__})")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "exit_code not integer"})
                continue
        else:
            # exit_code MUST be strictly integer, not boolean
            if type(data["exit_code"]) is not int:
                log(f"   [FAIL] Invalid exit_code type (must be integer, got {type(data['exit_code']).__name__})")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "exit_code not integer"})
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

        # Check freshness binding to repository commit
        freshness = "UNBOUND"
        record_commit = data.get("commit_sha")
        if record_commit:
            if current_head_sha and record_commit == current_head_sha:
                freshness = "VERIFIED_FRESH"
                log(f"   [FRESH] Bound to current repository HEAD ({record_commit[:8]}).")
            elif current_head_sha:
                freshness = "STALE"
                log(f"   [WARN] Stale commit binding: record is for {record_commit[:8]}, current HEAD is {current_head_sha[:8]}.")
            else:
                freshness = "RECORDED"

        # Check CI attestation if present
        ci_attestation = data.get("ci_attestation")
        provenance = "REPORTED"

        # If retest requested, safely execute authorized check via recipe registry
        current_status = "SCHEMA_VALID"
        if is_skipped:
            current_status = "SKIPPED_WITH_REASON"
            provenance = "NOT_RUN"
            log(f"   [SKIPPED] Task marked non-executable / documentation-only: {ef.name}")
        elif retest:
            res_ok, argv_to_run, res_msg = resolve_retest_argv(data, root, allow_custom=allow_custom_retest)
            if not res_ok:
                log(f"   [FAIL] Re-test rejected: {res_msg}")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": res_msg})
                continue

            log(f"   [INFO] Safe re-test executing: {res_msg}")
            exec_ok, exec_msg = execute_safe_argv(root, argv_to_run, timeout_seconds=timeout)
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
            "freshness": freshness,
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
    parser.add_argument("--retest", action="store_true", help="Safely re-execute authorized test commands via recipe registry")
    parser.add_argument("--allow-custom-retest", action="store_true", help="Allow custom repository script execution under safe retest")
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
        allow_custom_retest=args.allow_custom_retest,
        require_evidence=args.require_evidence,
        timeout=args.timeout,
        log_stream=log_stream,
    )

    if args.json:
        print(json.dumps({"exit_code": exit_code, "records": records}, indent=2))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
