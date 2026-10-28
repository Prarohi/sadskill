"""Defect class 2: --clean-backups must never delete backups whose
restoration was refused (conflict) or that are otherwise unresolved.

Current behavior: perform_uninstall's clean_backups pass deletes ".bak."
archives of every entry with restored=False, including backups that still
hold the user's pre-sadskill original after a refused restore.
"""

import json
import os
import unittest

from tests.helpers import SandboxCase

ORIGINAL = "ORIGINAL-USER-CONTENT-do-not-lose\n"
MARKER = "SADSKILL-USER-MARKER-restore-conflict"


class RestoreCleanupTests(SandboxCase):
    def _seed_and_install(self):
        """Pre-existing user install target, then install over it."""
        self.write_file(
            self.home, ".claude/skills/sadskill/SKILL.md", ORIGINAL
        )
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        installed = os.path.join(self.home, ".claude/skills/sadskill/SKILL.md")
        with open(installed, "a", encoding="utf-8") as fh:
            fh.write(MARKER + "\n")
        return installed

    def test_conflict_backup_survives_clean_backups(self):
        self._seed_and_install()

        first = self.run_uninstall("--restore-previous")
        self.assertNotEqual(first.returncode, 0,
                            "restore should refuse modified content without --force")
        backup_dirs = self.find_paths_under(
            self.home, ".bak.")
        self.assertTrue(backup_dirs, "backup must exist after refused restore")

        second = self.run_uninstall("--restore-previous", "--clean-backups")
        # Even if --force-less second run refuses again, the backup must stay.
        self.assertTrue(
            self.content_exists_under_home(ORIGINAL.strip()),
            "original user content was deleted by --clean-backups while its "
            "restoration remained unresolved (conflict-refused)",
        )
        self.assertTrue(
            self.find_paths_under(self.home, ".bak."),
            "unresolved .bak archive was deleted by --clean-backups",
        )

    def test_clean_backups_removes_only_resolved_backups(self):
        self._seed_and_install()
        # Related: a backup whose content matches the recorded content_hash is
        # a redundant copy of sadskill's own installed content and may be
        # cleaned. Simulate the entry state directly after a clean restore.
        manifest = self.load_manifest()
        entry = manifest["entries"][0]
        backup_dir = entry["backup"]
        self.assertTrue(os.path.isdir(backup_dir))

        rc = self.run_uninstall("--restore-previous", "--force", "--clean-backups")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertFalse(
            os.path.isdir(backup_dir),
            "resolved backup should be removed by --clean-backups",
        )
        # The original content must have been restored into place.
        restored = os.path.join(self.home, ".claude/skills/sadskill/SKILL.md")
        with open(restored, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), ORIGINAL)

    def test_unrelated_bak_files_never_deleted(self):
        self._seed_and_install()
        unrelated = self.write_file(
            self.home, ".claude/myproject.bak.19990101000000_1", "keep me"
        )
        self.run_uninstall("--restore-previous")
        self.run_uninstall("--clean-backups")
        self.assertTrue(
            os.path.exists(unrelated),
            "--clean-backups deleted a file it does not own",
        )


if __name__ == "__main__":
    unittest.main()
