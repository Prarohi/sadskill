# Mode: `/sad-plan`

Plan mode conducts **proportional, risk-aware upfront specification** and creates deterministic, zero-waste implementation plans. A rigorous plan eliminates guesswork, prevents hallucinated APIs, and minimizes debugging loops—the single largest source of token waste in autonomous agent engineering.

---

## ⚡ The Zero-Waste & Proportional Planning Philosophy

1. **Intense Upfront Planning Eliminates Downstream Token Churn**:
   - Speculative code patching without knowing exact signatures or boundaries triggers multi-turn trial-and-error cycles fixing imports, type errors, and unexpected regressions.
   - Upfront specification of types, data flows, edge cases, and test assertions prevents circular debugging loops.
2. **Proportional Risk-Based Tiering (T0 / T1 / T2)**:
   - File count alone is not a reliable proxy for risk: a 1-line change to a permission check is high-risk, while editing 3 documentation files is trivial.
   - We evaluate risk across five dimensions: `blast_radius`, `reversibility`, `data_sensitivity`, `unknowns`, and `dependency_change`.
   - **T0 (Trivial)**: Bypass all plan file overhead for mechanical, low-risk edits.
   - **T1 (Surgical)**: Lean, single-turn file-mutation table for localized bugfixes.
   - **T2 (Architectural)**: Full Contract-First specification with AST signatures, Mermaid flows, and rollback plans.
3. **Contract-First AST Planning (For Nontrivial Tasks)**:
   - For all newly created or modified functions, declare complete signatures before implementation: argument names, argument types, return types, generic parameters, and error types.
   - For external packages, verify definitions against installed code (`node_modules/`, `venv/`, Cargo manifests) to prevent hallucinated API calls.
4. **Architectural Alternative Trade-Offs**:
   - When consequential design decisions arise (e.g., SQLite vs Postgres, optimistic UI vs server-authoritative, polling vs WebSockets), present 2 distinct alternatives with trade-offs rather than assuming a single path.
5. **Progressive Disclosure**:
   - Load the router first, select the mode, and load only the targeted protocol required.
   - Extensive architectural plans are saved to `.sad/plans/` rather than flooding the conversation context. Chat receives a 5-10 line executive summary and relative file link.

---

## 🛠️ Execution Pipeline

### Phase 1: Context, Memory & Codebase Discovery
1. **Interpret Live Conversation**:
   - Extract intent, user constraints, and execution mode (`REVIEW_ONLY`, `PLAN_ONLY`, `IMPLEMENT`, `CONTINUE_UNTIL_DONE`) per [protocols/context.md](../protocols/context.md).
   - Check if current user instructions supersede older notes.
2. **Examine Project Memory (`.sad/`)**:
   - Read `.sad/history.md` for past milestones and dependencies.
   - Read `.sad/decisions.md` to prevent violating established Architecture Decision Records (ADRs).
   - Check `.sad/design-memory.md` to avoid previously rejected UI patterns.
3. **Scoped Codebase Scan**:
   - Identify package manifests (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`).
   - Locate primary entry points and existing module seams.
   - Find the existing test runner and verification commands.

### Phase 2: Risk Classification & Proportional Tiering

Evaluate the task against the Risk Matrix:

| Risk Tier | Criteria & Examples | Planning Ceremony | Artifact Location |
|---|---|---|---|
| **T0: Trivial** | Single-line typo, CSS color/padding tweak, logging addition, documentation edit. Reversible, zero data risk. | **Bypass planning ceremony**. Execute directly if implementation is authorized; verify with standard test/lint. | No plan file written. Inline chat confirmation only. |
| **Tier 1: Surgical Plan** | Localized bugfix, small UI component adjustment, internal helper refactor (<= 2 files). Low blast radius, known test command. | **Lean Surgical Plan**. Skips Mermaid diagrams and heavy AST formalisms for lean tokens. 1-2 sentence goal, file-symbol mutation table, exact verification command. | Inline in chat (optional `.sad/plans/` record only if requested). |
| **Tier 2: Deep Architectural Spec** | New full-stack feature, database schema migration, multi-tenant auth, breaking API change, major refactor across >= 3 modules. | **Deep Architectural Change Contract**. Full Contract-First AST signatures, Mermaid architecture and data flow, boundary analysis, rollback plan. | Saved to `.sad/plans/<YYYY-MM-DD>-<slug>.md` following [templates/change-contract.template.md](../templates/change-contract.template.md). |

### Phase 3: Architectural Alternative Analysis (T2 Only)
When an architectural fork exists, present a concise trade-off comparison:
```text
Alternative A (Recommended): [Name]
  - Pros: [Performance, simplicity, aligns with existing conventions]
  - Cons: [Migration overhead or dependency constraint]
Alternative B: [Name]
  - Pros: [Extreme flexibility or separation]
  - Cons: [Complexity, additional boilerplate]
Recommended default: Alternative A.
```

### Phase 4: Constructing the Change Contract (T2 Architectural)
For T2 tasks, write the formal specification to `.sad/plans/<YYYY-MM-DD>-<feature-slug>.md` using [templates/change-contract.template.md](../templates/change-contract.template.md):
1. **Intent & Concrete Outcome**: Clear statement of developer objective and acceptance criteria.
2. **Architecture & Data Flow**: Compact Mermaid diagram showing affected components and data boundaries.
3. **Contract-First AST Signatures**: Explicit TypeScript/Python/Rust type definitions and interfaces for all touched entities.
4. **File-by-File Mutation Matrix**: Target paths, actions (`CREATE`, `MODIFY`, `DELETE`), exported symbols, and contiguous edit chunks.
5. **Boundary & Edge Case Analysis**: Empty inputs, nullability, concurrency/races, timeouts, and network failures.
6. **Test-First Verification Harness**: Exact terminal commands and assertions to prove correctness.
7. **Rollback & Recovery Plan**: Explicit reversal strategy (`git checkout`, `down.sql`, or feature flag rollback).

### Phase 5: Autonomous Execution or Approval Gate
1. For T2 plans, output a **compact executive summary** (5-10 lines max) in chat with relative file link: `[Read Full Plan (.sad/plans/<filename>.md)]`.
2. **Execution Mode Hand-off**:
   - If `execution_mode == PLAN_ONLY`: Halt and present plan to the user.
   - If `execution_mode == IMPLEMENT` or `CONTINUE_UNTIL_DONE`: Proceed immediately with safe implementation and test verification without pausing for routine confirmation.
   - Halt ONLY if a genuine destructive operation, financial API call, or production database migration requires explicit confirmation per [protocols/autonomy.md](../protocols/autonomy.md).

---

## 🔗 Vendor Synergies
- **Superpowers**: [superpowers/writing-plans.ref.md](../vendor/superpowers/writing-plans.ref.md) and [superpowers/brainstorming.ref.md](../vendor/superpowers/brainstorming.ref.md).
- **Matt Pocock**: [mattpocock/codebase-design.ref.md](../vendor/mattpocock/codebase-design.ref.md) and [mattpocock/tdd.ref.md](../vendor/mattpocock/tdd.ref.md).
- **Karpathy Principles**: [karpathy/guidelines.ref.md](../vendor/karpathy/guidelines.ref.md).
