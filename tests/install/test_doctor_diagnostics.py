"""Doctor must distinguish usable local artifacts from incomplete installs."""

import json
from pathlib import Path
import shutil
import unittest

from tests.helpers import REPO_ROOT, SandboxCase


COMMANDS = ("sad-plan", "sad-design", "sad-backend", "sad-sec", "sad-analyze")
SKILL = "---\nname: sadskill\ndescription: Test skill\n---\n# sadskill\n"


class DoctorDiagnosticsTests(SandboxCase):
    def report(self, *args):
        result = self.run_doctor("--json", "--target", self.project, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def registered_hook(self, content=None):
        hook = Path(self.home) / ".claude/hooks/git-guardrail.sh"
        if content is not None:
            self.write_file(self.home, ".claude/hooks/git-guardrail.sh", content)
        self.write_file(self.home, ".claude/settings.json", json.dumps({
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": str(hook)}
            ]}]}
        }))
        return hook

    def test_confirmation_cannot_override_missing_or_failed_hook(self):
        for content in (None, "#!/bin/sh\nexit 1\n"):
            with self.subTest(content=content):
                self.registered_hook(content)
                result = self.report("--confirm-active")["claude_hook"]
                self.assertEqual(result["status"], "REGISTERED", result)

    def test_successful_local_hook_still_requires_host_confirmation(self):
        hook = self.registered_hook()
        hook.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(REPO_ROOT) / "scripts/git-guardrail.sh", hook)
        self.assertEqual(self.report()["claude_hook"]["status"], "LOCAL_TEST_PASSED")
        self.assertEqual(self.report("--confirm-active")["claude_hook"]["status"],
                         "HOST_VERIFIED_ACTIVE")

    def test_empty_artifacts_are_partial_not_installed(self):
        self.write_file(self.home, ".codex/skills/sadskill/SKILL.md", "")
        self.write_file(self.home, ".codex/prompts/sad-plan.md", "")
        self.write_file(self.project, ".cursor/skills/sadskill/SKILL.md", "")
        self.write_file(self.project, ".cursor/rules/sadskill.mdc", "")
        self.write_file(self.home, ".gemini/skills/sadskill/SKILL.md", "")
        report = self.report()
        for key in ("codex", "cursor", "antigravity_gemini"):
            with self.subTest(agent=key):
                self.assertEqual(report[key]["status"], "PARTIAL", report[key])

    def test_skill_directory_without_skill_file_is_partial(self):
        for part in (".codex/skills/sadskill", ".gemini/skills/sadskill"):
            (Path(self.home) / part).mkdir(parents=True)
        (Path(self.project) / ".cursor/skills/sadskill").mkdir(parents=True)
        self.write_file(self.project, ".cursor/rules/sadskill.mdc", "# Rule\n")
        for name in COMMANDS:
            self.write_file(self.home, f".codex/prompts/{name}.md", f"# {name}\n")
        report = self.report()
        for key in ("codex", "cursor", "antigravity_gemini"):
            self.assertEqual(report[key]["status"], "PARTIAL", report[key])

    def test_codex_missing_adapter_is_partial_and_complete_artifacts_are_installed(self):
        self.write_file(self.home, ".codex/skills/sadskill/SKILL.md", SKILL)
        for name in COMMANDS[:-1]:
            self.write_file(self.home, f".codex/prompts/{name}.md", f"# {name}\n")
        self.assertEqual(self.report()["codex"]["status"], "PARTIAL")
        self.write_file(self.home, ".codex/prompts/sad-analyze.md", "# sad-analyze\n")
        self.write_file(self.project, ".cursor/skills/sadskill/SKILL.md", SKILL)
        self.write_file(self.project, ".cursor/rules/sadskill.mdc", "# Rule\n")
        self.write_file(self.home, ".gemini/skills/sadskill/SKILL.md", SKILL)
        report = self.report()
        for key in ("codex", "cursor", "antigravity_gemini"):
            self.assertEqual(report[key]["status"], "INSTALLED", report[key])

    def test_gemini_complete_install_is_found_after_partial_antigravity(self):
        (Path(self.home) / ".gemini/antigravity/skills/sadskill").mkdir(parents=True)
        path = self.write_file(self.home, ".gemini/skills/sadskill/SKILL.md", SKILL)
        result = self.report()["antigravity_gemini"]
        self.assertEqual(result["status"], "INSTALLED")
        self.assertIn(str(Path(path).parent), result["details"])


if __name__ == "__main__":
    unittest.main()
