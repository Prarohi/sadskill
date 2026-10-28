"""Defect class 10: paths with spaces, Unicode, quotes, $-metachars, and
unusual HOME values must work end-to-end (install, modify, uninstall
roundtrip) with no stray temp files left behind.
"""

import os
import unittest

from tests.helpers import SandboxCase

WEIRD_HOME_REL = "ho me/üñïcodé-'qu\"ote$"
WEIRD_TARGET_REL = "tä rg et/a b's dir"
MARKER = "SADSKILL-USER-MARKER-paths"


class WeirdPathTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.base, WEIRD_HOME_REL)
        self.project = os.path.join(self.base, WEIRD_TARGET_REL)
        os.makedirs(self.home)
        os.makedirs(self.project)
        self.env["HOME"] = self.home

    def test_install_uninstall_roundtrip_weird_paths(self):
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, f"install failed: {rc.stderr}")
        installed = os.path.join(
            self.home, ".claude/skills/sadskill/SKILL.md"
        )
        self.assertTrue(
            os.path.exists(installed),
            "skill not installed under HOME containing spaces/unicode/quotes",
        )
        with open(installed, "a", encoding="utf-8") as fh:
            fh.write("\n" + MARKER + "\n")

        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, f"uninstall failed: {rc.stderr}")
        self.assertTrue(
            self.content_exists_under_home(MARKER),
            "uninstall lost user modification under weird paths",
        )
        # A user-modified install is preserved on plain uninstall (no --force):
        # the modified content must still be present under HOME.
        self.assertTrue(
            os.path.exists(installed),
            "uninstall silently removed user-modified content under weird paths "
            "(expected PRESERVE-MODIFIED)",
        )

    def test_uninstall_removes_pristine_install(self):
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, f"install failed: {rc.stderr}")
        installed = os.path.join(
            self.home, ".claude/skills/sadskill/SKILL.md"
        )
        self.assertTrue(os.path.exists(installed), "pristine skill not installed")
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, f"uninstall failed: {rc.stderr}")
        self.assertFalse(
            os.path.exists(installed),
            "uninstall did not remove the pristine installed skill",
        )

    def test_cursor_rule_with_spaced_target(self):
        rc = self.run_install("--agent", "cursor", "--target", self.project)
        self.assertEqual(rc.returncode, 0, f"cursor install failed: {rc.stderr}")
        rule = os.path.join(
            self.project, ".cursor/rules/sadskill.mdc"
        )
        self.assertTrue(
            os.path.exists(rule),
            "cursor rule not installed under target with spaces",
        )
        rc = self.run_uninstall("--target", self.project)
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertFalse(
            os.path.exists(rule),
            "cursor rule not removed under target with spaces",
        )

    def test_no_stray_files_left_in_home(self):
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, rc.stderr)
        leftovers = [
            rel for rel in self.tree_entries(self.home)
            if "sadskill-sandbox" in rel or rel.endswith(".tmp")
        ]
        self.assertFalse(
            leftovers, f"stray temp files left in HOME: {leftovers}"
        )


if __name__ == "__main__":
    unittest.main()
