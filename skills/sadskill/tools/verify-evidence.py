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
import stat
import subprocess
import sys
from pathlib import Path

# Dangerous shell syntax tokens rejected in arguments during safe execution
FORBIDDEN_ARG_TOKENS = {";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r"}

# Dangerous inline code flags rejected in unattended safe retest
DISALLOWED_INLINE_FLAGS = {"-c", "-e", "--eval"}
MAX_EVIDENCE_FILE_BYTES = 1024 * 1024
MAX_SUBMODULE_DEPTH = 16
_IGNORED_TEST_CONFIGS = {
    "cargo.toml", "cargo.lock", "build.rs", "conftest.py", "pytest.ini",
    "pyproject.toml", "setup.cfg", "tox.ini", "go.mod", "go.sum", "go.work",
    "go.work.sum", "rust-toolchain", "rust-toolchain.toml", "config",
    "config.toml",
}
_IGNORED_TEST_DIRS = {
    "test", "tests", "spec", "specs", "__tests__", "fixtures", "testdata",
}
_IGNORED_GENERATED_DIRS = {
    ".git", ".venv", "venv", "node_modules", ".tox", ".pytest_cache",
    "target", "build", "dist",
}


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


def _snapshot_git_command(project_root, *arguments):
    """Disable configured execution helpers for one local Git metadata read."""
    prefix = ["git", "-c", "core.fsmonitor=false"]
    configured = subprocess.run(
        [*prefix, "config", "--null", "--name-only", "--get-regexp",
         r"^filter\..*\.(clean|smudge|process|required)$"],
        cwd=str(project_root), capture_output=True, check=False,
    )
    if configured.returncode not in (0, 1):
        raise OSError("cannot inspect Git content-filter configuration")
    drivers = {
        os.fsdecode(key).rsplit(".", 1)[0]
        for key in configured.stdout.split(b"\0") if key
    }
    for driver in sorted(drivers):
        for conversion in ("clean", "smudge", "process"):
            prefix.extend(["-c", f"{driver}.{conversion}="])
        prefix.extend(["-c", f"{driver}.required=false"])
    return [*prefix, *arguments]


