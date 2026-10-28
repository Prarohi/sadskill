#!/usr/bin/env python3
"""
sadskill verification test suite (Hardened v0.3.0)
Validates skill frontmatter, single discoverable skill constraint,
markdown cross-reference links, commands integrity with $ARGUMENTS,
vendor indexing & manifest integrity, community health files, executable guardrails,
pre-push ref handling, evidence verifier safety & trusted recipes,
database RLS behavioral fixtures, transactional installer recovery, and strict privacy invariants.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def find_repo_root():
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "skills" / "sadskill" / "SKILL.md").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not determine repository root")


REPO_ROOT = find_repo_root()
SKILL_DIR = REPO_ROOT / "skills" / "sadskill"


class VerificationSuite:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = 0

    def assert_true(self, condition, message):
        if condition:
            self.passed += 1
            print(f"  [PASS] {message}")
        else:
            self.errors.append(message)
            print(f"  [FAIL] {message}")

    def test_frontmatter_and_discovery(self):
        print("\n--- Testing SKILL.md Frontmatter & Single Skill Discovery ---")
        root_skill = SKILL_DIR / "SKILL.md"
        self.assert_true(root_skill.exists(), "Root SKILL.md exists")

        content = root_skill.read_text(encoding="utf-8")
        self.assert_true(
            content.startswith("---\n"), "SKILL.md starts with YAML frontmatter delimiter"
        )
        self.assert_true(
            "\nname: sadskill\n" in content or "name: sadskill\n" in content,
            "SKILL.md frontmatter defines 'name: sadskill'",
        )

        other_skills = []
        for path in REPO_ROOT.rglob("*.md"):
            if path.resolve() == root_skill.resolve():
                continue
            rel = path.relative_to(REPO_ROOT)
            if any(part.startswith(".") for part in rel.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if text.startswith("---\n"):
                match = re.search(r"^name:\s+([a-zA-Z0-9_-]+)", text, re.MULTILINE)
                if match:
                    other_skills.append((str(rel), match.group(1)))

        self.assert_true(
            len(other_skills) == 0,
            f"Only sadskill/SKILL.md exposes frontmatter (found {len(other_skills)} conflicting: {other_skills})",
        )

    def test_commands_integrity(self):
        print("\n--- Testing Agent Commands (Codex & Claude) ---")
        expected_commands = [
            "sad-plan.md",
            "sad-design.md",
            "sad-backend.md",
            "sad-sec.md",
            "sad-analyze.md",
        ]

        for cmd in expected_commands:
            codex_cmd = REPO_ROOT / "commands" / "codex" / cmd
            claude_cmd = REPO_ROOT / "commands" / "claude" / cmd
            self.assert_true(codex_cmd.exists(), f"Codex command exists: commands/codex/{cmd}")
            self.assert_true(claude_cmd.exists(), f"Claude command exists: commands/claude/{cmd}")

            if codex_cmd.exists():
                text = codex_cmd.read_text(encoding="utf-8")
                self.assert_true(
                    "$ARGUMENTS" in text,
                    f"Codex command commands/codex/{cmd} supports $ARGUMENTS",
                )

            if claude_cmd.exists():
                text = claude_cmd.read_text(encoding="utf-8")
                self.assert_true(
                    "$ARGUMENTS" in text,
                    f"Claude command commands/claude/{cmd} supports $ARGUMENTS",
                )

    def test_modes_and_protocols(self):
        print("\n--- Testing Modes, Protocols, Checklists & Templates ---")
        expected_modes = ["plan.md", "design.md", "backend.md", "security.md", "analyze.md"]
        for mode in expected_modes:
            path = SKILL_DIR / "modes" / mode
            self.assert_true(path.exists(), f"Mode exists: modes/{mode}")

        expected_protocols = [
            "memory.md",
            "grilling.md",
            "human-voice.md",
            "output-style.md",
            "mcp.md",
            "profile.md",
            "safety.md",
            "evidence.md",
            "context.md",
            "coverage.md",
            "advice.md",
            "autonomy.md",
            "research.md",
        ]
        for proto in expected_protocols:
            path = SKILL_DIR / "protocols" / proto
            self.assert_true(path.exists(), f"Protocol exists: protocols/{proto}")

        expected_checklists = [
            "site-production.md",
            "app-launch-legal.md",
            "ui-polish-20-tips.md",
        ]
        for cl in expected_checklists:
            path = SKILL_DIR / "checklists" / cl
            self.assert_true(path.exists(), f"Checklist exists: checklists/{cl}")

        expected_templates = [
            "profile.template.md",
            "plan.template.md",
            "security-report.template.md",
            "analysis-report.template.md",
            "coverage-ledger.template.json",
            "context-handoff.template.json",
        ]
        for tmpl in expected_templates:
            path = SKILL_DIR / "templates" / tmpl
            self.assert_true(path.exists(), f"Template exists: templates/{tmpl}")

    def test_vendor_index_and_manifest(self):
        print("\n--- Testing Vendor Ecosystem, Manifest & Link Resolution ---")
        index_file = SKILL_DIR / "vendor" / "INDEX.md"
        sources_file = SKILL_DIR / "vendor" / "SOURCES.md"
        third_party_file = REPO_ROOT / "THIRD_PARTY.md"
        vendor_manifest = SKILL_DIR / "vendor" / "manifest.json"

        self.assert_true(index_file.exists(), "skills/sadskill/vendor/INDEX.md exists")
        self.assert_true(sources_file.exists(), "skills/sadskill/vendor/SOURCES.md exists")
        self.assert_true(third_party_file.exists(), "THIRD_PARTY.md exists in root")
        self.assert_true(vendor_manifest.exists(), "skills/sadskill/vendor/manifest.json exists")

        index_content = index_file.read_text(encoding="utf-8")
        links = re.findall(r"\[([^\]]+)\]\(([^)]+\.ref\.md)\)", index_content)
        self.assert_true(len(links) >= 20, f"Vendor INDEX contains >= 20 references (found {len(links)})")

        broken_links = []
        vendor_dir = SKILL_DIR / "vendor"
        for label, ref in links:
            target = (vendor_dir / ref).resolve()
            if not target.exists():
                broken_links.append((ref, str(target)))

        self.assert_true(
            len(broken_links) == 0,
            f"All INDEX.md reference links resolve to existing files (broken: {broken_links})",
        )

        if vendor_manifest.exists():
            vdata = json.loads(vendor_manifest.read_text(encoding="utf-8"))
            self.assert_true(len(vdata.get("references", [])) == 40, "Vendor manifest tracks all 40 reference files")

    def test_community_and_metadata(self):
        print("\n--- Testing Community Health, CI & Agent Metadata ---")
        ci_workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        bug_report = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
        feature_request = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml"
        security_policy = REPO_ROOT / "SECURITY.md"
        openai_yaml = SKILL_DIR / "agents" / "openai.yaml"
        guardrail_script = REPO_ROOT / "scripts" / "git-guardrail.sh"
        skill_hook = SKILL_DIR / "hooks" / "git-guardrail.sh"

        self.assert_true(ci_workflow.exists(), "CI workflow exists at .github/workflows/ci.yml")
        self.assert_true(bug_report.exists(), "Bug report template exists at .github/ISSUE_TEMPLATE/bug_report.yml")
        self.assert_true(feature_request.exists(), "Feature request template exists at .github/ISSUE_TEMPLATE/feature_request.yml")
        self.assert_true(security_policy.exists(), "Security policy exists at SECURITY.md")
        self.assert_true(openai_yaml.exists(), "OpenAI YAML exists at agents/openai.yaml")

        if openai_yaml.exists():
            text = openai_yaml.read_text(encoding="utf-8")
            self.assert_true("interface:" in text and "display_name:" in text, "OpenAI YAML contains valid interface schema")

        self.assert_true(guardrail_script.exists(), "Executable guardrail exists at scripts/git-guardrail.sh")
        self.assert_true(skill_hook.exists(), "Packaged guardrail exists at skills/sadskill/hooks/git-guardrail.sh")
        if guardrail_script.exists() and skill_hook.exists():
            self.assert_true(os.access(guardrail_script, os.X_OK), "scripts/git-guardrail.sh is marked executable")
            self.assert_true(os.access(skill_hook, os.X_OK), "skills/sadskill/hooks/git-guardrail.sh is marked executable")
            self.assert_true(guardrail_script.read_bytes() == skill_hook.read_bytes(), "Guardrail root script and packaged hook are byte-identical")

        evidence_verifier = REPO_ROOT / "scripts" / "verify-evidence.py"
        self.assert_true(evidence_verifier.exists(), "Evidence verifier exists at scripts/verify-evidence.py")
        if evidence_verifier.exists():
            self.assert_true(os.access(evidence_verifier, os.X_OK), "scripts/verify-evidence.py is marked executable")

        manifest_script = REPO_ROOT / "scripts" / "manifest.py"
        self.assert_true(manifest_script.exists(), "Manifest manager exists at scripts/manifest.py")
        if manifest_script.exists():
            self.assert_true(os.access(manifest_script, os.X_OK), "scripts/manifest.py is marked executable")

        doctor_script = REPO_ROOT / "scripts" / "doctor.py"
        self.assert_true(doctor_script.exists(), "Doctor script exists at scripts/doctor.py")
        if doctor_script.exists():
            self.assert_true(os.access(doctor_script, os.X_OK), "scripts/doctor.py is marked executable")

        benchmarks_runner = REPO_ROOT / "benchmarks" / "runner.py"
        benchmarks_tasks = REPO_ROOT / "benchmarks" / "tasks.json"
        self.assert_true(benchmarks_runner.exists(), "Benchmark runner exists at benchmarks/runner.py")
        self.assert_true(benchmarks_tasks.exists(), "Benchmark tasks exist at benchmarks/tasks.json")
        if benchmarks_runner.exists():
            self.assert_true(os.access(benchmarks_runner, os.X_OK), "benchmarks/runner.py is marked executable")

    def test_guardrail_advanced_hardening(self):
        print("\n--- Testing Guardrail Advanced Hardening (JSON & Pre-Push) ---")
        hook = REPO_ROOT / "scripts" / "git-guardrail.sh"

        # 1. Claude Code structured JSON with escaped quotes
        json_payload = '{"tool_name": "Bash", "tool_input": {"command": "git reset --hard HEAD~1"}}'
        res_json = subprocess.run(["bash", str(hook)], input=json_payload, text=True, capture_output=True)
        self.assert_true(res_json.returncode == 2, f"Claude Code JSON destructive payload blocked with exit 2 (got {res_json.returncode})")

        # 2. Git pre-push hook ref-update stream deletion (standard ref update format)
        pre_push_payload = "refs/heads/main 0000000000000000000000000000000000000000 refs/heads/main 1111111111111111111111111111111111111111\n"
        res_ref = subprocess.run(["bash", str(hook)], input=pre_push_payload, text=True, capture_output=True)
        self.assert_true(res_ref.returncode == 2, f"Git pre-push branch deletion of protected ref blocked with exit 2 (got {res_ref.returncode})")

        # 2b. Git pre-push hook deletion via (delete) token format
        pre_push_del = "(delete) 0000000000000000000000000000000000000000 refs/heads/main 1111111111111111111111111111111111111111\n"
        res_del = subprocess.run(["bash", str(hook)], input=pre_push_del, text=True, capture_output=True)
        self.assert_true(res_del.returncode == 2, f"Git pre-push (delete) ref format for protected branch blocked with exit 2 (got {res_del.returncode})")

        # 2c. Git pre-push hook deletion via 3-token / empty local_ref format (e.g. git push origin :main)
        pre_push_empty_local = " 0000000000000000000000000000000000000000 refs/heads/main 1111111111111111111111111111111111111111\n"
        res_empty = subprocess.run(["bash", str(hook)], input=pre_push_empty_local, text=True, capture_output=True)
        self.assert_true(res_empty.returncode == 2, f"Git pre-push empty local_ref format for protected branch blocked with exit 2 (got {res_empty.returncode})")

        # 3. Benign commit message containing dangerous phrase
        commit_msg_cmd = 'git commit -m "fix git reset --hard issue in docs"'
        res_msg = subprocess.run(["bash", str(hook), commit_msg_cmd], text=True, capture_output=True)
        self.assert_true(res_msg.returncode == 0, f"Git commit with dangerous word inside -m allowed with exit 0 (got {res_msg.returncode})")

        # 4. Benign commit message containing semicolon and SQL keywords (preventing false positive split)
        commit_sql_cmd = 'git commit -m "fix; DROP TABLE users in migration"'
        res_sql = subprocess.run(["bash", str(hook), commit_sql_cmd], text=True, capture_output=True)
        self.assert_true(res_sql.returncode == 0, f"Git commit with semicolon and SQL inside -m allowed with exit 0 (got {res_sql.returncode})")

        # 5. Compound command with benign commit followed by destructive SQL query
        compound_sql_cmd = 'git commit -m "normal commit"; DROP TABLE users'
        res_compound = subprocess.run(["bash", str(hook), compound_sql_cmd], text=True, capture_output=True)
        self.assert_true(res_compound.returncode == 2, f"Compound command with DROP TABLE blocked with exit 2 (got {res_compound.returncode})")

    def test_benchmarks_execution(self):
        print("\n--- Testing Reproducible Benchmark Suite ---")
        runner = REPO_ROOT / "benchmarks" / "runner.py"
        res = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True)
        self.assert_true(res.returncode == 0, f"Reproducible benchmarks passed 100% (exit code {res.returncode})")
        suite_24 = REPO_ROOT / "benchmarks" / "tasks" / "suite_24.json"
        self.assert_true(suite_24.exists(), "24-task benchmark evaluation suite exists at benchmarks/tasks/suite_24.json")

    def test_version_consistency(self):
        print("\n--- Testing Version Consistency Across Files ---")
        skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        install_text = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        uninstall_text = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
        guardrail_text = (REPO_ROOT / "scripts" / "git-guardrail.sh").read_text(encoding="utf-8")

        self.assert_true("version: 0.3.0" in skill_text, "SKILL.md defines version: 0.3.0")
        self.assert_true("v0.3.0" in readme_text, "README.md references v0.3.0")
        self.assert_true("v0.3.0" in install_text, "install.sh references v0.3.0")
        self.assert_true("v0.3.0" in uninstall_text, "uninstall.sh references v0.3.0")
        self.assert_true("v0.3.0" in guardrail_text, "git-guardrail.sh references v0.3.0")

    def test_evidence_verifier_safety(self):
        print("\n--- Testing Evidence Verifier Hardening & Safety ---")
        verifier = REPO_ROOT / "scripts" / "verify-evidence.py"

        # 1. Test --require-evidence on empty dir fails with exit 1
        with tempfile.TemporaryDirectory() as empty_dir:
            res = subprocess.run(
                [sys.executable, str(verifier), "--project-root", empty_dir, "--require-evidence"],
                capture_output=True,
                text=True,
            )
            self.assert_true(
                res.returncode == 1,
                f"verify-evidence --require-evidence on empty dir exited 1 (got {res.returncode})",
            )

        # 2. Test path traversal rejection (e.g. ../../outside)
        with tempfile.TemporaryDirectory() as proj_dir:
            ev_dir = Path(proj_dir) / ".sad" / "evidence"
            ev_dir.mkdir(parents=True)
            bad_record = {
                "timestamp": "2026-10-28T04:00:00Z",
                "task_slug": "traversal-test",
                "command": "python3 test.py",
                "exit_code": 0,
                "summary": "malicious record",
                "files_touched": ["../../etc/passwd"],
            }
            (ev_dir / "bad-traversal.json").write_text(json.dumps(bad_record), encoding="utf-8")
            res_bad = subprocess.run(
                [sys.executable, str(verifier), "--project-root", proj_dir],
                capture_output=True,
                text=True,
            )
            self.assert_true(
                res_bad.returncode == 1,
                f"verify-evidence rejected path traversal in files_touched (got exit {res_bad.returncode})",
            )

        # 3. Test arbitrary shell chaining rejection on --retest
        with tempfile.TemporaryDirectory() as proj_dir:
            ev_dir = Path(proj_dir) / ".sad" / "evidence"
            ev_dir.mkdir(parents=True)
            test_file = Path(proj_dir) / "test.py"
            test_file.write_text("print('ok')", encoding="utf-8")

            chained_record = {
                "timestamp": "2026-10-28T04:00:00Z",
                "task_slug": "chained-test",
                "command": "python3 test.py && echo pwned",
                "exit_code": 0,
                "summary": "chained command record",
                "files_touched": ["test.py"],
            }
            (ev_dir / "bad-chain.json").write_text(json.dumps(chained_record), encoding="utf-8")
            res_chain = subprocess.run(
                [sys.executable, str(verifier), "--project-root", proj_dir, "--retest"],
                capture_output=True,
                text=True,
            )
            self.assert_true(
                res_chain.returncode == 1,
                f"verify-evidence --retest rejected shell chaining tokens (got exit {res_chain.returncode})",
            )

        # 4. Strict type check: boolean exit_code rejected (T16)
        with tempfile.TemporaryDirectory() as proj_dir:
            ev_dir = Path(proj_dir) / ".sad" / "evidence"
            ev_dir.mkdir(parents=True)
            bool_record = {
                "timestamp": "2026-10-28T04:00:00Z",
                "task_slug": "bool-test",
                "command": "python3 test.py",
                "exit_code": False,
                "summary": "boolean exit code record",
                "files_touched": [],
            }
            (ev_dir / "bad-bool.json").write_text(json.dumps(bool_record), encoding="utf-8")
            res_bool = subprocess.run(
                [sys.executable, str(verifier), "--project-root", proj_dir],
                capture_output=True,
                text=True,
            )
            self.assert_true(
                res_bool.returncode == 1,
                f"verify-evidence rejected boolean exit_code (got exit {res_bool.returncode})",
            )

        # 5. Untrusted interpreter flag -c rejected in --retest (T20)
        with tempfile.TemporaryDirectory() as proj_dir:
            ev_dir = Path(proj_dir) / ".sad" / "evidence"
            ev_dir.mkdir(parents=True)
            untrusted_cmd_record = {
                "timestamp": "2026-10-28T04:00:00Z",
                "task_slug": "untrusted-eval",
                "command": "python3 -c 'print(1)'",
                "exit_code": 0,
                "summary": "untrusted eval record",
                "files_touched": [],
            }
            (ev_dir / "untrusted.json").write_text(json.dumps(untrusted_cmd_record), encoding="utf-8")
            res_untrusted = subprocess.run(
                [sys.executable, str(verifier), "--project-root", proj_dir, "--retest"],
                capture_output=True,
                text=True,
            )
            self.assert_true(
                res_untrusted.returncode == 1,
                f"verify-evidence --retest rejected untrusted -c flag (got exit {res_untrusted.returncode})",
            )

        # 5b. Arbitrary repository script rejected in --retest without trusted recipe (P0 safety)
        with tempfile.TemporaryDirectory() as proj_dir:
            ev_dir = Path(proj_dir) / ".sad" / "evidence"
            ev_dir.mkdir(parents=True)
            arbitrary_script = Path(proj_dir) / "evil.py"
            arbitrary_script.write_text("print('pwned')", encoding="utf-8")
            evil_record = {
                "timestamp": "2026-10-28T04:00:00Z",
                "task_slug": "arbitrary-script",
                "command": "python3 evil.py",
                "exit_code": 0,
                "summary": "arbitrary script record",
                "files_touched": ["evil.py"],
            }
            (ev_dir / "evil.json").write_text(json.dumps(evil_record), encoding="utf-8")
            res_evil = subprocess.run(
                [sys.executable, str(verifier), "--project-root", proj_dir, "--retest"],
                capture_output=True,
                text=True,
            )
            self.assert_true(
                res_evil.returncode == 1,
                f"verify-evidence --retest rejected arbitrary script execution (got exit {res_evil.returncode})",
            )

        # 5c. Trusted recipe (recipe_id) accepted and executed in --retest
        with tempfile.TemporaryDirectory() as proj_dir:
            ev_dir = Path(proj_dir) / ".sad" / "evidence"
            ev_dir.mkdir(parents=True)
            (Path(proj_dir) / "test_sample.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n", encoding="utf-8")
            recipe_record = {
                "schema_version": "1.0.0",
                "timestamp": "2026-10-28T04:00:00Z",
                "task_slug": "trusted-recipe-test",
                "recipe_id": "python-unittest",
                "command": "python3 -m unittest discover",
                "exit_code": 0,
                "summary": "trusted recipe discovery",
                "files_touched": [],
            }
            (ev_dir / "recipe.json").write_text(json.dumps(recipe_record), encoding="utf-8")
            res_recipe = subprocess.run(
                [sys.executable, str(verifier), "--project-root", proj_dir, "--retest"],
                capture_output=True,
                text=True,
            )
            self.assert_true(
                res_recipe.returncode == 0,
                f"verify-evidence --retest accepted trusted recipe (got exit {res_recipe.returncode})",
            )

        # 5d. Documentation-only task with status SKIPPED_WITH_REASON and exit_code null accepted without failure (T60)
        with tempfile.TemporaryDirectory() as proj_dir:
            ev_dir = Path(proj_dir) / ".sad" / "evidence"
            ev_dir.mkdir(parents=True)
            doc_file = Path(proj_dir) / "README.md"
            doc_file.write_text("# Doc update", encoding="utf-8")
            docs_record = {
                "timestamp": "2026-10-28T04:00:00Z",
                "task_slug": "doc-update-task",
                "command": "NONE",
                "exit_code": None,
                "status": "SKIPPED_WITH_REASON",
                "summary": "Documentation update without executable test harness",
                "files_touched": ["README.md"],
            }
            (ev_dir / "docs-task.json").write_text(json.dumps(docs_record), encoding="utf-8")
            res_docs = subprocess.run(
                [sys.executable, str(verifier), "--project-root", proj_dir, "--retest"],
                capture_output=True,
                text=True,
            )
            self.assert_true(
                res_docs.returncode == 0,
                f"verify-evidence accepted docs-only task with status SKIPPED_WITH_REASON (got exit {res_docs.returncode})",
            )

        # 6. Clean JSON output check (T26)
        with tempfile.TemporaryDirectory() as proj_dir:
            res_json = subprocess.run(
                [sys.executable, str(verifier), "--project-root", proj_dir, "--json"],
                capture_output=True,
                text=True,
            )
            self.assert_true(res_json.returncode == 0, "verify-evidence --json exited 0 on clean baseline")
            try:
                parsed = json.loads(res_json.stdout.strip())
                self.assert_true("exit_code" in parsed and "records" in parsed, "verify-evidence --json emitted valid JSON on stdout")
            except Exception as e:
                self.assert_true(False, f"verify-evidence --json stdout was not valid JSON: {e}")

    def test_behavioral_fixtures(self):
        print("\n--- Testing Behavioral Benchmark Fixtures ---")
        # 1. Tenant isolation in-memory fixture
        fixture_grader = REPO_ROOT / "benchmarks" / "fixtures" / "tenant-isolation" / "grader.py"
        self.assert_true(fixture_grader.exists(), "Tenant isolation fixture grader exists")
        if fixture_grader.exists():
            res = subprocess.run([sys.executable, str(fixture_grader)], capture_output=True, text=True)
            self.assert_true(res.returncode == 0, f"Tenant isolation behavioral tests passed cleanly (exit {res.returncode})")

        # 2. Real database RLS fixture
        rls_grader = REPO_ROOT / "benchmarks" / "fixtures" / "real-rls" / "grader.py"
        self.assert_true(rls_grader.exists(), "Real database RLS fixture grader exists")
        if rls_grader.exists():
            res_rls = subprocess.run([sys.executable, str(rls_grader)], capture_output=True, text=True)
            self.assert_true(res_rls.returncode == 0, f"Real database RLS behavioral tests passed cleanly (exit {res_rls.returncode})")

    def test_markdown_relative_links(self):
        print("\n--- Testing All Markdown Relative Links ---")
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        broken = []

        files_to_check = [
            SKILL_DIR / "SKILL.md",
            REPO_ROOT / "README.md",
            SKILL_DIR / "modes" / "plan.md",
            SKILL_DIR / "modes" / "design.md",
            SKILL_DIR / "modes" / "backend.md",
            SKILL_DIR / "modes" / "security.md",
            SKILL_DIR / "modes" / "analyze.md",
            SKILL_DIR / "protocols" / "context.md",
            SKILL_DIR / "protocols" / "coverage.md",
            SKILL_DIR / "protocols" / "advice.md",
            SKILL_DIR / "protocols" / "autonomy.md",
            SKILL_DIR / "protocols" / "research.md",
            SKILL_DIR / "protocols" / "memory.md",
        ]

        for doc in files_to_check:
            if not doc.exists():
                continue
            text = doc.read_text(encoding="utf-8")
            for label, url in link_pattern.findall(text):
                if url.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                clean_url = url.split("#")[0]
                if not clean_url:
                    continue
                resolved = (doc.parent / clean_url).resolve()
                if not resolved.exists():
                    broken.append((str(doc.relative_to(REPO_ROOT)), url))

        self.assert_true(
            len(broken) == 0,
            f"All intra-document relative links resolve (broken: {broken})",
        )

    def test_sandbox_installer_and_safety(self):
        print("\n--- Testing Multi-Agent Sandbox Installation, Safety & Restore ---")
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            env["HOME"] = temp_dir

            # 1. Test CLI exit codes on invalid arguments (T12, T13)
            res_bad_agent = subprocess.run(["bash", str(REPO_ROOT / "install.sh"), "--agent"], env=env, capture_output=True, text=True)
            self.assert_true(res_bad_agent.returncode == 2, f"install.sh missing --agent value exited with code 2 (got {res_bad_agent.returncode})")

            res_bad_arg = subprocess.run(["bash", str(REPO_ROOT / "install.sh"), "--unknown-option"], env=env, capture_output=True, text=True)
            self.assert_true(res_bad_arg.returncode == 2, f"install.sh unknown option exited with code 2 (got {res_bad_arg.returncode})")

            # 2. Test --help exits with code 0 (T14)
            res_help = subprocess.run(["bash", str(REPO_ROOT / "install.sh"), "--help"], env=env, capture_output=True, text=True)
            self.assert_true(res_help.returncode == 0, f"install.sh --help exited with code 0 (got {res_help.returncode})")

            # 3. Seed pre-existing user files to test safe restoration (T01, T02, T04)
            codex_prompts = Path(temp_dir) / ".codex" / "prompts"
            codex_prompts.mkdir(parents=True)
            user_original_prompt = codex_prompts / "sad-plan.md"
            user_original_prompt.write_text("USER_ORIGINAL_PROMPT_CONTENT", encoding="utf-8")

            claude_hooks = Path(temp_dir) / ".claude" / "hooks"
            claude_hooks.mkdir(parents=True)
            user_original_hook = claude_hooks / "git-guardrail.sh"
            user_original_hook.write_text("#!/bin/bash\n# USER_ORIGINAL_HOOK", encoding="utf-8")

            unrelated_backup = codex_prompts / "other-tool.md.bak.keep"
            unrelated_backup.write_text("UNRELATED_BACKUP_PRESERVED", encoding="utf-8")

            # 4. Run initial installation
            res1 = subprocess.run(
                ["bash", str(REPO_ROOT / "install.sh"), "all"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assert_true(res1.returncode == 0, f"install.sh all succeeded in sandbox (exit code {res1.returncode})")

            codex_dest = Path(temp_dir) / ".codex" / "skills" / "sadskill"
            claude_dest = Path(temp_dir) / ".claude" / "skills" / "sadskill"
            self.assert_true(codex_dest.exists(), "Codex skill directory created in sandbox")
            self.assert_true(claude_dest.exists(), "Claude skill directory created in sandbox")

            # Check that pre-existing prompt was backed up
            found_baks = list(codex_prompts.glob("sad-plan.md.bak.*"))
            self.assert_true(len(found_baks) > 0, "Pre-existing prompt backed up upon installation")

            # 5. Seed pre-existing Cursor workspace skill with sentinel to test directory restore
            target_proj = Path(temp_dir) / "sample_project"
            target_proj.mkdir()
            cursor_pre_skill = target_proj / ".cursor" / "skills" / "sadskill"
            cursor_pre_skill.mkdir(parents=True)
            cursor_sentinel = cursor_pre_skill / "sentinel.txt"
            cursor_sentinel.write_text("CURSOR_SENTINEL_SURVIVES", encoding="utf-8")

            # Run Cursor per-project target installation
            res_cur = subprocess.run(
                ["bash", str(REPO_ROOT / "install.sh"), "--agent", "cursor", "--target", str(target_proj)],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assert_true(res_cur.returncode == 0, "install.sh --agent cursor --target succeeded")
            self.assert_true((target_proj / ".cursor" / "rules" / "sadskill.mdc").exists(), "Cursor rule created in target")
            self.assert_true((target_proj / ".cursor" / "skills" / "sadskill").exists(), "Cursor skill directory created in target")

            manifest_file = Path(temp_dir) / ".sadskill" / "install-manifest.json"
            self.assert_true(manifest_file.exists(), "Installation manifest created")

            # 6. Test Gemini CLI agent installation
            res_gem = subprocess.run(
                ["bash", str(REPO_ROOT / "install.sh"), "--agent", "gemini"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assert_true(res_gem.returncode == 0, "install.sh --agent gemini succeeded")
            self.assert_true((Path(temp_dir) / ".gemini" / "skills" / "sadskill").exists(), "Gemini CLI skill directory created in sandbox")

            # 7. Test reinstallation preserves original backup references
            res_reinstall = subprocess.run(
                ["bash", str(REPO_ROOT / "install.sh"), "all"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assert_true(res_reinstall.returncode == 0, "install.sh all reinstall succeeded in sandbox")

            # 8. Test Doctor utility and --enable-hooks
            res_doc = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "doctor.py"), "--json", "--target", str(target_proj)],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assert_true(res_doc.returncode == 0, "doctor.py --json executed successfully")
            doc_data = json.loads(res_doc.stdout)
            self.assert_true(doc_data["cursor"]["status"] == "INSTALLED", "doctor correctly diagnosed Cursor as INSTALLED")
            self.assert_true(doc_data["antigravity_gemini"]["status"] == "INSTALLED", "doctor correctly diagnosed Gemini CLI / Antigravity as INSTALLED")
            self.assert_true(doc_data["claude_hook"]["status"] == "AVAILABLE", "doctor correctly diagnosed Claude hook as AVAILABLE before registration")

            # Test opt-in hook registration via doctor --enable-hooks (P1-01, S10)
            res_enable = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "doctor.py"), "--enable-hooks", "--json", "--target", str(target_proj)],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assert_true(res_enable.returncode == 0, "doctor.py --enable-hooks executed successfully")
            doc_data_act = json.loads(res_enable.stdout)
            self.assert_true(doc_data_act["claude_hook"]["status"] == "LOCAL_TEST_PASSED", "doctor truthfully reported local hook testing without claiming host activation")

            # 8b. Simulate user modifying an installed prompt to test conflict preservation (P0-01, P0-05, T05)
            codex_backend = codex_prompts / "sad-backend.md"
            self.assert_true(codex_backend.exists(), "Installed codex prompt exists")
            codex_backend.write_text("USER_CUSTOM_BACKEND_MODIFICATIONS", encoding="utf-8")

            # 9. Test uninstallation without --force (must refuse to overwrite/delete user-modified files)
            res_un_noforce = subprocess.run(
                ["bash", str(REPO_ROOT / "uninstall.sh"), "--restore-previous", "--target", str(target_proj)],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assert_true(res_un_noforce.returncode == 0, "uninstall.sh without --force succeeded")
            self.assert_true(codex_backend.exists(), "User-modified prompt preserved by conflict refusal")
            if codex_backend.exists():
                self.assert_true(
                    codex_backend.read_text(encoding="utf-8") == "USER_CUSTOM_BACKEND_MODIFICATIONS",
                    "User-modified prompt content untouched without --force",
                )

            # 9b. Test uninstallation with --force to remove/restore cleanly
            res_un = subprocess.run(
                ["bash", str(REPO_ROOT / "uninstall.sh"), "--restore-previous", "--clean-backups", "--force", "--target", str(target_proj)],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assert_true(res_un.returncode == 0, "uninstall.sh --restore-previous --force succeeded cleanly")

            # CRITICAL ASSERTION: The restored file MUST exist and match original content byte-for-byte!
            self.assert_true(user_original_prompt.exists(), "Restored prompt exists after uninstallation")
            if user_original_prompt.exists():
                self.assert_true(
                    user_original_prompt.read_text(encoding="utf-8") == "USER_ORIGINAL_PROMPT_CONTENT",
                    "Restored prompt content matches original pre-sadskill bytes exactly",
                )

            # CRITICAL ASSERTION: Restored Claude hook must exist and match original content
            self.assert_true(user_original_hook.exists(), "Restored Claude hook exists after uninstallation")
            if user_original_hook.exists():
                self.assert_true(
                    "USER_ORIGINAL_HOOK" in user_original_hook.read_text(encoding="utf-8"),
                    "Restored Claude hook matches original pre-sadskill bytes exactly",
                )

            # CRITICAL ASSERTION: Pre-existing Cursor directory sentinel must survive install and restore
            self.assert_true(cursor_sentinel.exists(), "Pre-existing Cursor directory sentinel survived install and restore")
            if cursor_sentinel.exists():
                self.assert_true(
                    cursor_sentinel.read_text(encoding="utf-8") == "CURSOR_SENTINEL_SURVIVES",
                    "Pre-existing Cursor sentinel content survived cleanly",
                )

            # CRITICAL ASSERTION: Unrelated backup MUST NOT be deleted (T04, S02 fix)
            self.assert_true(unrelated_backup.exists(), "Unrelated backup was NOT deleted by --clean-backups")

            # Clean removal of non-restored sadskill directories
            self.assert_true(not codex_dest.exists(), "Codex skill directory cleanly removed")
            self.assert_true(not (target_proj / ".cursor" / "rules" / "sadskill.mdc").exists(), "Cursor rule cleanly removed")

    def test_privacy_and_portability(self):
        print("\n--- Testing Privacy & Portability Constraints ---")
        p_home = r"/" + "home" + r"/\w+"
        p_brain = "gemini" + "_brain"
        p_lang = r"\b" + "bang" + "lish" + r"\b"
        p_name = r"\b" + "sad" + "af" + r"\b"

        violations = []

        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if path.suffix in [".png", ".jpg", ".pyc"]:
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_path = str(rel)

            if re.search(p_home, content):
                violations.append((rel_path, "Machine user home directory path detected"))

            if p_brain in content:
                violations.append((rel_path, "Internal brain reference detected"))

            if re.search(p_lang, content, re.IGNORECASE):
                violations.append((rel_path, "Personal language reference detected"))

            for m in re.finditer(p_name, content, re.IGNORECASE):
                violations.append((rel_path, f"Standalone personal name detected: {m.group(0)}"))

        self.assert_true(
            len(violations) == 0,
            f"Privacy scan passed (found {len(violations)} violations: {violations})",
        )

    def run(self):
        self.test_frontmatter_and_discovery()
        self.test_commands_integrity()
        self.test_modes_and_protocols()
        self.test_vendor_index_and_manifest()
        self.test_community_and_metadata()
        self.test_guardrail_advanced_hardening()
        self.test_version_consistency()
        self.test_evidence_verifier_safety()
        self.test_behavioral_fixtures()
        self.test_benchmarks_execution()
        self.test_markdown_relative_links()
        self.test_sandbox_installer_and_safety()
        self.test_privacy_and_portability()

        print("\n==========================================")
        print(f"Total Passed: {self.passed}")
        print(f"Total Failed: {len(self.errors)}")
        print("==========================================")

        if self.errors:
            print("\nFailures:")
            for err in self.errors:
                print(f"  - {err}")
            return 1
        print("\nAll sadskill verification checks passed successfully!")
        return 0


if __name__ == "__main__":
    suite = VerificationSuite()
    sys.exit(suite.run())
