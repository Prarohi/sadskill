import json
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestChangeContractTemplate(unittest.TestCase):
    def setUp(self):
        self.json_template = REPO_ROOT / "skills" / "sadskill" / "templates" / "change-contract.template.json"
        self.md_template = REPO_ROOT / "skills" / "sadskill" / "templates" / "change-contract.template.md"

    def test_json_template_exists_and_is_valid(self):
        self.assertTrue(self.json_template.exists(), "change-contract.template.json must exist")
        data = json.loads(self.json_template.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_json_template_has_required_schema_fields(self):
        data = json.loads(self.json_template.read_text(encoding="utf-8"))
        required_fields = [
            "contract_id",
            "created_at",
            "intent",
            "scope",
            "constraints",
            "risk",
            "assumptions",
            "verification",
            "rollback",
            "status",
        ]
        for field in required_fields:
            self.assertIn(field, data, f"Missing required field '{field}' in change-contract JSON template")

    def test_json_template_risk_evaluation_fields(self):
        data = json.loads(self.json_template.read_text(encoding="utf-8"))
        risk = data.get("risk", {})
        for key in ["tier", "blast_radius", "reversibility", "data_sensitivity"]:
            self.assertIn(key, risk, f"Missing risk sub-key '{key}'")

    def test_markdown_template_matches_contract_sections(self):
        self.assertTrue(self.md_template.exists(), "change-contract.template.md must exist")
        content = self.md_template.read_text(encoding="utf-8")
        expected_sections = [
            "Intent & Concrete Outcome",
            "Scope & Files Touched",
            "Risk Assessment & Tiering",
            "Contract-First AST Signatures",
            "Verification Harness",
            "Rollback & Reversal Strategy",
        ]
        for section in expected_sections:
            self.assertIn(section, content, f"Missing expected section '{section}' in markdown template")


if __name__ == "__main__":
    unittest.main()
