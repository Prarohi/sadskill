from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestModeContracts(unittest.TestCase):
    def test_plan_mode_contract(self):
        plan_path = REPO_ROOT / "skills" / "sadskill" / "modes" / "plan.md"
        self.assertTrue(plan_path.exists())
        text = plan_path.read_text(encoding="utf-8")
        self.assertIn("T0: Trivial", text)
        self.assertIn("Tier 1: Surgical Plan", text)
        self.assertIn("Tier 2: Deep Architectural Spec", text)
        self.assertIn("Contract-First AST Signatures", text)
        self.assertIn("Mermaid", text)

    def test_design_mode_contract(self):
        design_path = REPO_ROOT / "skills" / "sadskill" / "modes" / "design.md"
        self.assertTrue(design_path.exists())
        text = design_path.read_text(encoding="utf-8")
        self.assertIn("Zero-Lift", text)
        self.assertIn("scale(0.97)", text)
        self.assertIn("WCAG", text)
        self.assertIn("44px", text)
        self.assertIn("Truthful Visual Verification & Tooling Disclosure", text)

    def test_backend_mode_contract(self):
        backend_path = REPO_ROOT / "skills" / "sadskill" / "modes" / "backend.md"
        self.assertTrue(backend_path.exists())
        text = backend_path.read_text(encoding="utf-8")
        self.assertIn("up.sql", text)
        self.assertIn("down.sql", text)
        self.assertIn("Row Level Security", text)
        self.assertIn("timestamptz", text)
        self.assertIn("Database Engine Discovery", text)

    def test_security_mode_contract(self):
        sec_path = REPO_ROOT / "skills" / "sadskill" / "modes" / "security.md"
        self.assertTrue(sec_path.exists())
        text = sec_path.read_text(encoding="utf-8")
        self.assertIn("Strictly Read-Only", text)
        self.assertIn("OWASP Top 10", text)
        self.assertIn("Secrets", text)
        self.assertIn("Redaction", text)

    def test_analyze_mode_contract(self):
        analyze_path = REPO_ROOT / "skills" / "sadskill" / "modes" / "analyze.md"
        self.assertTrue(analyze_path.exists())
        text = analyze_path.read_text(encoding="utf-8")
        self.assertIn("Truthful Coverage & Honest Accounting", text)
        self.assertIn("PARTIAL_COVERAGE", text)
        self.assertIn("Ousterhout", text)
        self.assertIn("file:line", text)


if __name__ == "__main__":
    unittest.main()
