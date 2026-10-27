# Protocol: Project Memory (`.sad/`) & Context Persistence

`sadskill` maintains persistent, machine-readable project memory inside the `.sad/` directory at the project root. This guarantees that agent context, architectural decisions, and design choices survive across multi-turn sessions, agent restarts, and team collaboration.

---

## 📁 Directory Structure

```text
.sad/
├── history.md             # Chronological changelog of high-level project milestones
├── design-memory.md       # Approved palettes, typography, UI patterns, and rejected anti-patterns
├── decisions.md           # Architecture Decision Records (ADRs)
├── plans/                 # Generated implementation plans (YYYY-MM-DD-<slug>.md)
├── reports/               # Security audits (security-*.md) and analysis (analysis-*.md)
├── checkpoints/           # Resumable session state for multi-step tasks
└── evidence/              # Structured verification proof logs (*.json)
```

---

## 🔒 Memory Trust Model & Secret Hygiene

1. **Scoped Storage Separation**:
   - **Task Context**: Current user goal and explicit constraints (ephemeral).
   - **Project Decisions**: Shared ADRs in `.sad/decisions.md` (version-controlled, secret-free).
   - **Session Checkpoints**: Task resumption logs in `.sad/checkpoints/` (contains only file lists, hashes, and next steps).
   - **User Profile**: Private local workstation preferences stored in `~/.sadskill/profile.md` (never committed to repository).
2. **Secret Redaction**:
   - Never persist credentials, tokens, passwords, private keys, or personal identifiers in `.sad/`.
   - Scan memory payloads before writing; redact matching authorization patterns.
3. **Concurrent Multi-Agent Writers**:
   - Use atomic append/replace when updating `.sad/history.md` or `.sad/decisions.md`.
   - Never overwrite existing decisions without documenting rationale and superseding references.

---

## 🔄 Lifecycle Invariants

### 1. Pre-Task Reconnaissance
At the start of every task:
- Verify if `.sad/` exists. If missing, initialize it upon completing the first workflow.
- Read `.sad/history.md` for project context.
- In UI/frontend tasks, read `.sad/design-memory.md` to avoid re-introducing rejected aesthetic patterns.
- In architectural tasks, read `.sad/decisions.md` before proposing major structural changes.
- In multi-mode workflows, consume structured handoff JSON defined in [context-handoff.template.json](../templates/context-handoff.template.json).

### 2. Post-Task State Persistence
Upon completing a task:
- Append completed milestones and notable additions to `.sad/history.md`.
- Document key architectural decisions in `.sad/decisions.md` (Context, Decision, Consequences).
- Record UI lessons and design tokens in `.sad/design-memory.md`.
- Record verification evidence in `.sad/evidence/` conforming to [evidence.md](evidence.md).

### 3. Git Hygiene
- The `.sad/` directory is checked into version control so teams and collaborative agents share identical project memory.
- Ephemeral scratch notes or private secrets must NEVER be written to `.sad/`.
