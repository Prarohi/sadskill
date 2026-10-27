# Reference: Codebase Onboarding (ECC Standards)

Origin: ECC Community  
License: MIT  

## Rapid Codebase Reconnaissance

When exploring an unfamiliar repository:
1. **Locate Manifest & Scripts**:
   - Inspect package manifests (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`).
   - Check available build, test, and lint scripts.
2. **Identify Primary Entry Points**:
   - Web / API: routes, server listeners, middleware pipelines.
   - CLI / Daemon: `main()` function, argument parsers, event loops.
3. **Map Directory Conventions**:
   - Note where business logic, database queries, and UI components reside.
   - Check if the repository adheres to clean architecture, MVC, or feature-based grouping.
4. **Inspect Test Coverage**:
   - Determine whether tests are unit tests, integration tests, or end-to-end tests.
   - Confirm tests run successfully before attempting any new changes.
