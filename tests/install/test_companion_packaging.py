"""Installed evidence tooling must work outside the Sadskill source checkout."""

import hashlib
import json
from pathlib import Path
import shutil
import sys

from tests.helpers import REPO_ROOT, SandboxCase


class CompanionPackagingTests(SandboxCase):
    def consumer_commit(self):
        self.write_file(self.project, "app.py", "answer = 42\n")
        for command in (
            ["git", "init", "-q"],
            ["git", "add", "app.py"],
            ["git", "-c", "user.name=Sadskill Tests", "-c",
             "user.email=tests@example.invalid", "commit", "-q", "-m", "seed"],
        ):
            result = self._run(command)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self._run(["git", "rev-parse", "HEAD"]).stdout.strip()

    def assert_consumer_context(self, helper, commit):
        self.assertTrue(helper.is_file(), f"installed helper missing: {helper}")
        self.assertFalse((Path(self.project) / "scripts").exists())
        # Run outside the consumer to ensure explicit project selection wins.
        result = self._run([
            sys.executable, str(helper), "--project-root", self.project,
            "--print-context",
        ], cwd=self.home)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        context = json.loads(result.stdout)
        expected_identity = hashlib.sha256(
            str(Path(self.project).resolve()).encode("utf-8")
        ).hexdigest()
        self.assertEqual(context["project_id"], expected_identity)
        self.assertEqual(context["commit_sha"], commit)
        self.assertFalse(context["worktree_dirty"])
        self.assertEqual(len(context["worktree_digest"]), 64)

    def test_companion_installs_helper_for_every_host(self):
        commit = self.consumer_commit()
        cursor_workspace = Path(self.base) / "cursor-workspace"
        result = self.run_install("--agent", "all", "--target", str(cursor_workspace))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        root_helper = Path(REPO_ROOT) / "scripts/verify-evidence.py"
        targets = [
            Path(self.home) / ".codex/skills/sadskill",
            Path(self.home) / ".claude/skills/sadskill",
            Path(self.home) / ".gemini/skills/sadskill",
            Path(self.home) / ".gemini/antigravity/skills/sadskill",
            cursor_workspace / ".cursor/skills/sadskill",
        ]
        for target in targets:
            with self.subTest(host=str(target)):
                helper = target / "tools/verify-evidence.py"
                self.assert_consumer_context(helper, commit)
                self.assertEqual(helper.read_bytes(), root_helper.read_bytes())

    def test_skill_only_distribution_contains_self_contained_helper(self):
        commit = self.consumer_commit()
        target = Path(self.home) / ".agents/skills/sadskill"
        shutil.copytree(Path(REPO_ROOT) / "skills/sadskill", target)
        self.assert_consumer_context(target / "tools/verify-evidence.py", commit)
