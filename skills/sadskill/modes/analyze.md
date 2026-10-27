# Mode: `/sad-analyze`

Analyze mode conducts deep architectural discovery, module coupling assessment, dead code elimination, test coverage verification, and dependency topology visualization.

---

## 🔍 Execution Pipeline

### Phase 1: Scope & Reconnaissance
1. Determine analysis target:
   - **Scoped Mode**: Target a specific directory, package, or module when an argument is supplied (e.g. `/sad-analyze src/auth`).
   - **Full Codebase Mode**: Comprehensive scan when invoked with no arguments or `all`.
2. Locate entry points, public API boundaries, routing layers, and data schema models.
3. Identify build systems, package managers, and configuration files.

### Phase 2: Architecture & Dependency Topology
1. Construct a Mermaid dependency diagram illustrating high-level component flows:
   - Clients / Entry points -> Handlers / Controllers -> Domain / Business logic -> Data / Storage layer.
2. Identify cross-boundary violations (e.g. direct database queries inside UI templates or circular imports across modules).

### Phase 3: Structural & Code Health Audit
1. **Module Depth vs Shallow Complexity**:
   - Flag "god files" (>500 lines of mixed concerns).
   - Flag shallow abstractions that add indirection without encapsulating complexity.
2. **Coupling & Cohesion**:
   - Detect circular dependencies and tightly coupled sibling packages.
   - Locate hardcoded environment constants or magic numbers.
3. **Dead Code & Redundancy**:
   - Identify unreferenced exports, abandoned utility helpers, or obsolete feature flags.
   - Detect duplicated business logic that should be unified into deep modules.

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
   - Executive architectural summary.
   - Dependency Mermaid diagram.
   - High-impact architectural findings categorized by severity.
   - Concrete, phased recommendations.
2. Save the report to `.sad/reports/analysis-<YYYY-MM-DD>-<HHMMSS>.md` (or append `-2.md` to prevent overwriting prior runs on the same date).
3. Conclude with immediate next actions:
   - Propose `/sad-plan` to execute architectural refactors.
   - Propose `/sad-sec` if security vulnerabilities were observed.

---

## 🔗 Vendor Synergies
- **Matt Pocock**: [mattpocock/codebase-design.ref.md](../vendor/mattpocock/codebase-design.ref.md) and [mattpocock/tdd.ref.md](../vendor/mattpocock/tdd.ref.md).
- **Karpathy Principles**: [karpathy/guidelines.ref.md](../vendor/karpathy/guidelines.ref.md).
- **Superpowers**: [superpowers/writing-plans.ref.md](../vendor/superpowers/writing-plans.ref.md).
