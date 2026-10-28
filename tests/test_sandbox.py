"""Unit tests for sadskill Linux Bubblewrap Sandbox (scripts/sandbox.sh).
Validates workspace containment, protected .git read-only mounts,
and offline network isolation.
"""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SANDBOX_SH = ROOT / "scripts/sandbox.sh"


class SandboxTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("bwrap"):
            self.skipTest("bubblewrap ('bwrap') binary not available on host system")
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name)
        subprocess.run(["git", "init"], cwd=str(self.proj), capture_output=True, check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_benign_command_in_sandbox(self):
        res = subprocess.run(
            [str(SANDBOX_SH), "--project-dir", str(self.proj), "--", "echo", "sandbox_active"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(self.proj),
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
        )
        self.assertEqual(res.returncode, 0)


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
        self.env["BWRAP_ARGS_CAPTURE"] = str(self.capture)

    def tearDown(self):
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

    def test_git_worktree_pointer_is_read_only(self):
        (self.workspace / ".git").write_text("gitdir: /tmp/external-gitdir\n")
        result = self.sandbox(self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.capture.read_text().splitlines()
        self.assertEqual(arguments.count(str(self.workspace / ".git")), 2)


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
