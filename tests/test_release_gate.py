"""Release metadata, evidence, and draft-only workflow regression tests."""
import json
import hashlib
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile
import unittest
from unittest import mock

from scripts import release_gate as gate


def seed(root, status="Unreleased"):
    (root / "scripts").mkdir(exist_ok=True)
    (root / "skills/sadskill").mkdir(parents=True, exist_ok=True)
    (root / "VERSION").write_text("0.5.0\n")
    (root / "plugin.json").write_text('{"version":"0.5.0"}')
    (root / "README.md").write_text("> Version: `v0.5.0` (release candidate)\n")
    (root / "skills/sadskill/SKILL.md").write_text(
        "---\nname: sadskill\nmetadata:\n  version: 0.5.0\n---\n"
    )
    (root / "scripts/sad_cli.py").write_text('version="sadskill 0.5.0"\n')
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.5.0] - " + status +
        "\n\n### Fixed\n- A new fix.\n\n"
        "## [0.4.0] - 2026-10-29\n\n### Fixed\n- An old fix.\n"
    )


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        seed(self.root)
        patch = mock.patch.object(gate, "ROOT", self.root)
        patch.start()
        self.addCleanup(patch.stop)

    def test_metadata_consistency(self):
        self.assertEqual(gate.check(), "0.5.0")

    def test_wrong_plugin_version_rejected(self):
        (self.root / "plugin.json").write_text('{"version":"0.4.0"}')
        with self.assertRaisesRegex(gate.ReleaseError, "plugin.json"):
            gate.check()

    def test_wrong_cli_version_rejected(self):
        (self.root / "scripts/sad_cli.py").write_text('version="sadskill 0.4.0"')
        with self.assertRaisesRegex(gate.ReleaseError, "CLI"):
            gate.check()

    def test_wrong_changelog_version_rejected(self):
        (self.root / "CHANGELOG.md").write_text("## [0.4.0] - 2026-10-29\n### Fixed\n- Old\n")
        with self.assertRaisesRegex(gate.ReleaseError, "CHANGELOG first"):
            gate.check()

    def test_invalid_version_rejected(self):
        for invalid in ("v0.5.0", "0.05.0", "0.5.0-", "0.5"):
            (self.root / "VERSION").write_text(invalid + "\n")
            with self.subTest(invalid=invalid), self.assertRaisesRegex(gate.ReleaseError, "SemVer"):
                gate.check()

    def test_tag_mismatch_fails_without_git(self):
        with mock.patch.object(gate, "git") as git:
            with self.assertRaisesRegex(gate.ReleaseError, "tag must"):
                gate.check("v0.4.0")
            git.assert_not_called()

    def test_unreleased_tag_is_refused(self):
        with self.assertRaisesRegex(gate.ReleaseError, "release date"):
            gate.check("v0.5.0")

    def test_release_candidate_banner_is_refused(self):
        seed(self.root, status="2026-10-30")
        with self.assertRaisesRegex(gate.ReleaseError, "release candidate"):
            gate.check("v0.5.0")

    def test_notes_include_only_current_release(self):
        seed(self.root, status="2026-10-30")
        (self.root / "README.md").write_text("> Version: `v0.5.0` · MIT\n")
        with mock.patch.object(gate, "git", side_effect=["a" * 40, "a" * 40]):
            notes = gate.notes("v0.5.0")
        self.assertIn("A new fix.", notes)
        self.assertNotIn("An old fix.", notes)

    def test_ci_checks_reject_missing_failed_or_wrong_head(self):
        sha = "a" * 40
        good = [
            {"id": i, "head_sha": sha, "name": name,
             "status": "completed", "conclusion": "success"}
            for i, name in enumerate(gate.REQUIRED_CHECKS, 1)
        ]
        gate.verify_checks({"check_runs": good}, sha)
        for bad in [
            good[:-1],
            good + [{"id": 999, "head_sha": sha, "name": good[0]["name"],
                     "status": "completed", "conclusion": "failure"}],
            [{**entry, "head_sha": "b" * 40} for entry in good],
        ]:
            with self.assertRaisesRegex(gate.ReleaseError, "required check"):
                gate.verify_checks({"check_runs": bad}, sha)

    def test_reproducible_real_git_archives_and_checksums(self):
        seed(self.root, status="2026-10-30")
        (self.root / "README.md").write_text("> Version: `v0.5.0` · MIT\\n".replace("\\\\n", "\\n"))
        commands = [
            ["git", "init", "-q"],
            ["git", "config", "user.name", "Release Gate Test"],
            ["git", "config", "user.email", "release-test@example.invalid"],
            ["git", "add", "-A"],
            ["git", "commit", "-qm", "Seed fake release"],
            ["git", "tag", "v0.5.0"],
        ]
        for command in commands:
            subprocess.run(command, cwd=self.root, capture_output=True, check=True)
        first, second = self.root / "first", self.root / "second"
        gate.package("v0.5.0", first)
        gate.package("v0.5.0", second)
        files = sorted(p.name for p in first.iterdir())
        self.assertEqual(files, sorted(p.name for p in second.iterdir()))
        for name in files:
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        sums = (first / "SHA256SUMS.txt").read_text().splitlines()
        self.assertEqual(len(sums), 4)
        for line in sums:
            digest, name = line.split("  ", 1)
            self.assertEqual(digest, hashlib.sha256((first / name).read_bytes()).hexdigest())
        with tarfile.open(first / "sadskill-0.5.0.tar.gz", "r:gz") as archive:
            self.assertIn("sadskill-0.5.0/VERSION", archive.getnames())
        with zipfile.ZipFile(first / "sadskill-0.5.0.zip") as archive:
            self.assertIn("sadskill-0.5.0/VERSION", archive.namelist())

    def test_release_workflow_never_auto_publishes(self):
        flow = (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text()
        for expected in ("workflow_dispatch:", "--draft --verify-tag", "release_gate.py checks",
                         "sha256sum -c SHA256SUMS.txt", "contents: write"):
            self.assertIn(expected, flow)
        self.assertNotIn("pull_request_target:", flow)


if __name__ == "__main__":
    unittest.main()
