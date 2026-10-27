# sad-plan

Execute the `plan` workflow of `sadskill` on target scope: $ARGUMENTS

## Instructions
1. **Locate sadskill Configuration**:
   - Check local workspace: `./skills/sadskill/SKILL.md` (if vendored in project).
   - Check global agent path: `~/.claude/skills/sadskill/SKILL.md` (or `~/.codex/skills/sadskill/SKILL.md`).
   - Check developer profile: `~/.sadskill/profile.md` for local style or tooling preferences.
2. **Global Invariants**:
   - Check `.sad/` project memory (`.sad/history.md`, `.sad/decisions.md`, `.sad/plans/`).
   - Enforce Human-Voice: deliver answers first, strip AI filler words ("delve", "seamless", "testament").
   - Grill on Ambiguity: batch questions with recommended defaults so the user can approve with `yes`.
3. **Adaptive Planning Pipeline**:
   - **Tier 1 (Surgical Plan)** for <= 2 files, bugfixes, visual CSS/HTML tweaks, or typos:
     Generate a concise plan (Goal, Mutation Table, Verification Test Command). Skip diagrams.
   - **Tier 2 (Deep Architectural Spec)** for new features, multi-file refactors, schema migrations, or APIs:
     Pre-declare Contract-First AST signatures, Mermaid data flow, boundary/failure modes, and test-first harness.
4. **Progressive Disclosure**:
   - Write exhaustive plan to `.sad/plans/<YYYY-MM-DD>-<slug>.md`.
   - Output a 5-10 line executive summary in chat with file link.
   - Await user approval before writing production code.
