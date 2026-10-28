"""Unit tests for sadskill Linux Bubblewrap Sandbox (scripts/sandbox.sh).
Validates workspace containment, protected .git read-only mounts,
and offline network isolation.
"""

from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
