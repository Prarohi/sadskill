# sadskill Host Compatibility & Invocation Matrix (v0.3.0)

This matrix defines the supported coding agents, installation directories, invocation commands, safety hook coverage, and known limitations.

---

## 1. Compatibility Matrix

| Host Agent | Universal Skill Discovery | Native Slash Command | Hook Interception | Status | Tested Environment |
|---|---|---|---|---|---|
| **Claude Code** | `~/.claude/skills/sadskill` | `/sad-*` (`~/.claude/commands/`) | `PreToolUse` (`~/.claude/hooks/git-guardrail.sh`) | **Verified Active** | Linux x86_64, Bash 5.2 |
| **OpenAI Codex / ChatGPT Desktop** | `~/.codex/skills/sadskill` | `/sad-*` (`~/.codex/prompts/`) | Unsupported natively | **Verified Active** | Linux x86_64, Python 3.10+ |
| **Cursor** | `.cursor/skills/sadskill` | `.cursor/rules/sadskill.mdc` | Best-effort heuristic | **Verified Active** | Cursor IDE, Workspace rules |
| **Google Antigravity** | `~/.gemini/antigravity/skills/sadskill` | `$sadskill <mode>` | Host sandbox policy | **Verified Active** | AGY CLI / Runner |
| **Gemini CLI** | `~/.gemini/skills/sadskill` | `$sadskill <mode>` | Host sandbox policy | **Verified Active** | gemini-cli v0.1+ standard discovery |

---

## 2. Invocation Syntax by Host

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

## 3. Diagnostic Verification

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
