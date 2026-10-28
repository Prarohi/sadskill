"""Updater status/check offline behaviors (no network, no writes)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import SandboxCase  # noqa: E402


class OfflineTests(SandboxCase):
    def test_status_is_fully_offline(self):
        # Point at a closed loopback port: status must still succeed.
        self.env["SADSKILL_UPDATE_API_BASE"] = "http://127.0.0.1:9"
        p = self.run_update("status", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        import json
        data = json.loads(p.stdout)
        self.assertEqual(data["command"], "status")
        self.assertIs(data["network_accessed"], False)
        self.assertIn(data["ownership"],
                      ("unknown", "installer-managed", "unmanaged",
                       "external-manager"))

    def test_status_offline_after_install(self):
        p = self.run_install("-a", "claude")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.env["SADSKILL_UPDATE_API_BASE"] = "http://127.0.0.1:9"
        p = self.run_update("status", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        import json
        data = json.loads(p.stdout)
        self.assertEqual(data["ownership"], "installer-managed")
        self.assertEqual(data["version"], "0.3.0")
        self.assertIn("claude", data["hosts"])

    def test_check_offline_refuses_with_rc3_and_no_writes(self):
        self.run_install("-a", "claude")
        before = self.home_snapshot()
        self.env["SADSKILL_UPDATE_API_BASE"] = "http://127.0.0.1:9"
        p = self.run_update("check", "--json")
        self.assertEqual(p.returncode, 3, f"expected rc 3 offline, got {p.returncode}")
        import json
        data = json.loads(p.stdout)
        self.assertEqual(data["error"], "network")
        self.assertEqual(self.home_snapshot(), before)

    def test_check_never_modifies_installation(self):
        self.run_install("-a", "claude")
        before = self.home_snapshot()
        self.env["SADSKILL_UPDATE_API_BASE"] = "http://127.0.0.1:9"
        self.run_update("check")
        self.assertEqual(self.home_snapshot(), before)


if __name__ == "__main__":
    unittest.main()
