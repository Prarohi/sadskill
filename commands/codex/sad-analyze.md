# `/sad-analyze`

Execute the `analyze` workflow of `sadskill`.

## Instructions
1. Load and adhere to `sadskill`:
   - Inspect `.sad/` project memory.
   - Respect local profile if configured (`~/.sadskill/profile.md`).
   - Enforce the Human-Voice protocol.
2. Follow `skills/sadskill/modes/analyze.md`:
   - Determine scope:
     - Scoped analysis if specific path or module is provided (e.g., `/sad-analyze src/auth`).
     - Full codebase exploration if invoked without arguments or with `all`.
   - Analyze:
     - Architecture & entry points (generate Mermaid dependency graph).
     - Module depth, coupling, god-files, and cyclic dependencies.
     - Code health: dead code, duplicated logic, complexity bottlenecks.
     - Test coverage and verification gaps.
     - Quick security and performance smells.
   - Save report to `.sad/reports/analysis-<YYYY-MM-DD>.md`.
   - Provide summary with high-impact recommendations and next commands (`/sad-plan` or `/sad-sec`).
