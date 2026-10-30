"""Keep generated Sadskill runtime artifacts out of accidental git commits."""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RuntimeArtifactHygieneTests(unittest.TestCase):
    def check_ignored(self, path):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "--", path],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode == 0

    def test_generated_project_memory_is_ignored(self):
        for path in (
            ".sad/.lock",
            ".sad/events/20261030-event.json",
            ".sad/evidence/local-execution.json",
            ".sad/benchmark-codex.jsonl",
            ".sad/benchmarks/private-trial.jsonl",
        ):
            with self.subTest(path=path):
                self.assertTrue(self.check_ignored(path), path)

    def test_versioned_project_documents_are_not_ignored(self):
        for path in (
            ".sad/history.md",
            ".sad/decisions.md",
            ".sad/benchmark-latest.json",
            ".sad/benchmarks/c1-summary.md",
            "skills/sadskill/SKILL.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(self.check_ignored(path), path)


if __name__ == "__main__":
    unittest.main()
