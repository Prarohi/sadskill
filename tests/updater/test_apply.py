"""Updater apply/rollback transaction tests."""

import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from scripts import sadskill_core as core  # noqa: E402
from helpers import SandboxCase  # noqa: E402
from tests.updater.stub import GitHubStub, build_tarball  # noqa: E402

_updater_spec = importlib.util.spec_from_file_location(
    "sadskill_update_test_module",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "scripts", "sadskill-update.py"),
)
UPDATER = importlib.util.module_from_spec(_updater_spec)
_updater_spec.loader.exec_module(UPDATER)

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
        self.assertEqual(data.get("artifact_trust"), "TRANSPORT_ONLY")
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
        self.assertEqual(
            entry["content_hash"],
            core.compute_sha256(entry["destination"]),
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
        backups_dir = Path(journal["backups_dir"])
        self.assertEqual(stat.S_IMODE(backups_dir.stat().st_mode), 0o700)
        self.assertEqual(
            stat.S_IMODE((Path(self.home) / ".sadskill" / "backups").stat().st_mode),
            0o700,
        )
        destinations_dir = backups_dir / "destinations"
        self.assertEqual(stat.S_IMODE(destinations_dir.stat().st_mode), 0o700)
        for record in (list(journal["backup_map"].values())
                       + list(journal["metadata_backup_map"].values())):
            if not record["existed"]:
                continue
            self.assertEqual(
                stat.S_IMODE(Path(record["backup_path"]).stat().st_mode),
                0o600,
            )
        # Unrelated user data untouched.
        self.assertTrue(
            self.content_exists_under_home(UNRELATED))

    def test_apply_rejects_target_root_outside_canonical_home_agent(self):
        manifest_path = Path(self.manifest_path())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(item for item in manifest["entries"]
                     if item.get("agent") == "claude")
        external_workspace = Path(self.home).parent / "external-workspace"
        external_root = external_workspace / ".claude" / "skills" / "sadskill"
        external_root.mkdir(parents=True)
        marker = external_root / "SKILL.md"
        marker.write_text(
            "---\nversion: 0.3.0\n---\npreserve external path\n",
            encoding="utf-8",
        )
        shutil.rmtree(Path(self.home) / ".claude" / "skills" / "sadskill")
        entry["destination"] = str(external_root)
        entry["target_root"] = str(external_workspace)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                                 encoding="utf-8")

        applied = self.run_update("apply", "--json", "--force")
        self.assertEqual(applied.returncode, 4, applied.stdout + applied.stderr)
        self.assertIn("canonical HOME root", applied.stdout)
        self.assertEqual(marker.read_text(encoding="utf-8"),
                         "---\nversion: 0.3.0\n---\npreserve external path\n")
        self.assertFalse(Path(self.skill_md()).exists())
        self.assertFalse(
            (Path(self.home) / ".sadskill" / "update-journal.json").exists()
        )

    def test_apply_rejects_unsupported_special_permission_bits(self):
        target = Path(self.skill_md())
        original = target.read_bytes()
        os.chmod(target, 0o4755)

        applied = self.run_update("apply", "--json", "--force")
        self.assertEqual(applied.returncode, 4, applied.stdout + applied.stderr)
        self.assertIn("unsupported special permission bits", applied.stdout)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o4755)
        self.assertFalse(
            (Path(self.home) / ".sadskill" / "update-journal.json").exists()
        )

    def test_legacy_home_manifest_gets_canonical_target_roots(self):
        manifest_path = Path(self.manifest_path())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["entries"]:
            entry.pop("target_root", None)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                                 encoding="utf-8")

        applied = self.run_update("apply", "--json")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        upgraded = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(upgraded["entries"])
        self.assertTrue(all(
            entry.get("target_root") == str(Path(self.home) / ".claude")
            for entry in upgraded["entries"]
        ), upgraded["entries"])

    def test_cursor_workspace_root_remains_supported(self):
        installed = self.run_install(
            "--agent", "cursor", "--target", self.project
        )
        self.assertEqual(installed.returncode, 0,
                         installed.stdout + installed.stderr)

        applied = self.run_update("apply", "--json")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        cursor_skill = (
            Path(self.project) / ".cursor" / "skills" / "sadskill" / "SKILL.md"
        )
        self.assertIn(MARKER, cursor_skill.read_text(encoding="utf-8"))

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

    def test_force_refuses_directory_file_target_before_journaling(self):
        skill_path = Path(self.skill_md())
        hook_path = skill_path.parent / "hooks" / "git-guardrail.sh"
        original_skill = skill_path.read_bytes()
        hook_path.unlink()
        hook_path.mkdir()
        sentinel = hook_path / "owned-content.txt"
        sentinel.write_text("preserve this directory\n", encoding="utf-8")
        before = self.home_snapshot()

        planned = self.run_update("plan", "--json")
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        plan_data = json.loads(planned.stdout)
        self.assertTrue(any(
            item["destination"] == str(hook_path)
            and item["reason"] == "target is not a regular file"
            for item in plan_data["conflicts"]
        ))

        applied = self.run_update("apply", "--json", "--force")
        self.assertEqual(applied.returncode, 4, applied.stdout + applied.stderr)
        self.assertIn("target is not a regular file", applied.stdout)
        self.assertEqual(self.home_snapshot(), before)
        self.assertEqual(skill_path.read_bytes(), original_skill)
        self.assertEqual(sentinel.read_text(encoding="utf-8"),
                         "preserve this directory\n")
        self.assertFalse(Path(self.home, ".sadskill", "update-journal.json").exists())

    def test_rollback_rejects_journal_target_outside_owned_install(self):
        applied = self.run_update("apply", "--json")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        journal_path = Path(self.home) / ".sadskill" / "update-journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        victim = Path(self.home) / "unrelated.txt"
        backups_dir = Path(journal["backups_dir"])
        forged_backup = backups_dir / "destinations" / "forged-rollback.backup"
        forged_backup.write_bytes(b"forged journal data must not be restored\n")
        entry_destination = str(Path(self.home) / ".claude" / "skills" / "sadskill")
        journal["backup_map"][str(victim)] = {
            "existed": True,
            "backup_path": str(forged_backup),
            "sha256": core.compute_sha256(forged_backup),
            "kind": "file",
            "mode": 0o600,
        }
        journal["steps"].append({
            "name": "mutation_intent",
            "payload": {
                "category": "destination",
                "destination": str(victim),
                "entry_destination": entry_destination,
                "agent": "claude",
                "old_sha256": core.compute_sha256(forged_backup),
                "new_sha256": core.compute_sha256(victim),
            },
        })
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        before = self.home_snapshot()
        victim_before = victim.read_bytes()
        skill_before = Path(self.skill_md()).read_bytes()

        rollback = self.run_update("rollback", "--json")
        self.assertEqual(rollback.returncode, 4, rollback.stdout + rollback.stderr)
        self.assertIn("outside its owned root", rollback.stdout)
        self.assertEqual(self.home_snapshot(), before)
        self.assertEqual(victim.read_bytes(), victim_before)
        self.assertEqual(Path(self.skill_md()).read_bytes(), skill_before)

    def test_malformed_claude_hook_entry_cannot_target_settings(self):
        settings = Path(self.home) / ".claude" / "settings.json"
        settings.write_text('{"permissions":{"deny":[]}}\n', encoding="utf-8")
        manifest_path = Path(self.manifest_path())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hook = next(entry for entry in manifest["entries"]
                    if entry.get("agent") == "claude_hook")
        hook["destination"] = str(settings)
        hook["target_root"] = str(settings.parent)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                                 encoding="utf-8")
        before = self.home_snapshot()
        settings_before = settings.read_bytes()

        applied = self.run_update("apply", "--json", "--force")
        self.assertEqual(applied.returncode, 4, applied.stdout + applied.stderr)
        self.assertIn("canonical guardrail path", applied.stdout)
        self.assertEqual(self.home_snapshot(), before)
        self.assertEqual(settings.read_bytes(), settings_before)

    def test_rollback_restores_preapply_and_keeps_unrelated(self):
        manifest_before = Path(self.manifest_path()).read_bytes()
        state_path = Path(self.home) / ".sadskill" / "install-state.json"
        state_before = state_path.read_bytes() if state_path.exists() else None
        original_mode = stat.S_IMODE(Path(self.skill_md()).stat().st_mode)
        self.run_update("apply", "--json")
        p = self.run_update("rollback", "--json")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with open(self.skill_md(), encoding="utf-8") as fh:
            content = fh.read()
        self.assertNotIn(MARKER, content)
        self.assertIn("sadskill", content)
        self.assertEqual(stat.S_IMODE(Path(self.skill_md()).stat().st_mode),
                         original_mode)
        self.assertEqual(Path(self.manifest_path()).read_bytes(), manifest_before)
        self.assertEqual(
            state_path.read_bytes() if state_path.exists() else None,
            state_before,
            "rollback did not restore exact install-state metadata",
        )
        self.assertTrue(self.content_exists_under_home(UNRELATED))
        with open(os.path.join(self.home, ".sadskill", "update-journal.json"),
                  encoding="utf-8") as fh:
            journal = json.load(fh)
        self.assertEqual(journal["state"], "rolled_back")

        # Repeating recovery is a harmless no-op.
        snapshot = self.home_snapshot()
        again = self.run_update("rollback", "--json")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.home_snapshot(), snapshot)

    def test_corrupt_backup_refuses_force_rollback_without_changes(self):
        applied = self.run_update("apply", "--json")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        journal_path = Path(self.home) / ".sadskill" / "update-journal.json"
        journal = json.loads(journal_path.read_text())
        target = self.skill_md()
        backup = Path(journal["backup_map"][target]["backup_path"])
        backup.write_bytes(backup.read_bytes() + b"CORRUPTED_BACKUP")
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("\nKEEP_CURRENT_ON_BACKUP_FAILURE\n")
        target_before = Path(target).read_bytes()
        manifest_before = Path(self.manifest_path()).read_bytes()
        state_path = Path(self.home) / ".sadskill" / "install-state.json"
        state_before = state_path.read_bytes()
        journal_before = journal_path.read_bytes()

        result = self.run_update("rollback", "--json", "--force")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertEqual(Path(target).read_bytes(), target_before)
        self.assertEqual(Path(self.manifest_path()).read_bytes(), manifest_before)
        self.assertEqual(state_path.read_bytes(), state_before)
        self.assertEqual(journal_path.read_bytes(), journal_before)

    def test_interrupted_after_first_replace_is_recovered(self):
        original = Path(self.skill_md()).read_bytes()
        self.env["SADSKILL_FAULT"] = "after_first_replace"
        interrupted = self.run_update("apply", "--json")
        self.assertNotEqual(interrupted.returncode, 0, interrupted.stdout)
        self.env.pop("SADSKILL_FAULT", None)
        self.assertIn(MARKER.encode(), Path(self.skill_md()).read_bytes())

        restored = self.run_update("rollback", "--json")
        self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
        self.assertEqual(Path(self.skill_md()).read_bytes(), original)

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

    def test_forced_rollback_preserves_postapply_user_edit(self):
        applied = self.run_update("apply", "--json")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        sentinel = "POST_APPLY_FORCE_ROLLBACK_SENTINEL"
        with open(self.skill_md(), "a", encoding="utf-8") as fh:
            fh.write("\n" + sentinel + "\n")

        result = self.run_update("rollback", "--json", "--force")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        journal_path = os.path.join(self.home, ".sadskill", "update-journal.json")
        with open(journal_path, encoding="utf-8") as fh:
            journal = json.load(fh)
        found = False
        for dirpath, _dirs, files in os.walk(journal["backups_dir"]):
            for name in files:
                with open(os.path.join(dirpath, name), "rb") as fh:
                    found |= sentinel.encode() in fh.read()
        self.assertTrue(found, "forced rollback discarded the post-apply edit")

    def test_rollback_restores_exact_paths_with_duplicate_skill_basenames(self):
        installed = self.run_install("-a", "all")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        manifest = self.load_manifest()
        entries = [e for e in manifest["entries"]
                   if e.get("agent") in ("claude", "codex", "gemini")]
        self.assertGreaterEqual(len(entries), 3)

        def snapshot(root):
            result = {}
            for current, _dirs, files in os.walk(root):
                for filename in files:
                    path = Path(current) / filename
                    result[str(path.relative_to(root))] = path.read_bytes()
            return result

        before = {}
        for entry in entries:
            root = Path(entry["destination"])
            agent = entry["agent"]
            skill = root / "SKILL.md"
            with skill.open("a", encoding="utf-8") as fh:
                fh.write(f"\nORIGINAL_HOST_{agent}\n")
            entry["content_hash"] = core.compute_sha256(root)
            before[agent] = snapshot(root)
        with open(self.manifest_path(), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
            fh.write("\n")

        applied = self.run_update("apply", "--json")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        rolled = self.run_update("rollback", "--json")
        self.assertEqual(rolled.returncode, 0, rolled.stdout + rolled.stderr)
        for entry in entries:
            agent = entry["agent"]
            root = Path(entry["destination"])
            self.assertEqual(snapshot(root), before[agent], agent)
            self.assertIn(
                f"ORIGINAL_HOST_{agent}", (root / "SKILL.md").read_text()
            )

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


class UpdaterBackupPrimitiveTests(unittest.TestCase):
    def test_snapshot_guard_rejects_content_mode_and_create_races(self):
        with tempfile.TemporaryDirectory(prefix="sadskill-updater-primitive-") as tmp:
            root = Path(tmp)
            target = root / "managed.txt"
            target.write_bytes(b"original\n")
            backup_dir = root / ".sadskill" / "backups" / "update-test"
            snapshot = UPDATER._backup_dest(target, backup_dir, "content")

            target.write_bytes(b"concurrent user edit\n")
            with self.assertRaisesRegex(
                    UPDATER.core.IntegrityError,
                    "changed after its backup snapshot"):
                UPDATER._assert_matches_backup_snapshot(target, snapshot)
            self.assertEqual(target.read_bytes(), b"concurrent user edit\n")
            staged = root / "staged.txt"
            staged.write_bytes(b"release update\n")
            with self.assertRaisesRegex(
                    UPDATER.core.IntegrityError,
                    "changed after its backup snapshot"):
                UPDATER._atomic_install_file(
                    staged, target, expected_snapshot=snapshot
                )
            self.assertEqual(target.read_bytes(), b"concurrent user edit\n")

            metadata = root / "manifest.json"
            metadata.write_bytes(b'{"version":"before"}\n')
            metadata_snapshot = UPDATER._backup_dest(
                metadata, backup_dir, "metadata"
            )
            metadata.write_bytes(b'{"version":"concurrent"}\n')
            with self.assertRaisesRegex(
                    UPDATER.core.IntegrityError,
                    "changed after its backup snapshot"):
                UPDATER._atomic_install_text(
                    metadata, '{"version":"update"}\n',
                    expected_snapshot=metadata_snapshot,
                )
            self.assertEqual(metadata.read_bytes(), b'{"version":"concurrent"}\n')

            target.write_bytes(b"original\n")
            os.chmod(target, 0o600)
            with self.assertRaisesRegex(
                    UPDATER.core.IntegrityError,
                    "changed after its backup snapshot"):
                UPDATER._assert_matches_backup_snapshot(target, snapshot)
            self.assertEqual(target.read_bytes(), b"original\n")

            absent = root / "new-file.txt"
            absent_snapshot = UPDATER._backup_dest(
                absent, backup_dir, "absent"
            )
            absent.write_bytes(b"created concurrently\n")
            with self.assertRaisesRegex(
                    UPDATER.core.IntegrityError,
                    "changed after its backup snapshot"):
                UPDATER._assert_matches_backup_snapshot(absent, absent_snapshot)
            self.assertEqual(absent.read_bytes(), b"created concurrently\n")

    def test_private_directory_creation_syncs_each_parent_entry(self):
        with tempfile.TemporaryDirectory(prefix="sadskill-fsync-primitive-") as tmp:
            root = Path(tmp)
            target = root / "backups" / "update" / "destinations"
            synced = []
            with mock.patch.object(
                    UPDATER, "_sync_directory",
                    side_effect=lambda path: synced.append(Path(path))):
                UPDATER._ensure_private_directory(
                    target, parents=True, exist_ok=False
                )
            self.assertTrue({
                root, root / "backups", root / "backups" / "update", target,
            }.issubset(set(synced)))


if __name__ == "__main__":
    unittest.main()
