# sad-analyze

Execute the `analyze` workflow of `sadskill` on: $ARGUMENTS

Follow `skills/sadskill/SKILL.md` and `skills/sadskill/modes/analyze.md`:
1. Check `.sad/` project memory.
2. Read `~/.sadskill/profile.md` if present.
3. Apply the Human-Voice protocol.
4. Determine scope (scoped path if provided, or entire codebase if none/all).
5. Analyze repo structure, entry points, module depth, coupling, dead code, test coverage, and code smells.
6. Generate Mermaid architecture diagram.
7. Output structured analysis to `.sad/reports/analysis-<YYYY-MM-DD>.md`.
8. Recommend high-leverage follow-up commands (`/sad-plan` or `/sad-sec`).
