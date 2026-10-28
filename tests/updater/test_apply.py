"""Updater apply/rollback transaction tests."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import SandboxCase  # noqa: E402
from tests.updater.stub import GitHubStub, build_tarball  # noqa: E402

MARKER = "UPDATER_V031_MARKER"
UNRELATED = "UNRELATED_USER_FILE_KEEPS"


class ApplyRollbackTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.run_install("-a", "claude")
        self.stub = GitHubStub()
        self.tar, _ = build_tarball(top_dir="sadskill-0.3.1")
        self.stub.serve_release("v0.3.1", self.tar)
        self.base = self.stub.start()
        self.addCleanup(self.stub.stop)
        self.env["SADSKILL_UPDATE_API_BASE"] = self.base
        # Unrelated user file that must survive every transaction.
        self.write_file(self.home, "unrelated.txt", UNRELATED)

    def skill_md(self):
        return os.path.join(self.home, ".claude", "skills", "sadskill", "SKILL.md")

    def test_apply_transaction_full_lifecycle(self):
        p = self.run_update("apply", "--json")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        data = json.loads(p.stdout)
        self.assertTrue(data["applied"])
        self.assertEqual(data["to_version"], "0.3.1")
        # Content updated.
        with open(self.skill_md(), encoding="utf-8") as fh:
            self.assertIn(MARKER, fh.read())
        # Backup exists.
        self.assertTrue(data["backups_dir"])
        self.assertTrue(os.path.isdir(data["backups_dir"]))
        # Manifest content_hash refreshed to new content.
        manifest = self.load_manifest()
        entry = [e for e in manifest["entries"]
                 if e["agent"] == "claude"][0]
        import hashlib
        self.assertEqual(
            entry["content_hash"],
            hashlib.sha256(open(self.skill_md(), "rb").read()).hexdigest(),
        )
        # History + journal closed.
        with open(os.path.join(self.home, ".sadskill", "history.jsonl"),
                  encoding="utf-8") as fh:
            history = json.loads(fh.readline())
        with open(os.path.join(self.home, ".sadskill", "history.jsonl"),
                  encoding="utf-8") as fh:
            records = [json.loads(l) for l in fh if l.strip()]
        self.assertTrue(any(r["action"] == "update" for r in records))
        with open(os.path.join(self.home, ".sadskill", "update-journal.json"),
                  encoding="utf-8") as fh:
            journal = json.load(fh)
        self.assertEqual(journal["state"], "done")
        self.assertTrue(
            any(s["name"] == "backed_up" for s in journal["steps"]))
        # Unrelated user data untouched.
        self.assertTrue(
            self.content_exists_under_home(UNRELATED))

    def test_reapply_is_noop(self):
        self.run_update("apply", "--json")
        before = self.home_snapshot()
        p = self.run_update("apply", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertTrue(data.get("already_up_to_date"))
        self.assertEqual(self.home_snapshot(), before)

    def test_user_modified_conflict_refused_rc5_then_force(self):
        with open(self.skill_md(), "a", encoding="utf-8") as fh:
            fh.write("\nUSER_LOCAL_EDIT\n")
        before = self.home_snapshot()
        p = self.run_update("apply", "--json")
        self.assertEqual(p.returncode, 5, p.stdout)
        data = json.loads(p.stdout)
        self.assertTrue(data["refused"])
        self.assertTrue(data["conflicts"])
        # Nothing changed on disk.
        self.assertEqual(self.home_snapshot(), before)
        # --force applies after backing up the user modification.
        p = self.run_update("apply", "--json", "--force")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with open(self.skill_md(), encoding="utf-8") as fh:
            self.assertIn(MARKER, fh.read())
        with open(os.path.join(self.home, ".sadskill", "update-journal.json"),
                  encoding="utf-8") as fh:
            journal = json.load(fh)
        self.assertEqual(journal["state"], "done")
        # The user edit must exist in the backups dir.
        backup_text = ""
        for dirpath, _dirs, files in os.walk(journal["backups_dir"]):
            for name in files:
                with open(os.path.join(dirpath, name), encoding="utf-8",
                          errors="replace") as fh:
                    backup_text += fh.read()
        self.assertIn("USER_LOCAL_EDIT", backup_text)

    def test_rollback_restores_preapply_and_keeps_unrelated(self):
        self.run_update("apply", "--json")
        p = self.run_update("rollback", "--json")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with open(self.skill_md(), encoding="utf-8") as fh:
            content = fh.read()
        self.assertNotIn(MARKER, content)
        self.assertIn("sadskill", content)
        self.assertTrue(self.content_exists_under_home(UNRELATED))
        with open(os.path.join(self.home, ".sadskill", "update-journal.json"),
                  encoding="utf-8") as fh:
            journal = json.load(fh)
        self.assertEqual(journal["state"], "rolled_back")

    def test_rollback_conflict_on_postapply_user_edit(self):
        self.run_update("apply", "--json")
        with open(self.skill_md(), "a", encoding="utf-8") as fh:
            fh.write("\nPOST_APPLY_EDIT\n")
        before = self.home_snapshot()
        p = self.run_update("rollback", "--json")
        self.assertEqual(p.returncode, 5, p.stdout)
        self.assertEqual(self.home_snapshot(), before)
        p = self.run_update("rollback", "--json", "--force")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with open(self.skill_md(), encoding="utf-8") as fh:
            self.assertNotIn(MARKER, fh.read())

    def test_interrupted_apply_is_recoverable_via_rollback(self):
        self.env["SADSKILL_FAULT"] = "after_backup"
        p = self.run_update("apply", "--json")
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.env.pop("SADSKILL_FAULT", None)
        # Destination NOT updated.
        with open(self.skill_md(), encoding="utf-8") as fh:
            self.assertNotIn(MARKER, fh.read())
        # Backups + journal exist and are pending.
        with open(os.path.join(self.home, ".sadskill", "update-journal.json"),
                  encoding="utf-8") as fh:
            journal = json.load(fh)
        self.assertEqual(journal["state"], "interrupted")
        self.assertTrue(os.path.isdir(journal["backups_dir"]))
        # Rollback closes the journal and leaves installation unchanged.
        p = self.run_update("rollback", "--json")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with open(self.skill_md(), encoding="utf-8") as fh:
            self.assertNotIn(MARKER, fh.read())
        with open(os.path.join(self.home, ".sadskill", "update-journal.json"),
                  encoding="utf-8") as fh:
            journal = json.load(fh)
        self.assertEqual(journal["state"], "rolled_back")

    def test_history_command_reflects_transitions(self):
        self.run_update("apply", "--json")
        self.run_update("rollback", "--json")
        p = self.run_update("history", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        actions = [r["action"] for r in data["records"]]
        self.assertIn("update", actions)
        self.assertIn("rollback", actions)


if __name__ == "__main__":
    unittest.main()
