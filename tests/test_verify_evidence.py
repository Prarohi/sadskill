"""Adversarial tests for local evidence provenance and containment."""

import importlib.util
import io
import json
import os
import shlex
import shutil
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

    def test_git_index_hints_do_not_hide_changed_worktree_bytes(self):
        readme = self.root / "README.md"
        original = readme.read_bytes()
        for hint in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(hint=hint):
                readme.write_bytes(original)
                subprocess.run(["git", "-C", str(self.root), "update-index", hint,
                                "README.md"], check=True)
                captured = VERIFIER.git_context(self.root)
                self.write_record(**captured)
                readme.write_text("changed behind the Git index hint\n")
                (code, records), output = self.verify()
                self.assertEqual(code, 1, output)
                self.assertIn(records[0]["status"], {"WORKTREE_CHANGED", "DIRTY_WORKTREE"})
                subprocess.run(["git", "-C", str(self.root), "update-index",
                                "--no-assume-unchanged", "--no-skip-worktree", "README.md"],
                               check=True)

    def test_missing_tracked_file_is_a_bound_snapshot_state(self):
        readme = self.root / "README.md"
        original = readme.read_bytes()
        for hint in (None, "--assume-unchanged", "--skip-worktree"):
            with self.subTest(hint=hint):
                readme.write_bytes(original)
                if hint:
                    subprocess.run(
                        ["git", "-C", str(self.root), "update-index", hint,
                         "README.md"], check=True,
                    )
                try:
                    captured = VERIFIER.git_context(self.root)
                    readme.unlink()
                    current = VERIFIER.git_context(self.root)
                    self.assertIsNotNone(current)
                    self.assertNotEqual(captured["worktree_digest"],
                                        current["worktree_digest"])
                    self.assertEqual(current, VERIFIER.git_context(self.root))
                    self.write_record(**captured)
                    (code, records), output = self.verify()
                    self.assertEqual(code, 1, output)
                    self.assertIn(records[0]["status"],
                                  {"WORKTREE_CHANGED", "DIRTY_WORKTREE"})
                finally:
                    readme.write_bytes(original)
                    subprocess.run(
                        ["git", "-C", str(self.root), "update-index",
                         "--no-assume-unchanged", "--no-skip-worktree",
                         "README.md"], check=True,
                    )

    def test_staged_deletion_does_not_hide_ignored_remaining_bytes(self):
        (self.root / ".git/info/exclude").write_text("README.md\n")
        subprocess.run(
            ["git", "-C", str(self.root), "rm", "-q", "--cached",
             "README.md"], check=True,
        )
        captured = VERIFIER.git_context(self.root)
        self.assertIsNotNone(captured)
        self.assertTrue(captured["worktree_dirty"])
        self.write_record(**captured)
        (self.root / "README.md").write_text("changed after staged deletion\n")
        current = VERIFIER.git_context(self.root)
        self.assertNotEqual(captured["worktree_digest"],
                            current["worktree_digest"])
        (code, records), output = self.verify()
        self.assertEqual(code, 1, output)
        self.assertEqual(records[0]["status"], "WORKTREE_CHANGED")

    def test_tracked_evidence_files_remain_outside_snapshot(self):
        tracked = self.evidence / "tracked.json"
        tracked.write_text("{}\n")
        subprocess.run(["git", "-C", str(self.root), "add", ".sad/evidence"],
                       check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q",
             "-m", "tracked evidence fixture"], check=True,
        )
        captured = VERIFIER.git_context(self.root)
        tracked.write_text('{"changed":true}\n')
        (self.evidence / "new.json").write_text("{}\n")
        self.assertEqual(captured, VERIFIER.git_context(self.root))

    def test_tracked_parent_symlink_makes_snapshot_unavailable(self):
        directory = self.root / "tracked-input"
        directory.mkdir()
        (directory / "input.txt").write_text("tracked bytes\n")
        subprocess.run(["git", "-C", str(self.root), "add", "tracked-input"],
                       check=True)
        outside = self.root.parent / "outside-input"
        outside.mkdir()
        (outside / "input.txt").write_text("outside bytes\n")
        shutil.rmtree(directory)
        directory.symlink_to(outside, target_is_directory=True)
        self.assertIsNone(VERIFIER.git_context(self.root))

    def test_escaping_tracked_symlink_cannot_verify_external_test_bytes(self):
        outside = self.root.parent / "external-test.py"
        outside.write_text("def test_logic():\n    assert True\n")
        link = self.root / "test_logic.py"
        link.symlink_to(outside)
        subprocess.run(["git", "-C", str(self.root), "add", link.name],
                       check=True)
        captured = VERIFIER.git_context(self.root)
        self.write_record(**(captured or self.context))
        outside.write_text("def test_logic():\n    assert False\n")
        (code, records), output = self.verify()
        self.assertEqual(code, 1, output)
        self.assertEqual(records[0]["status"], "NOT_VERIFIABLE")
        self.assertIsNone(VERIFIER.git_context(self.root))

    def test_internal_symlink_binds_otherwise_ignored_target_bytes(self):
        target = self.root / "opaque-input.dat"
        target.write_bytes(b"test input before")
        (self.root / ".git/info/exclude").write_text(target.name + "\n")
        link = self.root / "test_logic.py"
        link.symlink_to(target.name)
        subprocess.run(["git", "-C", str(self.root), "add", link.name],
                       check=True)
        captured = VERIFIER.git_context(self.root)
        self.assertIsNotNone(captured)
        self.write_record(**captured)
        target.write_bytes(b"test input after")
        current = VERIFIER.git_context(self.root)
        self.assertIsNotNone(current)
        self.assertNotEqual(captured["worktree_digest"],
                            current["worktree_digest"])
        (code, records), output = self.verify()
        self.assertEqual(code, 1, output)
        self.assertEqual(records[0]["status"], "WORKTREE_CHANGED")

    def test_unsupported_worktree_symlink_targets_fail_closed(self):
        directory = self.root / "directory-target"
        directory.mkdir()
        evidence_target = self.evidence / "target.json"
        evidence_target.write_text("{}")
        link = self.root / "test_logic.py"
        for target in (directory, self.root / "missing-target", link,
                       evidence_target):
            with self.subTest(target=target):
                link.symlink_to(target)
                try:
                    self.assertIsNone(VERIFIER.git_context(self.root))
                finally:
                    link.unlink()

    def test_context_capture_never_executes_configured_diff_drivers(self):
        marker = self.root.parent / "diff-driver-executed"
        driver = self.root / ".git" / "untrusted-diff.py"
        driver.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('EXECUTED')\n"
            "print('untrusted conversion output')\n"
        )
        (self.root / ".gitattributes").write_text("README.md diff=untrusted\n")
        subprocess.run(["git", "-C", str(self.root), "add", ".gitattributes"],
                       check=True)
        (self.root / "README.md").write_text("changed file for diff drivers\n")
        command = shlex.join([sys.executable, str(driver)])
        for setting in ("textconv", "command"):
            subprocess.run(
                ["git", "-C", str(self.root), "config",
                 f"diff.untrusted.{setting}", command], check=True,
            )
            try:
                for capture in ("git_context", "print-context"):
                    with self.subTest(setting=setting, capture=capture):
                        marker.unlink(missing_ok=True)
                        if capture == "git_context":
                            self.assertIsNotNone(VERIFIER.git_context(self.root))
                        else:
                            result = subprocess.run(
                                [sys.executable, str(ROOT / "scripts/verify-evidence.py"),
                                 "--project-root", str(self.root), "--print-context"],
                                capture_output=True, text=True,
                            )
                            self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertFalse(marker.exists(),
                                         "context capture executed a Git diff driver")
            finally:
                subprocess.run(
                    ["git", "-C", str(self.root), "config", "--unset",
                     f"diff.untrusted.{setting}"], check=True,
                )

    def test_context_capture_never_executes_configured_fsmonitor(self):
        marker = self.root.parent / "fsmonitor-executed"
        monitor = self.root / ".git" / "untrusted-monitor.py"
        monitor.write_text(
            f"#!{sys.executable}\nfrom pathlib import Path\nimport sys\n"
            f"Path({str(marker)!r}).write_text('EXECUTED')\n"
            "sys.stdout.buffer.write(b'token\\0')\n"
        )
        monitor.chmod(0o700)
        subprocess.run(["git", "-C", str(self.root), "config", "core.fsmonitor",
                        str(monitor)], check=True)
        config_before = (self.root / ".git/config").read_bytes()
        for capture in ("git_context", "print-context"):
            with self.subTest(capture=capture):
                marker.unlink(missing_ok=True)
                if capture == "git_context":
                    context = VERIFIER.git_context(self.root)
                    self.assertFalse(marker.exists(), "snapshot executed fsmonitor")
                    self.assertIsNotNone(context)
                else:
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "scripts/verify-evidence.py"),
                         "--project-root", str(self.root), "--print-context"],
                        capture_output=True, text=True,
                    )
                    self.assertFalse(marker.exists(), "CLI snapshot executed fsmonitor")
                    self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.root / ".git/config").read_bytes(), config_before)

    def test_context_capture_never_executes_configured_content_filters(self):
        marker = self.root.parent / "content-filter-executed"
        driver = self.root / ".git" / "untrusted-filter.py"
        driver.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('EXECUTED')\n"
        )
        (self.root / ".gitattributes").write_text("README.md filter=untrusted\n")
        subprocess.run(["git", "-C", str(self.root), "add", ".gitattributes"],
                       check=True)
        (self.root / "README.md").write_text("changed file for content filters\n")
        command = shlex.join([sys.executable, str(driver)])
        subprocess.run(["git", "-C", str(self.root), "config",
                        "filter.untrusted.required", "true"], check=True)
        for setting in ("clean", "process"):
            subprocess.run(["git", "-C", str(self.root), "config",
                            f"filter.untrusted.{setting}", command], check=True)
            config_before = (self.root / ".git/config").read_bytes()
            try:
                for capture in ("git_context", "print-context"):
                    with self.subTest(setting=setting, capture=capture):
                        marker.unlink(missing_ok=True)
                        if capture == "git_context":
                            context = VERIFIER.git_context(self.root)
                            self.assertFalse(marker.exists(), "snapshot executed a content filter")
                            self.assertIsNotNone(context)
                        else:
                            result = subprocess.run(
                                [sys.executable, str(ROOT / "scripts/verify-evidence.py"),
                                 "--project-root", str(self.root), "--print-context"],
                                capture_output=True, text=True,
                            )
                            self.assertFalse(marker.exists(), "CLI snapshot executed a content filter")
                            self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual((self.root / ".git/config").read_bytes(), config_before)
            finally:
                subprocess.run(["git", "-C", str(self.root), "config", "--unset",
                                f"filter.untrusted.{setting}"], check=True)

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

    def test_ignored_go_fixtures_and_cargo_config_change_bound_snapshot(self):
        gitignore = self.root / ".gitignore"
        gitignore.write_text(
            ".cargo/config.toml\ntestdata/case.json\n"
            "tests/build/test_local.py\nrust-toolchain\n"
            "rust-toolchain.toml\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.root), "add", ".gitignore"],
                       check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q",
             "-m", "ignore local test inputs"],
            check=True,
        )
        captured = VERIFIER.git_context(self.root)
        for relative, content in (
                (".cargo/config.toml", "[build]\njobs = 1\n"),
                ("testdata/case.json", '{"case":1}\n'),
                ("tests/build/test_local.py", "def test_nested_build_path(): pass\n"),
                ("rust-toolchain", "1.85.0\n"),
                ("rust-toolchain.toml", "[toolchain]\nchannel = \"stable\"\n")):
            with self.subTest(path=relative):
                path = self.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                current = VERIFIER.git_context(self.root)
                self.assertIsNotNone(current)
                self.assertTrue(current["worktree_dirty"])
                self.assertNotEqual(
                    captured["worktree_digest"], current["worktree_digest"]
                )

    def _add_test_submodule(self):
        submodule_source = Path(self.temp.name) / "submodule-source"
        submodule_source.mkdir()
        (submodule_source / "test_local.py").write_text(
            "def test_submodule_input():\n    assert True\n", encoding="utf-8"
        )
        subprocess.run(["git", "init", "-q", str(submodule_source)], check=True)
        subprocess.run(
            ["git", "-C", str(submodule_source), "add", "test_local.py"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(submodule_source), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q",
             "-m", "submodule fixture"],
            check=True,
        )
        subprocess.run(
            ["git", "-c", "protocol.file.allow=always", "-C", str(self.root),
             "submodule", "add", str(submodule_source), "test-submodule"],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(["git", "-C", str(self.root), "add", ".gitmodules",
                        "test-submodule"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q",
             "-m", "add test submodule"],
            check=True,
        )
        return self.root / "test-submodule" / "test_local.py"

    def test_dirty_submodule_worktree_changes_bound_snapshot(self):
        test_file = self._add_test_submodule()
        captured = VERIFIER.git_context(self.root)
        self.assertIsNotNone(captured)
        self.assertFalse(captured["worktree_dirty"])
        test_file.write_text(
            "def test_submodule_input():\n    assert False\n", encoding="utf-8"
        )
        current = VERIFIER.git_context(self.root)
        self.assertIsNotNone(current)
        self.assertTrue(current["worktree_dirty"])
        self.assertNotEqual(
            captured["worktree_digest"], current["worktree_digest"]
        )

        self.write_record(**captured)
        (exit_code, records), output = self.verify()
        self.assertEqual(exit_code, 1)
        self.assertEqual(records[0]["status"], "DIRTY_WORKTREE")
        self.assertIn("dirty-state does not match", output)

    def test_parent_snapshot_does_not_run_submodule_content_filters(self):
        test_file = self._add_test_submodule()
        marker = self.root.parent / "submodule-filter-executed"
        driver = self.root / ".git" / "untrusted-submodule-filter.py"
        driver.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('EXECUTED')\n"
        )
        (test_file.parent / ".gitattributes").write_text(
            test_file.name + " filter=untrusted\n"
        )
        subprocess.run(
            ["git", "-C", str(test_file.parent), "add", ".gitattributes"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(test_file.parent), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q",
             "-m", "submodule attributes fixture"], check=True,
        )
        subprocess.run(["git", "-C", str(self.root), "add", "test-submodule"],
                       check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Sadskill Tests",
             "-c", "user.email=tests@example.invalid", "commit", "-q",
             "-m", "record submodule attributes fixture"], check=True,
        )
        test_file.write_text("def test_submodule_input():\n    assert 0==1\n")
        command = shlex.join([sys.executable, str(driver)])
        for setting in ("clean", "process"):
            subprocess.run(
                ["git", "-C", str(test_file.parent), "config",
                 f"filter.untrusted.{setting}", command], check=True,
            )
            try:
                with self.subTest(setting=setting):
                    marker.unlink(missing_ok=True)
                    context = VERIFIER.git_context(self.root)
                    self.assertFalse(marker.exists(),
                                     "parent snapshot executed a submodule filter")
                    self.assertIsNotNone(context)
            finally:
                subprocess.run(
                    ["git", "-C", str(test_file.parent), "config", "--unset",
                     f"filter.untrusted.{setting}"], check=True,
                )

    def test_submodule_index_hint_does_not_hide_changed_bytes(self):
        test_file = self._add_test_submodule()
        subprocess.run(
            ["git", "-C", str(test_file.parent), "update-index",
             "--skip-worktree", test_file.name], check=True,
        )
        captured = VERIFIER.git_context(self.root)
        self.assertIsNotNone(captured)
        self.write_record(**captured)
        test_file.write_text("def test_submodule_input():\n    assert False\n")
        current = VERIFIER.git_context(self.root)
        self.assertIsNotNone(current)
        self.assertNotEqual(captured["worktree_digest"],
                            current["worktree_digest"])
        (code, records), output = self.verify()
        self.assertEqual(code, 1, output)
        self.assertEqual(records[0]["status"], "WORKTREE_CHANGED")

    def test_missing_or_edited_gitmodules_cannot_hide_gitlinks(self):
        test_file = self._add_test_submodule()
        gitmodules = self.root / ".gitmodules"
        original_config = gitmodules.read_bytes()
        test_file.write_text(
            "def test_submodule_input():\n    assert False\n", encoding="utf-8"
        )

        gitmodules.unlink()
        self.assertIsNone(VERIFIER.git_context(self.root))

        gitmodules.write_bytes(original_config)
        self.assertIsNotNone(VERIFIER.git_context(self.root))
        gitmodules.write_text("", encoding="utf-8")
        self.assertIsNone(VERIFIER.git_context(self.root))

    def test_conflicted_gitlink_index_is_unavailable(self):
        test_file = self._add_test_submodule()
        submodule_sha = subprocess.run(
            ["git", "-C", str(test_file.parent), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        blob_sha = subprocess.run(
            ["git", "-C", str(self.root), "hash-object", "-w", "--stdin"],
            check=True, capture_output=True, text=True,
            input="regular file at a conflicting path\n",
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(self.root), "update-index", "--force-remove",
             "test-submodule"], check=True,
        )
        conflict_entries = (
            f"160000 {submodule_sha} 1\ttest-submodule\0"
            f"100644 {blob_sha} 2\ttest-submodule\0"
        ).encode("ascii")
        subprocess.run(
            ["git", "-C", str(self.root), "update-index", "-z",
             "--index-info"], input=conflict_entries, check=True,
        )
        self.assertIsNone(VERIFIER.git_context(self.root))

    def test_conflicted_regular_index_is_unavailable(self):
        blob_shas = []
        for content in ("stage one content\n", "stage two content\n"):
            blob_shas.append(subprocess.run(
                ["git", "-C", str(self.root), "hash-object", "-w", "--stdin"],
                check=True, capture_output=True, text=True, input=content,
            ).stdout.strip())
        subprocess.run(
            ["git", "-C", str(self.root), "update-index", "--force-remove",
             "README.md"], check=True,
        )
        conflict_entries = (
            f"100644 {blob_shas[0]} 1\tREADME.md\0"
            f"100644 {blob_shas[1]} 2\tREADME.md\0"
        ).encode("ascii")
        subprocess.run(
            ["git", "-C", str(self.root), "update-index", "-z",
             "--index-info"], input=conflict_entries, check=True,
        )
        self.assertIsNone(VERIFIER.git_context(self.root))

    def test_uninitialized_submodule_makes_snapshot_unavailable(self):
        self._add_test_submodule()
        shutil.rmtree(self.root / "test-submodule")
        self.assertIsNone(VERIFIER.git_context(self.root))

    def test_dangling_gitmodules_symlink_makes_snapshot_unavailable(self):
        (self.root / ".gitmodules").symlink_to(
            self.root.parent / "missing-gitmodules-target"
        )
        self.assertIsNone(VERIFIER.worktree_snapshot(self.root))

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
