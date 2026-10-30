"""Browser infrastructure failures must not be scored as candidate defects."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.harness.evaluators import EvaluationUnavailable, evaluate_c1_08


class ChromiumGraderRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        (self.workspace / "src").mkdir()
        (self.workspace / "src" / "styles.css").write_text(
            ".container { max-width: 100%; } pre { white-space: pre-wrap; }\n",
            encoding="utf-8",
        )

    @staticmethod
    def completed(stdout):
        return subprocess.CompletedProcess(["chromium"], 0, stdout, "")

    @patch("benchmarks.harness.evaluators._run_chromium")
    def test_incomplete_dom_retries_once_and_can_pass(self, run_chromium):
        run_chromium.side_effect = [
            self.completed("<html><body></body></html>"),
            self.completed('<html><body data-grader="pass"></body></html>'),
        ]

        result = evaluate_c1_08(self.workspace)

        self.assertTrue(result[0], result[3])
        self.assertEqual(run_chromium.call_count, 2)
        self.assertEqual(run_chromium.call_args.kwargs["timeout"], 30)

    @patch("benchmarks.harness.evaluators._run_chromium")
    def test_timeout_retries_once_and_can_pass(self, run_chromium):
        run_chromium.side_effect = [
            EvaluationUnavailable("Chromium grader timed out after 30s"),
            self.completed('<html><body data-grader="pass"></body></html>'),
        ]

        result = evaluate_c1_08(self.workspace)

        self.assertTrue(result[0], result[3])
        self.assertEqual(run_chromium.call_count, 2)

    @patch("benchmarks.harness.evaluators._run_chromium")
    def test_browser_process_error_retries_once_and_can_pass(self, run_chromium):
        run_chromium.side_effect = [
            EvaluationUnavailable("Chromium grader exited with status 1"),
            self.completed('<html><body data-grader="pass"></body></html>'),
        ]

        result = evaluate_c1_08(self.workspace)

        self.assertTrue(result[0], result[3])
        self.assertEqual(run_chromium.call_count, 2)

    @patch("benchmarks.harness.evaluators._run_chromium")
    def test_measured_overflow_fails_without_retry(self, run_chromium):
        run_chromium.return_value = self.completed(
            '<html><body data-result="{&quot;width&quot;:375}" data-grader="fail"></body></html>'
        )

        result = evaluate_c1_08(self.workspace)

        self.assertFalse(result[0])
        self.assertIn("overflowed", result[3])
        self.assertEqual(run_chromium.call_count, 1)

    @patch("benchmarks.harness.evaluators._run_chromium")
    def test_two_incomplete_results_are_unverifiable_not_candidate_failure(self, run_chromium):
        run_chromium.return_value = self.completed("<html><body></body></html>")

        with self.assertRaisesRegex(EvaluationUnavailable, "incomplete after two attempts"):
            evaluate_c1_08(self.workspace)

        self.assertEqual(run_chromium.call_count, 2)


if __name__ == "__main__":
    unittest.main()
