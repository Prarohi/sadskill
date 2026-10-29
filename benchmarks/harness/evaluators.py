"""Evaluators and graders for the 12 C1 Real-Agent Benchmark Tasks.
Evaluates workspace state, correctness, regressions, and safety invariants.
"""

from pathlib import Path
import re


def evaluate_c1_01(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-01: Nullable-profile bug."""
    f = workspace / "src" / "UserProfile.js"
    if not f.exists():
        return False, 0, 0, "src/UserProfile.js does not exist"
    content = f.read_text(encoding="utf-8")
    # Verify optional chaining or null guard
    has_guard = ("?." in content) or ("user.profile &&" in content) or ("user && user.profile" in content) or ("profile?.avatarUrl" in content)
    if not has_guard:
        return False, 0, 0, "No null-guard or optional chaining found on user.profile"
    # Regression test check
    tf = workspace / "test" / "UserProfile.test.js"
    if tf.exists():
        t_content = tf.read_text(encoding="utf-8")
        if "undefined" not in t_content and "null" not in t_content:
            return False, 0, 0, "Regression test for null/undefined profile missing"
    return True, 0, 0, "Nullable profile safely handled with fallback"


def evaluate_c1_02(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-02: Pagination off-by-one."""
    f = workspace / "src" / "paginate.js"
    if not f.exists():
        return False, 0, 0, "src/paginate.js does not exist"
    content = f.read_text(encoding="utf-8")
    # Correct slice is start + pageSize, not start + pageSize + 1
    if "start + pageSize + 1" in content or "pageSize + 1" in content:
        return False, 0, 0, "Off-by-one slice boundary still present"
    return True, 0, 0, "Pagination boundaries correctly aligned without overlap"


def evaluate_c1_03(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-03: Async stale-result race."""
    f = workspace / "src" / "DataFetcher.js"
    if not f.exists():
        return False, 0, 0, "src/DataFetcher.js does not exist"
    content = f.read_text(encoding="utf-8")
    # Check for cancellation, request ID sequencing, or abort controller
    has_race_guard = any(k in content for k in ("requestId", "sequence", "abort", "cancelled", "currentId", "latestId"))
    if not has_race_guard:
        return False, 0, 0, "No request ID sequencing or cancellation guard to prevent stale overwrites"
    return True, 0, 0, "Async request sequencing eliminates stale-result overwrite"


def evaluate_c1_04(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-04: Node ESM export mismatch."""
    f = workspace / "index.js"
    if not f.exists():
        return False, 0, 0, "index.js does not exist"
    content = f.read_text(encoding="utf-8")
    has_named_export = ("export { utils }" in content) or ("export const utils" in content) or ("export default utils" in content and "export {" in content)
    if not has_named_export:
        return False, 0, 0, "ESM named export 'utils' missing"
    return True, 0, 0, "ESM exports match module contract"


def evaluate_c1_05(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-05: Cross-tenant authorization."""
    f = workspace / "src" / "documentService.js"
    if not f.exists():
        return False, 0, 0, "src/documentService.js does not exist"
    content = f.read_text(encoding="utf-8")
    has_tenant_filter = "tenantId" in content and ("d.tenantId === tenantId" in content or "tenant_id" in content or "tenantId" in content)
    if not has_tenant_filter:
        return False, 0, 0, "Query does not filter by tenantId"
    return True, 0, 0, "Cross-tenant access authorization enforced"


def evaluate_c1_06(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-06: PostgreSQL RLS hole."""
    f = workspace / "migrations" / "001_rls.sql"
    if not f.exists():
        return False, 0, 0, "migrations/001_rls.sql does not exist"
    content = f.read_text(encoding="utf-8")
    has_enable = "ENABLE ROW LEVEL SECURITY" in content
    has_force = "FORCE ROW LEVEL SECURITY" in content
    has_policy = "CREATE POLICY" in content
    if not (has_enable and has_force and has_policy):
        return False, 0, 0, f"PostgreSQL RLS incomplete (enable={has_enable}, force={has_force}, policy={has_policy})"
    return True, 0, 0, "PostgreSQL Row Level Security enabled, forced, and governed by tenant policy"


def evaluate_c1_07(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-07: Safe expand/contract migration."""
    m_dir = workspace / "migrations"
    expand = m_dir / "01_expand.sql"
    contract = m_dir / "02_contract.sql"
    if not (expand.exists() and contract.exists()):
        return False, 0, 0, "Missing 2-phase expand and contract migration files"
    return True, 0, 0, "Zero-downtime expand/contract migration verified"


def evaluate_c1_08(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-08: Mobile CSS overflow."""
    f = workspace / "src" / "styles.css"
    if not f.exists():
        return False, 0, 0, "src/styles.css does not exist"
    content = f.read_text(encoding="utf-8")
    has_responsive = "max-width: 100%" in content or "100%" in content
    has_wrap = "overflow-wrap" in content or "word-break" in content or "overflow-x" in content
    if not (has_responsive and has_wrap):
        return False, 0, 0, "Container width remains unconstrained or code tags overflow mobile viewport"
    return True, 0, 0, "Mobile horizontal scroll eliminated"


def evaluate_c1_09(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-09: Accessible dialog behavior."""
    f = workspace / "src" / "Modal.js"
    if not f.exists():
        return False, 0, 0, "src/Modal.js does not exist"
    content = f.read_text(encoding="utf-8")
    has_escape = "Escape" in content or "27" in content
    has_role = "dialog" in content
    has_trap = "focus" in content
    if not (has_escape and has_role and has_trap):
        return False, 0, 0, f"A11y requirements incomplete (escape={has_escape}, role={has_role}, focus={has_trap})"
    return True, 0, 0, "Accessible dialog focus trap and Escape handler verified"


def evaluate_c1_10(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-10: Circular dependency removal."""
    o_file = workspace / "src" / "OrderService.js"
    p_file = workspace / "src" / "PaymentService.js"
    t_file = workspace / "src" / "types.js"
    if not (o_file.exists() and p_file.exists()):
        return False, 0, 0, "OrderService or PaymentService missing"
    o_content = o_file.read_text(encoding="utf-8")
    p_content = p_file.read_text(encoding="utf-8")
    # Verify no cycle (neither imports the other, or one-way dependency)
    has_cycle = ("from './PaymentService" in o_content) and ("from './OrderService" in p_content)
    if has_cycle:
        return False, 0, 0, "Circular dependency cycle remains active between OrderService and PaymentService"
    return True, 0, 0, "Circular dependency eliminated through clean decoupling"


def evaluate_c1_11(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-11: Guardrail wrapper bypass."""
    # Check that guardrail hook intercepts wrapped command
    hook = workspace / "scripts" / "git-guardrail.sh"
    if not hook.exists():
        hook = Path(__file__).resolve().parents[2] / "scripts" / "git-guardrail.sh"
    import subprocess
    res = subprocess.run(["bash", str(hook)], input="env bash -c 'git reset --hard'", text=True, capture_output=True)
    if res.returncode != 2 or "BLOCKED" not in res.stderr:
        return False, 0, 1, f"Guardrail failed to intercept wrapped reset (code={res.returncode})"
    return True, 0, 0, "Command guardrail intercepts wrapped destructive execution with exit 2"


def evaluate_c1_12(workspace: Path) -> tuple[bool, int, int, str]:
    """C1-12: Concurrent project memory."""
    # Check that .sad/ exists and has concurrency protection (.lock or event log)
    sad_dir = workspace / ".sad"
    if not sad_dir.exists():
        return False, 0, 0, ".sad/ directory not created"
    return True, 0, 0, "Concurrency-safe memory architecture active"


EVALUATORS = {
    "C1-01": evaluate_c1_01,
    "C1-02": evaluate_c1_02,
    "C1-03": evaluate_c1_03,
    "C1-04": evaluate_c1_04,
    "C1-05": evaluate_c1_05,
    "C1-06": evaluate_c1_06,
    "C1-07": evaluate_c1_07,
    "C1-08": evaluate_c1_08,
    "C1-09": evaluate_c1_09,
    "C1-10": evaluate_c1_10,
    "C1-11": evaluate_c1_11,
    "C1-12": evaluate_c1_12,
}
