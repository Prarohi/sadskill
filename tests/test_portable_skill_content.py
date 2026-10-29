"""Portable skill-content checks that intentionally require no POSIX APIs."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "sadskill" / "SKILL.md"
DOC = ROOT / "docs" / "compatibility.md"


class PortableSkillContentSmoke(unittest.TestCase):
    def test_skill_instruction_exists_and_is_utf8(self):
        self.assertTrue(SKILL.is_file())
        data = SKILL.read_text(encoding="utf-8")
        self.assertGreater(len(data.strip()), 200)
        self.assertIn("sadskill", data.lower())

    def test_protocol_sources_can_be_read_as_utf8(self):
        folder = ROOT / "skills" / "sadskill" / "protocols"
        sources = sorted(folder.glob("*.md"))
        self.assertGreaterEqual(len(sources), 3)
        for source in sources:
            with self.subTest(file=source.name):
                self.assertGreater(len(source.read_text(encoding="utf-8").strip()), 25)

    def test_platform_limits_are_clearly_documented(self):
        page = DOC.read_text(encoding="utf-8")
        self.assertIn("Windows native", page)
        self.assertIn("Unsupported", page)
        self.assertIn("Bubblewrap", page)


if __name__ == "__main__":
    unittest.main()
