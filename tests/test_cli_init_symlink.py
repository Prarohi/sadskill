"""Symlink and user-file-preservation regression tests for sad init."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from scripts.sad_cli import cmd_init

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sad_cli.py"


class CliInitSymlinkTests(unittest.TestCase):
    def invoke(self, project):
        return subprocess.run(
            [sys.executable, str(CLI), "--no-color", "init", "--project-root", str(project)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=20,
        )

    def test_refuses_symlinked_explicit_project_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside"
            alias = root / "project-alias"
            outside.mkdir()
            alias.symlink_to(outside, target_is_directory=True)

            res = self.invoke(alias)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("symlinked or non-directory project root", res.stderr)
            self.assertFalse((outside / ".sad").exists())

    def test_refuses_existing_hardlinked_template(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            (project / ".sad").mkdir(parents=True)
            outside = root / "private-decisions.md"
            outside.write_text("preserve me", encoding="utf-8")
            os.link(outside, project / ".sad" / "decisions.md")

            res = self.invoke(project)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("single-link file", res.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "preserve me")

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

    def test_directory_swap_before_open_does_not_follow_replacement_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            real_mkdir = os.mkdir
            swapped = False

            def mkdir_then_swap(path, *args, **kwargs):
                nonlocal swapped
                result = real_mkdir(path, *args, **kwargs)
                if path == ".sad" and kwargs.get("dir_fd") is not None and not swapped:
                    os.rename(project / ".sad", project / ".sad-original")
                    (project / ".sad").symlink_to(outside, target_is_directory=True)
                    swapped = True
                return result

            with mock.patch("scripts.sad_cli.os.mkdir", side_effect=mkdir_then_swap):
                result = cmd_init(SimpleNamespace(project_root=str(project)))

            self.assertTrue(swapped)
            self.assertEqual(result, 1)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertTrue((project / ".sad").is_symlink())

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
