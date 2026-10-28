"""Defect class 9: pre-existing Claude settings.json and unrelated hooks
must survive hook registration; corrupt settings must be rejected, never
overwritten; hook detection must understand the OFFICIAL nested schema.
"""

import json
import os
import unittest

from tests.helpers import SandboxCase

SETTINGS = ".claude/settings.json"
GUARDRAIL = ".claude/hooks/git-guardrail.sh"


class ClaudeSettingsTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.settings_path = os.path.join(self.home, SETTINGS)
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        self.user_settings = {
            "model": "opus",
            "permissions": {"allow": ["Bash(ls:*)"]},
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "echo unrelated"}]}
                ]
            },
        }

    def _enable(self):
        return self.run_doctor("--enable-hooks", "--json")

    def _disable(self):
        return self.run_doctor("--disable-hooks", "--json")

    def _load(self):
        with open(self.settings_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_registration_uses_official_nested_schema_and_preserves_user_data(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        settings = self._load()
        self.assertEqual(settings.get("model"), "opus",
                         "user settings fields destroyed by registration")
        self.assertIn("Stop", settings.get("hooks", {}),
                      "user's unrelated hook destroyed by registration")
        pre = settings["hooks"].get("PreToolUse")
        self.assertIsInstance(pre, list)
        self.assertTrue(pre, "no PreToolUse hook registered")
        matcher_entry = pre[0]
        self.assertIn("matcher", matcher_entry)
        self.assertIn("hooks", matcher_entry,
                      "flat hook entry written; official schema nests "
                      "command entries under a 'hooks' list")
        self.assertEqual(matcher_entry["hooks"][0]["type"], "command")

        # Idempotent: registering again must not duplicate.
        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        settings = self._load()
        our = [e for e in settings["hooks"]["PreToolUse"]
               if any("git-guardrail" in h.get("command", "")
                      for h in e.get("hooks", []))]
        self.assertEqual(len(our), 1, "duplicate hook registrations created")

    def test_backup_created_before_modification(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        backups = [n for n in os.listdir(os.path.dirname(self.settings_path))
                   if n.startswith("settings.json.bak")]
        self.assertTrue(backups, "no settings.json backup created before write")

    def test_corrupt_settings_rejected_without_overwrite(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            fh.write("{invalid json")
        original = self.read_bytes(self.settings_path)
        rc = self._enable()
        self.assertNotEqual(
            rc.returncode, 0,
            "corrupt settings.json must abort registration, not continue",
        )
        self.assertEqual(
            self.read_bytes(self.settings_path), original,
            "corrupt settings.json was overwritten",
        )

    def test_nested_registration_is_detected(self):
        """check_claude_hook must see the official nested schema, not only
        the legacy flat format."""
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({
                "hooks": {"PreToolUse": [{
                    "matcher": "Bash",
                    "hooks": [{"type": "command",
                               "command": os.path.join(self.home, GUARDRAIL)}],
                }]},
            }, fh)
        rc = self.run_doctor("--json")
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        report = json.loads(rc.stdout)
        status = report.get("claude_hook", {}).get("status")
        self.assertIn(
            status, ("REGISTERED", "LOCAL_TEST_PASSED"),
            f"nested registration invisible to doctor (status={status!r})",
        )

    def test_disable_hooks_is_ownership_aware(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        rc = self._disable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        settings = self._load()
        self.assertEqual(settings.get("model"), "opus")
        self.assertIn("Stop", settings.get("hooks", {}),
                      "user's unrelated hook destroyed by unregistration")
        pre = settings.get("hooks", {}).get("PreToolUse", [])
        self.assertFalse(
            [e for e in pre
             if any("git-guardrail" in h.get("command", "")
                    for h in e.get("hooks", []))],
            "sadskill hook survived --disable-hooks",
        )

    def test_labels_are_truthful(self):
        """No hook status may ever claim ACTIVE from a local simulation."""
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        self._enable()
        rc = self.run_doctor("--json")
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        report = json.loads(rc.stdout)
        status = report.get("claude_hook", {}).get("status")
        allowed = {
            "NOT_INSTALLED", "AVAILABLE", "REGISTERED",
            "LOCAL_TEST_PASSED", "HOST_VERIFIED_ACTIVE", "UNKNOWN",
            "UNSUPPORTED",
        }
        self.assertIn(status, allowed, f"untruthful hook status: {status!r}")


if __name__ == "__main__":
    unittest.main()
