# Sadskill Workflow Architecture — 0.5.0 Candidate

This guide describes **desired host-agent behavior**, not a claimed deterministic orchestration engine. The canonical executable-instruction policy is [`skills/sadskill/protocols/workflow.md`](../skills/sadskill/protocols/workflow.md).

## Design goals

- **Permission before convenience:** user intent and host-authorized operations are separate decisions. A slash command is a domain selector; it is not a grant to write.
- **Composability:** keep Plan, Design, Backend, Security and Analyze independently understandable; compose them in short phases when a task crosses concerns.
- **Smallest safe workflow:** T0 for trivial, T1 for isolated, T2 for security-sensitive or architectural work, regardless of number of files.
- **Low context overhead:** load the selected mode, orchestration contract when needed, direct protocol dependencies and one relevant vendor reference at a time.
- **Evidence, not assertion:** a skill file, fixture check, or agent-generated JSON is not a passing live-agent benchmark or independent CI attestation.

## End-to-end example: auth change with security review

1. Parse "fix login, check auth leakage, and merge safely". This permits implementation and a *requested* merge attempt but not bypassing branch protections.
2. Identify Backend as the primary mode, Analyze and Security as bounded supporting phases.
3. Discover auth entry points, policy checks and relevant tests. Classify T2 because authorization can fail across tenants.
4. Preserve local changes; select scoped baseline/negative tests. Analyze the flaw read-only.
5. Implement only the authorized fix, verify both acceptance and cross-tenant rejection.
6. Security phase remains read-only; report any residual findings.
7. Require current-head CI, required independent review and resolved review threads before merge. If blocked, report unmerged PR and precise blockers.

## Execution mode examples

| Request | Contract | Allowed output |
|---|---|---|
| "Audit dependencies" | `REVIEW_ONLY` | In-chat audit with explicit uninspected paths, no `.sad` writes |
| "Plan database migration" | `PLAN_ONLY` | Plan and rollback; no schema change |
| "Fix this UI bug" | `IMPLEMENT` | Scoped changes and real test results |
| "Ship and merge this PR" | `CONTINUE_UNTIL_DONE` | Implementation, tests, PR, then merge only if external protections are satisfied |

## Capability and evidence matrix

| Capability | Behavior |
|---|---|
| Shell and workspace accessible | Run targeted checks, preserve real outputs and exit codes |
| Skill instructions only, no shell | Provide patch or commands; mark tests `NOT_EXECUTED` |
| CI job finished at exact head | Verify immutable run/commit identity; report CI result |
| CI metadata only in agent-authored file | Report `ci_claimed`, never `ci_attested` |
| Read-only task | Explain verification inline; no report/evidence writes |

## Operational release gates

Changes to router behavior require: valid skill discovery, intact five-mode links, permission boundary tests, review-only no-write invariant, proportional baseline test, cross-agent installation smoke tests, and exact-head CI. Real-model superiority requires independent paired agent runs with measured correctness, safety, tokens and time. Static contract checks are not that benchmark.

If permissions or tools are missing, retain work in a reviewable PR and state the blocker. Do not bypass review protections or claim a green test you did not execute.
