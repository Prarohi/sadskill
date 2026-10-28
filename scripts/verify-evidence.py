#!/usr/bin/env python3
"""
sadskill Independent Evidence Verifier (Hardened v0.3.0)
Validates that .sad/evidence/*.json proof records are syntactically valid,
strictly contained within the project repository root, and distinguishes between
agent-reported claims, verified executions via trusted recipes, and CI attestations.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
from pathlib import Path

# Dangerous shell syntax tokens rejected in arguments during safe execution
FORBIDDEN_ARG_TOKENS = {";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r"}

# Dangerous inline code flags rejected in unattended safe retest
DISALLOWED_INLINE_FLAGS = {"-c", "-e", "--eval"}
MAX_EVIDENCE_FILE_BYTES = 1024 * 1024


def is_within(path: Path, root: Path) -> bool:
    """Containment check without string-prefix or Python-version ambiguity."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def project_identity(project_root: Path) -> str:
    """Stable local-checkout identity that does not expose the user's path."""
    canonical = str(project_root.resolve()).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def git_context(project_root: Path):
    """Return commit and dirty state, excluding evidence records themselves."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(project_root),
            capture_output=True, text=True, check=False,
        )
        if head.returncode != 0:
            return None
        status = subprocess.run(
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
            cwd=str(project_root), capture_output=True, text=True, check=False,
        )
        if status.returncode != 0:
            return None
        dirty = False
        for entry in status.stdout.split("\0"):
            if not entry:
                continue
            path = entry[3:] if len(entry) >= 3 else ""
            if path == ".sad/evidence" or path.startswith(".sad/evidence/"):
                continue
            dirty = True
            break
        return {"commit_sha": head.stdout.strip(), "worktree_dirty": dirty}
    except OSError:
        return None


def github_repository_slug(project_root: Path):
    """Read only the owner/repo portion of an origin URL; never expose creds."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=str(project_root),
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return None
        match = re.search(
            r"(?:github\.com[:/])([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$",
            result.stdout.strip(), re.IGNORECASE,
        )
        return f"{match.group(1)}/{match.group(2)}" if match else None
    except OSError:
        return None


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

    if rel_path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel_path):
        return False, f"Absolute paths prohibited in evidence: {rel_path}"

    if "\\" in rel_path:
        return False, f"Backslash paths are not portable evidence paths: {rel_path}"

    parts = Path(rel_path).parts
    if ".." in parts:
        return False, f"Path traversal ('..') prohibited in evidence: {rel_path}"

    target = project_root / rel_path
    try:
        resolved = target.resolve()
    except Exception as e:
        return False, f"Failed to resolve path {rel_path}: {e}"

    if not is_within(resolved, project_root):
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


