"""Unit tests for unified sad CLI (`bin/sad` and `scripts/sad_cli.py`).
"""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SAD_BIN = ROOT / "bin" / "sad"


class SadCLITests(unittest.TestCase):
    def test_version_flag(self):
        res = subprocess.run([str(SAD_BIN), "--version"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("sadskill 0.5.0", res.stdout)

    def test_help_flag(self):
        res = subprocess.run([str(SAD_BIN), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("The Multi-Agent Engineering Confidence Layer", res.stdout)
        self.assertIn("init", res.stdout)
        self.assertIn("guard", res.stdout)
        self.assertIn("bench", res.stdout)

    def test_guard_subcommand_benign(self):
        res = subprocess.run(
            [str(SAD_BIN), "--no-color", "guard", "git status"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("[🛡️ SAFE]", res.stdout)

    def test_guard_subcommand_destructive(self):
        res = subprocess.run(
            [str(SAD_BIN), "--no-color", "guard", "git reset --hard"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("[✕ FAIL]", res.stdout)
        self.assertIn("BLOCKED", res.stdout)

    def test_bench_mock_is_explicitly_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "mock.jsonl"
            res = subprocess.run(
                [str(SAD_BIN), "bench", "--provider", "mock", "--task", "C1-01", "--output", str(output)],
                capture_output=True, text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("SIMULATED", res.stdout)
            self.assertIn("MOCK fixture checks completed", res.stdout)
            self.assertNotIn("Benchmark run completed successfully!", res.stdout)
            self.assertTrue(output.exists())

    def test_bench_real_provider_fails_closed_without_adapter(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "real.jsonl"
            res = subprocess.run(
                [str(SAD_BIN), "bench", "--provider", "codex", "--task", "C1-01", "--output", str(output)],
                capture_output=True, text=True,
            )
            self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
            self.assertIn("NOT EXECUTED", res.stderr)
            self.assertNotIn("Live-agent execution completed", res.stdout)

    def test_init_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            res = subprocess.run(
                [str(SAD_BIN), "--no-color", "init", "--project-root", str(tmp_root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("[✓ PASS]", res.stdout)
            sad_dir = tmp_root / ".sad"
            self.assertTrue((sad_dir / "events").exists())
            self.assertTrue((sad_dir / "evidence").exists())
            self.assertTrue((sad_dir / "benchmarks").exists())
            self.assertTrue((sad_dir / "decisions.md").exists())
            self.assertTrue((sad_dir / "history.md").exists())


if __name__ == "__main__":
    unittest.main()
