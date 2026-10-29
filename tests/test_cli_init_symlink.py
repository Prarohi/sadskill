"""Symlink and user-file-preservation regression tests for sad init."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sad_cli.py"


class CliInitSymlinkTests(unittest.TestCase):
    def invoke(self, project):
        return subprocess.run(
            [sys.executable, str(CLI), "--no-color", "init", "--project-root", str(project)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=20,
        )

    def test_refuses_symlinked_dot_sad_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            (project / ".sad").symlink_to(outside, target_is_directory=True)
            res = self.invoke(project)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("symlink", res.stderr)
            self.assertEqual(list(outside.iterdir()), [])

    def test_refuses_symlinked_events_subdirectory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            outside = root / "external"
            (project / ".sad").mkdir(parents=True)
            outside.mkdir()
            (project / ".sad" / "events").symlink_to(outside, target_is_directory=True)
            res = self.invoke(project)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("symlink", res.stderr)
            self.assertEqual(list(outside.iterdir()), [])

    def test_dangling_template_symlink_does_not_create_outside_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            dot_sad = project / ".sad"
            dot_sad.mkdir(parents=True)
            outside = root / "notes.md"
            (dot_sad / "decisions.md").symlink_to(outside)
            res = self.invoke(project)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("symlink", res.stderr)
            self.assertFalse(outside.exists())

    def test_regular_existing_user_document_is_preserved_on_reinit(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            first = self.invoke(project)
            self.assertEqual(first.returncode, 0, first.stderr)
            path = project / ".sad" / "decisions.md"
            path.write_text("USER-OWNED DECISIONS\n", encoding="utf-8")
            second = self.invoke(project)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), "USER-OWNED DECISIONS\n")

    def test_existing_directory_at_template_path_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            (project / ".sad" / "decisions.md").mkdir(parents=True)
            result = self.invoke(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a file", result.stderr)


if __name__ == "__main__":
    unittest.main()
