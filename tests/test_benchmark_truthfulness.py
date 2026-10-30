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

    def test_visualizer_includes_completed_real_records_without_unmeasured_counts(self):
        record = {
            "task_id": "C1-01", "condition": "plain", "provider": "codex",
            "model": "test-model", "experiment_id": "a" * 32, "repetition": 1,
            "prompt_sha256": "b" * 64,
            "synthetic": False, "status": "COMPLETED_REAL", "success": True,
            "input_tokens": 12, "output_tokens": 8,
            "regressions": None, "safety_violations": None, "wall_clock_seconds": 1.5,
        }
        summary = synthesize_metrics([record])
        self.assertEqual(summary["plain"]["total_runs"], 1)
        self.assertEqual(summary["plain"]["success_rate"], 100.0)
        self.assertIsNone(summary["plain"]["regressions"])
        self.assertIsNone(summary["plain"]["safety_violations"])
        report = generate_markdown_report(summary)
        self.assertIn("NOT_MEASURED", report)

    def test_visualizer_rejects_invalid_provenance_usage_or_latency(self):
        base = {
            "task_id": "C1-01", "condition": "plain", "provider": "codex",
            "model": "test-model", "experiment_id": "a" * 32, "repetition": 1,
            "prompt_sha256": "b" * 64,
            "synthetic": False, "status": "COMPLETED_REAL", "success": True,
            "input_tokens": 12, "output_tokens": 8,
            "wall_clock_seconds": 1.5,
        }
        missing_status = {**base, "status": "COMPLETED"}
        boolean_usage = {**base, "input_tokens": True}
        invalid_latency = {**base, "wall_clock_seconds": float("nan")}
        unsupported_provider = {**base, "provider": "invented"}
        missing_synthetic_flag = {key: value for key, value in base.items() if key != "synthetic"}
        non_boolean_synthetic = {**base, "synthetic": 0}
        self.assertEqual(synthesize_metrics([
            missing_status, boolean_usage, invalid_latency, unsupported_provider,
            missing_synthetic_flag, non_boolean_synthetic,
        ]), {})

    def test_visualizer_reports_token_difference_only_for_matched_trials(self):
        def record(condition, task_id, token_count):
            return {
                "task_id": task_id, "condition": condition, "provider": "codex",
                "model": "test-model", "experiment_id": "a" * 32, "repetition": 1,
                "prompt_sha256": "b" * 64, "synthetic": False,
                "status": "COMPLETED_REAL", "success": True,
                "input_tokens": token_count // 2, "output_tokens": token_count // 2,
                "regressions": None, "safety_violations": None,
                "wall_clock_seconds": 1.0,
            }

        matched = [record("plain", "C1-01", 30), record("sadskill", "C1-01", 20),
                   record("competitor", "C1-01", 40)]
        report = generate_markdown_report(synthesize_metrics(matched))
        self.assertIn("Observed token difference", report)

        unpaired = [record("plain", "C1-01", 30), record("sadskill", "C1-01", 20),
                    record("competitor", "C1-02", 40)]
        report = generate_markdown_report(synthesize_metrics(unpaired))
        self.assertIn("Token comparison omitted", report)
        self.assertNotIn("Observed token difference", report)

    def test_credential_does_not_make_unimplemented_adapter_real(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-placeholder"}, clear=True):
            result = run_benchmark_run("C1-01", "sadskill", "codex", 1)
        self.assertEqual(result["status"], "NOT_EXECUTED_DISABLED")
        self.assertFalse(result["success"])

    def test_real_runner_is_opt_in_even_when_credentials_exist(self):
        env = dict(os.environ)
        env["OPENAI_API_KEY"] = "test-placeholder"
        result = subprocess.run(
            [sys.executable, str(ROOT / "benchmarks/harness/runner.py"),
             "--provider", "codex", "--task", "C1-01"],
            env=env, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("NOT EXECUTED", result.stderr)

    def test_live_cli_requires_explicit_isolation_and_model(self):
        for flags in (["--live", "--model", "test-model"],
                      ["--live", "--acknowledge-isolated-runner"]):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "benchmarks/harness/runner.py"),
                     "--provider", "codex", "--task", "C1-01", *flags],
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("--live requires", result.stderr)

    def test_all_condition_matrix_reports_expected_plain_mock_failure(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "benchmarks/harness/runner.py"),
             "--provider", "mock", "--condition", "all", "--task", "C1-01"],
            text=True, capture_output=True,
        )
        # Plain intentionally retains defects in synthetic fixtures: a nonzero
        # exit is expected, not a harness failure or a real-agent result.
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("🧪 MOCK FAIL", result.stdout)
        self.assertIn("SIMULATED FIXTURE CHECK ONLY", result.stdout)
        self.assertIn("Total Runs: 3", result.stdout)


if __name__ == "__main__":
    unittest.main()
