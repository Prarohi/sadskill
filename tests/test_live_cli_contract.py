"""Contract tests for real agent CLI adapters. No real model or API is invoked."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.harness.live_cli import execute_live, parse_usage

TASK = {"id": "C1-01", "prompt": "Fix the bug", "budget": {"max_turns": 2, "max_time_seconds": 60}}


class Dummy:
    returncode = 0
    stdout = '{"type":"turn.completed","usage":{"input_tokens":13,"output_tokens":7}}\n'
    stderr = ""


class LiveCLIContractTests(unittest.TestCase):
    def test_codex_command_uses_sandbox_and_real_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("benchmarks.harness.live_cli.shutil.which", return_value="/bin/fake-codex"):
                with patch("benchmarks.harness.live_cli.subprocess.run", return_value=Dummy()) as run:
                    result = execute_live(TASK, "plain", Path(tmp), "codex", "test-model")
        self.assertEqual(result["status"], "COMPLETED_REAL")
        self.assertFalse(result["synthetic"])
        self.assertEqual(result["input_tokens"], 13)
        self.assertEqual(result["output_tokens"], 7)
        command = run.call_args.args[0]
        self.assertIn("workspace-write", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_absent_cli_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("benchmarks.harness.live_cli.shutil.which", return_value=None):
                result = execute_live(TASK, "plain", Path(tmp), "gemini", "test-model")
        self.assertEqual(result["status"], "NOT_EXECUTED_NO_CLI")

    def test_invalid_json_is_not_successful(self):
        class Broken(Dummy):
            stdout = "not-json"
        with tempfile.TemporaryDirectory() as tmp:
            with patch("benchmarks.harness.live_cli.shutil.which", return_value="/bin/fake"):
                with patch("benchmarks.harness.live_cli.subprocess.run", return_value=Broken()):
                    result = execute_live(TASK, "plain", Path(tmp), "claude", "test-model")
        self.assertEqual(result["status"], "FAILED_UNVERIFIABLE_OUTPUT")

    def test_incomplete_codex_usage_is_not_real(self):
        class Missing(Dummy):
            stdout = '{"type":"turn.completed","usage":{"input_tokens":19}}\n'
        with tempfile.TemporaryDirectory() as tmp:
            with patch("benchmarks.harness.live_cli.shutil.which", return_value="/bin/fake-codex"):
                with patch("benchmarks.harness.live_cli.subprocess.run", return_value=Missing()):
                    result = execute_live(TASK, "plain", Path(tmp), "codex", "test-model")
        self.assertEqual(result["status"], "FAILED_UNVERIFIABLE_OUTPUT")
        self.assertIsNone(result["output_tokens"])

    def test_missing_or_malformed_model_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for model in (None, "", "bad model", 123, True):
                with self.subTest(model=model):
                    result = execute_live(TASK, "plain", Path(tmp), "codex", model)
                    self.assertEqual(result["status"], "NOT_EXECUTED_INVALID_CONFIGURATION")

    def test_partial_and_bool_usage_not_accepted(self):
        self.assertIsNone(parse_usage("claude", '{"usage":{"input_tokens":20}}'))
        self.assertIsNone(parse_usage("claude", '{"usage":{"input_tokens":true,"output_tokens":1}}'))
        self.assertIsNone(parse_usage("gemini", '{"stats":{"inputTokens":20,"outputTokens":-1}}'))

    def test_missing_usage_never_becomes_zero(self):
        self.assertIsNone(parse_usage("claude", '{"usage":{}}'))
        self.assertIsNone(parse_usage("gemini", '{"error":"unauthorized"}'))


if __name__ == "__main__":
    unittest.main()
