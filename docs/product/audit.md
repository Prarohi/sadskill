# Comprehensive Product & Codebase Audit: `sadskill`

**Audit Date:** 28 October 2026  
**Audited Base Commit:** `0711f806529bc2164161d898d03561435c9d573f`  
**Auditor Role:** Principal Product Architect & AI Agent Workflow Designer

---

## 1. Coverage Ledger

| Category | Path | Inspection Status | Notes |
|---|---|---|---|
| **Root Router** | `skills/sadskill/SKILL.md` | **Fully Inspected** | Evaluated router table, global invariants, progressive disclosure triggers |
| **Modes** | `skills/sadskill/modes/plan.md` | **Fully Inspected** | Evaluated tiering, AST requirements, execution gates, vendor synergies |
| **Modes** | `skills/sadskill/modes/design.md` | **Fully Inspected** | Evaluated craft floor, Zero-Lift nuance, WCAG criteria, surface modes |
| **Modes** | `skills/sadskill/modes/backend.md` | **Fully Inspected** | Evaluated schema rules, reversible migrations, RLS engine boundaries, query analysis |
| **Modes** | `skills/sadskill/modes/security.md` | **Fully Inspected** | Evaluated OWASP checks, secret detection, read-only contract, reporting |
| **Modes** | `skills/sadskill/modes/analyze.md` | **Fully Inspected** | Evaluated coverage ledger, AST vs static heuristics, coupling, test gap analysis |
| **Protocols** | `skills/sadskill/protocols/context.md` | **Fully Inspected** | Evaluated TaskContext schema, precedence hierarchy, scope derivation |
| **Protocols** | `skills/sadskill/protocols/coverage.md` | **Fully Inspected** | Evaluated whole-codebase inventory, exclusion accounting, truthfulness |
| **Protocols** | `skills/sadskill/protocols/advice.md` | **Fully Inspected** | Evaluated proactive suggestions, suppression rules, standard output format |
| **Protocols** | `skills/sadskill/protocols/autonomy.md` | **Fully Inspected** | Evaluated 4 execution modes, clarification budget, retry caps |
| **Protocols** | `skills/sadskill/protocols/research.md` | **Fully Inspected** | Evaluated web search modes, source provenance, untrusted data boundary |
| **Protocols** | `skills/sadskill/protocols/evidence.md` | **Fully Inspected** | Evaluated provenance states, strict path containment, docs-only skip handling |
| **Protocols** | `skills/sadskill/protocols/safety.md` | **Fully Inspected** | Evaluated defense-in-depth model, forbidden actions, hook lifecycle |
| **Protocols** | `skills/sadskill/protocols/memory.md` | **Fully Inspected** | Evaluated `.sad/` directory structure, ADR formats, design memory logging |
| **Protocols** | `skills/sadskill/protocols/human-voice.md`| **Fully Inspected** | Evaluated anti-cliché filters, conciseness, direct-answer-first rule |
| **Protocols** | `skills/sadskill/protocols/grilling.md` | **Fully Inspected** | Evaluated single-round ambiguity resolution, recommended default pattern |
| **Protocols** | `skills/sadskill/protocols/output-style.md`| **Fully Inspected** | Evaluated token efficiency, batching rules, executive summaries |
| **Protocols** | `skills/sadskill/protocols/profile.md` | **Fully Inspected** | Evaluated `~/.sadskill/profile.md` workstation isolation |
| **Protocols** | `skills/sadskill/protocols/mcp.md` | **Fully Inspected** | Evaluated MCP read-first policies and configuration boundaries |
| **Command Adapters**| `commands/claude/*.md` (5 files) | **Fully Inspected** | Evaluated `$ARGUMENTS` propagation, self-contained instruction fallbacks |
| **Command Adapters**| `commands/codex/*.md` (5 files) | **Fully Inspected** | Evaluated prompt structures, legacy adapter compatibility |
| **Templates** | `skills/sadskill/templates/*` (6 files) | **Fully Inspected** | Evaluated plan, security, analysis, profile, and ledger templates |
| **Checklists** | `skills/sadskill/checklists/*` (3 files) | **Fully Inspected** | Evaluated UI polish tips, site production, app launch legal |
| **Documentation** | `README.md`, `docs/compatibility.md` | **Fully Inspected** | Evaluated product promise, host capability matrix, diagnostics |
| **Vendor References**| `skills/sadskill/vendor/` (40 files) | **Partially Inspected** | Verified manifest tracking, frontmatter neutralization, link integrity |
| **Excluded (Out of Ownership)** | `install.sh`, `uninstall.sh`, `scripts/*.py`, `hooks/*.sh` | **Excluded from Modification** | Inspected interfaces for contract alignment; strictly preserved code |

---

## 2. Findings Across the 10 Core Dimensions

