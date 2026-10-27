# Architecture Decision Records (ADRs)

Key architectural decisions governing `sadskill` design and evolution.

---

## ADR-001: Frontmatter Neutralization for Single Discoverable Skill
- **Context**: Coding agents (Codex, Claude Code, Cursor) scan directories for YAML frontmatter delimiters (`--- name: ...`). Multiple discovered skills confuse agents and cause command routing conflicts.
- **Decision**: Only root `skills/sadskill/SKILL.md` exposes top-level frontmatter. All vendored reference files are named `*.ref.md` and routed through `vendor/INDEX.md`.
- **Consequences**: Universal package managers (`skills.sh`) register exactly 1 clean skill while retaining rich internal documentation.

## ADR-002: Adaptive Two-Tier Planning to Prevent Token Bloat
- **Context**: Exhaustive AST contract planning on minor bugfixes or 1-line CSS adjustments causes severe token waste and slower turnaround.
- **Decision**: `/sad-plan` dynamically bifurcates into **Tier 1 (Surgical Plan)** for <= 2 files/styling/bugfixes and **Tier 2 (Deep Architectural Spec)** for complex features/migrations.
- **Consequences**: Minimizes token burn on small tasks while retaining rigorous specification boundaries on architectural changes.

## ADR-003: Dual-Record Verification Evidence Standard
- **Context**: LLM coding agents often hallucinate "all tests pass" without running verification commands.
- **Decision**: Every completed task must record structured execution proof in `.sad/evidence/<timestamp>-<slug>.json` and output a 3-line terminal execution proof in chat showing exit code 0.
- **Consequences**: High credibility, reproducible audits, and zero unverified completions.

## ADR-004: Executable PreToolUse Safety Guardrails
- **Context**: Prompt-only safety instructions can be bypassed or ignored by agents executing tool calls.
- **Decision**: Provide an executable hook script `scripts/git-guardrail.sh` installable into Claude Code `PreToolUse` and Git hooks to programmatically intercept destructive Git (`reset --hard`, `push -f`, `clean -fd`) and SQL operations.
- **Consequences**: Deterministic safety enforcement at the OS process boundary.
