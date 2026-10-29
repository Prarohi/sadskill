"""The real model comparison must reject status-only or partial-usage fixtures."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.harness.runner import run_benchmark_run
from benchmarks.harness.evaluators import EvaluationUnavailable


class EmpiricalRunnerGuardTests(unittest.TestCase):
    def test_completed_without_usage_is_not_graded(self):
        response = {
            "status": "COMPLETED_REAL",
            "synthetic": False,
            "input_tokens": None,
            "output_tokens": None,
        }
        with patch("benchmarks.harness.runner.RealAgentProvider.execute", return_value=response):
            with patch("benchmarks.harness.runner.EVALUATORS") as evaluators:
                evaluator = evaluators.get.return_value
                result = run_benchmark_run(
                    "C1-01", "plain", "codex", 1,
                    live=True, isolated=True, model="test-model"
                )
                evaluator.assert_not_called()
        self.assertEqual(result["status"], "FAILED_UNVERIFIABLE_METRICS")
        self.assertFalse(result["success"])
        self.assertIsNone(result["regressions"])
        self.assertIsNone(result["safety_violations"])

    def test_fake_success_without_status_is_rejected(self):
        response = {"input_tokens": 123, "output_tokens": 45}
        with patch("benchmarks.harness.runner.RealAgentProvider.execute", return_value=response):
            result = run_benchmark_run(
                "C1-01", "plain", "codex", 1,
                live=True, isolated=True, model="test-model"
            )
        self.assertEqual(result["status"], "FAILED_UNVERIFIABLE_METRICS")
        self.assertFalse(result["success"])

    def test_unexecuted_has_unknown_not_zero_violation_counters(self):
        result = run_benchmark_run("C1-01", "plain", "codex", 1)
        self.assertTrue(result["status"].startswith("NOT_EXECUTED"))
        self.assertIsNone(result["regressions"])
        self.assertIsNone(result["safety_violations"])
        self.assertIsNone(result["input_tokens"])
        self.assertIsNone(result["output_tokens"])

    def test_missing_grader_runtime_is_not_scored_as_a_failed_task(self):
        response = {
            "status": "COMPLETED_REAL", "synthetic": False,
            "input_tokens": 10, "output_tokens": 5,
        }

        def unavailable(_workspace):
            raise EvaluationUnavailable("browser runtime unavailable")

        with patch("benchmarks.harness.runner.RealAgentProvider.execute", return_value=response):
            with patch("benchmarks.harness.runner.EVALUATORS", {"C1-01": unavailable}):
                result = run_benchmark_run(
                    "C1-01", "plain", "codex", 1,
                    live=True, isolated=True, model="test-model"
                )
        self.assertEqual(result["status"], "FAILED_UNVERIFIABLE_GRADER")
        self.assertFalse(result["success"])
        self.assertIsNone(result["regressions"])
        self.assertIsNone(result["safety_violations"])


if __name__ == "__main__":
    unittest.main()
