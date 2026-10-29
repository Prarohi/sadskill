"""Shared sandbox helpers for sadskill install/update regression tests.

Every test runs inside an isolated temporary HOME and project directory.
Tests must never touch the real user HOME and must never delete data
outside their own temp directories.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_SH = os.path.join(REPO_ROOT, "install.sh")
UNINSTALL_SH = os.path.join(REPO_ROOT, "uninstall.sh")
MANIFEST_CLI = os.path.join(REPO_ROOT, "scripts", "manifest.py")
DOCTOR_PY = os.path.join(REPO_ROOT, "scripts", "doctor.py")

UPDATE_CLI = os.path.join(REPO_ROOT, "scripts", "sadskill-update.py")

CLAUDE_SETTINGS = ".claude/settings.json"


class SandboxCase(unittest.TestCase):
    """TestCase with an isolated temporary HOME and project directory."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sadskill-sandbox-")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.home = os.path.join(self.base, "home")
        self.project = os.path.join(self.base, "project")
        os.makedirs(self.home)
        os.makedirs(self.project)
        self.env = dict(os.environ)
        self.env["HOME"] = self.home
        for var in (
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
            "TARGET_DIR",
            "SADSKILL_UPDATE_API_BASE",
            "GITHUB_TOKEN",
        ):
            self.env.pop(var, None)

    # -- subprocess helpers -------------------------------------------------

    def _run(self, cmd, cwd=None):
        return subprocess.run(
            cmd,
            cwd=cwd or self.project,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=180,
        )

    def run_install(self, *args):
        return self._run(["bash", INSTALL_SH, *args])

    def run_uninstall(self, *args):
        return self._run(["bash", UNINSTALL_SH, *args])

    def run_manifest(self, *args):
        return self._run([sys.executable, MANIFEST_CLI, *args])

    def run_doctor(self, *args):
        return self._run([sys.executable, DOCTOR_PY, *args])

    def run_update(self, *args, global_flags=()):
        """Run sadskill-update.py with optional global flags and arguments."""
        return self._run([sys.executable, UPDATE_CLI, *global_flags, *args])

    def spawn_manifest(self, *args):
        return subprocess.Popen(
            [sys.executable, MANIFEST_CLI, *args],
            cwd=self.project,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    # -- filesystem helpers ---------------------------------------------------

    def manifest_path(self):
        return os.path.join(self.home, ".sadskill", "install-manifest.json")

    def load_manifest(self):
        with open(self.manifest_path(), encoding="utf-8") as fh:
            return json.load(fh)

    def write_file(self, root, relpath, content):
        """Write a text file inside the sandbox; returns absolute path."""
        path = os.path.join(root, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def read_bytes(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def tree_entries(self, root):
        """All files and directories under root, relative paths, as a set."""
        found = set()
        for dirpath, dirnames, filenames in os.walk(root):
            for name in dirnames + filenames:
                found.add(os.path.relpath(os.path.join(dirpath, name), root))
        return found

    def home_snapshot(self):
        """(relpath, size) for every file under the sandbox HOME."""
        snapshot = set()
        for dirpath, _dirnames, filenames in os.walk(self.home):
            for name in filenames:
                path = os.path.join(dirpath, name)
                snapshot.add(
                    (os.path.relpath(path, self.home), os.path.getsize(path))
                )
        return snapshot

    def content_exists_under_home(self, needle):
        """True if any file under the sandbox HOME contains needle."""
        return self.content_exists_under(self.home, needle)

    def content_exists_under(self, root, needle):
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    with open(path, "rb") as fh:
                        if needle.encode("utf-8") in fh.read():
                            return True
                except OSError:
                    continue
        return False

    def find_paths_under(self, root, substr):
        """Relative paths (files AND directories) under root whose name contains substr."""
        hits = []
        for dirpath, dirnames, filenames in os.walk(root):
            for name in dirnames + filenames:
                if substr in name:
                    hits.append(os.path.relpath(os.path.join(dirpath, name), root))
        return hits

    def read_claude_settings(self):
        path = os.path.join(self.home, CLAUDE_SETTINGS)
        with open(path, "rb") as fh:
            return fh.read()

    def assert_not_in_home(self, relpath, msg=None):
        self.assertFalse(
            os.path.exists(os.path.join(self.home, relpath)),
            msg or f"unexpected path under HOME: {relpath}",
        )
