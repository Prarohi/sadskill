"""Static contract checks for native project-memory platform coverage."""

from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "cli-init-safety.yml"
)


class CLIMemoryWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_memory_changes_trigger_platform_regressions(self):
        for path in (
            "scripts/sad_memory.py",
            "tests/test_concurrent_memory.py",
            "tests/test_memory_search.py",
            "docs/compatibility.md",
        ):
            self.assertIn(f"- '{path}'", self.workflow)

    def test_macos_runs_memory_filesystem_and_search_suites(self):
        self.assertIn("Native macOS memory/filesystem regressions", self.workflow)
        self.assertIn("runs-on: macos-15", self.workflow)
        self.assertIn("-p 'test_concurrent_memory.py'", self.workflow)
        self.assertIn("-p 'test_memory_search.py'", self.workflow)

    def test_windows_companion_memory_is_explicitly_unsupported_and_non_mutating(self):
        self.assertIn("Native Windows memory CLI fails closed", self.workflow)
        self.assertIn("runs-on: windows-2025", self.workflow)
        self.assertIn("unavailable on this platform", self.workflow)
        self.assertIn("Unsupported Windows memory CLI created a project memory directory", self.workflow)


if __name__ == "__main__":
    unittest.main()
