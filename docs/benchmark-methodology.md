# sadskill Benchmark & Evaluation Methodology (v0.3.0)

This document describes the two-track evaluation methodology used to measure `sadskill` instruction compliance, safety invariants, and real-world behavioral improvements.

---

## 1. Two-Track Architecture

To ensure both high-speed offline continuous integration and honest empirical evaluation, sadskill separates evaluation into two distinct tracks:

```text
┌────────────────────────────────────────────────────────┐
│ TRACK A: Deterministic Contract & Policy Verification  │
│ - Zero API cost, runs offline on every test/PR         │
│ - Verifies schema contracts, AST declarations, syntax  │
│ - Tests guardrail interception & installer safety      │
│ - Runner: python3 benchmarks/runner.py                 │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ TRACK B: Real Behavioral Fixtures & Agent Evaluations  │
│ - Executes actual code modifications in sandboxes      │
│ - Hidden graders evaluate behavior, not keywords       │
│ - Tenant isolation & database RLS fixtures             │
│ - Graders: python3 benchmarks/fixtures/*/grader.py     │
└────────────────────────────────────────────────────────┘
```

---

## 2. Track A — Contract & Policy Verification Suite

Run via `python3 benchmarks/runner.py`. Evaluates:
1. `task-01-tier1-bugfix`: Verifies Tier 1 plan definitions, Mermaid diagram omission for token efficiency, and 2-file threshold rules.
2. `task-02-zero-lift-ui`: Verifies preferred touch target requirements, Zero-Lift hover rule documentation, and micro-compression `scale(0.97)` specification.
3. `task-03-schema-migration`: Verifies paired `up.sql` / `down.sql` migrations, Row Level Security baseline commands, and `timestamptz` enforcement.
4. `task-04-owasp-sec-audit`: Verifies strictly read-only security audit contracts, OWASP Top 10 coverage, and secret leak detection.
5. `task-05-tier2-ast-contract`: Verifies Tier 2 Contract-First AST signature declarations and Mermaid data flow specifications.
6. `task-06-safety-guardrail`: Verifies real execution blocking of `git reset --hard` (exit code 2) and pass-through of `git status` (exit code 0).

---

## 3. Track B — Behavioral Fixtures

1. **Tenant Isolation Fixture (`benchmarks/fixtures/tenant-isolation/`)**:
   - Tests in-memory service isolation.
   - Grader executes unit tests asserting that cross-tenant read/list requests raise `AuthorizationError`.
2. **Database Row Level Security Fixture (`benchmarks/fixtures/real-rls/`)**:
   - Tests database engine-level isolation using SQLite authorizer hooks.
   - Grader executes queries asserting that cross-tenant database fetches fail and destructive schema drops are denied at the driver level.

---

## 4. Evaluation Rubric & Honest Reporting

- **Keyword Checks vs True Agent Superiority**: Static keyword matching verifies instruction presence, not agent capability. Claims of model superiority must be backed by real model task runs.
- **Unavailable Metrics**: If token consumption or provider execution cost is not exposed by the host CLI, record as `N/A`.
- **Reproducibility**: All benchmark fixtures provide runnable `grader.py` harnesses that exit 0 on clean verification or 1 on behavioral failure.
