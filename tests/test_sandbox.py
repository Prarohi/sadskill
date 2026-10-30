"""Unit tests for Sadskill's Linux Bubblewrap sandbox.

Validates workspace containment, home/environment isolation, protected .git
mounts, and fail-closed behavior when Bubblewrap is unavailable.
"""

from pathlib import Path
import os
import pwd
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SANDBOX_SH = ROOT / "scripts/sandbox.sh"


class SandboxTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("bwrap"):
            if os.environ.get("SADSKILL_REQUIRE_BWRAP") == "1":
                self.fail("Bubblewrap is mandatory for native sandbox integration CI")
            self.skipTest("bubblewrap ('bwrap') binary not available on host system")
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name)
        self.home_tmp = tempfile.TemporaryDirectory(prefix="sadskill-sandbox-home-")
        self.worktree_tmp = None
        self.host_home = Path(self.home_tmp.name)
        (self.host_home / "private-canary").write_text("synthetic test data", encoding="utf-8")
        self.env = dict(os.environ)
        self.env["HOME"] = str(self.host_home)
        subprocess.run(["git", "init"], cwd=str(self.proj), capture_output=True, check=True)

    def tearDown(self):
        if self.worktree_tmp is not None:
            self.worktree_tmp.cleanup()
        self.home_tmp.cleanup()
        self.tmp.cleanup()

    def create_linked_worktree(self):
        subprocess.run(
            ["git", "-c", "user.name=Sandbox Test", "-c", "user.email=sandbox@example.invalid",
             "commit", "--allow-empty", "-m", "sandbox base"],
            cwd=str(self.proj), env=self.env, capture_output=True, check=True,
        )
        self.worktree_tmp = tempfile.TemporaryDirectory(prefix="sadskill-linked-worktree-")
        worktree = Path(self.worktree_tmp.name) / "checkout"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
            cwd=str(self.proj), env=self.env, capture_output=True, check=True,
        )
        return worktree

    def test_benign_command_in_sandbox(self):
        res = subprocess.run(
            [str(SANDBOX_SH), "--project-dir", str(self.proj), "--", "echo", "sandbox_active"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(self.proj),
            env=self.env,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("sandbox_active", res.stdout)

    def test_ro_git_protection(self):
        # Attempting to write into .git inside sandbox must fail with read-only filesystem error
        res = subprocess.run(
            [str(SANDBOX_SH), "--project-dir", str(self.proj), "--", "bash", "-c", "touch .git/sandbox_hazard_file"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(self.proj),
            env=self.env,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertTrue(
            "Read-only file system" in res.stderr or "Permission denied" in res.stderr
        )

    def test_allow_git_flag(self):
        # With --allow-git, touching and removing a temporary file inside .git should succeed
        res = subprocess.run(
            [
                str(SANDBOX_SH),
                "--project-dir",
                str(self.proj),
                "--allow-git",
                "--",
                "bash",
                "-c",
                "touch .git/sandbox_test_temp && rm .git/sandbox_test_temp",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(self.proj),
            env=self.env,
        )
        self.assertEqual(res.returncode, 0)

    def test_host_home_and_inherited_environment_are_hidden(self):
        env = dict(self.env)
        env["SADSKILL_SANDBOX_SECRET_CANARY"] = "synthetic-only"
        command = (
            'test -z "${SADSKILL_SANDBOX_SECRET_CANARY:-}" '
            '&& test "$HOME" = /tmp/sadskill-home '
            f"&& test ! -e {shlex.quote(str(self.host_home / 'private-canary'))}"
        )
        result = subprocess.run(
            [str(SANDBOX_SH), "--project-dir", str(self.proj), "--", "bash", "-c", command],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(self.proj),
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_linked_worktree_git_status_works_with_read_only_metadata(self):
        worktree = self.create_linked_worktree()
        result = subprocess.run(
            [str(SANDBOX_SH), "--project-dir", str(worktree), "--", "git", "status", "--short", "--branch"],
            capture_output=True, text=True, check=False, cwd=str(worktree), env=self.env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## HEAD (no branch)", result.stdout)

        mutation = subprocess.run(
            [str(SANDBOX_SH), "--project-dir", str(worktree), "--", "git", "update-ref",
             "refs/heads/sandbox-read-only-check", "HEAD"],
            capture_output=True, text=True, check=False, cwd=str(worktree), env=self.env,
        )
        self.assertNotEqual(mutation.returncode, 0, mutation.stderr)
        absent_ref = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/sandbox-read-only-check"],
            capture_output=True, cwd=str(self.proj), env=self.env, check=False,
        )
        self.assertNotEqual(absent_ref.returncode, 0)

    def test_allow_git_allows_linked_worktree_metadata_writes(self):
        worktree = self.create_linked_worktree()
        original_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(worktree), env=self.env,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        result = subprocess.run(
            [str(SANDBOX_SH), "--project-dir", str(worktree), "--allow-git", "--", "git",
             "-c", "user.name=Sandbox Test", "-c", "user.email=sandbox@example.invalid",
             "commit", "--allow-empty", "-m", "sandbox writable metadata"],
            capture_output=True, text=True, check=False, cwd=str(worktree), env=self.env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        new_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(worktree), env=self.env,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertNotEqual(new_head, original_head)


class SandboxWritableRootTests(unittest.TestCase):
    """Validation must work without any real Bubblewrap privileges."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "project"
        self.workspace.mkdir()
        self.capture = self.root / "args.txt"
        fake_dir = self.root / "fakebin"
        fake_dir.mkdir()
        fake = fake_dir / "bwrap"
        fake.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$BWRAP_ARGS_CAPTURE"\n')
        fake.chmod(0o755)
        self.env = dict(os.environ)
        self.env["PATH"] = str(fake_dir) + os.pathsep + self.env.get("PATH", "")
        self.home_tmp = tempfile.TemporaryDirectory(prefix="sadskill-sandbox-home-")
        self.env["HOME"] = self.home_tmp.name
        self.env["BWRAP_ARGS_CAPTURE"] = str(self.capture)

    def tearDown(self):
        self.home_tmp.cleanup()
        self.tmp.cleanup()

    def sandbox(self, project):
        return subprocess.run(
            ["/bin/bash", str(SANDBOX_SH), "--project-dir", str(project), "--", "/bin/true"],
            cwd=str(self.workspace), env=self.env, capture_output=True, text=True,
        )

    def test_broad_system_roots_are_refused(self):
        for root in ("/", "/etc", "/usr", "/tmp", "/home"):
            with self.subTest(root=root):
                self.capture.unlink(missing_ok=True)
                result = self.sandbox(root)
                self.assertEqual(result.returncode, 78, result.stderr)
                self.assertIn("refusing", result.stderr)
                self.assertFalse(self.capture.exists())

    def test_user_home_is_not_a_workspace(self):
        self.env["HOME"] = str(self.root)
        result = self.sandbox(self.root)
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertIn("entire user HOME", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_overridden_home_cannot_make_real_account_home_writable(self):
        account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
        fake_home = self.root / "fake-home"
        fake_home.mkdir()
        self.env["HOME"] = str(fake_home)
        result = self.sandbox(account_home)
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertIn("entire user HOME", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_sensitive_home_directory_is_refused_as_workspace(self):
        sensitive = self.root / "unlisted-user" / ".ssh"
        sensitive.mkdir(parents=True)
        result = self.sandbox(sensitive)
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertIn("sensitive HOME path", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_sensitive_descendant_at_arbitrary_depth_is_refused(self):
        project = self.root / "deep-project"
        sensitive = project.joinpath(*(["nested"] * 9), ".aws")
        sensitive.mkdir(parents=True)
        result = self.sandbox(project)
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertIn("sensitive credential paths", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_project_path_symlinks_are_refused(self):
        target = self.root / "ordinary-target"
        target.mkdir()
        alias = self.root / "project-alias"
        alias.symlink_to(target, target_is_directory=True)
        result = self.sandbox(alias)
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertIn("symlinked project path", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_default_logical_working_directory_symlink_is_refused(self):
        target = self.root / "ordinary-working-directory"
        target.mkdir()
        alias = self.root / "working-directory-alias"
        alias.symlink_to(target, target_is_directory=True)
        env = dict(self.env, PWD=str(alias))
        result = subprocess.run(
            ["/bin/bash", str(SANDBOX_SH), "--", "/bin/true"],
            cwd=str(target), env=env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertIn("symlinked project path", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_root_identity_helper_classifies_only_uid_zero_as_root(self):
        helper = Path(__file__).resolve().parents[1] / "scripts/sandbox-paths.sh"
        script = 'source "$1"; sadskill_is_root "$2"'
        root_user = subprocess.run(
            ["bash", "-c", script, "sandbox-test", str(helper), "0"],
            env=self.env, capture_output=True, text=True,
        )
        regular_user = subprocess.run(
            ["bash", "-c", script, "sandbox-test", str(helper), "1000"],
            env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(root_user.returncode, 0)
        self.assertEqual(regular_user.returncode, 1)

    def test_symlink_to_root_is_refused(self):
        alias = self.root / "root-link"
        alias.symlink_to("/", target_is_directory=True)
        result = self.sandbox(alias)
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertFalse(self.capture.exists())

    def test_narrow_workspace_is_writable(self):
        result = self.sandbox(self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--bind", self.capture.read_text())

    def test_process_namespace_is_isolated_before_proc_is_mounted(self):
        result = self.sandbox(self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.capture.read_text().splitlines()
        self.assertIn("--unshare-pid", arguments)
        self.assertLess(arguments.index("--unshare-pid"), arguments.index("--proc"))

    def test_runtime_socket_roots_are_hidden(self):
        result = self.sandbox(self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.capture.read_text().splitlines()
        tmpfs_targets = {
            arguments[index + 1]
            for index, option in enumerate(arguments[:-1])
            if option == "--tmpfs"
        }
        expected = {
            str(Path(path).resolve())
            for path in ("/run", "/var/run")
            if Path(path).is_dir()
        }
        self.assertTrue(expected <= tmpfs_targets)

    def test_home_and_environment_are_isolated(self):
        result = self.sandbox(self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.capture.read_text().splitlines()
        self.assertIn("--clearenv", arguments)
        self.assertIn("--tmpfs", arguments)
        self.assertIn("/tmp", arguments)
        self.assertNotIn(self.env["HOME"], arguments)
        account_home = str(Path(pwd.getpwuid(os.getuid()).pw_dir).resolve())
        if account_home != "/tmp" and not account_home.startswith("/tmp/"):
            self.assertIn(account_home, arguments)
        home_index = arguments.index("--setenv")
        self.assertEqual(arguments[home_index + 1], "PATH")
        self.assertEqual(arguments[home_index + 3], "--setenv")
        self.assertEqual(arguments[home_index + 4], "HOME")
        self.assertEqual(arguments[home_index + 5], "/tmp/sadskill-home")
        self.assertEqual(arguments[home_index + 6], "--setenv")
        self.assertEqual(arguments[home_index + 7], "TMPDIR")

    def test_workspace_below_home_is_recreated_then_bound(self):
        project = Path(self.env["HOME"]) / "work" / "sample"
        project.mkdir(parents=True)
        result = self.sandbox(project)
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.capture.read_text().splitlines()
        directory_targets = [
            arguments[index + 1]
            for index, argument in enumerate(arguments[:-1])
            if argument == "--dir"
        ]
        self.assertIn(str(project.parent), arguments)
        self.assertIn(str(project), directory_targets)
        bind_index = arguments.index("--bind")
        self.assertEqual(arguments[bind_index + 1 : bind_index + 3], [str(project), str(project)])

    def test_unverified_git_worktree_pointer_is_not_mounted(self):
        (self.workspace / ".git").write_text("gitdir: /tmp/external-gitdir\n")
        result = self.sandbox(self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("failed validation", result.stderr)
        arguments = self.capture.read_text().splitlines()
        self.assertEqual(arguments.count(str(self.workspace / ".git")), 2)
        self.assertNotIn("/tmp/external-gitdir", arguments)

    def test_allow_git_rejects_unverified_worktree_pointer_before_bwrap(self):
        (self.workspace / ".git").write_text("gitdir: /tmp/external-gitdir\n")
        result = subprocess.run(
            ["/bin/bash", str(SANDBOX_SH), "--project-dir", str(self.workspace), "--allow-git",
             "--", "/bin/true"],
            cwd=str(self.workspace), env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertIn("requires validated repository metadata", result.stderr)
        self.assertFalse(self.capture.exists())


class SandboxMissingBwrapTests(unittest.TestCase):
    """Fail-closed behavior must be tested even on CI machines without bwrap."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fake_path = self.root / "empty-path"
        self.fake_path.mkdir()
        self.env = dict(os.environ, PATH=str(self.fake_path))
        self.target = self.root / "must-not-run"

    def tearDown(self):
        self.tmp.cleanup()

    def run_sandbox(self, *options):
        return subprocess.run(
            ["/bin/bash", str(SANDBOX_SH), *options, "--", "/usr/bin/touch", str(self.target)],
            cwd=str(self.root),
            env=self.env,
            text=True,
            capture_output=True,
        )

    def test_missing_bwrap_fails_closed(self):
        result = self.run_sandbox()
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertFalse(self.target.exists())
        self.assertIn("NOT executed", result.stderr)

    def test_explicit_unsandboxed_opt_in(self):
        result = self.run_sandbox("--allow-unsandboxed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.target.exists())
        self.assertIn("WITHOUT containment", result.stderr)

    def test_offline_refuses_unsandboxed_fallback(self):
        result = self.run_sandbox("--offline", "--allow-unsandboxed")
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertFalse(self.target.exists())
        self.assertIn("cannot be honored", result.stderr)


if __name__ == "__main__":
    unittest.main()
