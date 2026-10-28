"""Adversarial tests for local evidence provenance and containment."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sadskill_verify_evidence", ROOT / "scripts" / "verify-evidence.py"
)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class EvidenceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sadskill-evidence-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        (self.root / "README.md").write_text("# Evidence fixture\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q", "-m", "fixture"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "remote", "add", "origin",
             "https://github.com/example/sadskill.git"], check=True,
        )
        self.context = {
            "project_id": VERIFIER.project_identity(self.root),
            **VERIFIER.git_context(self.root),
        }
        self.evidence = self.root / ".sad" / "evidence"
        self.evidence.mkdir(parents=True)

    def write_record(self, name="record.json", **overrides):
        data = {
            **self.context,
            "timestamp": "2026-10-28T04:00:00Z",
            "task_slug": "evidence-test",
            "command": "python3 -m unittest discover",
            "exit_code": 0,
            "summary": "one test passed",
            "files_touched": ["README.md"],
        }
        data.update(overrides)
        path = self.evidence / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def verify(self, evidence_dir=None):
        stream = io.StringIO()
        result = VERIFIER.verify_evidence(
            project_root=self.root,
            evidence_dir=evidence_dir,
            log_stream=stream,
        )
        return result, stream.getvalue()

    def test_forged_verified_boolean_is_only_a_claim(self):
        self.write_record(ci_attestation={
            "repository": "example/sadskill",
            "run_url": "https://github.com/example/sadskill/actions/runs/123",
            "head_sha": self.context["commit_sha"],
            "workflow": "CI",
            "verified": True,
        })
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 0, output)
        self.assertEqual(records[0]["status"], "CI_CLAIMED")
        self.assertEqual(records[0]["provenance"], "CI_CLAIMED")
        self.assertNotIn("CI_ATTESTED", output)

    def test_wrong_ci_repository_is_rejected(self):
        self.write_record(ci_attestation={
            "repository": "attacker/other",
            "run_url": "https://github.com/attacker/other/actions/runs/123",
            "head_sha": self.context["commit_sha"],
            "workflow": "CI",
            "verified": True,
        })
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "FAILED")
        self.assertIn("repository does not match", output)

    def test_wrong_ci_sha_is_rejected(self):
        self.write_record(ci_attestation={
            "repository": "example/sadskill",
            "run_url": "https://github.com/example/sadskill/actions/runs/123",
            "head_sha": "0" * 40,
            "workflow": "CI",
            "verified": True,
        })
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "FAILED")
        self.assertIn("does not match evidence commit_sha", output)

    def test_stale_commit_and_wrong_project_identity_fail(self):
        self.write_record(commit_sha="0" * 40)
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "STALE")
        self.assertIn("does not match current HEAD", output)

        self.evidence.joinpath("record.json").unlink()
        self.write_record(project_id="f" * 64)
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "NOT_VERIFIABLE")
        self.assertIn("identity does not match", output)

    def test_dirty_worktree_mismatch_fails(self):
        self.write_record()
        (self.root / "untracked.txt").write_text("changed\n", encoding="utf-8")
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "DIRTY_WORKTREE")
        self.assertIn("dirty-state does not match", output)

    def test_dirty_worktree_content_change_invalidates_bound_record(self):
        readme = self.root / "README.md"
        readme.write_text("# dirty state one\n", encoding="utf-8")
        captured = VERIFIER.git_context(self.root)
        self.assertTrue(captured["worktree_dirty"])
        self.write_record(**captured)

        readme.write_text("# dirty state two\n", encoding="utf-8")
        current = VERIFIER.git_context(self.root)
        self.assertTrue(current["worktree_dirty"])
        self.assertNotEqual(captured["worktree_digest"], current["worktree_digest"])
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "WORKTREE_CHANGED")
        self.assertIn("contents changed after capture", output)

    def test_ignored_pytest_input_changes_bound_snapshot(self):
        gitignore = self.root / ".gitignore"
        gitignore.write_text("test_local.py\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", ".gitignore"],
                       check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q",
             "-m", "ignore local test input"],
            check=True,
        )
        captured = VERIFIER.git_context(self.root)
        self.assertFalse(captured["worktree_dirty"])

        ignored_test = self.root / "test_local.py"
        ignored_test.write_text(
            "def test_local_input():\n    assert True\n", encoding="utf-8"
        )
        current = VERIFIER.git_context(self.root)
        self.assertTrue(current["worktree_dirty"])
        self.assertNotEqual(
            captured["worktree_digest"], current["worktree_digest"]
        )
        self.write_record(**captured)

        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "DIRTY_WORKTREE")
        self.assertIn("dirty-state does not match", output)

    def test_ignored_cargo_manifest_changes_bound_snapshot(self):
        gitignore = self.root / ".gitignore"
        gitignore.write_text("Cargo.toml\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", ".gitignore"],
                       check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q",
             "-m", "ignore local Cargo manifest"],
            check=True,
        )
        captured = VERIFIER.git_context(self.root)
        self.assertFalse(captured["worktree_dirty"])

        (self.root / "Cargo.toml").write_text(
            '[package]\nname = "fixture"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        current = VERIFIER.git_context(self.root)
        self.assertTrue(current["worktree_dirty"])
        self.assertNotEqual(
            captured["worktree_digest"], current["worktree_digest"]
        )

    def test_invalid_calendar_timestamp_fails(self):
        self.write_record(timestamp="2026-02-31T04:00:00Z")
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "FAILED")
        self.assertIn("Invalid timestamp", output)

    def test_evidence_directory_prefix_sibling_is_rejected(self):
        sibling = self.root.parent / "repo-evil" / ".sad" / "evidence"
        sibling.mkdir(parents=True)
        result, output = self.verify(sibling)
        self.assertEqual(result[0], 1)
        self.assertIn("outside project root", output)

    def test_escaping_evidence_symlink_fails(self):
        outside = self.root.parent / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        os.symlink(outside, self.evidence / "escape.json")
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "FAILED")
        self.assertIn("Evidence symlink escapes", output)

    def test_evidence_symlink_to_prefix_sibling_fails(self):
        sibling = self.root.parent / f"{self.root.name}-evil"
        sibling.mkdir()
        outside = sibling / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        os.symlink(outside, self.evidence / "prefix-escape.json")
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "FAILED")
        self.assertIn("Evidence symlink escapes", output)

    def test_oversized_record_is_rejected_before_json_parse(self):
        (self.evidence / "huge.json").write_bytes(b"{" + b" " * (1024 * 1024) + b"}")
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "FAILED")
        self.assertIn("exceeds", output)

    def test_removed_custom_retest_escape_hatch_is_not_accepted(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify-evidence.py"),
             "--project-root", str(self.root), "--allow-custom-retest"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_runner_arguments_cannot_select_paths_outside_checkout(self):
        commands = (
            "python3 -m pytest /tmp/evil.py",
            "python3 -m unittest discover -s /tmp/evil",
            "cargo test --manifest-path /tmp/evil/Cargo.toml",
            "go test /tmp/evil",
            "pytest /tmp/evil.py",
        )
        for command in commands:
            with self.subTest(command=command):
                ok, argv, reason = VERIFIER.resolve_retest_argv(
                    {"command": command}, self.root
                )
                self.assertFalse(ok, (argv, reason))

    def test_malformed_recipe_id_is_reported_without_exception(self):
        for recipe_id in (["python-pytest"], {"name": "python-pytest"}, ""):
            with self.subTest(recipe_id=recipe_id):
                ok, argv, reason = VERIFIER.resolve_retest_argv(
                    {"recipe_id": recipe_id, "command": "python3 -m pytest"},
                    self.root,
                )
                self.assertFalse(ok)
                self.assertEqual(argv, [])
                self.assertIn("expected a non-empty string", reason)

    def test_raw_retest_commands_match_only_fixed_recipe_arguments(self):
        commands = (
            "python3 scripts/verify.py",
            "python3 benchmarks/runner.py",
            "python3 -m pytest",
            "python3 -m unittest discover",
            "cargo test",
            "go test ./...",
            "pytest",
        )
        for command in commands:
            with self.subTest(command=command):
                ok, _argv, reason = VERIFIER.resolve_retest_argv(
                    {"command": command}, self.root
                )
                self.assertTrue(ok, reason)

    def test_timeout_kills_child_process_after_parent_exits(self):
        marker = Path(self.temp.name) / "child-survived-timeout"
        child_code = (
            "import time; time.sleep(1.0); "
            f"open({str(marker)!r}, 'w').write('alive')"
        )
        parent_code = (
            "import subprocess,sys; "
            f"subprocess.Popen([sys.executable, '-c', {child_code!r}])"
        )
        ok, message = VERIFIER.execute_safe_argv(
            self.root, [sys.executable, "-c", parent_code], timeout_seconds=0.1
        )
        self.assertFalse(ok, message)
        time.sleep(1.2)
        self.assertFalse(marker.exists(), "timed-out child process was left running")


if __name__ == "__main__":
    unittest.main()
