# sadskill Host Compatibility, Capability Tiers & Graceful Degradation (v0.3.0)

This matrix defines the supported AI coding agents, capability tiers, installation directories, invocation commands, safety hook coverage, and graceful degradation behaviors.

---

## 1. Capability Tiers

To ensure clear expectations across diverse developer environments, `sadskill` classifies host agents into four capability tiers:

| Capability Tier | Definition | Supported Environments | Feature Set Available |
|---|---|---|---|
| **Tier 1: Native** | Host agent natively executes slash commands, file read/write, terminal execution, and supports lifecycle hooks or policy sandboxes. | Claude Code, OpenAI Codex CLI / ChatGPT Desktop, Google Antigravity, Gemini CLI. | Full workflow: slash commands (`/sad-*`), automated test verification, git guardrail hooks, persistent `.sad/` memory, change contracts. |
| **Tier 2: Companion** | Host IDE or extension integrates workspace rules and file context, but delegates terminal execution to human review or lacks pre-tool hook interceptors. | Cursor IDE, Windsurf, Roo Code / Cline. | Full skill instructions, `.cursor/rules/sadskill.mdc`, automated plan generation, design/backend checklists. Safety relies on agent-side prompt contracts. |
| **Tier 3: Prompt-Only** | LLM interfaces with markdown file attachments or custom instructions but no native filesystem or bash execution. | Web ChatGPT, Claude Web, Gemini Web, GitHub Copilot Chat (browser). | Read-only analysis, specification generation, architectural review. Terminal verification must be executed manually by the developer. |
| **Tier 4: Unsupported** | Read-only chat environments without multi-turn state, workspace access, or file viewing. | Ephemeral chat playgrounds, single-turn completion APIs. | General prompt advice only. Multi-step change contracts and persistent memory disabled. |

---

## 2. Host Agent Compatibility Matrix

| Host Agent | Capability Tier | Universal Skill Discovery | Native Slash Command | Hook Interception | Status | Tested Environment |
|---|---|---|---|---|---|---|
| **Claude Code** | Native | `~/.claude/skills/sadskill` | `/sad-*` (`~/.claude/commands/`) | `PreToolUse` (`~/.claude/hooks/git-guardrail.sh`) | **Verified Active** | Linux x86_64, macOS arm64, Bash 5.2 |
| **OpenAI Codex / Desktop** | Native | `~/.codex/skills/sadskill` | `/sad-*` (`~/.codex/prompts/`) | Host sandboxing | **Verified Active** | Linux x86_64, macOS, Python 3.10+ |
| **Cursor** | Companion | `.cursor/skills/sadskill` | `.cursor/rules/sadskill.mdc` | Prompt-level contract | **Verified Active** | Cursor IDE 0.40+, Workspace rules |
| **Google Antigravity** | Native | `~/.gemini/antigravity/skills/sadskill` | `$sadskill <mode>` | Host sandbox policy | **Verified Active** | AGY CLI / Runner |
| **Gemini CLI** | Native | `~/.gemini/skills/sadskill` | `$sadskill <mode>` | Host sandbox policy | **Verified Active** | gemini-cli v0.1+ standard discovery |
| **Windsurf / Cascade** | Companion | `.windsurf/skills/sadskill` | `.windsurfrules` | Prompt-level contract | **Compatible** | Windsurf Editor |

---

## 3. Graceful Degradation Matrix

When specific capabilities or host tools are absent, `sadskill` gracefully degrades without aborting:

| Missing Capability | Host Scenario | Degradation Behavior | Developer Disclosure |
|---|---|---|---|
| **No Hook Interceptor** | Codex, Cursor, or vanilla terminals lacking `PreToolUse` hook support. | Agent enforces safety constraints at the reasoning level ([protocols/safety.md](../skills/sadskill/protocols/safety.md)). Blocks destructive commands (`git reset --hard`, `DROP TABLE`) internally. | Prompts user before destructive actions; logs `[HOOK_INTERCEPTOR: PROMPT_LEVEL_FALLBACK]`. |
| **No Browser / Visual Preview** | Headless CLI, terminal SSH, or agents lacking Chrome DevTools / Puppeteer MCP. | UI analysis operates strictly via static source code inspection (CSS variables, layout flex/grid structure, WCAG contrast math). | Explicitly marks visual rendering as `[UNVERIFIED - CODE-LEVEL ONLY]`. Never hallucinates screenshot confirmation. |
| **No Live Database Connection** | Offline environments or repos without running PostgreSQL/SQLite instances. | Generates paired `up.sql` / `down.sql` migrations and simulates RLS logic statically. Analyzes queries via AST checks. | Marks schema verification as `[STATIC_ANALYSIS_VERIFIED]`. Explicitly notes that live execution requires active connection string. |
| **No Internet / Package Registry** | Air-gapped networks, corporate firewalls, or offline coding sessions. | Skips external `npm audit` / `cargo audit` and web research. Inspects local package manifests and bundled [vendor references](../skills/sadskill/vendor/INDEX.md). | Outputs `[SKIPPED - OFFLINE / AIR-GAPPED]`. Proceeds with static code analysis without crashing. |
| **No Persistent File Storage** | Ephemeral evaluation containers where `.sad/` cannot be committed. | Retains task context in memory for the duration of the multi-turn session. Dumps final Change Contract or report to chat. | Notifies developer to manually save plan or export `.sad/` state before closing container. |

---

## 4. Invocation Syntax by Host

### Claude Code
- Commands registered: `/sad-plan`, `/sad-design`, `/sad-backend`, `/sad-sec`, `/sad-analyze`
- Usage: `/sad-plan refactor authentication module`
- Hook: Copies `git-guardrail.sh` to `~/.claude/hooks/`. Add to `~/.claude/settings.json` under `PreToolUse` for automatic command blocking.

### OpenAI Codex / ChatGPT Desktop
- Prompts registered: `~/.codex/prompts/sad-plan.md`, etc.
- Usage: Select prompt or invoke with `$sadskill <mode>`

### Cursor
- Workspace rule: Deploys `.cursor/rules/sadskill.mdc` with complete workflow definitions and `.cursor/skills/sadskill/` for local link resolution.
- Usage: Referenced automatically across agent turns matching configured globs (`*`).

### Universal Agent Skills (`skills.sh`)
- Installation: `npx skills add sadafbabu/sadskill`
- Usage: `$sadskill plan`, `$sadskill design`, `$sadskill backend`, `$sadskill sec`, `$sadskill analyze`

---

## 5. Diagnostic Verification

Use `scripts/doctor.py` to inspect installation and hook status:

```bash
python3 scripts/doctor.py
# Or for machine-readable JSON:
python3 scripts/doctor.py --json
```

Status definitions:
- `NOT_INSTALLED`: No skill or command files found in the standard directory.
- `AVAILABLE`: Hook script is installed in the agent hooks directory, but requires user activation in settings.
- `REGISTERED`: Hook is configured in host settings.
- `ACTIVE`: Hook is verified responsive to simulated tool events.
- `UNSUPPORTED`: Host agent does not expose a native hook lifecycle.
