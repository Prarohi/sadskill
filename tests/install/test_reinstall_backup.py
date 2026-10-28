"""Defect class 1: reinstall after user modification must never delete the
only remaining copy of the user's modified content.

Current behavior: manifest.py record_entry treats the fresh backup created by
the reinstall as a redundant duplicate and deletes it, even when the recorded
backup path is empty (first-install case). Result: user's modifications are
lost forever.
"""

import os
import unittest

from tests.helpers import SandboxCase

MARKER = "SADSKILL-USER-MARKER-reinstall-01"


class ReinstallBackupTests(SandboxCase):
    def test_modified_skill_survives_reinstall(self):
        rc_install = self.run_install("--agent", "claude")
        self.assertEqual(
            rc_install.returncode, 0,
            f"install failed:\n{rc_install.stdout}\n{rc_install.stderr}",
        )
        skill = "claude/skills/sadskill/SKILL.md"
        self.assertTrue(
            os.path.exists(os.path.join(self.home, "." + skill)),
            "expected skill file installed at ~/.claude/skills/sadskill/SKILL.md",
        )
        installed = os.path.join(self.home, ".claude/skills/sadskill/SKILL.md")
        with open(installed, "a", encoding="utf-8") as fh:
            fh.write("\n" + MARKER + "\n")

        rc_re = self.run_install("--agent", "claude")
        self.assertEqual(
            rc_re.returncode, 0,
            f"reinstall failed:\n{rc_re.stdout}\n{rc_re.stderr}",
        )
        self.assertTrue(
            self.content_exists_under_home(MARKER),
            "user's modified skill content was deleted by reinstall "
            "(the freshly created backup holding the only copy was removed)",
        )

    def test_reinstall_keeps_first_install_backup_of_user_content(self):
        """Second reinstall after further modification: earlier conflict
        backups must also survive, not just the newest one."""
        self.run_install("--agent", "claude")
        installed = self.home + "/.claude/skills/sadskill/SKILL.md"
        with open(installed, "a", encoding="utf-8") as fh:
            fh.write("\n" + MARKER + "\n")
        self.run_install("--agent", "claude")

        marker2 = "SADSKILL-USER-MARKER-reinstall-02"
        with open(installed, "a", encoding="utf-8") as fh:
            fh.write("\n" + marker2 + "\n")
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0)
        self.assertTrue(
            self.content_exists_under_home(MARKER),
            "earlier user modification backup was deleted by reinstall",
        )
        self.assertTrue(
            self.content_exists_under_home(marker2),
            "newest user modification backup was deleted by reinstall",
        )


if __name__ == "__main__":
    unittest.main()
