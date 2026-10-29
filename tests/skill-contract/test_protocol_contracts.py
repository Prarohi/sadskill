from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestProtocolContracts(unittest.TestCase):
    def test_context_protocol(self):
        path = REPO_ROOT / "skills" / "sadskill" / "protocols" / "context.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("Precedence Hierarchy", text)
        self.assertIn("TaskContext", text)
        self.assertIn("Untrusted Input Defense", text)

    def test_advice_protocol(self):
        path = REPO_ROOT / "skills" / "sadskill" / "protocols" / "advice.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("Critical Safety Warning", text)
        self.assertIn("Elective Guidance", text)
        self.assertIn("Respect Suppression Directives", text)

    def test_autonomy_protocol(self):
        path = REPO_ROOT / "skills" / "sadskill" / "protocols" / "autonomy.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        for mode in ["REVIEW_ONLY", "PLAN_ONLY", "IMPLEMENT", "CONTINUE_UNTIL_DONE"]:
            self.assertIn(mode, text)
        self.assertIn("Hard Stop Triggers", text)
        self.assertIn("Bounded Retries", text)

    def test_research_protocol(self):
        path = REPO_ROOT / "skills" / "sadskill" / "protocols" / "research.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("RESEARCH_OFF", text)
        self.assertIn("RESEARCH_APPROVED", text)
        self.assertIn("Untrusted Data Boundary", text)
        self.assertIn("Honest Offline Degradation", text)

    def test_output_style_protocol(self):
        path = REPO_ROOT / "skills" / "sadskill" / "protocols" / "output-style.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("High Information Density", text)
        self.assertIn("Progressive Disclosure", text)
        self.assertIn("Batched Mutations", text)


if __name__ == "__main__":
    unittest.main()
