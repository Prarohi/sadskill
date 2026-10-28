"""Defect class 8: interruption between backup creation and manifest write
leaves orphan .bak archives. Recovery must (a) never delete orphan backups
during later operations, and (b) offer an explicit adopt-orphans command.
"""

import json
import os
import unittest

from tests.helpers import SandboxCase

ORPHAN_MARKER = "ORPHANED-USER-CONTENT-interrupted-install"


class InterruptedTests(SandboxCase):
    def _make_orphan(self):
        """Simulate a crash after `mv dest .bak.ts` but before manifest
        record: install a skill, hand-create a .bak archive, wipe the
        manifest so the backup is orphaned."""
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        orphan = os.path.join(
            self.home, ".claude/skills/.bak.20260101000000_1234"
        )
        os.makedirs(orphan)
        with open(os.path.join(orphan, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write(ORPHAN_MARKER + "\n")
        os.remove(self.manifest_path())
        return orphan

    def test_operations_never_delete_orphan_backups(self):
        orphan = self._make_orphan()
        rc = self.run_install("--agent", "claude")
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue(
            os.path.isdir(orphan),
            "install deleted an orphaned .bak backup it does not own",
        )
        rc = self.run_uninstall()
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertTrue(
            os.path.isdir(orphan),
            "uninstall deleted an orphaned .bak backup it does not own",
        )

    def test_adopt_orphans_registers_and_preserves(self):
        orphan = self._make_orphan()
        result = self.run_manifest(
            "adopt-orphans", "--manifest", self.manifest_path(),
            "--target", self.project,
        )
        self.assertEqual(
            result.returncode, 0,
            f"adopt-orphans subcommand missing or failed: {result.stderr}",
        )
        self.assertTrue(
            os.path.isdir(orphan),
            "adopt-orphans must not delete the backup it adopts",
        )
        manifest = self.load_manifest()
        backups = json.dumps(manifest)
        self.assertIn(os.path.basename(orphan), backups,
                      "adopted orphan not referenced by manifest")

    def test_adopt_orphans_idempotent(self):
        self._make_orphan()
        first = self.run_manifest(
            "adopt-orphans", "--manifest", self.manifest_path(),
            "--target", self.project,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_manifest(
            "adopt-orphans", "--manifest", self.manifest_path(),
            "--target", self.project,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        manifest = self.load_manifest()
        self.assertEqual(
            len(manifest["entries"]),
            len({e["destination"] for e in manifest["entries"]}),
            "adopt-orphans created duplicate entries on second run",
        )


if __name__ == "__main__":
    unittest.main()
