"""Command hook boundaries, exercised without executing the inspected commands."""

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOOKS = (
    ROOT / "scripts/git-guardrail.sh",
    ROOT / "skills/sadskill/hooks/git-guardrail.sh",
)


class HookBoundaryTests(unittest.TestCase):
    def assert_hook_status(self, command, expected):
        for hook in HOOKS:
            for payload in (command, json.dumps({"tool_input": {"command": command}})):
                with self.subTest(hook=str(hook.relative_to(ROOT)), command=command,
                                  structured=payload != command):
                    result = subprocess.run(
                        ["bash", str(hook)], input=payload, text=True,
                        capture_output=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, expected, result.stderr)

    def test_ordinary_push_refspecs_and_urls_are_allowed(self):
        for command in (
            "git push origin HEAD:feature/review",
            "git push origin feature/review:refs/heads/feature/review",
            "git push https://example.invalid/project/repo.git HEAD:feature/review",
        ):
            self.assert_hook_status(command, 0)

    def test_forced_and_deletion_refspecs_remain_blocked(self):
        for command in (
            "git push origin +HEAD:feature/review",
            "git push origin :feature/review",
            "git push --force origin HEAD:feature/review",
            "git push --force-with-lease=refs/heads/main origin HEAD:main",
            "git push --delete origin feature/review",
        ):
            self.assert_hook_status(command, 2)

    def test_quoted_global_option_values_do_not_hide_reset(self):
        for command in (
            'git -C "/tmp/project with spaces" reset --hard HEAD',
            "git -C '/tmp/project with spaces' reset --hard HEAD",
            'git --work-tree "/tmp/project with spaces" reset --hard HEAD',
            'git -C "/tmp/project with spaces" -c core.pager=cat reset --hard HEAD',
        ):
            self.assert_hook_status(command, 2)

    def test_quoted_messages_remain_data_but_following_commands_are_checked(self):
        self.assert_hook_status('git commit -m "fix; DROP TABLE wording"', 0)
        self.assert_hook_status('git commit -m "normal"; git reset --hard', 2)

    def test_packaged_hook_matches_root_hook(self):
        self.assertEqual(HOOKS[0].read_bytes(), HOOKS[1].read_bytes())


if __name__ == "__main__":
    unittest.main()
