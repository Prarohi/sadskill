"""Offline vendor manifest integrity tests in disposable fixture roots."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "update-vendor.sh"


class VendorManifestIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "scripts").mkdir()
        self.script = self.repo / "scripts" / "update-vendor.sh"
        shutil.copy2(SOURCE, self.script)
        self.vendor = self.repo / "skills" / "sadskill" / "vendor"
        self.vendor.mkdir(parents=True)
        (self.vendor / "INDEX.md").write_text("index", encoding="utf-8")
        (self.vendor / "SOURCES.md").write_text("example", encoding="utf-8")
        self.ref = self.vendor / "example" / "reference.ref.md"
        self.ref.parent.mkdir()
        self.ref.write_text("# Curated reference\n", encoding="utf-8")
        self.relative = str(self.ref.relative_to(self.repo))
        self.sha = hashlib.sha256(self.ref.read_bytes()).hexdigest()
        self.manifest = self.vendor / "manifest.json"
        self.write_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self, path=None, digest=None, entries=None):
        data = {
            "schema_version": "1.0.0",
            "total_references": 1 if entries is None else len(entries),
            "references": entries if entries is not None else [
                {"path": self.relative if path is None else path,
                 "sha256": self.sha if digest is None else digest}
            ],
        }
        self.manifest.write_text(json.dumps(data), encoding="utf-8")

    def check(self):
        return subprocess.run(["bash", str(self.script), "--check"],
                              text=True, capture_output=True, timeout=15)

    def test_valid_manifest_hash_passes(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verified SHA-256", result.stdout)

    def test_tampered_contents_rejected(self):
        self.ref.write_text("tampered", encoding="utf-8")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mismatch", result.stderr)

    def test_corrupted_digest_rejected(self):
        self.write_manifest(digest="0" * 64)
        self.assertNotEqual(self.check().returncode, 0)

    def test_path_traversal_rejected(self):
        self.write_manifest(path="../outside.ref.md")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe", result.stderr)

    def test_duplicate_references_rejected(self):
        entry = {"path": self.relative, "sha256": self.sha}
        self.write_manifest(entries=[entry, entry])
        self.assertNotEqual(self.check().returncode, 0)

    def test_symlink_reference_rejected(self):
        self.ref.unlink()
        self.ref.symlink_to(self.repo / "outside.md")
        self.assertNotEqual(self.check().returncode, 0)

    def test_unlisted_symlink_anywhere_in_vendor_is_rejected(self):
        (self.vendor / "unexpected-link").symlink_to(self.repo / "outside")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr.lower())

    def test_name_after_five_frontmatter_lines_is_rejected(self):
        self.ref.write_text(
            "---\na: 1\nb: 2\nc: 3\nd: 4\ne: 5\nname: executable-skill\n---\nbody\n",
            encoding="utf-8",
        )
        self.sha = hashlib.sha256(self.ref.read_bytes()).hexdigest()
        self.write_manifest()
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("frontmatter", result.stdout.lower())

    def test_unlisted_reference_rejected(self):
        (self.ref.parent / "other.ref.md").write_text("extra", encoding="utf-8")
        self.assertNotEqual(self.check().returncode, 0)


if __name__ == "__main__":
    unittest.main()
