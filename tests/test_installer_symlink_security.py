"""Installer symlink regression tests. All filesystem writes are isolated to temporary HOME and project."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"


class InstallerSymlinkTests(unittest.TestCase):
    def run_install(self, home, *args):
        env = os.environ.copy()
        env["HOME"] = str(home)
        return subprocess.run(
            ["bash", str(INSTALL), *args], cwd=str(ROOT),
            env=env, capture_output=True, text=True, timeout=45,
        )

    def test_symlinked_codex_prompt_never_overwrites_external_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            prompts = home / ".codex" / "prompts"
            prompts.mkdir(parents=True)
            external = root / "user-file.txt"
            external.write_text("PRIVATE ORIGINAL", encoding="utf-8")
            (prompts / "sad-plan.md").symlink_to(external)
            result = self.run_install(home, "--no-backup", "codex")
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("symlink", result.stderr.lower())
            self.assertEqual(external.read_text(encoding="utf-8"), "PRIVATE ORIGINAL")

    def test_claude_hook_parent_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            (home / ".claude").mkdir(parents=True)
            external = root / "external-hooks"
            external.mkdir()
            (home / ".claude" / "hooks").symlink_to(external)
            result = self.run_install(home, "claude")
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse((external / "git-guardrail.sh").exists())

    def test_cursor_rules_parent_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            project = root / "project"
            (project / ".cursor").mkdir(parents=True)
            external = root / "external-rules"
            external.mkdir()
            (project / ".cursor" / "rules").symlink_to(external)
            result = self.run_install(home, "--agent", "cursor", "--target", str(project))
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse((external / "sadskill.mdc").exists())


if __name__ == "__main__":
    unittest.main()
