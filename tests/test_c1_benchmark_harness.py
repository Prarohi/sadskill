"""Unit tests for the C1 Real-Agent Benchmark Harness."""

import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.harness.runner import run_benchmark_run
from benchmarks.harness.tasks import C1_TASKS


class C1BenchmarkHarnessTests(unittest.TestCase):
    def test_all_12_tasks_registered(self):
        self.assertEqual(len(C1_TASKS), 12)
        for i in range(1, 13):
            tid = f"C1-{i:02d}"
            self.assertIn(tid, C1_TASKS)
            task = C1_TASKS[tid]
            self.assertTrue(task.get("name"))
            self.assertTrue(task.get("prompt"))
            self.assertTrue(task.get("budget"))
            self.assertTrue(task.get("setup_files"))

    def test_mock_sadskill_run_c1_01_success(self):
        res = run_benchmark_run("C1-01", "sadskill", "mock", 1)
        self.assertEqual(res["status"], "SIMULATED")
        self.assertTrue(res["success"])
        self.assertEqual(res["regressions"], 0)
        self.assertTrue(res["synthetic"])
        self.assertIsNone(res["input_tokens"])
        self.assertFalse(res["evidence_produced"])

    def test_mock_plain_run_c1_06_fails_rls_invariant(self):
        res = run_benchmark_run("C1-06", "plain", "mock", 1)
        self.assertEqual(res["status"], "SIMULATED")
        self.assertFalse(res["success"], "Plain mock fixture should not satisfy forced RLS invariants")

    def test_unauthenticated_codex_provider_reports_truthful_unauth(self):
        res = run_benchmark_run("C1-01", "sadskill", "codex", 1)
        self.assertEqual(res["status"], "NOT_EXECUTED_NO_AUTH")
        self.assertFalse(res["success"])
        self.assertIn("Missing provider API key", res["reason"])


if __name__ == "__main__":
    unittest.main()
