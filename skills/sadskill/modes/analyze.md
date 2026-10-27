# Mode: `/sad-analyze`

Analyze mode conducts deep conversation-aware architectural discovery, whole-codebase mapping with coverage ledgers, module coupling assessment, dead code elimination, test coverage verification, and dependency topology visualization.

---

## 🔍 Execution Pipeline

### Phase 1: Context Interpretation & Scope Discovery
1. **Interpret Live Conversation**: Construct `TaskContext` per [context.md](../protocols/context.md) to extract true user intent, requested depth (`quick`, `standard`, `deep`, `exhaustive`), advice preferences, and execution mode (`REVIEW_ONLY` vs `CONTINUE_UNTIL_DONE`).
2. **Determine Analysis Scope**:
   - **Scoped Mode**: Target a specific directory, package, or module when an argument is supplied (e.g. `/sad-analyze src/auth`).
   - **Whole Codebase Mode**: Comprehensive scan when invoked with no arguments, `all`, or whole-project phrasing.
3. **Repository Inventory & Coverage Accounting**:
   - Discover roots, package manifests, build tools, and configuration files per [coverage.md](../protocols/coverage.md).
   - Enumerate tracked files and record explicit exclusions (`node_modules/`, `dist/`, build artifacts).
   - Produce a structured coverage ledger (`FULL_COVERAGE` or `PARTIAL_COVERAGE`). Never claim 100% inspected without full interface verification.

### Phase 2: Architecture & Dependency Topology
1. Construct a Mermaid dependency diagram illustrating component flows:
   - Clients / Entry points -> Handlers / Controllers -> Domain / Business logic -> Data / Storage layer.
2. Identify cross-boundary violations (e.g. direct database queries inside UI templates or circular imports across modules).

### Phase 3: Structural, Code Health & Risk Audit
1. **Module Depth vs Shallow Complexity**:
   - Flag "god files" (>500 lines of mixed concerns).
   - Flag shallow abstractions that add indirection without encapsulating complexity.
2. **Coupling & Cohesion**:
   - Detect circular dependencies and tightly coupled sibling packages.
   - Locate hardcoded environment constants or magic numbers.
3. **Multi-Dimensional Defect Scan**:
   - **Correctness**: Null/undefined dereferences, unhandled error cases, race conditions.
   - **Runtime & Performance**: N+1 queries, unindexed foreign keys, memory leaks, blocking operations.
   - **Dead Code**: Unreferenced exports, abandoned utility helpers, or obsolete feature flags.

### Phase 4: Test Coverage & Verification Gap Analysis
1. Inspect the existing test suite:
   - Identify unit, integration, and end-to-end test runners.
   - Check test execution speed and reliability.
2. Map verification gaps:
   - Uncovered error handling paths and boundary conditions.
   - Critical workflows lacking automated test assertions.
   - Mocking anti-patterns (e.g. mocking internal implementation details rather than external seams).

### Phase 5: Reporting & Actionable Roadmap
1. Generate the structured analysis report:
   - Executive architectural summary and coverage statistics.
   - Dependency Mermaid diagram.
   - High-impact architectural findings categorized by severity.
   - Concrete, phased recommendations following [advice.md](../protocols/advice.md).
2. Save the report to `.sad/reports/analysis-<YYYY-MM-DD>-<HHMMSS>.md` (or append `-2.md` to prevent overwriting prior runs on the same date).
3. If in `REVIEW_ONLY` mode, stop immediately without making modifications to the user's workspace code.
4. Conclude with immediate next actions:
   - Propose `/sad-plan` to execute architectural refactors.
   - Propose `/sad-sec` if security vulnerabilities were observed.

---

## 🔗 Vendor Synergies
- **Matt Pocock**: [mattpocock/codebase-design.ref.md](../vendor/mattpocock/codebase-design.ref.md) and [mattpocock/tdd.ref.md](../vendor/mattpocock/tdd.ref.md).
- **Karpathy Principles**: [karpathy/guidelines.ref.md](../vendor/karpathy/guidelines.ref.md).
- **Superpowers**: [superpowers/writing-plans.ref.md](../vendor/superpowers/writing-plans.ref.md).
