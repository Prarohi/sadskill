"""Updater check/plan behaviors against the loopback stub."""

import json
import os
import sys
import unittest
from pathlib import Path
from scripts.sadskill_core import compute_sha256

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.updater.fixtures import UpdaterSandboxCase as SandboxCase  # noqa: E402
from tests.updater.stub import GitHubStub, build_tarball, REPO  # noqa: E402


class CheckPlanTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.run_install("-a", "claude")
        self.stub = GitHubStub()
        tar, _ = build_tarball(top_dir="sadskill-0.3.0")
        self.stub.serve_release("v0.3.0", tar)
        self.base = self.stub.start()
        self.addCleanup(self.stub.stop)
        self.env["SADSKILL_UPDATE_API_BASE"] = self.base

    def test_check_reports_up_to_date_and_writes_nothing(self):
        before = self.home_snapshot()
        p = self.run_update("check", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertTrue(data["up_to_date"])
        self.assertEqual(data["latest"], "0.3.0")
        self.assertEqual(data["repo"], REPO)
        self.assertEqual(self.home_snapshot(), before)

    def test_check_reports_newer_available_no_writes(self):
        tar, _ = build_tarball(top_dir="sadskill-0.3.1")
        self.stub.serve_release("v0.3.1", tar)
        before = self.home_snapshot()
        p = self.run_update("check", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertFalse(data["up_to_date"])
        self.assertEqual(data["latest"], "0.3.1")
        self.assertEqual(self.home_snapshot(), before)

    def test_plan_is_zero_write_and_lists_files(self):
        tar, _ = build_tarball(top_dir="sadskill-0.3.1")
        self.stub.serve_release("v0.3.1", tar)
        before = self.home_snapshot()
        p = self.run_update("plan", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertEqual(data["from_version"], "0.3.0")
        self.assertEqual(data["to_version"], "0.3.1")
        self.assertTrue(data["zero_writes"])
        sources = {f["source"] for f in data["files_affected"]}
        self.assertIn("skills/sadskill/SKILL.md", sources)
        self.assertIn("skills/sadskill/hooks/git-guardrail.sh", sources)
        affected = [f for f in data["files_affected"]
                    if f["source"] == "skills/sadskill/SKILL.md"]
        self.assertTrue(affected)
        self.assertTrue(
            any(p.endswith(".claude/skills/sadskill/SKILL.md")
                for p in affected[0]["destinations"]),
            affected[0]["destinations"],
        )
        self.assertEqual(self.home_snapshot(), before)

    def test_beta_channel_sees_prerelease(self):
        tar, _ = build_tarball(top_dir="sadskill-0.3.1-rc.1")
        self.stub.serve_release("v0.3.1-rc.1", tar, prerelease=True)
        p = self.run_update("check", "--json", "--channel", "beta")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertEqual(data["latest"], "0.3.1-rc.1")
        self.assertFalse(data["up_to_date"])

    def test_stable_release_is_newer_than_installed_prerelease(self):
        self.set_installed_version("0.3.0-rc.1")
        state = os.path.join(self.home, ".sadskill", "install-state.json")
        with open(state, "w") as stream:
            json.dump({"version": "0.3.0-rc.1"}, stream)
        p = self.run_update("check", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(json.loads(p.stdout)["up_to_date"])

    def test_mixed_host_versions_are_reported_and_update_refused_without_writes(self):
        self.assertEqual(self.run_install("codex").returncode, 0)
        skill = Path(self.home) / ".codex/skills/sadskill/SKILL.md"
        skill.write_text(skill.read_text().replace("version: 0.3.0", "version: 0.4.0", 1))
        manifest = self.load_manifest()
        entry = next(e for e in manifest["entries"] if e["agent"] == "codex")
        entry["content_hash"] = compute_sha256(skill.parent)
        Path(self.manifest_path()).write_text(json.dumps(manifest))
        tar, _ = build_tarball(top_dir="sadskill-0.4.0")
        self.stub.serve_release("v0.4.0", tar)
        before = self.home_snapshot()
        check = self.run_update("check", "--json")
        self.assertEqual(check.returncode, 0, check.stderr)
        checked = json.loads(check.stdout)
        self.assertTrue(checked["mixed_versions"])
        self.assertFalse(checked["up_to_date"])
        applied = self.run_update("apply", "--json")
        self.assertEqual(applied.returncode, 5, applied.stdout + applied.stderr)
        self.assertIn("mixed", applied.stdout.lower())
        self.assertEqual(self.home_snapshot(), before)

    def test_repo_identity_verified(self):
        # A stub whose release payload lacks our repo identity must be refused.
        self.stub._routes[f"/repos/{REPO}/releases/latest"] = (
            200,
            json.dumps({
                "tag_name": "v9.9.9", "prerelease": False,
                "tarball_url": f"{self.base}/dl/v9.9.9.tar.gz",
                "assets": [], "url": "https://evil.example/repos/x/y/1",
            }).encode(),
        )
        p = self.run_update("check", "--json")
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
