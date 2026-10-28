# Mode: `/sad-analyze`

Analyze mode conducts **deep, evidence-driven architectural discovery, codebase topology mapping with coverage ledgers, module coupling assessment, dead code detection, verification gap analysis, and phased remediation planning**.

---

## 🏛️ Core Analysis Principles

1. **Truthful Coverage & Honest Accounting**:
   - Explicitly declare whether the analysis is **Scoped** (targeted directory, module, or package) or **Exhaustive Whole-Codebase**.
   - Enumerate tracked files and declare exclusions per [protocols/coverage.md](../protocols/coverage.md).
   - Produce a structured coverage status: declare `PARTIAL_COVERAGE` unless every relevant module interface has been directly inspected. Never claim 100% audit without evidence.
2. **Deep Modules Over Shallow Ceremony (Ousterhout Philosophy)**:
   - Identify shallow modules: complex interfaces that reveal internal mechanics while encapsulating little actual complexity.
   - Identify deep modules: simple, powerful interfaces that hide significant internal complexity behind clean seams.
   - Flag "god files" (>500 lines of mixed concerns) and find clean seams to decompose them into cohesive units.
3. **Evidence-Based Heuristics Over Speculative Hand-Waving**:
   - Detect coupling, drift, and dead code using verifiable heuristics: import graph cycles, export reference tracing, AST call hierarchies, and git churn.
   - Cite exact `file:line` coordinates for every architectural defect, anti-pattern, or complexity hotspot.
4. **Actionable Phased Roadmap (T0 / T1 / T2)**:
   - Analysis must not terminate in a vague laundry list of complaints.
   - Group recommendations into a prioritized, phased repair plan categorized by risk tiers (T0 Trivial, T1 Surgical, T2 Architectural) ready for direct hand-off to [modes/plan.md](plan.md).

---

## 🔍 Execution Pipeline

### Phase 1: Context Interpretation, Intent & Scope Discovery
1. **Interpret Live Conversation & Execution Mode**:
   - Construct `TaskContext` per [protocols/context.md](../protocols/context.md) to extract true user intent, requested depth (`quick`, `standard`, `deep`, `exhaustive`), advice preferences, and execution mode (`REVIEW_ONLY` vs `CONTINUE_UNTIL_DONE`).
2. **Determine Analysis Scope**:
   - **Scoped Mode**: Target a specific directory, package, or module when an argument is supplied (e.g. `/sad-analyze src/auth`).
   - **Whole-Codebase Mode**: Comprehensive scan when invoked with no arguments, `all`, or whole-project phrasing.
3. **Repository Inventory & Coverage Accounting**:
   - Locate root manifests (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `pom.xml`, `build.gradle`).
   - Enumerate tracked source files using `git ls-files` or filesystem walk.
   - Record explicit exclusions (`node_modules/`, `target/`, `dist/`, `.git/`, build artifacts).
   - Output coverage metrics: total tracked files, total inspected files, and coverage classification (`PARTIAL_COVERAGE` vs `FULL_COVERAGE`).

### Phase 2: Architecture & Dependency Topology
1. **Component Flow & Layering**:
   - Trace data flows: Client/UI -> Entry points / Controllers -> Domain / Business Logic -> Data / Storage Layer.
   - Generate a concise Mermaid architecture diagram visualizing primary boundaries and external services.
2. **Boundary Violations**:
   - Detect architectural leaks (e.g., database queries directly inside UI views, controller logic in ORM models, or circular dependencies across package boundaries).

### Phase 3: Code Health, Coupling & Structural Risk Audit
1. **Module Depth & Complexity Spikes**:
   - Flag monolithic files (>500 LOC) combining multiple disparate responsibilities.
   - Flag excessive nesting depth (>4 levels) and cyclomatic complexity hotspots.
2. **Coupling & Cohesion**:
   - Detect circular imports between modules.
   - Detect high afferent/efferent coupling where changes to one module ripple through the entire codebase.
   - Identify hardcoded environment assumptions, magic numbers, and missing configuration centralization.
3. **Dead Code & Drift**:
   - Detect unused exports and unreferenced internal functions.
   - Flag abandoned utility files, obsolete feature flags, and orphaned mock fixtures.
4. **Correctness & Concurrency**:
   - Identify unhandled promise rejections, unmanaged race conditions, resource leaks (unclosed sockets or file handles), and unvalidated input boundaries.

### Phase 4: Test Coverage & Verification Gap Analysis
1. **Test Suite Discovery**:
   - Discover test runners (Jest, Vitest, Pytest, Cargo test, Go test).
   - Measure test pass/fail status and execution speed.
2. **Verification Gaps**:
   - Identify critical business logic and authorization paths lacking automated test assertions.
   - Flag mock abuse (mocking internal implementation details instead of testing external boundaries).
   - Identify missing edge-case assertions (zero/empty inputs, network timeouts, error handling).

### Phase 5: Collision-Proof Reporting & Phased Roadmap
1. **Generate Structured Report**:
   - Compile findings into [templates/analysis-report.template.md](../templates/analysis-report.template.md).
   - Include coverage ledger, Mermaid topology, findings with exact `file:line` citations, and severity rankings.
   - Save report to `.sad/reports/analysis-<YYYY-MM-DD>-<HHMMSS>.md` (with collision handling).
2. **Produce Phased Repair Roadmap**:
   - **Phase A (T0 / Quick Wins)**: Zero-risk cleanup (unused imports, typo fixes, dead helper functions).
   - **Phase B (T1 / Surgical Repairs)**: Localized bug fixes, test gap filling, modularizing small functions (<= 2 files).
   - **Phase C (T2 / Architectural Refactors)**: Decomposing god files, breaking circular dependencies, standardizing error handling.
3. **Execution Gate**:
   - If in `REVIEW_ONLY` mode, halt and present the executive summary in chat without mutating source code.
   - Recommend next command:
     - Route to `/sad-plan` to design and execute specific phases of the repair roadmap.
     - Route to `/sad-sec` if security vulnerabilities or secret leaks were discovered.

---

## 🔗 Vendor Synergies
- **Matt Pocock**: [mattpocock/codebase-design.ref.md](../vendor/mattpocock/codebase-design.ref.md) and [mattpocock/tdd.ref.md](../vendor/mattpocock/tdd.ref.md).
- **Karpathy Principles**: [karpathy/guidelines.ref.md](../vendor/karpathy/guidelines.ref.md).
- **Superpowers**: [superpowers/writing-plans.ref.md](../vendor/superpowers/writing-plans.ref.md).
