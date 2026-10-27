---
name: sadskill
description: "Unified autonomous engineering skill for coding agents. Provides 5 high-leverage workflows: /sad-plan (planning & spec), /sad-design (UI/UX & polish), /sad-backend (schema & RLS), /sad-sec (security & OWASP audit), and /sad-analyze (architecture & code health)."
metadata:
  version: 0.1.0
  author: sadafbabu
  license: MIT
---

# `sadskill` Router & Runtime

`sadskill` is a unified agent skill uniting the best engineering workflows, design practices, architectural patterns, and security audits under one roof. It runs on any modern coding agent (Codex / ChatGPT, Claude Code, Cursor, Antigravity, Gemini CLI).

---

## 🧭 Command Router

Inspect the incoming user prompt or slash command. Route immediately to the corresponding mode:

| Trigger | Target Mode | Reference Document | Purpose |
|---|---|---|---|
| `/sad-plan` or `$sadskill plan` | **Plan** | [modes/plan.md](modes/plan.md) | Codebase reconnaissance, requirement grilling, and A-to-Z execution plans in `.sad/plans/`. |
| `/sad-design` or `$sadskill design` | **Design** | [modes/design.md](modes/design.md) | Accessible, distinctive UI/UX craft, design tokens, anti-slop rules, and `.sad/design-memory.md`. |
| `/sad-backend` or `$sadskill backend` | **Backend** | [modes/backend.md](modes/backend.md) | Schema-first DDL, reversible migrations, Row Level Security, indexing, and API verification. |
| `/sad-sec` or `$sadskill sec` | **Security** | [modes/security.md](modes/security.md) | OWASP Top 10, secret detection, dependency audit, headers/CSP, and 15-point launch legal checklist in `.sad/reports/`. |
| `/sad-analyze` or `$sadskill analyze` | **Analyze** | [modes/analyze.md](modes/analyze.md) | Deep codebase exploration, module coupling, dead code, test gaps, and Mermaid architecture diagrams. |

If no slash command is used but the user requests engineering assistance, select the most relevant mode or ask a single clarifying question.

---

## 🛡️ Global Invariants (Always Active)

Regardless of the active mode, every agent turn must honor these invariants:

### 1. Project Memory (`.sad/`)
- Check for `.sad/` in the workspace root at the start of every task.
- Read `.sad/history.md`, `.sad/design-memory.md`, and `.sad/decisions.md` before taking action.
- Update memory upon task completion. Never re-introduce an approach previously rejected in `.sad/design-memory.md`.
- Read protocol details in [protocols/memory.md](protocols/memory.md).

### 2. Human Voice Protocol
- Deliver the answer or action immediately before any exposition.
- Strip all AI conversational filler and clichés ("delve", "seamless", "tapestry", "in summary", "moreover", "testament").
- Ban sycophantic openers ("Great question!", "Certainly, I'd love to help!").
- Keep responses concise, specific, and technically grounded.
- Read protocol details in [protocols/human-voice.md](protocols/human-voice.md).

### 3. Grilling on Ambiguity
- When requirements are underspecified or architectural choices carry irreversible trade-offs, grill the user.
- Ask questions one round at a time; never interrogate over trivial facts that can be inspected in the codebase.
- Always provide a recommended default so the user can reply with "yes" or hit Enter.
- Read protocol details in [protocols/grilling.md](protocols/grilling.md).

### 4. Local User Profile Support (`~/.sadskill/profile.md`)
- Check dynamically whether `~/.sadskill/profile.md` exists on the local machine.
- If present, adopt the developer's language, style, or personal tooling preferences.
- If absent, proceed with neutral, professional engineering defaults.
- **Strict Isolation**: Personal profiles live outside the repository and are never committed.
- Read protocol details in [protocols/profile.md](protocols/profile.md).

### 5. Safe MCP Tool Usage
- Use configured Model Context Protocol (MCP) tools when available (e.g., browser inspection, database querying).
- Never modify MCP configurations or attempt automated installation of unverified MCP plugins.
- Read protocol details in [protocols/mcp.md](protocols/mcp.md).

### 6. Maximum Token Efficiency & Progressive Disclosure
- Maximize information density: deliver findings in structured tables, concise bullets, and diff boundaries.
- Never paste entire manuals, long transcripts, or raw file dumps into conversation context. Load only the targeted rule or slice needed.
- Write extensive plans and reports to `.sad/plans/` and `.sad/reports/`, outputting a 5-10 line executive summary and relative file link in chat.
- Batch code edits into contiguous replacements rather than piecemeal roundtrips.
- Read protocol details in [protocols/output-style.md](protocols/output-style.md).

### 7. Destructive Action Guardrails
- Autonomous agents must never execute destructive operations (`git reset --hard`, `git push --force`, `git clean -fd`, `DROP TABLE`, `TRUNCATE`) without an explicit user approval gate.
- Prefer non-destructive workflows (`git stash`, reversible migrations, transaction rollbacks).
- Read protocol details in [protocols/safety.md](protocols/safety.md).

---

## 📚 Ecosystem & Vendor References

`sadskill` integrates curated best practices mapped in the [vendor index](vendor/INDEX.md):
- **Planning & Architecture**: Matt Pocock deep modules, Superpowers, Karpathy guidelines.
- **Design & UI**: Impeccable craft floor, Taste taxonomy, Shadcn/Radix primitives, Vercel design guidelines.
- **Backend & Database**: Supabase patterns, PostgreSQL indexing & RLS.
- **Security & Quality**: OWASP Top 10, ECC security reviews, 15-point launch legal checklist.