def _hash_git_diff(digest, project_root):
    command = _snapshot_git_command(
        project_root, "diff", "--no-textconv", "--no-ext-diff", "--binary",
        "--ignore-submodules=dirty",
        "HEAD", "--", ".",
        ":(exclude).sad/evidence", ":(exclude).sad/evidence/**",
    )
    try:
        proc = subprocess.Popen(
            command, cwd=str(project_root), stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        with proc.stdout:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        return proc.wait() == 0
    except OSError:
        return False


def _untracked_paths(project_root):
    result = subprocess.run(
        _snapshot_git_command(
            project_root, "ls-files", "--others", "--exclude-standard", "-z", "--",
            ".", ":(exclude).sad/evidence", ":(exclude).sad/evidence/**",
        ), cwd=str(project_root), capture_output=True, check=False,
    )
    if result.returncode != 0:
        return None
    return [path for path in result.stdout.split(b"\0") if path]


def _tracked_paths(project_root):
    """List HEAD and index paths without trusting worktree cache hints."""
    paths = set()
    for arguments in (
        ["ls-files", "--cached", "-z"],
        ["ls-tree", "-rz", "--name-only", "--full-tree", "HEAD"],
    ):
        result = subprocess.run(
            _snapshot_git_command(project_root, *arguments),
            cwd=str(project_root), capture_output=True, check=False,
        )
        if result.returncode != 0:
            return None
        paths.update(path for path in result.stdout.split(b"\0") if path)
    return paths


def _is_relevant_ignored_test_input(relative):
    """Select ignored source, config, and fixture files used by fixed recipes."""
    path = Path(os.fsdecode(relative))
    parts = [part.lower() for part in path.parts]
    test_index = next(
        (index for index, part in enumerate(parts[:-1])
         if part in _IGNORED_TEST_DIRS),
        None,
    )
    generated_index = next(
        (index for index, part in enumerate(parts)
         if part in _IGNORED_GENERATED_DIRS),
        None,
    )
    if (generated_index is not None
            and (test_index is None or generated_index < test_index)):
        return False
    if test_index is not None:
        return True
    basename = path.name.lower()
    if basename in _IGNORED_TEST_CONFIGS:
        return True
    if len(parts) >= 2 and parts[-2] == ".cargo" and parts[-1] in {
            "config", "config.toml"}:
        return True
    if path.suffix.lower() in {".py", ".rs", ".go"}:
        return True
    return (basename.startswith(("test_", "test-", "fixture_", "fixture-"))
            or basename.endswith("_test.json"))


def _ignored_test_paths(project_root):
    """List ignored test inputs that Git status would otherwise omit."""
    result = subprocess.run(
        _snapshot_git_command(
            project_root, "ls-files", "--others", "--ignored", "--exclude-standard",
            "-z", "--", ".", ":(exclude).sad/evidence",
            ":(exclude).sad/evidence/**",
        ), cwd=str(project_root), capture_output=True, check=False,
    )
    if result.returncode != 0:
        return None
    return [
        path for path in result.stdout.split(b"\0")
        if path and _is_relevant_ignored_test_input(path)
    ]


def _configured_submodule_paths(project_root):
    """Read safe relative submodule paths from the local .gitmodules file."""
    config = project_root / ".gitmodules"
    if config.is_symlink():
        return None
    if not config.exists():
        return []
    result = subprocess.run(
        _snapshot_git_command(
            project_root, "config", "--null", "--file", str(config),
            "--get-regexp", r"^submodule\..*\.path$",
        ),
        cwd=str(project_root), capture_output=True, check=False,
    )
    if result.returncode == 1 and not result.stdout:
        return []
    if result.returncode != 0:
        return None
    paths = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        key, separator, value = record.partition(b"\n")
        if (not separator or not key.lower().startswith(b"submodule.")
                or not key.lower().endswith(b".path") or not value):
            return None
        relative = Path(os.fsdecode(value))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            return None
        paths.append(relative)
    if len({path.as_posix() for path in paths}) != len(paths):
        return None
    return paths


def _gitlink_paths(project_root, *, index):
    """Return Gitlink paths from HEAD or the index, or None when untrusted."""
    if index:
        arguments = ["ls-files", "--stage", "-z"]
    else:
        arguments = ["ls-tree", "-rz", "--full-tree", "HEAD"]
    result = subprocess.run(
        _snapshot_git_command(project_root, *arguments),
        cwd=str(project_root), capture_output=True, check=False,
    )
    if result.returncode != 0:
        return None
    paths = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, separator, raw_path = record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            return None
        if index and fields[2] != b"0":
            # An unmerged index has competing content versions whose file data
            # is not represented by a single checkout snapshot.
            return None
        if fields[0] != b"160000":
            continue
        path = Path(os.fsdecode(raw_path))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            return None
        paths.append(path)
    normalized = [path.as_posix() for path in paths]
    if len(set(normalized)) != len(normalized):
        # Conflicted Gitlinks do not identify one unambiguous worktree.
        return None
    return paths


def _regular_file_digest(path, before):
    """Hash one regular file, refusing replacement or mutation during the read."""
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)

    expected = identity(before)
    content = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        if identity(os.fstat(stream.fileno())) != expected:
            return None
        for chunk in iter(lambda: stream.read(65536), b""):
            content.update(chunk)
        if identity(os.fstat(stream.fileno())) != expected:
            return None
    if identity(path.lstat()) != expected:
        return None
    return content.digest()


