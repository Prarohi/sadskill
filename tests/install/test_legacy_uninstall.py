"""Defect class 4: legacy uninstall (no manifest) removes user files by
weak ownership signals (the word "sadskill", or a directory merely named
sadskill). Ownership must be proven by exact content identity with the
shipped source, never by name or substring.
"""

import os
import shutil
import unittest

from tests.helpers import SandboxCase, REPO_ROOT


class LegacyUninstallTests(SandboxCase):
    def _no_manifest(self):
        # Legacy path triggers only when no manifest exists.
        sadskill_dir = os.path.join(self.home, ".sadskill")
        if os.path.isdir(sadskill_dir):
            shutil.rmtree(sadskill_dir)

    def test_user_file_with_sadskill_word_is_preserved(self):
        self._no_manifest()
        user_file = self.write_file(
            self.home,
            ".claude/commands/sad-notes.md",
            "# My notes about the sadskill project\n"
            "I use sadskill for my workflow.\n",
        )
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue(
            os.path.exists(user_file),
            "legacy uninstall deleted the user's own file merely because it "
            "contains the word 'sadskill'",
        )

    def test_source_identical_file_is_removed(self):
        """Files byte-identical to shipped sources are ours to remove."""
        self._no_manifest()
        src = os.path.join(REPO_ROOT, "commands", "claude", "sad-analyze.md")
        with open(src, encoding="utf-8") as fh:
            content = fh.read()
        target = self.write_file(
            self.home, ".claude/commands/sad-analyze.md", content
        )
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertFalse(
            os.path.exists(target),
            "legacy uninstall failed to remove an exactly-owned file",
        )

    def test_gemini_cli_pristine_skill_removed_without_manifest(self):
        self._no_manifest()
        import pathlib
        target = pathlib.Path(self.home) / ".gemini" / "skills" / "sadskill"
        shutil.copytree(os.path.join(REPO_ROOT, "skills", "sadskill"), target)
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertFalse(target.exists(), "Gemini CLI legacy skill was not removed")

    def test_gemini_cli_user_modified_skill_is_preserved(self):
        self._no_manifest()
        import pathlib
        target = pathlib.Path(self.home) / ".gemini" / "skills" / "sadskill"
        shutil.copytree(os.path.join(REPO_ROOT, "skills", "sadskill"), target)
        (target / "USER-NOTES.md").write_text("keep this", encoding="utf-8")
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue((target / "USER-NOTES.md").is_file(),
                        "Uninstall removed user-modified Gemini CLI skill")

    def test_user_dir_named_sadskill_with_unrelated_content_preserved(self):
        self._no_manifest()
        keep = self.write_file(
            self.home,
            ".codex/skills/sadskill/MY-OWN-NOTES.md",
            "This directory is mine, content unrelated to sadskill.\n",
        )
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue(
            os.path.exists(keep),
            "legacy uninstall removed a user-owned directory named sadskill "
            "containing unrelated files",
        )


if __name__ == "__main__":
    unittest.main()
