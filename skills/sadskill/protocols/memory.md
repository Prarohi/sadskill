# Protocol: Project Memory (`.sad/`)

`sadskill` maintains persistent, machine-readable project memory inside the `.sad/` directory at the project root. This guarantees that agent context, architectural decisions, and design choices survive across multi-turn sessions and agent restarts.

---

## 📁 Directory Structure

```text
.sad/
├── history.md             # Chronological changelog of high-level project milestones
├── design-memory.md       # Approved palettes, typography, UI patterns, and rejected anti-patterns
├── decisions.md           # Architecture Decision Records (ADRs)
├── plans/                 # Generated implementation plans (YYYY-MM-DD-<slug>.md)
└── reports/               # Security audits (security-*.md) and analysis (analysis-*.md)
```

---

## 🔄 Lifecycle Invariants

### 1. Pre-Task Reconnaissance
At the start of every task:
- Verify if `.sad/` exists. If missing, initialize it upon completing the first workflow.
- Always read `.sad/history.md` for project context.
- In UI/frontend tasks, read `.sad/design-memory.md` to avoid re-introducing rejected aesthetic patterns.
- In architectural tasks, read `.sad/decisions.md` before proposing major structural changes.

### 2. Post-Task State Persistence
Upon completing a task:
- Append completed milestones and notable additions to `.sad/history.md`.
- Document key architectural decisions in `.sad/decisions.md` (Context, Decision, Consequences).
- Record UI lessons and design tokens in `.sad/design-memory.md`.

### 3. Git Hygiene
- The `.sad/` directory is checked into version control so teams and collaborative agents share identical project memory.
- Ephemeral scratch notes or private secrets must NEVER be written to `.sad/`.
