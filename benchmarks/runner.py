#!/usr/bin/env python3
"""
sadskill Contract & Policy Verification Suite
Evaluates specification contracts, architectural requirements, and policy invariants
defined in benchmarks/tasks.json.

Note: This suite performs deterministic contract and policy verification.
For end-to-end multi-agent performance evaluations, see benchmarks/fixtures/.
"""

import argparse
import json
import os
import subprocess
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
TASKS_FILE = REPO_ROOT / "benchmarks" / "tasks.json"


def evaluate_tier1_bugfix(task, repo_root):
    criteria = task.get("evaluation_criteria", {})
    plan_file = repo_root / "skills" / "sadskill" / "modes" / "plan.md"
    if not plan_file.exists():
        return False, "modes/plan.md does not exist"

    text = plan_file.read_text(encoding="utf-8")
    checks = []

    if criteria.get("plan_tier") == "Tier 1 (Surgical)" and "Tier 1: Surgical Plan" in text:
        checks.append("Tier 1 plan definition present")
    else:
        return False, "Tier 1 plan definition missing from modes/plan.md"

    if criteria.get("mermaid_omitted") and "Skips Mermaid diagrams" in text:
        checks.append("Mermaid diagram omission for lean tokens verified")
    else:
        return False, "Omission of Mermaid diagrams in Tier 1 missing"

    if criteria.get("files_touched_limit") == 2 and "<= 2 files" in text:
        checks.append("2-file threshold rule verified")
    else:
        return False, "<= 2 files boundary rule missing"

    return True, ", ".join(checks)


def evaluate_zero_lift_ui(task, repo_root):
    criteria = task.get("evaluation_criteria", {})
    design_checklist = repo_root / "skills" / "sadskill" / "checklists" / "ui-polish-20-tips.md"
    readme_file = repo_root / "README.md"
    design_mode = repo_root / "skills" / "sadskill" / "modes" / "design.md"

    checks = []
    checklist_text = design_checklist.read_text(encoding="utf-8") if design_checklist.exists() else ""
    readme_text = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""
    design_mode_text = design_mode.read_text(encoding="utf-8") if design_mode.exists() else ""

    if criteria.get("touch_target_min_px") == 44 and "44px" in checklist_text:
        checks.append("44px touch target minimum verified")
    else:
        return False, "44px touch target minimum missing from checklists"

    if "Zero-Lift" in readme_text and "Zero-Lift" in design_mode_text:
        checks.append("Zero-Lift rule documented in README and design mode")
    else:
        return False, "Zero-Lift rule missing from README or design mode"

    if criteria.get("scale_click_compression") and "scale(0.97)" in design_mode_text:
        checks.append("Micro-compression scale(0.97) on click verified")
    else:
        return False, "Micro-compression scale(0.97) specification missing"

    return True, ", ".join(checks)


def evaluate_schema_migration(task, repo_root):
    criteria = task.get("evaluation_criteria", {})
    backend_file = repo_root / "skills" / "sadskill" / "modes" / "backend.md"
    if not backend_file.exists():
        return False, "modes/backend.md does not exist"

    text = backend_file.read_text(encoding="utf-8")
    checks = []

    if criteria.get("paired_up_and_down_migrations") and "up.sql" in text and "down.sql" in text:
        checks.append("Paired up.sql / down.sql migration requirement verified")
    else:
        return False, "Paired migration requirement missing"

    if criteria.get("rls_enabled_and_forced") and "ENABLE ROW LEVEL SECURITY" in text:
        checks.append("Row Level Security requirement verified")
    else:
        return False, "ENABLE ROW LEVEL SECURITY requirement missing"

    if criteria.get("timestamptz_enforced") and "timestamptz" in text:
        checks.append("timestamptz timezone requirement verified")
    else:
        return False, "timestamptz timezone requirement missing"

    return True, ", ".join(checks)


def evaluate_owasp_sec_audit(task, repo_root):
    criteria = task.get("evaluation_criteria", {})
    sec_mode = repo_root / "skills" / "sadskill" / "modes" / "security.md"
    claude_sec = repo_root / "commands" / "claude" / "sad-sec.md"
    codex_sec = repo_root / "commands" / "codex" / "sad-sec.md"

    checks = []
    sec_mode_text = sec_mode.read_text(encoding="utf-8") if sec_mode.exists() else ""
    claude_sec_text = claude_sec.read_text(encoding="utf-8") if claude_sec.exists() else ""
    codex_sec_text = codex_sec.read_text(encoding="utf-8") if codex_sec.exists() else ""

    if criteria.get("read_only_mutations_zero") and "Strictly Read-Only" in claude_sec_text and "Strictly Read-Only" in codex_sec_text:
        checks.append("Strictly Read-Only security contract verified across command adapters")
    else:
        return False, "Strictly Read-Only contract missing in command adapters"

    if "OWASP" in sec_mode_text:
        checks.append("OWASP Top 10 coverage verified in security mode")
    else:
        return False, "OWASP Top 10 coverage missing in security mode"

    if criteria.get("secret_leak_flagged") and "Secrets" in sec_mode_text:
        checks.append("Secret leak detection requirements verified")
    else:
        return False, "Secret leak detection requirements missing"

    return True, ", ".join(checks)


