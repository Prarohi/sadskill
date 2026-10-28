"""Unit tests for Evidence v2 cryptographic provenance and hash-chain verification."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sadskill_verify_evidence", ROOT / "scripts" / "verify-evidence.py"
)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)

canonical_record_hash = VERIFIER.canonical_record_hash
create_evidence_record = VERIFIER.create_evidence_record
generate_slsa_predicate = VERIFIER.generate_slsa_predicate
verify_evidence = VERIFIER.verify_evidence


class EvidenceV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Initialize a minimal git repository in temp root
        subprocess.run(["git", "init"], cwd=str(self.root), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(self.root), check=True)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=str(self.root), check=True)
        (self.root / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=str(self.root), check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(self.root), check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_verify_single_v2_record(self):
        rec_path = create_evidence_record(
            project_root=self.root,
            task_slug="test-task-1",
            command="echo 'test passed'",
            exit_code=0,
            summary="Verification passed",
            files_touched=["README.md"],
        )
        self.assertTrue(rec_path.exists())
        data = json.loads(rec_path.read_text(encoding="utf-8"))
        self.assertEqual(data["evidence_version"], "2.0")
        self.assertEqual(data["previous_record_hash"], "GENESIS")
        self.assertEqual(data["record_hash"], canonical_record_hash(data))

        code, records = verify_evidence(project_root=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "SCHEMA_VALID")

    def test_multi_record_hash_chain_verification(self):
        create_evidence_record(
            project_root=self.root,
            task_slug="task-step-1",
            command="echo 'step 1'",
            exit_code=0,
            summary="Step 1 complete",
            files_touched=["README.md"],
        )
        create_evidence_record(
            project_root=self.root,
            task_slug="task-step-2",
            command="echo 'step 2'",
            exit_code=0,
            summary="Step 2 complete",
            files_touched=["README.md"],
        )
        create_evidence_record(
            project_root=self.root,
            task_slug="task-step-3",
            command="echo 'step 3'",
            exit_code=0,
            summary="Step 3 complete",
            files_touched=["README.md"],
        )

        code, records = verify_evidence(project_root=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(len(records), 3)

    def test_tampered_record_hash_fails_closed(self):
        rec_path = create_evidence_record(
            project_root=self.root,
            task_slug="tamper-test",
            command="echo 'orig'",
            exit_code=0,
            summary="Original summary",
            files_touched=["README.md"],
        )
        data = json.loads(rec_path.read_text(encoding="utf-8"))
        data["summary"] = "Tampered summary after signature!"
        rec_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        code, records = verify_evidence(project_root=self.root)
        self.assertEqual(code, 1)
        self.assertEqual(records[0]["status"], "FAILED")
        self.assertIn("record_hash mismatch", records[0]["reason"])

    def test_broken_hash_chain_fails_closed(self):
        create_evidence_record(
            project_root=self.root,
            task_slug="chain-1",
            command="echo 1",
            exit_code=0,
            summary="Rec 1",
            files_touched=["README.md"],
        )
        rec2_path = create_evidence_record(
            project_root=self.root,
            task_slug="chain-2",
            command="echo 2",
            exit_code=0,
            summary="Rec 2",
            files_touched=["README.md"],
        )
        data2 = json.loads(rec2_path.read_text(encoding="utf-8"))
        data2["previous_record_hash"] = "0" * 64
        data2["record_hash"] = canonical_record_hash(data2)
        rec2_path.write_text(json.dumps(data2, indent=2), encoding="utf-8")

        code, records = verify_evidence(project_root=self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("broken hash chain" in r.get("reason", "") for r in records))

    def test_slsa_predicate_generation_and_cli(self):
        rec_path = create_evidence_record(
            project_root=self.root,
            task_slug="slsa-test-task",
            command="echo 'verifying slsa provenance'",
            exit_code=0,
            summary="SLSA test completed",
            files_touched=["README.md"],
        )
        data = json.loads(rec_path.read_text(encoding="utf-8"))
        predicate = generate_slsa_predicate(data)

        self.assertEqual(predicate["_type"], "https://in-toto.io/Statement/v1")
        self.assertEqual(predicate["predicateType"], "https://slsa.dev/provenance/v1")
        self.assertEqual(predicate["subject"][0]["name"], "sadskill-evidence-slsa-test-task")
        self.assertIn("sha256", predicate["subject"][0]["digest"])
        self.assertEqual(predicate["predicate"]["buildDefinition"]["buildType"], "https://sadskill.dev/evidence/v2")

        # Test CLI flag --emit-slsa
        res = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify-evidence.py"), "--project-root", str(self.root), "--emit-slsa"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        cli_stmt = json.loads(res.stdout)
        self.assertEqual(cli_stmt["_type"], "https://in-toto.io/Statement/v1")
        self.assertEqual(cli_stmt["predicateType"], "https://slsa.dev/provenance/v1")


if __name__ == "__main__":
    unittest.main()
