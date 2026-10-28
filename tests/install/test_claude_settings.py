"""Defect class 9: pre-existing Claude settings.json and unrelated hooks
must survive hook registration; corrupt settings must be rejected, never
overwritten; hook detection must understand the OFFICIAL nested schema.
"""

import json
import os
import re
import stat
import unittest

from tests.helpers import SandboxCase

SETTINGS = ".claude/settings.json"
GUARDRAIL = ".claude/hooks/git-guardrail.sh"


class ClaudeSettingsTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.settings_path = os.path.join(self.home, SETTINGS)
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        self.user_settings = {
            "model": "opus",
            "permissions": {"allow": ["Bash(ls:*)"]},
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "echo unrelated"}]}
                ]
            },
        }
        # The defect-9 scenario is an install performed ON TOP of
        # pre-existing user settings: place the guardrail hook (install
        # never touches settings.json), keep user settings in place.
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        inst = self.run_install("-a", "claude")
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.home, GUARDRAIL)))

    def _enable(self):
        return self.run_doctor("--enable-hooks", "--json")

    def _disable(self):
        return self.run_doctor("--disable-hooks", "--json")

    def _load(self):
        with open(self.settings_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_registration_uses_official_nested_schema_and_preserves_user_data(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        settings = self._load()
        self.assertEqual(settings.get("model"), "opus",
                         "user settings fields destroyed by registration")
        self.assertIn("Stop", settings.get("hooks", {}),
                      "user's unrelated hook destroyed by registration")
        pre = settings["hooks"].get("PreToolUse")
        self.assertIsInstance(pre, list)
        self.assertTrue(pre, "no PreToolUse hook registered")
        matcher_entry = pre[0]
        self.assertIn("matcher", matcher_entry)
        self.assertIn("hooks", matcher_entry,
                      "flat hook entry written; official schema nests "
                      "command entries under a 'hooks' list")
        self.assertEqual(matcher_entry["hooks"][0]["type"], "command")

        # Idempotent: registering again must not duplicate.
        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        settings = self._load()
        our = [e for e in settings["hooks"]["PreToolUse"]
               if any("git-guardrail" in h.get("command", "")
                      for h in e.get("hooks", []))]
        self.assertEqual(len(our), 1, "duplicate hook registrations created")

    def test_backup_created_before_modification(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        backups = [n for n in os.listdir(os.path.dirname(self.settings_path))
                   if n.startswith("settings.json.bak")]
        self.assertTrue(backups, "no settings.json backup created before write")

    def test_settings_mode_is_preserved_and_backup_is_private(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        os.chmod(self.settings_path, 0o600)

        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(self.settings_path).st_mode), 0o600)

        backups = [
            os.path.join(os.path.dirname(self.settings_path), name)
            for name in os.listdir(os.path.dirname(self.settings_path))
            if name.startswith("settings.json.bak")
        ]
        self.assertTrue(backups, "no settings.json backup created")
        self.assertEqual(stat.S_IMODE(os.stat(backups[0]).st_mode), 0o600)

    def test_corrupt_settings_rejected_without_overwrite(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            fh.write("{invalid json")
        original = self.read_bytes(self.settings_path)
        rc = self._enable()
        self.assertNotEqual(
            rc.returncode, 0,
            "corrupt settings.json must abort registration, not continue",
        )
        self.assertEqual(
            self.read_bytes(self.settings_path), original,
            "corrupt settings.json was overwritten",
        )

    def test_unexpected_hooks_value_is_rejected_without_overwrite(self):
        original = b'{"model":"opus","hooks":"keep-me"}\n'
        with open(self.settings_path, "wb") as fh:
            fh.write(original)
        rc = self._enable()
        self.assertNotEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        self.assertEqual(self.read_bytes(self.settings_path), original)

    def test_symlinked_settings_are_rejected_without_replacing_link(self):
        target = os.path.join(self.home, ".claude", "managed-settings.json")
        original = b'{"model":"managed"}\n'
        with open(target, "wb") as fh:
            fh.write(original)
        os.unlink(self.settings_path)
        os.symlink(target, self.settings_path)

        rc = self._enable()
        self.assertNotEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        self.assertTrue(os.path.islink(self.settings_path))
        self.assertEqual(os.readlink(self.settings_path), target)
        self.assertEqual(self.read_bytes(target), original)

    def test_nested_registration_is_detected(self):
        """check_claude_hook must see the official nested schema, not only
        the legacy flat format."""
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({
                "hooks": {"PreToolUse": [{
                    "matcher": "Bash",
                    "hooks": [{"type": "command",
                               "command": os.path.join(self.home, GUARDRAIL)}],
                }]},
            }, fh)
        rc = self.run_doctor("--json")
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        report = json.loads(rc.stdout)
        status = report.get("claude_hook", {}).get("status")
        self.assertIn(
            status, ("REGISTERED", "LOCAL_TEST_PASSED"),
            f"nested registration invisible to doctor (status={status!r})",
        )

    def test_non_bash_matcher_does_not_satisfy_bash_registration(self):
        hook = os.path.join(self.home, GUARDRAIL)
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "Write",
                "hooks": [
                    {"type": "command", "command": hook},
                    {"type": "command", "command": "echo user-owned"},
                ],
            }]}}, fh)

        before = self.run_doctor("--json")
        self.assertEqual(before.returncode, 0, before.stdout + before.stderr)
        self.assertEqual(json.loads(before.stdout)["claude_hook"]["status"], "AVAILABLE")

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        self.assertTrue(any(
            group.get("matcher") == "Write"
            and any(sub.get("command") == "echo user-owned" for sub in group.get("hooks", []))
            for group in groups
        ), "registration removed an unrelated Write hook")
        self.assertTrue(any(
            group.get("matcher") == "Bash"
            and any(sub.get("command") == hook for sub in group.get("hooks", []))
            for group in groups
        ), "enable-hooks failed to add a Bash-matching hook")

        after = self.run_doctor("--json")
        self.assertEqual(after.returncode, 0, after.stdout + after.stderr)
        self.assertEqual(json.loads(after.stdout)["claude_hook"]["status"], "LOCAL_TEST_PASSED")

    def test_plain_matcher_is_exact_not_a_regex_substring(self):
        hook = os.path.join(self.home, GUARDRAIL)
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "B",
                "hooks": [{"type": "command", "command": hook}],
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        self.assertFalse(any(group.get("matcher") == "B" for group in groups))
        self.assertTrue(any(
            group.get("matcher") == "Bash"
            and any(sub.get("command") == hook for sub in group.get("hooks", []))
            for group in groups
        ), "plain matcher 'B' incorrectly suppressed exact Bash registration")

    def test_python_only_regex_does_not_suppress_exact_bash_registration(self):
        hook = os.path.join(self.home, GUARDRAIL)
        python_only_matcher = r"(?P<tool>Bash)"
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": python_only_matcher,
                "hooks": [
                    {"type": "command", "command": hook},
                    {"type": "command", "command": "echo user-owned"},
                ],
            }]}}, fh)

        # This is valid Python regex syntax but invalid JavaScript RegExp
        # syntax, which Claude Code uses for matcher expressions.
        self.assertEqual(re.search(python_only_matcher, "Bash").group("tool"), "Bash")
        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        self.assertTrue(any(
            group.get("matcher") == python_only_matcher
            and any(sub.get("command") == "echo user-owned" for sub in group.get("hooks", []))
            and not any(sub.get("command") == hook for sub in group.get("hooks", []))
            for group in groups
        ), "registration failed to preserve unrelated handlers in the user's regex group")
        self.assertTrue(any(
            group.get("matcher") == "Bash"
            and any(sub.get("command") == hook for sub in group.get("hooks", []))
            for group in groups
        ), "Python-only regex incorrectly suppressed exact Bash registration")

    def test_python_inline_flags_are_not_treated_as_shared_regex(self):
        hook = os.path.join(self.home, GUARDRAIL)
        matcher = "(?i)Bash"
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": matcher,
                "hooks": [{"type": "command", "command": hook}],
            }]}}, fh)

        self.assertEqual(re.search(matcher, "Bash").group(0), "Bash")
        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        owned = [
            (group, sub)
            for group in groups for sub in group.get("hooks", [])
            if sub.get("command") == hook
        ]
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0][0].get("matcher"), "Bash")

    def test_normalization_preserves_user_hook_command_arguments(self):
        hook = os.path.join(self.home, GUARDRAIL)
        command = hook + " --custom-mode"
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "(?i)Bash",
                "hooks": [{"type": "command", "command": command}],
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        owned = [
            (group, sub)
            for group in groups for sub in group.get("hooks", [])
            if isinstance(sub, dict) and sub.get("command", "").startswith(hook)
        ]
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0][0].get("matcher"), "Bash")
        self.assertEqual(owned[0][1]["command"], command)

    def test_conflicting_owned_hook_arguments_fail_without_writing_settings(self):
        hook = os.path.join(self.home, GUARDRAIL)
        original = {
            "hooks": {"PreToolUse": [
                {
                    "matcher": "Bash.*",
                    "hooks": [{"type": "command", "command": hook + " --one"}],
                },
                {
                    "matcher": "(?i)Bash",
                    "hooks": [{"type": "command", "command": hook + " --two"}],
                },
            ]},
        }
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(original, fh)
        before = self.read_bytes(self.settings_path)

        enabled = self._enable()
        self.assertNotEqual(enabled.returncode, 0)
        self.assertIn("conflicting owned Claude hook", enabled.stderr)
        self.assertEqual(self.read_bytes(self.settings_path), before)

    def test_shell_quoting_differences_fail_without_writing_settings(self):
        hook = os.path.join(self.home, GUARDRAIL)
        original = {
            "hooks": {"PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{
                        "type": "command",
                        "command": hook + ' "$HOME/target"',
                    }],
                },
                {
                    "matcher": "(?i)Bash",
                    "hooks": [{
                        "type": "command",
                        "command": hook + " '$HOME/target'",
                    }],
                },
            ]},
        }
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(original, fh)
        before = self.read_bytes(self.settings_path)

        enabled = self._enable()
        self.assertNotEqual(enabled.returncode, 0)
        self.assertIn("conflicting owned Claude hook", enabled.stderr)
        self.assertEqual(self.read_bytes(self.settings_path), before)

    def test_owned_non_command_type_is_normalized_to_executable_command(self):
        hook = os.path.join(self.home, GUARDRAIL)
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "(?i)Bash",
                "hooks": [{"type": "prompt", "command": hook}],
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        owned = [
            (group, sub)
            for group in groups for sub in group.get("hooks", [])
            if isinstance(sub, dict) and sub.get("command") == hook
        ]
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0][0].get("matcher"), "Bash")
        self.assertEqual(owned[0][1]["type"], "command")

    def test_legacy_flat_migration_preserves_hook_arguments(self):
        hook = os.path.join(self.home, GUARDRAIL)
        command = hook + " --custom-mode"
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "(?i)Bash",
                "command": command,
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        owned = [
            (group, sub)
            for group in groups for sub in group.get("hooks", [])
            if isinstance(sub, dict) and sub.get("command", "").startswith(hook)
        ]
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0][0].get("matcher"), "Bash")
        self.assertEqual(owned[0][1]["command"], command)

    def test_legacy_migration_refuses_to_overwrite_malformed_pretool_value(self):
        hook = os.path.join(self.home, GUARDRAIL)
        settings = {
            "hooks": {
                "PreToolUse": None,
                "Stop": [{"command": hook + " --custom-mode"}],
            },
        }
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(settings, fh)
        before = self.read_bytes(self.settings_path)

        enabled = self._enable()
        self.assertNotEqual(enabled.returncode, 0)
        self.assertIn("hooks.PreToolUse has an unexpected shape", enabled.stderr)
        self.assertEqual(self.read_bytes(self.settings_path), before)

    def test_regex_matcher_is_normalized_without_duplicate_hook(self):
        hook = os.path.join(self.home, GUARDRAIL)
        matcher = "Bash.*"
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": matcher,
                "hooks": [{"type": "command", "command": hook}],
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        owned_handlers = [
            (group, sub)
            for group in groups
            if isinstance(group, dict)
            for sub in group.get("hooks", [])
            if isinstance(sub, dict) and sub.get("command") == hook
        ]
        self.assertEqual(len(owned_handlers), 1, "valid shared regex caused duplicate execution")
        self.assertEqual(owned_handlers[0][0].get("matcher"), "Bash")

    def test_catch_all_matchers_are_normalized_to_bash_only(self):
        hook = os.path.join(self.home, GUARDRAIL)
        cases = [
            ({"hooks": [
                {"type": "command", "command": hook},
                {"type": "command", "command": "echo user-owned"},
            ]}, None),
            ({"matcher": "*", "hooks": [
                {"type": "command", "command": hook},
                {"type": "command", "command": "echo user-owned"},
            ]}, "*"),
            ({"matcher": ".*", "hooks": [
                {"type": "command", "command": hook},
                {"type": "command", "command": "echo user-owned"},
            ]}, ".*"),
            ({"matcher": "Bash|Write", "hooks": [
                {"type": "command", "command": hook},
                {"type": "command", "command": "echo user-owned"},
            ]}, "Bash|Write"),
        ]
        for group, original_matcher in cases:
            with self.subTest(matcher=original_matcher):
                with open(self.settings_path, "w", encoding="utf-8") as fh:
                    json.dump({"hooks": {"PreToolUse": [group]}}, fh)
                enabled = self._enable()
                self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
                groups = self._load()["hooks"]["PreToolUse"]
                self.assertTrue(any(
                    item.get("matcher") == original_matcher
                    and any(sub.get("command") == "echo user-owned"
                            for sub in item.get("hooks", []))
                    for item in groups
                ), "normalization removed an unrelated user handler")
                owned = [
                    (item, sub)
                    for item in groups for sub in item.get("hooks", [])
                    if isinstance(sub, dict) and sub.get("command") == hook
                ]
                self.assertEqual(len(owned), 1)
                self.assertEqual(owned[0][0].get("matcher"), "Bash")

    def test_if_filtered_handler_is_normalized_and_other_handlers_survive(self):
        hook = os.path.join(self.home, GUARDRAIL)
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": hook,
                        "if": "Bash(git status)",
                    },
                    {"type": "command", "command": "echo user-owned"},
                ],
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        self.assertTrue(any(
            group.get("matcher") == "Bash"
            and any(sub.get("command") == "echo user-owned" for sub in group.get("hooks", []))
            for group in groups
        ), "registration dropped an unrelated hook")
        owned = [
            (group, sub)
            for group in groups for sub in group.get("hooks", [])
            if sub.get("command") == hook
        ]
        self.assertEqual(len(owned), 1, "normalization left duplicate guardrail handlers")
        self.assertNotIn("if", owned[0][1], "filtered Sadskill handler was not normalized")
        self.assertTrue(any(
            group.get("matcher") == "Bash"
            and any(
                sub.get("command") == hook and not sub.get("if")
                for sub in group.get("hooks", [])
            )
            for group in groups
        ), "registration failed to add an unrestricted Bash handler")

    def test_explicit_null_matcher_and_if_are_not_unrestricted(self):
        hook = os.path.join(self.home, GUARDRAIL)
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": None,
                "hooks": [{"type": "command", "command": hook, "if": None}],
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        self.assertTrue(any(
            group.get("matcher") == "Bash"
            and any(
                sub.get("command") == hook and "if" not in sub
                for sub in group.get("hooks", [])
            )
            for group in groups
        ), "explicit null values incorrectly suppressed a known-good Bash handler")

    def test_explicit_empty_if_is_not_assumed_unrestricted(self):
        hook = os.path.join(self.home, GUARDRAIL)
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": hook, "if": ""}],
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        groups = self._load()["hooks"]["PreToolUse"]
        self.assertTrue(any(
            group.get("matcher") == "Bash"
            and any(
                sub.get("command") == hook and "if" not in sub
                for sub in group.get("hooks", [])
            )
            for group in groups
        ), "explicit empty if was treated as an unfiltered handler")

    def test_same_basename_external_hook_is_not_claimed_or_removed(self):
        external = os.path.join(self.home, ".other-tool", "git-guardrail.sh")
        os.makedirs(os.path.dirname(external), exist_ok=True)
        with open(external, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": external}],
            }]}}, fh)

        enabled = self._enable()
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        settings = self._load()
        hooks = settings["hooks"]["PreToolUse"]
        commands = [
            sub.get("command")
            for group in hooks if isinstance(group, dict)
            for sub in group.get("hooks", []) if isinstance(sub, dict)
        ]
        self.assertIn(external, commands)
        self.assertIn(os.path.join(self.home, GUARDRAIL), commands)

        disabled = self._disable()
        self.assertEqual(disabled.returncode, 0, disabled.stdout + disabled.stderr)
        commands_after = [
            sub.get("command")
            for group in self._load()["hooks"]["PreToolUse"]
            if isinstance(group, dict)
            for sub in group.get("hooks", []) if isinstance(sub, dict)
        ]
        self.assertIn(external, commands_after)
        self.assertNotIn(os.path.join(self.home, GUARDRAIL), commands_after)

    def test_hook_path_as_an_unrelated_command_argument_is_not_owned(self):
        hook = os.path.join(self.home, GUARDRAIL)
        unrelated_command = f"/bin/echo {hook}"
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": unrelated_command}],
            }]}}, fh)

        rc = self._disable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        commands = [
            sub.get("command")
            for group in self._load()["hooks"]["PreToolUse"]
            for sub in group.get("hooks", [])
        ]
        self.assertIn(unrelated_command, commands)

    def test_disable_hooks_is_ownership_aware(self):
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        rc = self._enable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        rc = self._disable()
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        settings = self._load()
        self.assertEqual(settings.get("model"), "opus")
        self.assertIn("Stop", settings.get("hooks", {}),
                      "user's unrelated hook destroyed by unregistration")
        pre = settings.get("hooks", {}).get("PreToolUse", [])
        self.assertFalse(
            [e for e in pre
             if any("git-guardrail" in h.get("command", "")
                    for h in e.get("hooks", []))],
            "sadskill hook survived --disable-hooks",
        )

    def test_labels_are_truthful(self):
        """No hook status may ever claim ACTIVE from a local simulation."""
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.user_settings, fh)
        self._enable()
        rc = self.run_doctor("--json")
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        report = json.loads(rc.stdout)
        status = report.get("claude_hook", {}).get("status")
        self.assertNotEqual(status, "HOST_VERIFIED_ACTIVE",
                            "local diagnostic claimed host activation without confirmation")
        allowed = {
            "NOT_INSTALLED", "AVAILABLE", "REGISTERED",
            "LOCAL_TEST_PASSED", "HOST_VERIFIED_ACTIVE", "UNKNOWN",
        }
        self.assertIn(status, allowed, f"untruthful hook status: {status!r}")

    def test_host_verified_status_requires_explicit_confirmation_flag(self):
        hook = os.path.join(self.home, GUARDRAIL)
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"PreToolUse": [{
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": hook}],
            }]}}, fh)

        ordinary = self.run_doctor("--json")
        confirmed = self.run_doctor("--confirm-active", "--json")
        self.assertEqual(ordinary.returncode, 0, ordinary.stdout + ordinary.stderr)
        self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
        self.assertEqual(json.loads(ordinary.stdout)["claude_hook"]["status"], "LOCAL_TEST_PASSED")
        self.assertEqual(json.loads(confirmed.stdout)["claude_hook"]["status"], "HOST_VERIFIED_ACTIVE")


if __name__ == "__main__":
    unittest.main()