def resolve_retest_argv(data: dict, project_root: Path):
    """
    Resolves the execution argv for safe re-testing.
    Prioritizes trusted recipe IDs. If raw command is provided, matches against
    known safe patterns and rejects every arbitrary repository script. Repository
    containment alone is not an execution sandbox, so there is no custom-script
    bypass.
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

    return (
        False,
        [],
        f"Arbitrary repository script execution ({exe}) prohibited in evidence retests; use a registered check_id/recipe_id",
    )


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
    if not re.match(iso_pattern, ts):
        return False
    try:
        parsed = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        return False


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

    root = detect_project_root(project_root).resolve()
    ev_dir = Path(evidence_dir).resolve() if evidence_dir else (root / ".sad" / "evidence")

    # Security check: evidence dir must be contained within project root unless explicitly permitted
    if not is_within(ev_dir, root):
        log(f"  [FAIL] Evidence directory outside project root: {ev_dir}")
        return 1, []

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

    required_keys = [
        "timestamp", "task_slug", "command", "exit_code", "summary",
        "files_touched", "project_id", "commit_sha", "worktree_dirty",
    ]

    # Check current git commit for freshness binding
    current_context = git_context(root)
    current_project_id = project_identity(root)

    for ef in evidence_files:
        log(f"\n-> Inspecting evidence record: {ef.name}")

        try:
            if ef.stat().st_size > MAX_EVIDENCE_FILE_BYTES:
                log(f"   [FAIL] Evidence file exceeds {MAX_EVIDENCE_FILE_BYTES} byte limit.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "Evidence file too large"})
                continue
        except OSError as e:
            log(f"   [FAIL] Cannot inspect evidence file: {e}")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "Cannot inspect evidence file"})
            continue

        # Check if evidence file is a symlink escaping root
        try:
            if ef.is_symlink() and not is_within(ef, root):
                log("   [FAIL] Evidence symlink escapes project root.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "Symlink escape"})
                continue
        except (OSError, RuntimeError, ValueError) as e:
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

        ci_attestation = data.get("ci_attestation")
        if "ci_attestation" in data and not isinstance(ci_attestation, dict):
            log("   [FAIL] ci_attestation must be an object when present.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "ci_attestation not an object"})
            continue
        if isinstance(ci_attestation, dict):
            claim_fields = ("repository", "run_url", "head_sha", "workflow")
            if any(not isinstance(ci_attestation.get(key), str) or not ci_attestation[key].strip()
                   for key in claim_fields):
                log("   [FAIL] ci_attestation requires non-empty repository, run_url, head_sha, and workflow strings.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "incomplete CI claim"})
                continue
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", ci_attestation["repository"]):
                log("   [FAIL] ci_attestation repository must be owner/repository.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "invalid CI repository claim"})
                continue
            actual_repository = github_repository_slug(root)
            if actual_repository is None:
                log("   [NOT_VERIFIABLE] Cannot determine this checkout's GitHub repository from origin.")
                errors += 1
                records.append({"file": ef.name, "status": "NOT_VERIFIABLE", "reason": "GitHub repository unavailable"})
                continue
            if ci_attestation["repository"].lower() != actual_repository.lower():
                log("   [FAIL] ci_attestation repository does not match this checkout's origin.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "CI repository mismatch"})
                continue
            if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+(?:/attempts/[0-9]+)?", ci_attestation["run_url"]):
                log("   [FAIL] ci_attestation run_url is not a GitHub Actions run URL.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "invalid CI run URL claim"})
                continue
            url_match = re.match(
                r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/actions/runs/",
                ci_attestation["run_url"], re.IGNORECASE,
            )
            url_repository = f"{url_match.group(1)}/{url_match.group(2)}" if url_match else ""
            if url_repository.lower() != actual_repository.lower():
                log("   [FAIL] ci_attestation run URL repository does not match this checkout's origin.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "CI run repository mismatch"})
                continue
            if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", ci_attestation["head_sha"]):
                log("   [FAIL] ci_attestation head_sha is not a Git object ID.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "invalid CI head claim"})
                continue
            if "verified" in ci_attestation and type(ci_attestation["verified"]) is not bool:
                log("   [FAIL] ci_attestation verified must be a boolean claim.")
                errors += 1
                records.append({"file": ef.name, "status": "FAILED", "reason": "invalid CI verified claim"})
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

        if any(not isinstance(path, str) for path in data["files_touched"]):
            log("   [FAIL] Every files_touched entry must be a string.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "files_touched item not a string"})
            continue

        if not isinstance(data.get("task_slug"), str) or not data["task_slug"].strip():
            log("   [FAIL] task_slug must be a non-empty string.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "invalid task_slug"})
            continue
        if not isinstance(data.get("command"), str) or not isinstance(data.get("summary"), str):
            log("   [FAIL] command and summary must be strings.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "command or summary not a string"})
            continue

        if not isinstance(data.get("project_id"), str) or not re.fullmatch(r"[0-9a-f]{64}", data["project_id"]):
            log("   [FAIL] project_id must be a SHA-256 hex digest.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "invalid project_id"})
            continue
        if not isinstance(data.get("commit_sha"), str) or not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", data["commit_sha"]):
            log("   [FAIL] commit_sha must be a 40- or 64-character hexadecimal Git object ID.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "invalid commit_sha"})
            continue
        if isinstance(ci_attestation, dict) and ci_attestation["head_sha"].lower() != data["commit_sha"].lower():
            log("   [FAIL] ci_attestation head_sha claim does not match evidence commit_sha.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "CI head claim mismatch"})
            continue
        if type(data.get("worktree_dirty")) is not bool:
            log("   [FAIL] worktree_dirty must be a boolean.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "invalid worktree_dirty"})
            continue

        if current_context is None:
            log("   [NOT_VERIFIABLE] Project is not in a readable Git worktree.")
            errors += 1
            records.append({"file": ef.name, "status": "NOT_VERIFIABLE", "reason": "Git context unavailable"})
            continue
        if data["project_id"] != current_project_id:
            log("   [NOT_VERIFIABLE] Evidence project identity does not match this checkout.")
            errors += 1
            records.append({"file": ef.name, "status": "NOT_VERIFIABLE", "reason": "project identity mismatch"})
            continue
        if data["commit_sha"].lower() != current_context["commit_sha"].lower():
            log("   [STALE] Evidence commit does not match current HEAD.")
            errors += 1
            records.append({"file": ef.name, "status": "STALE", "reason": "commit mismatch"})
            continue
        if data["worktree_dirty"] != current_context["worktree_dirty"]:
            log("   [DIRTY_WORKTREE] Evidence dirty-state does not match current checkout.")
            errors += 1
            records.append({"file": ef.name, "status": "DIRTY_WORKTREE", "reason": "dirty-state mismatch"})
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
        freshness = "VERIFIED_FRESH"
        log(f"   [FRESH] Bound to project and current HEAD ({data['commit_sha'][:8]}), dirty={data['worktree_dirty']}.")
        provenance = "REPORTED"

        # If retest requested, safely execute authorized check via recipe registry
        current_status = "SCHEMA_VALID"
        if is_skipped:
            current_status = "SKIPPED_WITH_REASON"
            provenance = "NOT_RUN"
            log(f"   [SKIPPED] Task marked non-executable / documentation-only: {ef.name}")
        elif retest:
            res_ok, argv_to_run, res_msg = resolve_retest_argv(data, root)
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
        elif "ci_attestation" in data:
            current_status = "CI_CLAIMED"
            provenance = "CI_CLAIMED"
            schema_valid_count += 1
            log("   [CI_CLAIMED] Metadata is self-reported; no external GitHub verification was performed.")
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
            "commit_sha": data.get("commit_sha"),
            "worktree_dirty": data.get("worktree_dirty"),
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
    parser.add_argument("--print-context", action="store_true", help="Print project_id, commit_sha, and worktree_dirty for a new evidence record")
    parser.add_argument(
        "--require-evidence", action="store_true", help="Fail if zero evidence records are present"
    )
    parser.add_argument("--timeout", type=int, default=30, help="Per-command timeout in seconds (default: 30, range 1-300)")
    parser.add_argument("--json", action="store_true", help="Output JSON results")

    args = parser.parse_args()

    if args.print_context:
        if args.json:
            parser.error("--print-context and --json cannot be combined")
        root = detect_project_root(args.project_root).resolve()
        context = git_context(root)
        if context is None:
            print(json.dumps({"status": "NOT_VERIFIABLE"}, indent=2))
            sys.exit(1)
        print(json.dumps({"project_id": project_identity(root), **context}, indent=2))
        sys.exit(0)

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