def evaluate_tier2_ast_contract(task, repo_root):
    criteria = task.get("evaluation_criteria", {})
    plan_file = repo_root / "skills" / "sadskill" / "modes" / "plan.md"
    if not plan_file.exists():
        return False, "modes/plan.md does not exist"

    text = plan_file.read_text(encoding="utf-8")
    checks = []

    if criteria.get("contract_first_ast_signatures") and "Contract-First AST Signatures" in text:
        checks.append("Contract-First AST signatures requirement verified")
    else:
        return False, "Contract-First AST signatures missing from modes/plan.md"

    if criteria.get("mermaid_graph_included") and "Mermaid" in text:
        checks.append("Mermaid architecture and data flow requirements verified")
    else:
        return False, "Mermaid data flow requirement missing"

    return True, ", ".join(checks)


def evaluate_safety_guardrail(task, repo_root):
    criteria = task.get("evaluation_criteria", {})
    hook = repo_root / "scripts" / "git-guardrail.sh"
    if not hook.exists():
        return False, "scripts/git-guardrail.sh does not exist"

    # Test interception of dangerous command
    res = subprocess.run(
        ["bash", str(hook)],
        input="git reset --hard HEAD~1",
        text=True,
        capture_output=True,
    )

    expected_code = criteria.get("exit_code_blocked", 2)
    if res.returncode != expected_code:
        return False, f"Guardrail exited with code {res.returncode}, expected {expected_code}"

    if "BLOCKED" not in res.stderr:
        return False, "Guardrail stderr missing BLOCKED notice"

    # Test benign command passes
    res_ok = subprocess.run(
        ["bash", str(hook)],
        input="git status",
        text=True,
        capture_output=True,
    )
    if res_ok.returncode != 0:
        return False, f"Guardrail falsely blocked benign command 'git status' (exit code {res_ok.returncode})"

    return True, "Destructive command intercepted with exit 2; benign command allowed with exit 0"


# Task Evaluator Registry
TASK_EVALUATORS = {
    "task-01-tier1-bugfix": evaluate_tier1_bugfix,
    "task-02-zero-lift-ui": evaluate_zero_lift_ui,
    "task-03-schema-migration": evaluate_schema_migration,
    "task-04-owasp-sec-audit": evaluate_owasp_sec_audit,
    "task-05-tier2-ast-contract": evaluate_tier2_ast_contract,
    "task-06-safety-guardrail": evaluate_safety_guardrail,
}


def run_track_b_fixtures():
    print("\n--- Track B: Behavioral Fixture Graders ---")
    fixtures = [
        ("Tenant Isolation Fixture", REPO_ROOT / "benchmarks" / "fixtures" / "tenant-isolation" / "grader.py"),
        ("Database RLS Fixture", REPO_ROOT / "benchmarks" / "fixtures" / "real-rls" / "grader.py"),
    ]
    passed = 0
    results = []
    for name, grader_path in fixtures:
        if not grader_path.exists():
            print(f"  ❌ FAIL: Grader not found at {grader_path}")
            results.append({"name": name, "status": "FAIL", "reason": "Missing grader"})
            continue
        res = subprocess.run([sys.executable, str(grader_path)], capture_output=True, text=True)
        if res.returncode == 0:
            passed += 1
            print(f"  ✓ PASS: {name} behavioral checks passed cleanly (exit 0)")
            results.append({"name": name, "status": "PASS"})
        else:
            print(f"  ❌ FAIL: {name} exited with code {res.returncode}")
            results.append({"name": name, "status": "FAIL", "reason": res.stderr.strip()})
    return passed, len(fixtures), results