def worktree_snapshot(project_root: Path, _submodule_depth=0):
    """Digest tracked, untracked, and relevant ignored test inputs."""
    if _submodule_depth > MAX_SUBMODULE_DEPTH:
        return None
    status = subprocess.run(
        _snapshot_git_command(
            project_root, "status", "--porcelain", "-z", "--untracked-files=all",
            # Nested worktrees are read below with their own safe overrides.
            # Implicit Git traversal could execute a submodule-only filter.
            "--ignore-submodules=dirty", "--",
            ".", ":(exclude).sad/evidence", ":(exclude).sad/evidence/**",
        ), cwd=str(project_root), capture_output=True, check=False,
    )
    paths = _untracked_paths(project_root)
    tracked_paths = _tracked_paths(project_root)
    ignored_paths = _ignored_test_paths(project_root)
    submodule_paths = _configured_submodule_paths(project_root)
    head_gitlinks = _gitlink_paths(project_root, index=False)
    index_gitlinks = _gitlink_paths(project_root, index=True)
    if (status.returncode != 0 or paths is None or tracked_paths is None
            or ignored_paths is None
            or submodule_paths is None or head_gitlinks is None
            or index_gitlinks is None):
        return None
    expected_gitlinks = {
        path.as_posix() for path in head_gitlinks + index_gitlinks
    }
    configured_paths = {path.as_posix() for path in submodule_paths}
    if configured_paths != expected_gitlinks:
        # A missing or edited .gitmodules file must not make a Gitlink vanish
        # from the content-bound test-input snapshot.
        return None

    digest = hashlib.sha256()
    digest.update(b"status\0")
    digest.update(len(status.stdout).to_bytes(8, "big"))
    digest.update(status.stdout)
    digest.update(b"diff\0")
    diff_digest = hashlib.sha256()
    if not _hash_git_diff(diff_digest, project_root):
        return None
    digest.update(diff_digest.digest())

    digest.update(b"ignored-test-inputs\0")
    digest.update(len(ignored_paths).to_bytes(8, "big"))
    for relative in sorted(ignored_paths):
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)

    gitlink_paths = {os.fsencode(path) for path in expected_gitlinks}
    file_paths = {
        relative for relative in tracked_paths | set(paths) | set(ignored_paths)
        if relative not in gitlink_paths and relative != b".sad/evidence"
        and not relative.startswith(b".sad/evidence/")
    }
    digest.update(b"files\0")
    digest.update(len(file_paths).to_bytes(8, "big"))
    for relative in sorted(file_paths):
        path = project_root / os.fsdecode(relative)
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        before = None
        try:
            # A tracked directory replaced with a symlink must not redirect
            # content reads outside the checkout (or hide a missing file).
            cursor = project_root
            for part in Path(os.fsdecode(relative)).parts[:-1]:
                cursor = cursor / part
                if cursor.is_symlink():
                    return None
            before = path.lstat()
            digest.update(b"present\0")
            digest.update(stat.S_IFMT(before.st_mode).to_bytes(4, "big"))
            digest.update(stat.S_IMODE(before.st_mode).to_bytes(4, "big"))
            content = hashlib.sha256()
            if stat.S_ISREG(before.st_mode):
                payload = _regular_file_digest(path, before)
                if payload is None:
                    return None
            elif stat.S_ISLNK(before.st_mode):
                if relative in ignored_paths:
                    return None
                link = os.fsencode(os.readlink(path))
                target = path.resolve(strict=True)
                root = project_root.resolve(strict=True)
                if not is_within(target, root):
                    return None
                target_relative = target.relative_to(root)
                if (target_relative == Path(".sad/evidence")
                        or Path(".sad/evidence") in target_relative.parents):
                    # Evidence must not become its own test-input dependency.
                    return None
                target_before = target.lstat()
                if not stat.S_ISREG(target_before.st_mode):
                    return None
                target_digest = _regular_file_digest(target, target_before)
                if target_digest is None:
                    return None
                target_name = os.fsencode(target_relative.as_posix())
                content.update(len(link).to_bytes(8, "big"))
                content.update(link)
                content.update(len(target_name).to_bytes(8, "big"))
                content.update(target_name)
                content.update(stat.S_IMODE(target_before.st_mode).to_bytes(4, "big"))
                content.update(target_digest)
                payload = content.digest()
            else:
                return None
            digest.update(payload)
            after = path.lstat()
            if (before.st_dev, before.st_ino, before.st_mode, before.st_size,
                    before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_mode, after.st_size,
                    after.st_mtime_ns):
                return None
        except (FileNotFoundError, NotADirectoryError):
            if before is not None or relative not in tracked_paths:
                return None
            # Deletions, including sparse/skip-worktree paths, are valid
            # snapshot states. Bind absence rather than silently omitting it.
            digest.update(b"missing\0")
        except OSError:
            return None
        except RuntimeError:
            return None  # An unresolved symlink cycle cannot bind test inputs.

    submodule_dirty = False
    for relative in sorted(expected_gitlinks):
        relative = Path(relative)
        submodule = project_root / relative
        cursor = project_root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                return None
        if not submodule.is_dir():
            # An uninitialized submodule cannot provide a complete test-input
            # snapshot, so evidence from this checkout is not verifiable.
            return None
        resolved = submodule.resolve(strict=True)
        if not is_within(resolved, project_root):
            return None
        top = subprocess.run(
            _snapshot_git_command(resolved, "rev-parse", "--show-toplevel"),
            cwd=str(resolved),
            capture_output=True, text=True, check=False,
        )
        head = subprocess.run(
            _snapshot_git_command(resolved, "rev-parse", "HEAD"), cwd=str(resolved),
            capture_output=True, text=True, check=False,
        )
        if (top.returncode != 0 or head.returncode != 0
                or Path(top.stdout.strip()).resolve() != resolved):
            return None
        nested = worktree_snapshot(resolved, _submodule_depth + 1)
        if nested is None:
            return None
        relative_bytes = os.fsencode(relative.as_posix())
        digest.update(b"submodule\0")
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        digest.update(head.stdout.strip().encode("ascii", errors="strict"))
        digest.update(nested["worktree_digest"].encode("ascii"))
        submodule_dirty = submodule_dirty or nested["worktree_dirty"]

    return {
        "worktree_dirty": bool(status.stdout or ignored_paths or submodule_dirty),
        "worktree_digest": digest.hexdigest(),
    }


