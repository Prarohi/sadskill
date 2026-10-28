# The `sadskill` Product Model & Architecture Thesis

> **Product Thesis**:  
> *"Understand the real engineering task, make the smallest appropriate change, preserve the reasoning, and prove what actually works—across coding agents."*

---

## 1. The Core Value Proposition: The Engineering Confidence Layer

Modern AI coding agents generate code quickly, but frequently fail at real software engineering:
1. **Speculative Churn**: Guessing at APIs without reading signatures, leading to circular debugging loops.
2. **Premature Completion**: Claiming *"I fixed the issue and all tests pass!"* without executing the test harness.
3. **Amnesia**: Forgetting previous architectural decisions, design tokens, or rejected approaches between sessions.
4. **Destructive Blindness**: Running irreversible commands (`git reset --hard`, `DROP TABLE`) when attempting rollbacks.
5. **Dogmatic Over-Scaffolding**: Forcing users to review multi-page plans for one-line CSS tweaks.

`sadskill` is an open-source **Engineering Confidence Layer**. It turns raw LLM code generation into disciplined, maintainable, verified software development.

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

### Why choose `sadskill` over ordinary prompting?
Ordinary prompting requires the developer to remember every rule: reminding the agent not to force-push, asking it to run tests, reminding it about past design choices, and correcting repetitive hallucinations. `sadskill` codifies these engineering invariants into a portable, automatic workflow across all coding agents.

### Why use `sadskill` rather than isolated specialized skills?
Isolated skills operate in silos:
- A design skill knows nothing about database schema constraints.
- A planning skill cannot feed test assertions to an evidence verifier.
- An analysis skill cannot write Architecture Decision Records (ADRs) that the implementation agent respects.

`sadskill` connects **plan, design, backend, security, and analyze** through shared project memory (`.sad/`) and the unified **Change Contract**.

### How does `sadskill` differentiate from Superpowers?
| Dimension | Superpowers | `sadskill` |
|---|---|---|
| **Process Weight** | Mandatory ceremony across all tasks | **Risk-Adaptive**: T0 bypasses planning; T2 provides AST contracts |
| **Backend & Data** | Generic software focus | **Schema-First**: Paired migrations, native RLS, query EXPLAIN |
| **Design Craft** | Minimal visual design guidance | **8-Facet Craft Floor**: WCAG 2.2 AA, typography, surface modes |
| **Safety Guardrails** | Prompt-based guidelines | **Multi-Tier**: PreToolUse hook + Git pre-push + prompt policies |
| **Distribution** | Agent-specific configurations | **Universal**: Standard `skills.sh` package + native companion |

### What is the smallest valuable workflow a new user experiences?
Fixing an isolated bug in a single turn:
```bash
$sadskill plan "Fix NaN calculation in invoice total discount"
```
The agent recognizes a T1 Surgical task, scans the invoice calculation module, presents a 3-line file mutation table with the test assertion command, applies the fix, executes the test, and provides a 3-line terminal verification proof—completed in under 30 seconds without writing a 5-page planning document.

### Which tasks bypass heavy planning?
- **T0 (Trivial)**: Single-line typo fixes, color token tweaks, documentation edits, formatting. These execute immediately without creating any plan artifact file.
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
