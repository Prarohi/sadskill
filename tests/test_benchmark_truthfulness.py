"""Truthfulness regression tests: simulation must never be presented as model performance."""

import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from benchmarks.harness.runner import run_benchmark_run
from benchmarks.harness.visualize import generate_markdown_report, synthesize_metrics

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkTruthfulnessTests(unittest.TestCase):
    def test_mock_results_are_synthetic_and_not_measured_tokens(self):
        result = run_benchmark_run("C1-01", "sadskill", "mock", 1)
        self.assertEqual(result["status"], "SIMULATED")
        self.assertTrue(result["synthetic"])
        self.assertIsNone(result["input_tokens"])
        self.assertIsNone(result["output_tokens"])
        self.assertFalse(result["evidence_produced"])

    def test_visualizer_rejects_mock_superiority_statistics(self):
        samples = [run_benchmark_run("C1-01", c, "mock", 1)
                   for c in ("plain", "sadskill", "competitor")]
        summary = synthesize_metrics(samples)
        self.assertEqual(summary, {})
        report = generate_markdown_report(summary)
        self.assertIn("NOT_EXECUTED", report)
        self.assertNotIn("45.7%", report)
        self.assertNotIn("100.0%", report)

    def test_credential_does_not_make_unimplemented_adapter_real(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-placeholder"}, clear=True):
            result = run_benchmark_run("C1-01", "sadskill", "codex", 1)
        self.assertEqual(result["status"], "NOT_EXECUTED_NOT_IMPLEMENTED")
        self.assertFalse(result["success"])

    def test_live_runner_exits_failure_without_adapter(self):
        env = dict(os.environ)
        env["OPENAI_API_KEY"] = "test-placeholder"
        result = subprocess.run(
            [sys.executable, str(ROOT / "benchmarks/harness/runner.py"),
             "--provider", "codex", "--task", "C1-01"],
            env=env, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("NOT EXECUTED", result.stderr)

    def test_all_condition_matrix_works_in_mock(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "benchmarks/harness/runner.py"),
             "--provider", "mock", "--condition", "all", "--task", "C1-01"],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SIMULATED FIXTURE CHECK ONLY", result.stdout)
        self.assertIn("Total Runs: 3", result.stdout)


if __name__ == "__main__":
    unittest.main()
