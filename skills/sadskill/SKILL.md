---
name: sadskill
description: "One engineering workflow. Any coding agent. Turn AI-generated code into verified, maintainable software. Provides 5 high-leverage workflows: /sad-plan (adaptive planning & spec), /sad-design (UI/UX & polish), /sad-backend (schema & RLS), /sad-sec (security & OWASP audit), and /sad-analyze (architecture & code health)."
metadata:
  version: 0.3.0
  author: sadafbabu
  license: MIT
---

# `sadskill` Router & Runtime

> **Product Thesis**: *"Understand the real engineering task, make the smallest appropriate change, preserve the reasoning, and prove what actually works—across coding agents."*

`sadskill` is an **Engineering Confidence Layer** that equips autonomous AI agents with structured planning, craft-quality UI standards, database reliability, security auditing, and verification evidence.

---

## 🧭 Step 1: Command & Intent Router

Inspect the incoming user prompt or slash command. Route immediately to the target mode:

| Universal Trigger (`skills.sh`) | Native Slash Command (`install.sh`) | Natural Language Intent | Target Mode | Mode Specification |
|---|---|---|---|---|
| `$sadskill plan` | `/sad-plan` | "plan this feature", "create spec", "break down task" | **Plan** | [modes/plan.md](modes/plan.md) |
| `$sadskill design` | `/sad-design` | "design component", "UI polish", "style landing page" | **Design** | [modes/design.md](modes/design.md) |
| `$sadskill backend` | `/sad-backend` | "write schema", "database migration", "RLS policy" | **Backend** | [modes/backend.md](modes/backend.md) |
| `$sadskill sec` | `/sad-sec` | "audit security", "find secret leaks", "check OWASP" | **Security** | [modes/security.md](modes/security.md) |
| `$sadskill analyze` | `/sad-analyze` | "analyze codebase", "module depth", "find dead code" | **Analyze** | [modes/analyze.md](modes/analyze.md) |

### Invocation Architecture:
- **Standard (`skills.sh`)**: When installed via `npx skills add sadafbabu/sadskill`, invoke via `$sadskill <mode>` or natural language prompts.
- **Companion (`install.sh`)**: When installed via `./install.sh`, native slash commands (`/sad-*`) are registered directly into Claude Code commands (`~/.claude/commands/`), OpenAI Codex prompts (`~/.codex/prompts/`), and Cursor rules (`.cursor/rules/`).

---

## ⚡ Step 2: Progressive Disclosure Pipeline

To prevent context window bloat and minimize token waste, do **not** dump all protocols or vendor references into conversation context at once. Follow this lazy-loading sequence:

```text
[Incoming Prompt] ──> [1. Router: Select Mode]
                              │
                              ▼
                      [2. Load Target Mode: modes/<mode>.md]
                              │
                              ▼
                      [3. Load Targeted Protocols as Needed]
                        ├── Context & Autonomy (protocols/context.md, protocols/autonomy.md)
                        ├── Memory & Verification (protocols/memory.md, protocols/evidence.md)
                        └── Domain Protocol (e.g. coverage.md, research.md, advice.md)
                              │
                              ▼
                      [4. Load Specific Vendor Reference Only on Demand]
                        └── Look up single file via vendor/INDEX.md
```

---

## 🛡️ Step 3: Global Engineering Invariants (Always Active)

Regardless of the active mode, every agent turn must honor these core invariants:

### 1. Safety Guardrails & Non-Destructive Operations
- Autonomous agents must **never** execute destructive operations (`git reset --hard`, `git push --force`, `git clean -fd`, `DROP TABLE`, `TRUNCATE`) without an explicit user approval gate.
- Enforce the executable guardrail hook at [scripts/git-guardrail.sh](../../scripts/git-guardrail.sh).
- Read protocol details in [protocols/safety.md](protocols/safety.md).

### 2. Verification Evidence Standard
- Never claim a task, fix, or feature is complete without executing the test or build command and verifying exit code 0.
- Record structured verification metadata in `.sad/evidence/<timestamp>-<slug>.json`.
- Output a 3-line terminal execution proof in chat displaying command, exit code, and passed assertions.
- Read protocol details in [protocols/evidence.md](protocols/evidence.md).

### 3. Context & Project Memory (`.sad/`)
- Check for `.sad/` in the workspace root at the start of every task.
- Read `.sad/decisions.md` before taking architectural action, and `.sad/design-memory.md` before styling.
- Precedence: The user's newest explicit instruction in active conversation strictly overrides older memory notes.
- Read protocol details in [protocols/context.md](protocols/context.md) and [protocols/memory.md](protocols/memory.md).

### 4. Output Style & Token Efficiency
- Deliver findings in structured tables, concise diff boundaries, and lean bullet points.
- Output structure: `Done`, `Verified`, `Important note` (if safety-relevant), `Suggested next move`.
- Avoid narrative conversational filler and clichés ("delve", "seamless", "tapestry").
- Read protocol details in [protocols/output-style.md](protocols/output-style.md) and [protocols/human-voice.md](protocols/human-voice.md).

### 5. Grilling on Ambiguity & Adaptive Advice
- When requirements have irreversible trade-offs, ask batched questions with recommended defaults so the user can reply with "yes".
- Respect advice suppression flags ("just fix it", "quiet").
- Read protocol details in [protocols/grilling.md](protocols/grilling.md) and [protocols/advice.md](protocols/advice.md).

### 6. Local User Profile Support (`~/.sadskill/profile.md`)
- Dynamically detect if `~/.sadskill/profile.md` exists on the host machine.
- If present, adopt developer communication preferences without committing private data to the repository.
- Read protocol details in [protocols/profile.md](protocols/profile.md).

---

## 📚 Ecosystem & Vendor References

`sadskill` integrates curated best practices mapped in the [vendor index](vendor/INDEX.md):
- **Planning & Architecture**: Matt Pocock deep modules, Superpowers, Karpathy guidelines.
- **Design & UI**: Impeccable craft floor, Taste taxonomy, Shadcn/Radix primitives, Vercel design guidelines.
- **Backend & Database**: Supabase patterns, PostgreSQL indexing & RLS.
- **Security & Quality**: OWASP Top 10, ECC security reviews, 15-point launch legal checklist.
