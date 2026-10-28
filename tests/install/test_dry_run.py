"""Defect class 3: --dry-run must be a TRUE read-only operation.

Current behavior: install.sh runs `mkdir -p "${HOME}/.sadskill"` before the
dry-run guard, so even --dry-run creates ~/.sadskill on disk.
"""

import os
import unittest

from tests.helpers import SandboxCase


class DryRunTests(SandboxCase):
    def test_install_dry_run_creates_nothing_in_clean_home(self):
        before = self.home_snapshot()
        rc = self.run_install("--agent", "claude", "--dry-run")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        after = self.home_snapshot()
        self.assertFalse(
            os.path.exists(os.path.join(self.home, ".sadskill")),
            "install --dry-run created ~/.sadskill (contradicts no-write promise)",
        )
        self.assertEqual(
            before, after,
            "install --dry-run modified files under HOME",
        )

    def test_install_dry_run_over_existing_install_changes_nothing(self):
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        before = self.home_snapshot()
        rc = self.run_install("--agent", "claude", "--dry-run")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertEqual(
            before, self.home_snapshot(),
            "install --dry-run modified an existing installation",
        )

    def test_uninstall_dry_run_changes_nothing(self):
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        before = self.home_snapshot()
        rc = self.run_uninstall("--dry-run")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertEqual(
            before, self.home_snapshot(),
            "uninstall --dry-run modified files under HOME",
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.home, ".claude/skills/sadskill/SKILL.md")),
            "uninstall --dry-run removed the installed skill",
        )


if __name__ == "__main__":
    unittest.main()
