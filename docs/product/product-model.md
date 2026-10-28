# The `sadskill` Product Model & Architecture Thesis

> **Product Thesis**:
>
> *"Understand the real engineering task, make the smallest appropriate change, preserve the reasoning, and prove what actually works—across coding agents."*

---

## 1. The Core Value Proposition: The Engineering Confidence Layer

Modern AI coding agents generate code quickly, but frequently fail at real software engineering:
1. **Speculative Churn**: Guessing at APIs without reading signatures, leading to circular debugging loops.
2. **Premature Completion**: Claiming *"I fixed the issue and all tests pass!"* without executing the test harness.
3. **Amnesia**: Forgetting previous architectural decisions, design tokens, or rejected approaches between sessions.
4. **Destructive Blindness**: Running irreversible commands (`git reset --hard`, `DROP TABLE`) when attempting rollbacks.
5. **Dogmatic Over-Scaffolding**: Forcing users to review multi-page plans for one-line CSS tweaks.

`sadskill` is an open-source workflow guide for coding agents. Its goal is to encourage scoped changes, preserve project decisions, and distinguish verified results from proposals. Host access, tool availability, and actual test execution still determine what an agent can do.

```text
+-------------------------------------------------------------------------+
|                         Developer Engineering Task                      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                          1. Task Understanding                          |
|         Parse user intent, check latest directives, inspect memory      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                      2. Proportional Depth Selection                    |
|    T0 (Trivial: Direct) · T1 (Surgical: Lean Table) · T2 (Architectural)|
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                  3. Context & Codebase Discovery (Scoped)               |
|      Locate entry points, package manifests, and existing test runners  |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                        4. Change Contract Creation                      |
|       Intent · Scope · Constraints · Risk · Assumptions · Rollback      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                     5. Execution (When Authorized)                      |
|           Contiguous code replacements · Framework-native patterns      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                 6. Verification & Truthful Reporting                    |
|    Execute real harness · Capture exit code · Report provenance status  |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                   7. Durable, Privacy-Conscious Handoff                 |
|       Update .sad/ memory (ADRs, design memory) · Zero secret leaks     |
+-------------------------------------------------------------------------+
```

---

## 2. Answers to Essential Strategic Questions

### How do the workflows connect?
The plan, design, backend, security, and analyze modes share the same project context and evidence rules. A Change Contract can capture intent, scope, risk, verification, and recovery steps. This is guidance: it does not make external host tools run or turn a prompt-level safety rule into technical enforcement.

### What is the smallest valuable workflow a new user experiences?
Fixing an isolated bug in a single turn:
Example request: “Fix the NaN calculation in the invoice discount and verify it with the existing test.” The agent should identify the relevant implementation and test, make a scoped change when implementation is authorized, run the actual test, and report its exit status. If the user requested `PLAN_ONLY`, it should stop after presenting the plan. Runtime depends on the repository and host; no completion time is guaranteed.

### Which tasks bypass heavy planning?
- **T0 (Trivial)**: Single-line typo fixes, color token tweaks, documentation edits, formatting. When implementation is authorized, these can be handled directly without a plan artifact file.
- **T1 (Surgical)**: Scoped bugfixes and minor UI tweaks in <= 2 files with known test commands. These use a lean inline diff table.

### Which tasks genuinely need deep analysis and verification?
- Schema changes and database migrations.
- Multi-tenant isolation and Row Level Security.
- Authentication, session, and role authorization refactors.
- New full-stack features crossing multiple module boundaries.
- External API contracts and third-party integrations with breaking changes.

### What happens when tools or companion runtime are unavailable?
`sadskill` degrades gracefully across four clear capability tiers:
1. **Native Host Capability**: The host agent's built-in file editing, terminal, and browser tools.
2. **Optional Companion Capability**: Helper scripts (`doctor.py`, `manifest.py`, `verify-evidence.py`). When present, they provide automated checks; when absent, the agent evaluates contracts through inspection.
3. **Prompt-Only Guidance**: In lightweight hosts without shell tools, `sadskill` acts as a senior technical advisor, generating correct code and test scripts for the user to execute manually.
4. **Unsupported / Unverified**: Features requiring external tools (e.g. live database connections, real browser rendering) are clearly labelled as `UNVERIFIED` rather than fabricating execution proof.
