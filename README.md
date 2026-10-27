# `sadskill`

> **One engineering workflow. Any coding agent.**  
> *A portable engineering workflow for coding agents that plans proportionally, remembers decisions, verifies outcomes, and reports uncertainty.*  
> Version: `v0.3.0` · License: `MIT` · Multi-Agent Compatible (Claude Code, OpenAI Codex, Cursor, Antigravity)

> *"Don't just generate code. Engineer it, verify it, and remember why."*

[![CI](https://github.com/sadafbabu/sadskill/actions/workflows/ci.yml/badge.svg)](https://github.com/sadafbabu/sadskill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![skills.sh](https://img.shields.io/badge/skills.sh-sadskill-success.svg)](https://skills.sh)

`sadskill` is an open-source engineering workflow framework for AI coding agents. Instead of juggling conflicting prompt fragments or enduring repetitive trial-and-error cycles, `sadskill` provides **adaptive planning, persistent project memory, defense-in-depth safety guardrails, and proof-grounded verification** across coding agents.

---

## ⚡ Quickstart (Universal via `skills.sh`)

Install `sadskill` into any supported agent using the universal standard:

```bash
npx skills add sadafbabu/sadskill
```

---

## 📊 Why `sadskill`? Core Advantages

| Dimension | Default Plain Coding Agent | Agent Powered by `sadskill` |
|---|---|---|
| **Verification Proof** | Claims *"all tests pass"* blindly without proof | Verifiable terminal proof with exit code `0` recorded in `.sad/evidence/` |
| **Token Efficiency** | Speculative trial-and-error editing cycles | **Adaptive 2-Tier Planning** (Surgical Plan for bugfixes; AST Contracts for features) |
| **Context Retention** | Resets completely across sessions | Persistent `.sad/` memory (`history.md`, `decisions.md`, `design-memory.md`) |
| **Safety Guardrails** | Can run `git reset --hard` or `DROP TABLE` | Executable `git-guardrail.sh` defense filter intercepting destructive commands |
| **UI/UX Craft Floor** | Generic AI aesthetic (purple gradients, unscaled cards) | **Zero-Lift** hover rule (click compression; drawers/tooltips permitted), 44px targets, 20 UI polish rules |
| **Backend Reliability** | Destructive migrations and permissive queries | Reversible UP/DOWN migrations, zero-trust RLS, safe `EXPLAIN (BUFFERS)` |

---

## 🧭 The Five Core Workflows

| Command | Workflow | Description & Core Value |
|---|---|---|
| `/sad-plan` | **Adaptive Spec & Planning** | **Tier 1 (Surgical)**: <= 2 files/bugfix/CSS; single-turn lean diff table.<br>**Tier 2 (Architectural)**: Contract-First AST signatures, Mermaid data flows, and failure modes in `.sad/plans/`. |
| `/sad-design` | **UI/UX & Visual Polish** | Distinctive, accessible UI. Enforces the Zero-Lift hover rule (`translateY` card-hover float banned, `scale(0.97)` micro-compression), 20 UI polish tips, and reads `.sad/design-memory.md`. |
| `/sad-backend` | **Schema, RLS & Safe APIs** | Schema-first DDL, reversible UP/DOWN migrations, zero-trust Row Level Security policies, and safe query performance analysis (`EXPLAIN (BUFFERS)`). |
| `/sad-sec` | **Security & Compliance Audit** | Strictly read-only audit: OWASP Top 10 web & API, secrets exposure, offline-resilient dependency scanning, and 15-point launch legal compliance in `.sad/reports/`. |
| `/sad-analyze` | **Architecture & Code Health** | Scoped (`/sad-analyze <path>`) or full codebase scan: John Ousterhout deep module analysis, coupling, dead code detection, and prioritization matrix. |

> **Universal Invocation**: If slash commands are not supported in your environment, trigger with `$sadskill <mode>` (e.g. `$sadskill plan`, `$sadskill design`) or via natural language intent.

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
    Protocols --> Guardrails["Defense-in-Depth Guardrail (git-guardrail.sh)"]
    Protocols --> LocalProfile["Optional Local User Profile (~/.sadskill/profile.md)"]
```

---

## 🚀 Advanced Companion Installer (`install.sh`)

For deep local host integrations (Claude Code commands, Cursor `.mdc` rules, non-destructive backups):

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

> **Safe by Design**: `install.sh` tracks all installed artifacts in `~/.sadskill/install-manifest.json` and preserves preexisting files in timestamped `.bak.<timestamp>` archives.

---

## 🛡️ Core Protocols & Security Model

### 1. Verification Evidence Standard (`protocols/evidence.md`)
Tasks conclude with demonstrable terminal verification and machine-readable evidence:
```text
✓ Command: npm test -- tests/auth.test.ts (exit code 0)
✓ Result: 4 passed, 0 failed (verified in 1.2s)
✓ Evidence: .sad/evidence/20261028-031200-auth-login-fix.json
```

#### Verification Provenance States:
- `reported`: Agent claims execution in conversation.
- `schema_valid`: Valid JSON format and strictly contained project paths verified by `scripts/verify-evidence.py`.
- `retested`: Independently executed by authorized verifier.
- `ci_attested`: Linked to immutable GitHub Actions CI run SHA/URL.

### 2. Defense-in-Depth Safety Guardrails (`protocols/safety.md`)
Safety operates through layered boundaries:
- **Tier 1 (Agent Prompts)**: Strictly forbids destructive operations without explicit confirmation.
- **Tier 2 (Hook Filter)**: `skills/sadskill/hooks/git-guardrail.sh` intercepts dangerous bash commands before execution.
- **Tier 3 (Host Boundaries)**: Sandbox permissions, branch rules, and least privilege.

#### Hook Lifecycle Status:
- `HOOK_AVAILABLE`: Hook script installed on disk.
- `HOOK_REGISTERED`: Registered in host configuration (e.g. `PreToolUse` in `~/.claude/settings.json`).
- `HOOK_ACTIVE`: Actively receiving and filtering host tool events.

### 3. Human Voice Protocol (`protocols/human-voice.md`)
AI responses lead with the direct answer or diff before commentary. Fluff phrases ("delve", "seamless", "tapestry", "in summary") and sycophantic praise ("Great question!") are strictly banned.

### 4. Workstation Profile Isolation (`~/.sadskill/profile.md`)
Personal communication preferences or private tooling rules live exclusively on your workstation outside git:
```bash
cp skills/sadskill/templates/profile.template.md ~/.sadskill/profile.md
```

---

## 🧪 Verification & Benchmarks

### 1. Independent Evidence Verifier
Validate `.sad/evidence/*.json` records for syntax, strict path containment, and authorized execution:
```bash
python3 scripts/verify-evidence.py
python3 scripts/verify-evidence.py --retest  # Safely re-executes authorized checks with timeout
```

### 2. Contract & Policy Verification Suite
Evaluates specification compliance across planning, design, backend, security, and guardrails:
```bash
python3 benchmarks/runner.py
```

### 3. Real Behavioral Test Fixture
Execute behavioral tests on real fixture code:
```bash
python3 benchmarks/fixtures/tenant-isolation/grader.py
```

---

## 🧹 Uninstallation

To cleanly remove `sadskill` and optionally restore original backed-up configurations:

```bash
./uninstall.sh                    # Clean removal of installed files
./uninstall.sh --restore-previous # Restores original pre-install files from backups
./uninstall.sh --purge            # Removes ~/.sadskill user profile directory
```

---

## 🤝 Contributing & Community

We welcome contributions! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md) before submitting pull requests.

Run the full verification suite before submitting:
```bash
python3 scripts/verify.py
```

---

## 📄 License & Attribution

- Distributed under the [MIT License](LICENSE).
- Vendored reference guides and community standards are credited in [`THIRD_PARTY.md`](THIRD_PARTY.md) and [`skills/sadskill/vendor/SOURCES.md`](skills/sadskill/vendor/SOURCES.md).
