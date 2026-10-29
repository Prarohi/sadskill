from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestSkillRouter(unittest.TestCase):
    def setUp(self):
        self.skill_file = REPO_ROOT / "skills" / "sadskill" / "SKILL.md"

    def test_skill_file_exists(self):
        self.assertTrue(self.skill_file.exists(), "skills/sadskill/SKILL.md must exist")

    def test_frontmatter_metadata(self):
        text = self.skill_file.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---"), "SKILL.md must start with YAML frontmatter")
        self.assertIn("name: sadskill", text)
        self.assertIn("version: " + (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip(), text)

    def test_five_modes_registered_and_linked(self):
        text = self.skill_file.read_text(encoding="utf-8")
        expected_modes = [
            ("modes/plan.md", "/sad-plan"),
            ("modes/design.md", "/sad-design"),
            ("modes/backend.md", "/sad-backend"),
            ("modes/security.md", "/sad-sec"),
            ("modes/analyze.md", "/sad-analyze"),
        ]
        for mode_rel_path, command_slug in expected_modes:
            mode_path = REPO_ROOT / "skills" / "sadskill" / mode_rel_path
            self.assertTrue(mode_path.exists(), f"Mode file {mode_rel_path} must exist on disk")
            self.assertIn(command_slug, text, f"Command {command_slug} must be documented in SKILL.md router")

    def test_progressive_disclosure_pipeline_documented(self):
        text = self.skill_file.read_text(encoding="utf-8")
        self.assertIn("Progressive Disclosure Pipeline", text)
        self.assertIn("Router", text)


if __name__ == "__main__":
    unittest.main()
