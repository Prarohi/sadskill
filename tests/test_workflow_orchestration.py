"""Contract tests for cross-mode permissions and proportional verification.

These test *documentation invariants*, not live-agent behavior.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "sadskill"


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class WorkflowOrchestrationContracts(unittest.TestCase):
    def test_version_contract_is_current(self):
        version = read("VERSION").strip()
        router = read("skills/sadskill/SKILL.md")
        self.assertIn(f"version: {version}", router)

    def test_router_loads_shared_workflow(self):
        router = read("skills/sadskill/SKILL.md")
        self.assertIn("protocols/workflow.md", router)
        self.assertIn("execution contract and permissions first", router)
        for name in ("plan", "design", "backend", "security", "analyze"):
            self.assertTrue((SKILL / "modes" / (name + ".md")).is_file())

    def test_read_only_does_not_write_evidence(self):
        workflow = read("skills/sadskill/protocols/workflow.md")
        evidence = read("skills/sadskill/protocols/evidence.md")
        router = read("skills/sadskill/SKILL.md")
        self.assertIn("REVIEW_ONLY", workflow)
        self.assertIn("Any writes", workflow)
        self.assertIn("REVIEW_ONLY", evidence)
        self.assertIn("must **never** be written", evidence)
        self.assertIn("writes nothing", router)

    def test_sensitive_one_file_tasks_are_t2(self):
        workflow = read("skills/sadskill/protocols/workflow.md")
        self.assertIn("even if only **one** file changes", workflow)
        for risk in ("auth", "payments", "tenant isolation", "schema migrations"):
            self.assertIn(risk, workflow)
        self.assertIn("risk-first", workflow.lower())

    def test_multimode_permission_boundaries(self):
        workflow = read("skills/sadskill/protocols/workflow.md")
        autonomy = read("skills/sadskill/protocols/autonomy.md")
        for mode in ("REVIEW_ONLY", "PLAN_ONLY", "IMPLEMENT", "CONTINUE_UNTIL_DONE"):
            self.assertIn(mode, workflow)
            self.assertIn(mode, autonomy)
        self.assertIn("audit phase remains read-only", workflow)
        self.assertIn("required reviews", workflow)
        self.assertIn("workflow.md", autonomy)

    def test_verification_status_truthfulness(self):
        workflow = read("skills/sadskill/protocols/workflow.md")
        evidence = read("skills/sadskill/protocols/evidence.md")
        for state in ("NOT_EXECUTED", "SKIPPED_WITH_REASON", "VERIFIED"):
            self.assertIn(state, workflow)
        self.assertIn("NOT_EXECUTED", evidence)
        self.assertIn("relevant checks", read("skills/sadskill/SKILL.md"))

    def test_no_unconditional_full_suite_preflight(self):
        autonomy = read("skills/sadskill/protocols/autonomy.md")
        self.assertIn("Proportional Baseline Discovery", autonomy)
        self.assertIn("full-suite preflight is not mandatory", autonomy)


if __name__ == "__main__":
    unittest.main()