def run_track_c_suite():
    print("\n--- Track C: 24-Task Real Evaluation Suite Validation ---")
    suite_file = REPO_ROOT / "benchmarks" / "tasks" / "suite_24.json"
    if not suite_file.exists():
        print(f"  ❌ FAIL: 24-task benchmark suite file missing: {suite_file}")
        return 0, 1, [{"status": "FAIL", "reason": "Missing suite_24.json"}]

    try:
        tasks = json.loads(suite_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ❌ FAIL: Invalid JSON in suite_24.json: {e}")
        return 0, 1, [{"status": "FAIL", "reason": str(e)}]

    expected_categories = {
        "Bugfix": 4,
        "Backend & Security": 4,
        "Frontend & Design": 4,
        "Architecture & Reliability": 4,
        "Full-Codebase Analysis": 4,
        "Autonomy, Research & Context": 4,
    }

    required_fields = [
        "id", "name", "category", "difficulty", "repo_snapshot",
        "user_prompt", "tool_requirements", "budget", "fixture_seed",
        "baseline_branch", "sadskill_branch", "hidden_grader",
        "safety_scope", "expected_outputs", "success_metrics",
        "evaluation_metadata", "reproduction_procedure",
    ]

    cat_counts = {}
    schema_errors = []

    for t in tasks:
        cat = t.get("category", "Unknown")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        for field in required_fields:
            if field not in t:
                schema_errors.append(f"Task {t.get('id')} missing field: {field}")

    if schema_errors:
        print(f"  ❌ FAIL: Schema errors in suite_24.json: {schema_errors[:3]}")
        return 0, 1, [{"status": "FAIL", "errors": schema_errors}]

    all_cats_match = True
    for cat, exp in expected_categories.items():
        actual = cat_counts.get(cat, 0)
        if actual < exp:
            print(f"  ❌ FAIL: Category '{cat}' has {actual} tasks, expected {exp}")
            all_cats_match = False
        else:
            print(f"  ✓ PASS: Category '{cat}': {actual}/{exp} tasks fully specified")

    if len(tasks) >= 24 and all_cats_match:
        print(f"  ✓ PASS: Complete 24-task benchmark suite ({len(tasks)} tasks) validated successfully.")
        return 1, 1, [{"status": "PASS", "total_tasks": len(tasks)}]
    return 0, 1, [{"status": "FAIL", "reason": "Category count mismatch"}]


def run_benchmarks(output_file=None):
    print("==================================================")
    print("  sadskill Benchmark & Evaluation Suite (v0.3.0)  ")
    print("==================================================")

    if not TASKS_FILE.exists():
        print(f"Error: Tasks file not found at {TASKS_FILE}", file=sys.stderr)
        return 1

    try:
        tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error parsing tasks file: {e}", file=sys.stderr)
        return 1

    print("\n--- Track A: Deterministic Policy & Contract Checks ---")
    passed = 0
    total = len(tasks)
    results = []

    for task in tasks:
        tid = task.get("id", "unknown")
        tname = task.get("name", "Unnamed")
        tcat = task.get("category", "General")
        print(f"\n[Verifying {tid}] {tname} ({tcat})")

        evaluator = TASK_EVALUATORS.get(tid)
        if evaluator is None:
            print(f"  ❌ FAIL: No evaluator registered for task ID '{tid}' (UNSUPPORTED_TASK)")
            results.append({"id": tid, "status": "FAIL", "reason": "UNSUPPORTED_TASK"})
            continue

        try:
            ok, notes = evaluator(task, REPO_ROOT)
        except Exception as e:
            ok = False
            notes = f"Unhandled evaluator exception: {e}"

        if ok:
            passed += 1
            print(f"  ✓ PASS: {notes}")
            results.append({"id": tid, "status": "PASS", "notes": notes})
        else:
            print(f"  ❌ FAIL: {notes}")
            results.append({"id": tid, "status": "FAIL", "reason": notes})

    pass_rate = (passed / total * 100.0) if total > 0 else 0.0
    print(f"\nTrack A Results: {passed}/{total} Contract Checks Passed ({pass_rate:.1f}%)")

    # Track B: Behavioral Fixtures
    b_pass, b_total, b_res = run_track_b_fixtures()

    # Track C: 24-Task Evaluation Suite
    c_pass, c_total, c_res = run_track_c_suite()

    all_passed = (passed == total) and (b_pass == b_total) and (c_pass == c_total)

    print("\n==================================================")
    print(f"Overall Benchmark Status: {'ALL PASS (100%)' if all_passed else 'FAILURES DETECTED'}")
    print(f"  - Track A (Contracts): {passed}/{total}")
    print(f"  - Track B (Fixtures):  {b_pass}/{b_total}")
    print(f"  - Track C (24 Tasks):  {c_pass}/{c_total}")
    print("==================================================")

    if output_file:
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "track_a_contracts": {"passed": passed, "total": total, "results": results},
            "track_b_fixtures": {"passed": b_pass, "total": b_total, "results": b_res},
            "track_c_suite_24": {"passed": c_pass, "total": c_total, "results": c_res},
            "overall_success": all_passed,
        }
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Saved verification summary to: {out_path}")

    return 0 if all_passed else 1


def main():
    parser = argparse.ArgumentParser(description="sadskill Contract & Benchmark Evaluation Suite")
    parser.add_argument("--output", help="Optional path to write verification JSON summary")
    args = parser.parse_args()

    sys.exit(run_benchmarks(output_file=args.output))


if __name__ == "__main__":
    main()
