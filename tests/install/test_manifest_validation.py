"""Defect class 5: invalid, corrupted, tampered, symlinked, or partial
manifests must fail closed — nonzero exit, no repair, no silent reset,
manifest bytes untouched.
"""

import json
import os
import unittest

from tests.helpers import SandboxCase


def entry(**overrides):
    base = {
        "agent": "claude",
        "destination": "/tmp/unused-destination",
        "backup": "",
        "content_hash": "a" * 64,
        "backup_hash": "",
        "installed_at": "2026-01-01T00:00:00Z",
        "restored": False,
    }
    base.update(overrides)
    return base


class ManifestValidationTests(SandboxCase):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.home, ".sadskill"), exist_ok=True)

    def _write_manifest(self, raw):
        path = self.manifest_path()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        return path

    def _assert_fails_closed(self, result, path, original_bytes):
        self.assertNotEqual(
            result.returncode, 0,
            f"operation on corrupt manifest must fail closed\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        with open(path, "rb") as fh:
            self.assertEqual(
                fh.read(), original_bytes,
                "manifest bytes were modified by a failed operation",
            )

    def _uninstall(self):
        return self.run_manifest(
            "uninstall", "--manifest", self.manifest_path(),
            "--target", self.project,
        )

    def test_invalid_json_fails_closed(self):
        path = self._write_manifest("{not json at all")
        original = self.read_bytes(path)
        self._assert_fails_closed(self._uninstall(), path, original)

    def test_top_level_array_fails_closed(self):
        path = self._write_manifest(json.dumps([entry()]))
        original = self.read_bytes(path)
        self._assert_fails_closed(self._uninstall(), path, original)

    def test_entries_not_a_list_fails_closed(self):
        path = self._write_manifest(json.dumps({"version": "0.3.0", "entries": {}}))
        original = self.read_bytes(path)
        self._assert_fails_closed(self._uninstall(), path, original)

    def test_entry_missing_destination_fails_closed(self):
        bad = entry()
        del bad["destination"]
        path = self._write_manifest(
            json.dumps({"version": "0.3.0", "entries": [bad]})
        )
        original = self.read_bytes(path)
        self._assert_fails_closed(self._uninstall(), path, original)

    def test_relative_destination_fails_closed(self):
        path = self._write_manifest(
            json.dumps({"version": "0.3.0",
                        "entries": [entry(destination="relative/path")]})
        )
        original = self.read_bytes(path)
        self._assert_fails_closed(self._uninstall(), path, original)

    def test_unknown_newer_version_fails_closed(self):
        path = self._write_manifest(
            json.dumps({"version": "9.9.9", "entries": [entry()]})
        )
        original = self.read_bytes(path)
        self._assert_fails_closed(self._uninstall(), path, original)

    def test_duplicate_destinations_fail_closed(self):
        path = self._write_manifest(
            json.dumps({"version": "0.3.0",
                        "entries": [entry(), entry()]})
        )
        original = self.read_bytes(path)
        self._assert_fails_closed(self._uninstall(), path, original)

    def test_symlinked_manifest_fails_closed(self):
        real = os.path.join(self.base, "real-manifest.json")
        with open(real, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"version": "0.3.0", "entries": [entry()]}))
        original = self.read_bytes(real)
        path = self.manifest_path()
        os.symlink(real, path)
        self._assert_fails_closed(self._uninstall(), real, original)

    def test_record_on_corrupt_manifest_fails_closed(self):
        path = self._write_manifest("[")
        original = self.read_bytes(path)
        result = self.run_manifest(
            "record", "--manifest", path,
            "--agent", "claude",
            "--destination", os.path.join(self.home, ".claude/skills/sadskill"),
            "--backup", "",
            "--target", self.project,
        )
        self._assert_fails_closed(result, path, original)


if __name__ == "__main__":
    unittest.main()
