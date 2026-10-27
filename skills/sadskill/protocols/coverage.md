# Whole-Codebase Coverage & Discovery Protocol

> Systematic Repository Mapping, Exclusion Accounting, and Truthful Coverage Reporting

## 1. Repository Inventory & Discovery

When evaluating an entire repository or complex subsystem, the agent constructs an objective inventory before drawing conclusions:

1. **Manifest & Workspace Detection**: Identify root and nested package manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.).
2. **Tracked File Enumeration**: Enumerate tracked source files using `git ls-files` or fast filesystem queries.
3. **Explicit Exclusion Ledger**: Record all ignored or deprioritized paths:
   - Dependency trees (`node_modules/`, `vendor/`, `.venv/`)
   - Build outputs and caches (`dist/`, `build/`, `.next/`, `target/`)
   - Minified bundles, binaries, media assets, and large data fixtures
4. **Reachable Surface Mapping**: Identify public API endpoints, controllers, UI components, background workers, database models/migrations, and security boundaries.

## 2. Coverage Ledger & Truthfulness Invariant

The agent must never claim "100% analyzed" or "entire project verified" unless every reachable interface has been inspected.

The inspection maintains a **Coverage Ledger**:
- Subsystems identified and inspected
- Total tracked source files vs inspected files
- Config and test coverage status
- Excluded paths with explicit rationale
- Coverage Status: `FULL_COVERAGE` or `PARTIAL_COVERAGE`

If token budgets or context windows necessitate sampling or truncation, the agent must explicitly state `PARTIAL_COVERAGE` and document the uninspected boundaries.

## 3. Risk-First Prioritization

When whole-repository analysis is initiated, inspect high-risk surfaces first:
1. Authentication, authorization, and tenant isolation boundaries
2. Financial, billing, and transactional operations
3. Database migrations, schema constraints, and raw SQL queries
4. Untrusted user input processing, file uploads, and shell command execution
5. Secret handling, logging hygiene, and external network interactions
