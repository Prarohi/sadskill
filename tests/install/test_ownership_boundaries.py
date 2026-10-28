"""Untrusted or stale bookkeeping must not authorize user-data deletion."""

import hashlib
import json
import os
import fcntl
import subprocess
import time
from pathlib import Path

from tests.helpers import SandboxCase


class OwnershipBoundaryTests(SandboxCase):
    def test_incomplete_hash_metadata_fails_before_removing_anything(self):
        self.assertEqual(self.run_install("claude").returncode, 0)
        original = self.load_manifest()
        installed = Path(self.home) / ".claude/skills/sadskill/SKILL.md"
        before = installed.read_bytes()
        for bad_hash in (None, "", "not-a-sha256"):
            with self.subTest(hash=bad_hash):
                data = json.loads(json.dumps(original))
                if bad_hash is None:
                    data["entries"][0].pop("content_hash")
                else:
                    data["entries"][0]["content_hash"] = bad_hash
                manifest = Path(self.manifest_path())
                manifest.write_text(json.dumps(data))
                snapshot = manifest.read_bytes()
                result = self.run_uninstall("--force")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(manifest.read_bytes(), snapshot)
                self.assertEqual(installed.read_bytes(), before)

    def test_cleanup_preserves_changed_backup_and_its_ledger_entry(self):
        dest = self.write_file(self.home, ".claude/commands/sad-plan.md", "installed")
        backup = self.write_file(self.home, ".claude/commands/sad-plan.md.bak.test", "installed")
        recorded = self.run_manifest("record", "--manifest", self.manifest_path(),
                                     "--agent", "claude_command", "--destination", dest,
                                     "--backup", backup)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        Path(backup).write_text("USER_EDITED_BACKUP")
        result = self.run_uninstall("--clean-backups")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(backup).read_text(), "USER_EDITED_BACKUP")
        self.assertTrue(any(e.get("backup") == backup for e in self.load_manifest()["entries"]))

    def test_orphan_adoption_never_grants_destination_ownership(self):
        for name in ("my-private-tool.md", "sad-plan.md"):
            with self.subTest(name=name):
                dest = self.write_file(self.home, ".claude/commands/" + name, "USER_FILE")
                backup = self.write_file(self.home, ".claude/commands/" + name + ".bak.keep", "USER_BACKUP")
                adopted = self.run_manifest("adopt-orphans", "--manifest", self.manifest_path())
                self.assertEqual(adopted.returncode, 0, adopted.stderr)
                data = self.load_manifest() if Path(self.manifest_path()).exists() else {"entries": []}
                self.assertFalse(any(e["destination"] == dest for e in data["entries"]))
                removed = self.run_uninstall("--force", "--clean-backups")
                self.assertEqual(removed.returncode, 0, removed.stderr)
                self.assertEqual(Path(dest).read_text(), "USER_FILE")
                self.assertEqual(Path(backup).read_text(), "USER_BACKUP")

    def test_manifest_cannot_claim_a_non_sadskill_config_even_with_valid_hash(self):
        config = self.write_file(self.home, ".claude/settings.json", "USER_CONFIG")
        manifest = {"version": "0.3.0", "entries": [{
            "agent": "claude", "destination": config,
            "content_hash": hashlib.sha256(b"USER_CONFIG").hexdigest(),
            "backup": "", "backup_hash": ""}]}
        self.write_file(self.home, ".sadskill/install-manifest.json", json.dumps(manifest))
        result = self.run_uninstall("--force")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(Path(config).read_text(), "USER_CONFIG")

    def test_restore_cannot_move_unrelated_config_as_a_backup(self):
        self.assertEqual(self.run_install("claude").returncode, 0)
        config = Path(self.write_file(self.home, ".claude/settings.json", "USER_CONFIG"))
        data = self.load_manifest()
        entry = next(e for e in data["entries"] if e["agent"] == "claude_hook")
        entry["backup"] = str(config)
        entry["backup_hash"] = hashlib.sha256(config.read_bytes()).hexdigest()
        manifest = Path(self.manifest_path())
        manifest.write_text(json.dumps(data))
        before = manifest.read_bytes()
        destination = Path(entry["destination"])
        installed = destination.read_bytes()
        result = self.run_uninstall("--restore-previous", "--force")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(config.read_text(), "USER_CONFIG")
        self.assertEqual(destination.read_bytes(), installed)
        self.assertEqual(manifest.read_bytes(), before)

    def test_installer_corrupt_manifest_preflight_preserves_existing_files(self):
        installed = self.write_file(self.home, ".claude/skills/sadskill/SKILL.md", "USER_INSTALL")
        manifest = self.write_file(self.home, ".sadskill/install-manifest.json", "{INVALID_JSON")
        for args in (("claude",), ("claude", "--no-backup")):
            with self.subTest(args=args):
                result = self.run_install(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(Path(installed).read_text(), "USER_INSTALL")
                self.assertEqual(Path(manifest).read_text(), "{INVALID_JSON")
                self.assertFalse(self.find_paths_under(self.home, ".bak."))

    def test_tree_path_content_collision_does_not_hide_modification(self):
        original = self.write_file(self.home, ".claude/skills/sadskill/a", "bc")
        dest = str(Path(original).parent)
        recorded = self.run_manifest("record", "--manifest", self.manifest_path(),
                                     "--agent", "claude", "--destination", dest)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        Path(original).unlink()
        changed = Path(dest) / "ab"
        changed.write_text("c")
        result = self.run_uninstall()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(changed.exists(), "modified tree was mistaken for installed content")
        self.assertEqual(changed.read_text(), "c")

    def test_legacy_directory_hash_never_authorizes_automatic_removal(self):
        original = self.write_file(self.home, ".claude/skills/sadskill/a", "bc")
        destination = str(Path(original).parent)
        manifest = {"version": "0.3.0", "entries": [{
            "agent": "claude", "destination": destination,
            "content_hash": hashlib.sha256(b"abc").hexdigest(),
            "content_hash_type": "tree", "backup": "", "backup_hash": ""}]}
        self.write_file(self.home, ".sadskill/install-manifest.json", json.dumps(manifest))
        result = self.run_uninstall()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(original).read_text(), "bc")

    def test_full_installer_waits_for_manifest_lock_before_file_replacement(self):
        original = self.write_file(self.home, ".claude/skills/sadskill/SKILL.md", "USER_INSTALL")
        lock_path = Path(self.home) / ".sadskill/.install-manifest.json.lock"
        lock_path.parent.mkdir()
        with lock_path.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen(
                ["bash", str(Path(__file__).resolve().parents[2] / "install.sh"), "claude"],
                cwd=self.project, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertIn("Installing", process.stdout.readline())
                time.sleep(0.2)
                self.assertIsNone(process.poll())
                self.assertEqual(Path(original).read_text(), "USER_INSTALL")
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stdout + stderr)