### 1. Redundant Instructions
- **Confirmed**: Protocol duplication between `protocols/output-style.md` and `protocols/context.md` regarding progressive disclosure and executive summaries.
- **Confirmed**: Duplicate warnings regarding destructive Git commands appearing in both `modes/plan.md`, `protocols/safety.md`, and `commands/claude/*.md`.
- **Target Improvement**: Unify change planning, context routing, and verification requirements into a single lightweight **Change Contract**, cross-referencing protocols rather than repeating rules verbatim.

### 2. Contradictory Rules
- **Confirmed**: `modes/plan.md` stated "Tier 1: <= 2 files, bug fixes" while `protocols/context.md` defined "Tiny tasks" that execute directly. A 1-line typo fix in 1 file had ambiguous status—did it require writing `.sad/plans/YYYY-MM-DD-slug.md` or not?
- **Confirmed**: `modes/plan.md` phase 4 had "stop and present plan" while `protocols/autonomy.md` stated `CONTINUE_UNTIL_DONE` should proceed without pausing.
- **Target Improvement**: Establish a clear risk-based tiering matrix (T0 Tiny: zero plan file overhead; T1 Surgical: lean inline table; T2 Architectural: formal spec in `.sad/plans/`).

### 3. Unnecessarily Rigid Style Preferences
- **Confirmed**: `modes/design.md` phrased the Zero-Lift rule as an absolute prohibition (`translateY` banned as a style floor), which caused friction for legitimate component animations like slide-in sheets, accordions, and dialog transitions.
- **Confirmed**: Mandating `scale(0.97)` click micro-compression on all interactive elements even when building native desktop or data-dense enterprise control panels.
- **Target Improvement**: Frame Zero-Lift and click compression as **intelligent defaults and anti-slop guidelines**, explicitly encouraging adaptation to existing brand tokens, design systems, and platform conventions.

### 4. Excessive Context Loading
- **Confirmed**: `SKILL.md` listed 13 global protocols in its main body. An agent activating the skill risks pulling all 13 protocols into context simultaneously, consuming thousands of tokens before beginning work.
- **Likely**: Loading full vendor reference manuals when only a 3-line pattern was needed.
- **Target Improvement**: Implement strict progressive disclosure in `SKILL.md`: load the router, select the mode, and load only the targeted protocol required for the specific task depth (`quick`, `standard`, `deep`, `exhaustive`).

### 5. Ambiguous Mode Boundaries
- **Confirmed**: Overlap between `/sad-analyze` and `/sad-plan` during initial codebase discovery. When a user asks "how does auth work and how should we change it?", both modes claim responsibility.
- **Confirmed**: Boundary between `/sad-sec` (audit) and `/sad-backend` (RLS and schema remediation).
- **Target Improvement**: Clearly delineate: `/sad-analyze` is strictly read-only reconnaissance and diagnosis; `/sad-plan` creates forward execution contracts; `/sad-sec` identifies vulnerabilities; `/sad-backend` executes safe data migrations.

### 6. Missing Input/Output Contracts
- **Confirmed**: Absence of a unified, lightweight data structure bridging the output of `/sad-plan` to the input of `/sad-backend`, `/sad-sec`, or `/sad-design`.
- **Target Improvement**: Introduce the **Change Contract** (`templates/change-contract.template.json` and `.md`) defining `intent`, `scope`, `constraints`, `risk`, `assumptions`, `verification`, `rollback`, and `status`.

### 7. Agent-Host-Specific Instructions Incorrectly Presented as Universal
- **Confirmed**: Native slash commands (`/sad-plan`) were documented in some places as if universally functional, whereas standard `npx skills add` installations on vanilla OpenAI Codex only expose `$sadskill <mode>` or natural language prompts.
- **Target Improvement**: Explicitly distinguish Native Host Commands, Universal Skill Triggers, and Prompt-Only Guidance in documentation and mode headers.

### 8. Claims Unsupported by Executable Evidence
- **Confirmed**: Previous README versions promised generalized "80% token savings" without controlled, paired comparative benchmarks against plain agents.
- **Target Improvement**: Adopt the verified engineering promise: *"Understand the real engineering task, make the smallest appropriate change, preserve the reasoning, and prove what actually works—across coding agents."*

### 9. Instructions Likely to Make Simple Tasks Unnecessarily Expensive
- **Confirmed**: Forcing the creation of `.sad/plans/` markdown files, Mermaid diagrams, and test assertion logs for trivial single-character typo fixes or CSS color changes.
- **Target Improvement**: Explicit T0 bypass: low-risk, trivial changes execute immediately with inline verification, completely skipping plan artifact generation.

### 10. Places Where an Agent Could Misinterpret the Conversation or Repeat Questions
- **Confirmed**: Stale `.sad/` decisions overriding explicit new user directions during multi-turn chats.
- **Likely**: The agent re-asking questions already answered in earlier turns because it only looked at static files rather than live conversation history.
- **Target Improvement**: Enforce strict Interpretation Contract: Current user request > Active conversation > Authorized `.sad/` memory > Installed defaults. Never re-ask an answered question.
