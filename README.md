# `sadskill`

> **One engineering workflow. Any coding agent.**  
> *Turn AI-generated code into verified, maintainable software.*  
> Version: `v0.2.0` · License: `MIT` · Multi-Agent Compatible (Claude Code, OpenAI Codex, Cursor, Antigravity)

> *"Don't just generate code. Engineer it, verify it, and remember why."*

[![CI](https://github.com/sadafbabu/sadskill/actions/workflows/ci.yml/badge.svg)](https://github.com/sadafbabu/sadskill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![skills.sh](https://img.shields.io/badge/skills.sh-sadskill-success.svg)](https://skills.sh)

`sadskill` is an open-source autonomous engineering workflow framework. Instead of juggling dozens of conflicting agent plugins or enduring circular trial-and-error edits, `sadskill` provides **adaptive planning, shared project memory, executable safety guardrails, and proof-grounded verification** across every major coding agent.

---

## ⚡ Quickstart (Universal via `skills.sh`)

Install `sadskill` into any supported agent in one command:

```bash
npx skills add sadafbabu/sadskill
```

---

## 📊 Why `sadskill`? Benchmark Advantage

| Dimension | Default Plain Coding Agent | Agent Powered by `sadskill` |
|---|---|---|
| **Verification Proof** | Claims *"all tests pass"* blindly without proof | Real terminal proof with exit code `0` recorded in `.sad/evidence/` |
| **Token Efficiency** | Speculative trial-and-error editing cycles | **Adaptive 2-Tier Planning** (Surgical Plan for bugfixes; AST Contracts for features) |
| **Context Retention** | Resets completely across sessions | Persistent `.sad/` memory (`history.md`, `decisions.md`, `design-memory.md`) |
| **Safety Guardrails** | Can run `git reset --hard` or `DROP TABLE` | Executable `scripts/git-guardrail.sh` OS hook blocking destructive commands |
| **UI/UX Craft Floor** | Generic AI aesthetic (purple gradients, unscaled cards) | Strict **Zero-Lift** rule, 44px hit targets, WCAG AA, 20 UI polish rules |
| **Backend Reliability** | Destructive migrations and permissive queries | Reversible UP/DOWN migrations, zero-trust RLS, safe `EXPLAIN (BUFFERS)` |

---

## 🧭 The Five Core Workflows

| Command | Workflow | Description & Core Value |
|---|---|---|
| `/sad-plan` | **Adaptive Spec & Planning** | **Tier 1 (Surgical)**: <= 2 files/bugfix/CSS; single-turn lean diff table.<br>**Tier 2 (Architectural)**: Contract-First AST signatures, Mermaid data flows, and failure modes in `.sad/plans/`. |
| `/sad-design` | **UI/UX & Visual Polish** | Distinctive, accessible UI. Enforces the strict Zero-Lift rule (`translateY` banned, `scale(0.97)` micro-compression), 20 UI polish tips, and reads `.sad/design-memory.md`. |
| `/sad-backend` | **Schema, RLS & Safe APIs** | Schema-first DDL, reversible UP/DOWN migrations, zero-trust Row Level Security policies, and safe query performance analysis (`EXPLAIN (BUFFERS)`). |
| `/sad-sec` | **Security & Compliance Audit** | Strictly read-only audit: OWASP Top 10 web & API, secrets exposure, offline-resilient dependency scanning, and 15-point launch legal compliance in `.sad/reports/`. |
| `/sad-analyze` | **Architecture & Code Health** | Scoped (`/sad-analyze <path>`) or full codebase scan: John Ousterhout deep module analysis, coupling, dead code detection, and prioritization matrix. |

> **Universal Fallback**: If slash commands are not supported in your environment, trigger with `$sadskill <mode>` (e.g. `$sadskill plan`, `$sadskill design`).

---

## 🏗️ Architecture

```mermaid
flowchart TD
    User["Developer Prompt / Slash Command ($ARGUMENTS)"] --> Router["sadskill / SKILL.md (Root Router)"]
    Router --> Protocols["Protocols: Memory · Evidence · Safety · Human-Voice · Grilling"]
    Router --> Modes["Modes: plan · design · backend · security · analyze"]
    Modes --> Memory[".sad/ Project Memory (history.md, decisions.md, design-memory.md)"]
    Modes --> Evidence[".sad/evidence/ (Execution proof logs with exit code 0)"]
    Modes --> VendorIndex["Vendor Index (40 Curated Reference Patterns)"]
    Protocols --> Guardrails["Executable Guardrail (scripts/git-guardrail.sh)"]
    Protocols --> LocalProfile["Optional Local User Profile (~/.sadskill/profile.md)"]
```

---

## 🚀 Advanced Companion Installer (`install.sh`)

For deep local integrations (Claude Code commands, Cursor `.mdc` rules, non-destructive backups):

```bash
git clone https://github.com/sadafbabu/sadskill.git
cd sadskill
./install.sh
```

### Agent-Specific Options
```bash
./install.sh --agent codex                     # Installs to ~/.codex/skills/ & ~/.codex/prompts/
./install.sh --agent claude                    # Installs to ~/.claude/skills/ & ~/.claude/commands/
./install.sh --agent cursor --target /path/app # Generates .cursor/rules/sadskill.mdc in target
./install.sh --agent antigravity               # Installs to ~/.gemini/antigravity/skills/
./install.sh --agent all                       # Configures all detected environments
```

> **Safe by Design**: `install.sh` automatically preserves any existing installation in a timestamped `sadskill.bak.<timestamp>` directory rather than executing unprompted deletions.

---

## 🛡️ Core Protocols

### 1. Project Memory (`.sad/`)
Persistent context stored in the project root:
- `.sad/history.md`: Chronological changelog of high-level project milestones.
- `.sad/decisions.md`: Architecture Decision Records (ADRs).
- `.sad/design-memory.md`: Approved palettes, typography, UI patterns, and rejected anti-patterns.
- `.sad/evidence/`: Machine-readable verification evidence logs (`.json`).
- `.sad/plans/`: Generated execution specifications (`YYYY-MM-DD-<slug>.md`).
- `.sad/reports/`: Timestamped security audits (`security-*.md`) and architecture scans (`analysis-*.md`).

### 2. Verification Evidence Protocol
Every task must conclude with demonstrable terminal verification:
```text
✓ Command: npm test -- tests/auth.test.ts (exit code 0)
✓ Output: 4 passed, 0 failed (verified in 1.2s)
✓ Evidence: .sad/evidence/20261028-031200-auth-login-fix.json
```

### 3. Executable Safety Guardrails
`sadskill` blocks dangerous terminal actions before they cause data loss:
- Prohibits `git reset --hard`, `git push --force`, `git clean -fd`, `git checkout .`, `git branch -D`.
- Prohibits unconditional `DROP TABLE`, `DROP DATABASE`, and `TRUNCATE`.
- Integrates via `scripts/git-guardrail.sh` into Claude Code `PreToolUse` hooks and Git hooks.

### 4. Human Voice Protocol
AI responses lead with the direct answer or diff before commentary. All conversational fluff ("delve", "seamless", "tapestry", "in summary", "moreover") and sycophantic praise ("Great question!") are strictly banned.

### 5. Workstation Profile Isolation (`~/.sadskill/profile.md`)
Personal communication preferences or private tooling rules live exclusively on your workstation outside git:
```bash
cp skills/sadskill/templates/profile.template.md ~/.sadskill/profile.md
```
`sadskill` checks dynamically for this file; if absent, it operates on clean, neutral industry standards.

---

## 🗺️ 90-Day Roadmap

- **Day 1–14 (v0.2.0: Reliability)**: Broken installer/path fixes, adaptive 2-tier planning, dual-record verification evidence, CI pipeline, executable guardrails.
- **Day 15–30 (v0.3.0: Intelligence)**: Automated subagent debate (`/octo:debate`), automated test flakiness detectors, deeper database schema AST analysis.
- **Day 31–60 (v0.4.0: Public Beta)**: Real-world reproducible benchmarks (token cost vs success rate), demo showcase, developer onboarding.
- **Day 61–90 (v1.0 Release Candidate)**: Stable API, community ecosystem contributions, production certification.

---

## 🤝 Contributing & Community

We welcome contributions! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md) before submitting issues or pull requests.

Run the automated verification suite before submitting:
```bash
python3 scripts/verify.py
```

---

## 📄 License & Attribution

- Distributed under the [MIT License](LICENSE).
- Vendored reference guides and community standards are credited in [`THIRD_PARTY.md`](THIRD_PARTY.md) and [`skills/sadskill/vendor/SOURCES.md`](skills/sadskill/vendor/SOURCES.md).
