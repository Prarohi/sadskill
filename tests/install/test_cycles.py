"""Defect class 6: repeated install / reinstall / uninstall cycles,
including version upgrades, must preserve user modifications at every step
of the chain.
"""

import os
import unittest

from tests.helpers import SandboxCase

MARKER = "SADSKILL-USER-MARKER-cycle"


class CycleTests(SandboxCase):
    def _installed_skill(self):
        return os.path.join(self.home, ".claude/skills/sadskill/SKILL.md")

    def _modify(self):
        with open(self._installed_skill(), "a", encoding="utf-8") as fh:
            fh.write("\n" + MARKER + "\n")

    def test_full_cycle_preserves_user_content_everywhere(self):
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self._modify()

        # reinstall
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue(
            self.content_exists_under_home(MARKER),
            "cycle step 'reinstall' lost user modification",
        )

        # uninstall without restore
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue(
            self.content_exists_under_home(MARKER),
            "cycle step 'uninstall' lost user modification",
        )

        # reinstall again
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue(
            self.content_exists_under_home(MARKER),
            "cycle step 'reinstall-after-uninstall' lost user modification",
        )

        # uninstall with forced restore (explicit overwrite is the user's
        # choice) — prior modification copies must still exist somewhere.
        rc = self.run_uninstall("--restore-previous", "--force")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue(
            self.content_exists_under_home(MARKER),
            "cycle step 'forced restore' deleted every copy of the user's "
            "modification",
        )


if __name__ == "__main__":
    unittest.main()
