# sad-analyze

Execute the `analyze` workflow of `sadskill` on target scope: $ARGUMENTS

## Instructions
1. **Locate sadskill Configuration**:
   - Check local workspace: `./skills/sadskill/SKILL.md` (or global `~/.claude/skills/sadskill/SKILL.md`).
   - Check `.sad/decisions.md` and past reports in `.sad/reports/`.
2. **Determine Analysis Scope**:
   - Scoped: If a specific path or module is passed in `$ARGUMENTS` (e.g. `/sad-analyze src/auth`).
   - Full: If invoked without arguments or with `all`.
3. **Multi-Vector Architecture Scan**:
   - John Ousterhout Deep Module Philosophy: Identify shallow modules (bloated interfaces hiding minimal logic) and find seams for deepening.
   - Coupling & Cycles: Detect circular dependencies and monolithic god-files.
   - Code Health & Dead Code: Find unused exports, redundant dependencies, and unreachable code paths.
   - Verification Gaps: Identify critical workflows lacking automated test assertions.
   - Mermaid Architecture Diagram: Generate visual component flow.
4. **Collision-Proof Reporting**:
   - Write report to `.sad/reports/analysis-<YYYY-MM-DD>-<HHMMSS>.md`.
   - Output high-impact prioritization matrix and recommend next command (`/sad-plan` or `/sad-sec`).
