# Mode: `/sad-plan`

Plan mode conducts **intense upfront specification** and creates deterministic, zero-waste implementation plans. A rigorous, deep plan eliminates guesswork, prevents hallucinated APIs, and minimizes debugging loops—the single largest source of token waste in autonomous agent engineering.

---

## ⚡ The Zero-Waste / High-Density Philosophy

1. **Intense Upfront Planning Saves 80% of Downstream Tokens**:
   - Speculative code patching is the #1 token waster in autonomous agents. When an agent edits code without knowing exact signatures, it enters a 3-5 turn error cycle fixing imports, type errors, and missing parameters.
   - 10 minutes spent nailing the exact types, data flows, edge cases, and test assertions upfront prevents hours of trial-and-error edits and circular error loops.
2. **Contract-First AST Planning**:
   - Every modified or created function, method, interface, and type must have its full signature declared before any implementation starts.
   - Declare exact parameter names, parameter types, return types, generic bounds, and error types.
   - For external dependencies, inspect their installed definitions (`node_modules`, `venv`, cargo docs) to prevent hallucinated API calls.
3. **Maximum Information Density**:
   - Avoid conversational prose, narrative essays, or repetitive summaries. Use structured tables, compact Mermaid graphs, and explicit file:symbol contracts.
4. **Progressive Disclosure**:
   - Do not dump all vendor references into context. Inspect [vendor/INDEX.md](../vendor/INDEX.md) and load only the single reference file relevant to the immediate sub-problem.
   - Extensive plans are written to `.sad/plans/` rather than flooded into chat context. The chat receives only an executive summary and file link.

---

## 🛠️ Execution Pipeline

### Phase 1: Memory & Codebase Reconnaissance
1. **Examine Project Memory (`.sad/`)**:
   - Read `.sad/history.md` for past milestones and dependencies.
   - Read `.sad/decisions.md` to prevent violating established Architecture Decision Records (ADRs).
   - Check `.sad/plans/` to avoid duplicating past specs.
2. **Deterministic Codebase Scan**:
   - Identify package manifests (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`).
   - Locate primary entry points and existing module seams.
   - Find the existing test runner and verification commands.

### Phase 2: Grilling on Ambiguity (Single-Round Frontier)
1. Never ask questions about facts discoverable from the repository.
2. If real architectural trade-offs exist (e.g. database schema vs document store, library choice, breaking API change):
   - Group all questions into **one batched round**.
   - Provide a concise title, context, and an explicit **Recommended Answer**.
   - Phrase questions so that the user can accept all recommendations by typing `yes`.

### Phase 3: Adaptive Specification (Tier 1 vs. Tier 2)

Evaluate task scope and execution mode per [context.md](../protocols/context.md) and [autonomy.md](../protocols/autonomy.md) before generating the plan to prevent instruction over-scaffolding and token waste:

- **Tiny Task** (typos, single line tweaks, mechanical lint): Minimal 2-5 step internal plan, execute directly without generating an external markdown spec if implementation is already authorized.

#### ⚡ Tier 1: Surgical Plan (Scope: <= 2 files, bug fixes, visual CSS/HTML tweaks, typos)
- **Format**:
  1. **Goal**: 1-2 sentence statement of target fix and user outcome.
  2. **File Mutation Table**: Target file, action (`MODIFY`), target symbol, and exact replacement diff.
  3. **Verification Command**: Exact test command and expected exit code 0.
- **Token Saver**: Skips Mermaid diagrams and extensive AST formalisms. Generates a lean 15-20 line plan in `.sad/plans/<YYYY-MM-DD>-<slug>.md` for rapid single-turn execution.

#### 🏛️ Tier 2: Deep Architectural Spec (Scope: new features, multi-file refactors, schema migrations, API changes)
The plan written to `.sad/plans/<YYYY-MM-DD>-<slug>.md` follows [templates/plan.template.md](../templates/plan.template.md) with full rigor:
1. **User Value & Concrete Outcome**: Single high-density paragraph.
2. **Architecture & Data Flow**: Compact Mermaid diagram showing components, boundaries, and dependencies.
3. **Contract-First AST Signatures**:
   - Explicit TypeScript/Python/Rust type definitions and interfaces for all new and touched entities.
   - Exact function signatures: arguments, types, return types, throws/errors.
4. **File-by-File Mutation Matrix**:
   - Target File Path (absolute or repo-relative).
   - Action: `CREATE`, `MODIFY`, or `DELETE`.
   - Exported symbols impacted and contiguous replacement boundaries.
   - Contiguous chunk strategy: batched edits to avoid piecemeal rewrites.
5. **Exhaustive Boundary & Edge Case Analysis**:
   - Zero/empty inputs (`[]`, `""`, `0`, `null`).
   - Boundary limits, overflow, concurrency, race conditions.
   - External failure modes: timeouts, network drops, auth token expiration, rate limits.
6. **Test-First Verification Harness**:
   - Exact test commands to execute (e.g. `npm test -- <path>`).
   - Specific assertions proving both the happy path and edge cases.
7. **Rollback & Recovery Plan**:
   - Step-by-step instructions to revert code and database migrations cleanly if verification fails.

### Phase 4: Mode-Aware Execution or Approval Gate
1. Write the completed plan to `.sad/plans/<YYYY-MM-DD>-<feature-slug>.md`.
2. Output a **compact executive summary** (5-10 lines max) in the chat:
   - 1-2 sentence summary of goal and approach.
   - Markdown table of files to create/modify.
   - Verification command.
   - Relative link to the plan markdown: `[Read Full Plan (.sad/plans/<filename>.md)]`.
3. **Execution Mode Hand-off**:
   - If `execution_mode` is `PLAN_ONLY`: stop and present plan to user.
   - If `execution_mode` is `CONTINUE_UNTIL_DONE` or `IMPLEMENT`: proceed autonomously with implementation and testing without halting for redundant confirmation.

---

## 🔗 Vendor Synergies
- **Superpowers**: [superpowers/writing-plans.ref.md](../vendor/superpowers/writing-plans.ref.md) and [superpowers/brainstorming.ref.md](../vendor/superpowers/brainstorming.ref.md).
- **Matt Pocock**: [mattpocock/codebase-design.ref.md](../vendor/mattpocock/codebase-design.ref.md) and [mattpocock/tdd.ref.md](../vendor/mattpocock/tdd.ref.md).
- **Karpathy Principles**: [karpathy/guidelines.ref.md](../vendor/karpathy/guidelines.ref.md).
