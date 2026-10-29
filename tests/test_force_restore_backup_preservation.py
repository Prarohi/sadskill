"""User edits and restore archives must survive forced uninstall and purge."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ForceRestorePreservationTests(unittest.TestCase):
    def call(self, home, script, *args):
        env = dict(os.environ, HOME=str(home))
        return subprocess.run(["bash", str(ROOT / script), *args],
                              cwd=str(ROOT), env=env, capture_output=True,
                              text=True, timeout=60)

    def test_force_restore_archives_user_edits_and_refuses_destructive_purge(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            target = home / ".codex" / "prompts" / "sad-plan.md"
            target.parent.mkdir(parents=True)
            target.write_text("PRE-INSTALL USER CONTENT", encoding="utf-8")
            first = self.call(home, "install.sh", "codex")
            self.assertEqual(first.returncode, 0, first.stderr)
            target.write_text("USER MODIFICATION VERSION ONE", encoding="utf-8")
            reinstall = self.call(home, "install.sh", "codex")
            self.assertEqual(reinstall.returncode, 0, reinstall.stderr)
            target.write_text("USER MODIFICATION VERSION TWO", encoding="utf-8")
            uninstall = self.call(home, "uninstall.sh", "--restore-previous",
                                  "--clean-backups", "--force")
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), "PRE-INSTALL USER CONTENT")
            archives = [p.read_text(encoding="utf-8")
                        for p in target.parent.glob("sad-plan.md.bak*") if p.is_file()]
            self.assertIn("USER MODIFICATION VERSION ONE", archives)
            self.assertIn("USER MODIFICATION VERSION TWO", archives)
            ledger = home / ".sadskill" / "install-manifest.json"
            self.assertTrue(ledger.is_file())
            data = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertTrue(any(e.get("conflict_backups") for e in data["entries"]))
            purge = self.call(home, "uninstall.sh", "--purge")
            self.assertEqual(purge.returncode, 5, purge.stderr)
            self.assertTrue(ledger.exists())


if __name__ == "__main__":
    unittest.main()
