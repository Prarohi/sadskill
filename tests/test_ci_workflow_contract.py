"""Regression checks for the CI job contracts.

These static checks catch accidental workflow regressions; GitHub Actions runs
at the exact PR head are the source of truth for actual successful execution.
"""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


class CIWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_required_jobs_retained(self):
        for name in ("Verify sadskill (Node", "Native PostgreSQL RLS"):
            self.assertIn(name, self.workflow)
        self.assertIn("node-version: [20, 22]", self.workflow)

    def test_nonprivileged_checkout_and_timeouts(self):
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertIn("timeout-minutes: 30", self.workflow)
        self.assertIn("timeout-minutes: 10", self.workflow)
        self.assertIn("fail-fast: false", self.workflow)

    def test_contract_directory_is_explicitly_executed(self):
        self.assertIn("python3 -m unittest discover -s tests/skill-contract", self.workflow)
        self.assertIn("python3 -m unittest discover -s tests -v", self.workflow)

    def test_concurrent_prs_do_not_cancel_each_other(self):
        self.assertIn("github.event.pull_request.number || github.ref", self.workflow)
        self.assertIn("cancel-in-progress: true", self.workflow)

    def test_integrity_and_negative_control_preserved(self):
        self.assertIn("git diff --check", self.workflow)
        self.assertIn("npx --yes skills@1.7.4 add . -l", self.workflow)
        self.assertIn("test_rls.py --disable-rls", self.workflow)


if __name__ == "__main__":
    unittest.main()
