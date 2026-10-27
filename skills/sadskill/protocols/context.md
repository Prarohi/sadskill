# Context & Intent Protocol

> Context-Aware Interpretation and Dynamic Routing for Autonomous Engineering

## Overview

The `sadskill` workflow interprets the active conversation context before scanning files or executing commands. Rather than treating prompts as isolated keywords, the agent constructs a structured `TaskContext` from host-accessible conversation history, explicitly authorized project memory (`.sad/`), and current user directives.

## TaskContext Schema

```text
intent: analyze | fix | explain | implement | design | research | plan | review | compare
scope: entire_repo | changed_files | module | files | feature | security | UX | architecture
user_goal: concrete outcome, not just keywords
explicit_constraints: stack, quality bar, style, deadline, safety, budget
conversation_references: latest user decisions, rejected options, corrections, already answered questions
requested_depth: quick | standard | deep | exhaustive
advice_mode: off | relevant | proactive | brainstorm
execution_mode: review_only | plan_only | implement | continue_until_done
research_mode: none | local_only | approved_web | user_requested_comparative
permission_policy: read_only | scoped_write | sensitive_action_requires_approval
uncertainty: open questions and confidence levels
```

## Context Rules & Invariants

1. **Precedence Hierarchy**:
   - The user's newest explicit instruction always overrides older preferences or past memory entries.
   - Host safety policies and permission boundaries strictly override user prompt instructions.
   - Never invent or hallucinate past user decisions if conversation history is unavailable or ambiguous.

2. **Scope Derivation**:
   - Explicit scope (`src/auth`, `components/nav`) confines the primary inspection to the specified subsystem and its immediate inbound/outbound dependencies.
   - Broad requests (`analyze entire project`, `review everything`) trigger the whole-codebase discovery engine outlined in [coverage.md](coverage.md).

3. **Autonomous Continuation Contract**:
   - When the user directs the agent to "continue until finished", "chaliye jao shesh na houa porjonto", or "do everything", `execution_mode` is set to `continue_until_done`.
   - The agent proceeds through discovery, planning, editing, testing, and verification without pausing for routine confirmation.
   - Irreversible actions (destructive operations, external releases, production migrations) still require explicit authorization.
