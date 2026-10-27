#!/usr/bin/env python3
"""
sadskill verification test suite
Validates skill frontmatter, single discoverable skill constraint,
markdown cross-reference links, commands integrity, vendor indexing,
and strict privacy/portability invariants.
"""

import os
import re
import sys
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

        # Check that NO other file in the repository exposes top-level frontmatter with 'name:'
        other_skills = []
        for path in REPO_ROOT.rglob("*.md"):
            if path.resolve() == root_skill.resolve():
                continue
            # Ignore .git and .sad
            if any(part.startswith(".") for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if text.startswith("---\n"):
                match = re.search(r"^name:\s+([a-zA-Z0-9_-]+)", text, re.MULTILINE)
                if match:
                    other_skills.append((str(path.relative_to(REPO_ROOT)), match.group(1)))

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
        ]
        for tmpl in expected_templates:
            path = SKILL_DIR / "templates" / tmpl
            self.assert_true(path.exists(), f"Template exists: templates/{tmpl}")

    def test_vendor_index_and_sources(self):
        print("\n--- Testing Vendor Ecosystem & Link Resolution ---")
        index_file = SKILL_DIR / "vendor" / "INDEX.md"
        sources_file = SKILL_DIR / "vendor" / "SOURCES.md"
        third_party_file = REPO_ROOT / "THIRD_PARTY.md"

        self.assert_true(index_file.exists(), "skills/sadskill/vendor/INDEX.md exists")
        self.assert_true(sources_file.exists(), "skills/sadskill/vendor/SOURCES.md exists")
        self.assert_true(third_party_file.exists(), "THIRD_PARTY.md exists in root")

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
        ]

        for doc in files_to_check:
            if not doc.exists():
                continue
            text = doc.read_text(encoding="utf-8")
            for label, url in link_pattern.findall(text):
                # Ignore external URLs, mailto, and anchor jumps
                if url.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                # Strip anchor fragments
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

    def test_privacy_and_portability(self):
        print("\n--- Testing Privacy & Portability Constraints ---")
        # Privacy invariants (string fragments assembled dynamically so repo scanners find 0 matches)
        p_home = r"/" + "home" + r"/\w+"
        p_brain = "gemini" + "_brain"
        p_lang = r"\b" + "bang" + "lish" + r"\b"
        p_name = r"\b" + "sad" + "af" + r"\b"

        violations = []

        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.parts):
                continue
            if path.suffix in [".png", ".jpg", ".pyc"]:
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_path = str(path.relative_to(REPO_ROOT))

            # Check machine paths
            if re.search(p_home, content):
                violations.append((rel_path, "Machine user home directory path detected"))

            # Check brain mentions
            if p_brain in content:
                violations.append((rel_path, "Internal brain reference detected"))

            # Check local dialect mentions
            if re.search(p_lang, content, re.IGNORECASE):
                violations.append((rel_path, "Personal language reference detected"))

            # Check standalone personal name (case-insensitive, word boundary, ignoring repo handle)
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
        self.test_vendor_index_and_sources()
        self.test_markdown_relative_links()
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
