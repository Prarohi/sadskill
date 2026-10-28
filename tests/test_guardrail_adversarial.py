"""Adversarial wrapper bypass tests for sadskill safety guardrail.
Ensures that malicious or accidental destructive commands wrapped in env, sudo,
command, exec, or recursive shell invocations (bash -c, sh -c) are blocked.
"""

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = (
    ROOT / "scripts/git-guardrail.sh",
    ROOT / "skills/sadskill/hooks/git-guardrail.sh",
)


class GuardrailAdversarialTests(unittest.TestCase):
    def assert_blocked(self, command: str):
        for hook in HOOKS:
            with self.subTest(hook=str(hook.relative_to(ROOT)), command=command):
                res = subprocess.run(
                    ["bash", str(hook)],
                    input=command,
                    text=True,
                    capture_output=True,
                    timeout=10,
                )
                self.assertEqual(
                    res.returncode,
                    2,
                    f"Command '{command}' was not blocked (exit={res.returncode}, stdout={res.stdout}, stderr={res.stderr})",
                )
                self.assertIn("BLOCKED", res.stderr)

    def assert_allowed(self, command: str):
        for hook in HOOKS:
            with self.subTest(hook=str(hook.relative_to(ROOT)), command=command):
                res = subprocess.run(
                    ["bash", str(hook)],
                    input=command,
                    text=True,
                    capture_output=True,
                    timeout=10,
                )
                self.assertEqual(
                    res.returncode,
                    0,
                    f"Benign command '{command}' was unexpectedly blocked (exit={res.returncode}, stderr={res.stderr})",
                )

    def test_env_wrapper_bypass(self):
        self.assert_blocked('env bash -c "git reset --hard"')
        self.assert_blocked("env -u FOO git reset --hard")
        self.assert_blocked("env GIT_DIR=/tmp git reset --hard")
        self.assert_blocked("env -i git reset --hard")

    def test_sudo_wrapper_bypass(self):
        self.assert_blocked("sudo git reset --hard")
        self.assert_blocked("sudo -u root git clean -fd")
        self.assert_blocked("sudo git clean -fx")

    def test_command_and_exec_wrapper_bypass(self):
        self.assert_blocked("command git push origin +main:main")
        self.assert_blocked("command -p git reset --hard")
        self.assert_blocked("exec git reset --hard")
        self.assert_blocked("nohup git reset --hard")

    def test_recursive_shell_unwrapping(self):
        self.assert_blocked(r"""bash -c "sh -c 'git reset --hard'" """)
        self.assert_blocked('sh -c "bash -c \\"git clean -fd\\""')

    def test_compound_command_with_wrapper(self):
        self.assert_blocked('echo "building project" && sudo bash -c "git reset --hard"')
        self.assert_blocked('ls -la; env bash -c "DROP TABLE users;"')

    def test_benign_commands_with_wrappers_are_allowed(self):
        self.assert_allowed("env git status")
        self.assert_allowed("sudo git log -n 5")
        self.assert_allowed("command -v git")
        self.assert_allowed('bash -c "echo hello world"')
        self.assert_allowed('git commit -m "feat: handle git reset --hard in parser"')


if __name__ == "__main__":
    unittest.main()
