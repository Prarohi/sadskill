# Autonomous Continuation & Execution Modes Protocol

> Bounded Autonomy, Four Predictable Execution Modes, and Clarification Budgets

## 1. The Four Execution Modes

Every task operates under one of four unambiguous execution contracts:

| Mode | Meaning | Permitted Operations | Stop / Completion Policy |
|---|---|---|---|
| `REVIEW_ONLY` | Analysis or audit requested | Inspect files, run read-only queries, generate reports | Never modify workspace code; output report and stop |
| `PLAN_ONLY` | Architectural plan requested | Inspect repository, draft implementation plan | Stop before creating or editing source files |
| `IMPLEMENT` | Specific code changes requested | Implement scoped edits, run tests, fix local failures | Stop once authorized task passes tests |
| `CONTINUE_UNTIL_DONE` | Explicit delegation to complete task | Execute all safe dependent steps, tests, and follow-ups | Continue until fully verified; stop only on hard blockers |

## 2. Clarification Budget

To avoid unnecessary question loops and token waste:
1. **Inspect First**: Check repository code, configuration, and conversation history before asking a question.
2. **Standard Conventions**: If multiple reasonable options exist, select the convention already established in the codebase.
3. **Approval Threshold**: Prompt the user ONLY when:
   - Irreversible destructive actions are required (e.g., dropping database tables, deleting branches).
   - Production deployments, external releases, or paid API usage are involved.
   - Contradictory requirements cannot be resolved from existing context.
4. **Never Repeat Questions**: If the user has already answered a question in accessible context, treat that decision as binding.

## 3. Autonomous State Machine

```text
DISCOVER -> UNDERSTAND -> PLAN_PROPORTIONALLY -> EXECUTE -> TEST -> REVISE -> VERIFY -> COMPLETE
                                     |               ^
                                     v               |
                               BLOCKED_SCOPE --------+
                                     |
                         ASK_ONLY_IF_REQUIRED
```

- **Bounded Retries**: Cap fix attempts per issue at 3. If a fix fails repeatedly, change strategy or segregate the blocker.
- **Pre-existing Failures**: If existing tests were already broken prior to current work, record baseline failures separately without modifying unrelated files.
- **Checkpointing**: For multi-step tasks, record incremental status in `.sad/checkpoints/` or durable task notes without exposing secrets.
