"""Real installation metadata must reflect the packaged release, not fixtures."""

import json
from pathlib import Path

from tests.helpers import REPO_ROOT, SandboxCase


class ReleaseVersionTests(SandboxCase):
    def test_reinstall_does_not_report_stale_updater_state_version(self):
        version = (Path(REPO_ROOT) / "VERSION").read_text().strip()
        state = Path(self.write_file(self.home, ".sadskill/install-state.json",
                                    json.dumps({"version": "0.3.1", "channel": "stable"})))
        result = self.run_install("claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        status = self.run_update("status", "--json")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["version"], version)
        self.assertEqual(json.loads(state.read_text())["channel"], "stable")

    def test_installed_version_and_cli_banner_match_release(self):
        version = (Path(REPO_ROOT) / "VERSION").read_text().strip()
        result = self.run_install("claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"Installing sadskill (v{version})", result.stdout)
        status = self.run_update("status", "--json")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["version"], version)
