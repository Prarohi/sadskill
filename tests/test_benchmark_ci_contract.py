"""CI-only Chromium compatibility must stay narrowly scoped and read-only."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "benchmark-evidence.yml"


class BenchmarkCIContractTests(unittest.TestCase):
    def test_chromium_sandbox_compatibility_is_only_enabled_for_the_isolated_ci_job(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertEqual(workflow.count("SADSKILL_CI_CHROMIUM_NO_SANDBOX"), 1)
        self.assertIn(
            "      - name: Run full Python regression suite\n"
            "        env:\n"
            "          SADSKILL_REQUIRE_C1_GRADERS: '1'\n"
            "          SADSKILL_CI_CHROMIUM_NO_SANDBOX: '1'\n",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
