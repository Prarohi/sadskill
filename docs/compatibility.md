# Host Integration Paths and Verification Limits

This page records paths written by Sadskill's installer and what its local doctor can inspect. It is not a claim that every listed host version has loaded the skill, command, or hook. Host discovery and lifecycle behavior must be verified in the host itself.

## Installer paths

| Integration target | Paths written by `install.sh` | Local evidence |
|---|---|---|
| Claude Code | `~/.claude/skills/sadskill`, `~/.claude/commands/`, `~/.claude/hooks/git-guardrail.sh` | Doctor checks files and `settings.json`; a benign local hook run is `LOCAL_TEST_PASSED`, not proof Claude Code loaded it. |
| OpenAI Codex | `~/.codex/skills/sadskill`, `~/.codex/prompts/` | Doctor requires a nonempty `SKILL.md` and all five command files. This does not verify host discovery or instruction validity. |
| Cursor | `<target>/.cursor/skills/sadskill`, `<target>/.cursor/rules/sadskill.mdc` | Doctor requires a nonempty skill file and rule for the selected workspace. This does not verify Cursor loaded the rule. |
| Google Antigravity | `~/.gemini/antigravity/skills/sadskill` | Doctor checks for a nonempty `SKILL.md`. This does not verify host discovery. |
| Gemini CLI | `~/.gemini/skills/sadskill` | Doctor checks for a nonempty `SKILL.md`. This does not verify host discovery. |

Windsurf, Roo Code, Cline, web chat, and other environments are not installed or host-tested by this repository's current installer. Do not describe them as supported based only on prompt compatibility.

## Portable evidence helper

The complete skill folder includes `tools/verify-evidence.py`, both when distributed as a skill folder and when copied by the companion installer. Resolve its location relative to the `SKILL.md` loaded by the host; for example, a Codex companion installation places it at `~/.codex/skills/sadskill/tools/verify-evidence.py`. Skill-manager installations may use a different directory.

Invoke the helper with Python and explicitly select the consumer checkout, even if the current directory is elsewhere:

```bash
python3 "$HOME/.codex/skills/sadskill/tools/verify-evidence.py" --project-root "/absolute/path/to/consumer-project" --print-context
```

Replace the example checkout and helper path with their discovered locations. The consumer project needs no Sadskill `scripts/` directory. Python, Git and a readable Git checkout are required for context capture; an unavailable helper or checkout snapshot must be reported as unavailable. Prompt-only hosts can relay these steps but cannot claim execution or verified evidence. See the [evidence protocol](../skills/sadskill/protocols/evidence.md) for recording and retest boundaries.

## Capability boundaries

- **Agent guidance:** Prompt rules can ask an agent to pause or explain a risky command. They cannot technically block the host from running it.
- **Executable hook:** Enforcement exists only when the host supports the hook lifecycle, the hook is registered using that host's accepted schema, and the host actually invokes it. Claude Code's current hook configuration nests command handlers under a matcher group's `hooks` array; see the [official Claude Code hooks reference](https://code.claude.com/docs/en/hooks). A standalone script simulation does not establish host activation.
- **Matcher inspection:** The local doctor accepts only exact `Bash` names/lists for the command guardrail. It normalizes missing, catch-all, multi-tool, and regex matchers to an executable exact `Bash` handler without evaluating host JavaScript regexes in Python. It preserves command arguments through legacy and nested schema migration, retains unrelated matchers/handlers, and removes handler-level `if` filters from the Sadskill guardrail so they cannot narrow its coverage. Any differing owned command text/options, including shell quoting, causes a safe refusal instead of a guessed rewrite.
- **No browser preview:** Source inspection can identify CSS and markup risks but cannot prove rendered layout or visual behavior. Report that evidence as code-level only.
- **No live database:** SQL inspection or a deterministic fixture is not a live migration or production RLS test. Say exactly which one ran.
- **No network:** Local inspection can continue, but dependency advisories and external documentation checks are skipped. Do not call that a complete dependency audit.
- **No persistent workspace:** Conversation memory is not durable project storage. Export or save a requested artifact before ending the session.

## Doctor status labels

`python3 scripts/doctor.py --json` reports local path and configuration evidence:

- `NOT_INSTALLED`: the hook script is absent.
- `AVAILABLE`: the hook script exists but is not registered in settings.
- `REGISTERED`: settings reference the hook, but its benign local simulation did not pass or the installed script is missing.
- `LOCAL_TEST_PASSED`: the registered script passed a benign local simulation. This does not show that a host has loaded it.
- `HOST_VERIFIED_ACTIVE`: the local simulation passed and an operator explicitly confirmed activity in the host using `--confirm-active`; the doctor did not observe host events itself. Confirmation cannot override a missing or failing hook.
- `UNKNOWN`: settings could not be parsed safely.

Use `--enable-hooks` and `--disable-hooks` for opt-in registration and ownership-aware removal. Check the host's own hook view or debug log to verify that it loaded the configuration. The Claude Code documentation describes the hook lifecycle and its debug log behavior in the [hooks reference](https://code.claude.com/docs/en/hooks).