def git_context(project_root: Path):
    """Return HEAD plus a content-bound dirty snapshot, excluding evidence."""
    try:
        head = subprocess.run(
            _snapshot_git_command(project_root, "rev-parse", "HEAD"), cwd=str(project_root),
            capture_output=True, text=True, check=False,
        )
        if head.returncode != 0:
            return None
        snapshot = worktree_snapshot(project_root)
        if snapshot is None:
            return None
        return {"commit_sha": head.stdout.strip(), **snapshot}
    except OSError:
        return None


def github_repository_slug(project_root: Path):
    """Read only the owner/repo portion of an origin URL; never expose creds."""
    try:
        result = subprocess.run(
            _snapshot_git_command(project_root, "remote", "get-url", "origin"),
            cwd=str(project_root),
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
            _snapshot_git_command(Path.cwd(), "rev-parse", "--show-toplevel"),
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
    check_id = data.get("check_id")
    if check_id is None:
        check_id = data.get("recipe_id")
    if check_id is not None:
        if not isinstance(check_id, str) or not check_id.strip():
            return False, [], "Invalid check_id/recipe_id; expected a non-empty string"
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

    # Match raw commands only when they exactly select a fixed recipe. Any
    # caller-supplied selector, path, manifest, or test-name argument could
    # redirect an otherwise trusted runner outside the checkout.
    exe = Path(argv[0]).name
    if exe in ("python", "python3"):
        if argv[1:] == ["scripts/verify.py"]:
            return True, list(TRUSTED_RECIPES["repo-verify"]), "Matched repo-verify recipe"
        if argv[1:] == ["benchmarks/runner.py"]:
            return True, list(TRUSTED_RECIPES["repo-benchmarks"]), "Matched repo-benchmarks recipe"
        if argv[1:] == ["-m", "pytest"]:
            return True, list(TRUSTED_RECIPES["python-pytest"]), "Matched python pytest recipe"
        if argv[1:] == ["-m", "unittest", "discover"]:
            return True, list(TRUSTED_RECIPES["python-unittest"]), "Matched python unittest recipe"
        if argv[1:] == ["benchmarks/fixtures/tenant-isolation/grader.py"]:
            return True, [sys.executable, "benchmarks/fixtures/tenant-isolation/grader.py"], "Matched tenant isolation grader"
        if argv[1:] == ["benchmarks/fixtures/real-rls/grader.py"]:
            return True, [sys.executable, "benchmarks/fixtures/real-rls/grader.py"], "Matched real RLS grader"

    if exe == "pytest" and len(argv) == 1:
        return True, list(TRUSTED_RECIPES["python-pytest"]), "Matched pytest recipe"

    if exe == "cargo" and argv[1:] == ["test"]:
        return True, list(TRUSTED_RECIPES["cargo-test"]), "Matched cargo-test recipe"

    if exe == "go" and argv[1:] == ["test", "./..."]:
        return True, list(TRUSTED_RECIPES["go-test"]), "Matched go-test recipe"

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
                # start_new_session=True makes the child PID its process-group
                # ID. Keep using it even if the parent exited while a child
                # still holds the captured output pipes open.
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                proc.kill()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                for pipe in (proc.stdout, proc.stderr):
                    if pipe is not None:
                        pipe.close()
                proc.wait()
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


def canonical_record_hash(data: dict) -> str:
    """Computes SHA-256 over canonical JSON without record_hash or signature."""
    clean = {k: v for k, v in data.items() if k not in ("record_hash", "signature")}
    canonical_bytes = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def create_evidence_record(
    project_root: Path,
    task_slug: str,
    command: str,
    exit_code: int,
    summary: str,
    files_touched: list,
    status: str = "COMPLETED",
    evidence_version: str = "2.0",
    output_dir: Path = None,
) -> Path:
    """Creates a cryptographic Evidence v2 record in .sad/evidence/."""
    root = Path(project_root).resolve()
    ev_dir = output_dir or (root / ".sad" / "evidence")
    ev_dir.mkdir(parents=True, exist_ok=True)

    proj_id = project_identity(root)
    ctx = git_context(root)
    commit_sha = ctx["commit_sha"] if ctx else "0" * 40
    worktree_dirty = ctx["worktree_dirty"] if ctx else False
    worktree_digest = ctx["worktree_digest"] if ctx else "0" * 64

    existing_files = sorted(ev_dir.glob("*.json"))
    prev_hash = "GENESIS"
    if existing_files:
        try:
            last_record = json.loads(existing_files[-1].read_text(encoding="utf-8"))
            if "record_hash" in last_record:
                prev_hash = last_record["record_hash"]
            else:
                prev_hash = canonical_record_hash(last_record)
        except Exception:
            pass

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    record = {
        "timestamp": now_iso,
        "task_slug": task_slug,
        "command": command,
        "exit_code": exit_code,
        "summary": summary,
        "files_touched": files_touched,
        "project_id": proj_id,
        "commit_sha": commit_sha,
        "worktree_dirty": worktree_dirty,
        "worktree_digest": worktree_digest,
        "status": status,
        "evidence_version": evidence_version,
        "previous_record_hash": prev_hash,
    }

    record["record_hash"] = canonical_record_hash(record)

    time_prefix = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_file = ev_dir / f"{time_prefix}-{task_slug}.json"
    out_file.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return out_file


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
        "worktree_digest",
    ]

    # Check current git commit for freshness binding
    current_context = git_context(root)
    current_project_id = project_identity(root)
    last_seen_record_hash = None

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

        # Evidence v2 Cryptographic Provenance & Hash-Chain Verification
        ev_version = str(data.get("evidence_version", "1.0"))
        has_hash = "record_hash" in data
        has_prev = "previous_record_hash" in data

        if ev_version == "2.0" or has_hash or has_prev:
            expected_record_hash = canonical_record_hash(data)
            if has_hash:
                if not isinstance(data["record_hash"], str) or not re.fullmatch(r"[0-9a-fA-F]{64}", data["record_hash"]):
                    log("   [FAIL] record_hash must be a 64-character SHA-256 hex string.")
                    errors += 1
                    records.append({"file": ef.name, "status": "FAILED", "reason": "invalid record_hash format"})
                    continue
                if data["record_hash"].lower() != expected_record_hash.lower():
                    log(f"   [FAIL] Evidence record hash mismatch (recorded: {data['record_hash'][:12]}..., expected: {expected_record_hash[:12]}...).")
                    errors += 1
                    records.append({"file": ef.name, "status": "FAILED", "reason": "record_hash mismatch"})
                    continue

            if has_prev:
                prev_val = data["previous_record_hash"]
                if last_seen_record_hash is None:
                    if prev_val not in ("GENESIS", "genesis") and not re.fullmatch(r"[0-9a-fA-F]{64}", str(prev_val)):
                        log("   [FAIL] Initial previous_record_hash must be 'GENESIS' or a SHA-256 digest.")
                        errors += 1
                        records.append({"file": ef.name, "status": "FAILED", "reason": "invalid genesis hash"})
                        continue
                else:
                    if str(prev_val).lower() != str(last_seen_record_hash).lower():
                        log(f"   [FAIL] Provenance hash chain broken at {ef.name} (expected {last_seen_record_hash[:12]}..., got {str(prev_val)[:12]}...).")
                        errors += 1
                        records.append({"file": ef.name, "status": "FAILED", "reason": "broken hash chain"})
                        continue

            last_seen_record_hash = data.get("record_hash", expected_record_hash)

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
        if not isinstance(data.get("worktree_digest"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", data["worktree_digest"]
        ):
            log("   [FAIL] worktree_digest must be a SHA-256 hex digest.")
            errors += 1
            records.append({"file": ef.name, "status": "FAILED", "reason": "invalid worktree_digest"})
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
        if data["worktree_digest"] != current_context["worktree_digest"]:
            log("   [WORKTREE_CHANGED] Non-evidence checkout contents changed after capture.")
            errors += 1
            records.append({"file": ef.name, "status": "WORKTREE_CHANGED", "reason": "worktree digest mismatch"})
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
            "worktree_digest": data.get("worktree_digest"),
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
    parser.add_argument("--print-context", action="store_true", help="Print project_id, commit_sha, worktree_dirty, and worktree_digest for a new evidence record")
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
