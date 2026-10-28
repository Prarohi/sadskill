# Autonomous Continuation & Execution Modes Protocol

> Bounded Autonomy, Four Predictable Execution Modes, Hard Stop Triggers, and Bounded Retries

## 1. The Four Execution Contracts

Every task operates under an explicit execution contract derived from user intent:

| Mode | Contract Intent | Permitted Operations | Completion & Stop Policy |
|---|---|---|---|
| `REVIEW_ONLY` | Analysis, audit, or diagnostic requested. | Inspect source files, execute read-only queries, generate reports. | **Zero file mutations**. Output report and stop immediately. |
| `PLAN_ONLY` | Architecture spec or implementation plan requested. | Inspect codebase, evaluate alternatives, draft Change Contract. | Stop before modifying application source files. |
| `IMPLEMENT` | Specific scoped code changes requested. | Modify authorized files, run test suites, resolve localized test failures. | Stop once authorized scope is implemented and tests pass. |
| `CONTINUE_UNTIL_DONE` | End-to-end task delegation ("finish it", "chaliye jao shesh na houa porjonto"). | Autonomously execute all safe dependent steps, refactors, tests, and documentation updates. | Continue across steps without pausing for routine confirmation; stop ONLY at Hard Stop Triggers. |

---

## 2. Hard Stop Triggers (Non-Autonomous Boundaries)

Even under `CONTINUE_UNTIL_DONE`, the agent **must halt** and request explicit confirmation before executing:

1. **Irreversible Destructive Actions**:
   - `DROP TABLE`, `TRUNCATE`, deleting production branches, `git reset --hard` destroying uncommitted user work.
2. **External Side-Effects & Billing**:
   - Live deployments, DNS updates, emailing real users, running paid third-party API mutations.
3. **Unresolved Contradictory Requirements**:
   - Ambiguities where two mutually exclusive architectural directions have equal validity and no codebase precedent exists.
4. **Credential & Secret Requests**:
   - Never attempt to guess or brute-force missing credentials or private keys.

---

## 3. Autonomous State Machine & Bounded Retries

```text
DISCOVER -> UNDERSTAND -> PLAN_PROPORTIONALLY -> EXECUTE -> TEST -> REVISE -> VERIFY -> COMPLETE
                                      |               ^
                                      v               |
                                BLOCKED_SCOPE --------+
                                      |
                            HARD_STOP_TRIGGER
```

### Bounded Retry Discipline
1. **Cap Fix Attempts at 3**:
   - When a test failure occurs during autonomous implementation, attempt at most **3** iterative fixes for the same underlying error.
2. **Strategy Shift on Attempt 3**:
   - If Attempt 1 and Attempt 2 fail with the same or worse error, do NOT retry the identical pattern a third time. Re-examine the fundamental assumption, inspect the upstream caller or dependency AST, and try an alternative approach.
3. **Clean Degradation & Reporting**:
   - If after 3 attempts the failure persists, halt execution, explain the exact obstacle with terminal logs, and present the user with concrete options rather than looping indefinitely.

---

## 4. Pre-Existing Failure Segregation

1. **Baseline Discovery**:
   - Before applying modifications, run the project's test suite to establish the baseline health.
2. **Failure Segregation**:
   - If pre-existing tests fail prior to any edits, record them in the task notes:
     ```text
     Pre-existing test failure: tests/legacy/payment_test.py (unrelated to current feature)
     ```
   - Do NOT attempt unauthorized broad rewrites of unrelated failing modules. Focus strictly on ensuring that new and touched code passes and introduces zero regressions against the pre-existing baseline.
