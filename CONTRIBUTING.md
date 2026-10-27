# Contributing to `sadskill`

Thank you for contributing to `sadskill`! Our goal is to maintain a unified, high-leverage agent skill repository that works across all modern autonomous coding agents (Codex / ChatGPT, Claude Code, Cursor, Antigravity, Gemini CLI).

## Core Principles

1. **One Frontmatter Rule**: Only the root skill `skills/sadskill/SKILL.md` exposes top-level YAML frontmatter with `name: sadskill`. Vendored skills must have neutralized frontmatter (`*.ref.md` or comment blocks) so agents do not discover hundreds of separate skills.
2. **Neutral Defaults**: Defaults are strict, modern engineering standards. Zero personal preferences, machine paths, or specific username configurations belong in the repository. Personal preferences belong in the user's local `~/.sadskill/profile.md`.
3. **Human Voice**: Prompts and protocols must enforce crisp, natural, BS-free language. Never use AI filler words (e.g. "delve", "seamless", "in summary", "testament").
4. **License Compliance**: Every vendored or referenced work must be credited in `THIRD_PARTY.md` with its original license. Only permissively licensed works (MIT, Apache 2.0, BSD, CC-BY) are vendored in-tree.

## Adding a New Mode or Workflow

1. Place the mode definition in `skills/sadskill/modes/<mode>.md`.
2. Add routing logic to `skills/sadskill/SKILL.md`.
3. Provide slash commands in both `commands/codex/<command>.md` and `commands/claude/<command>.md`.
4. Update `skills/sadskill/vendor/INDEX.md` if the mode references vendor resources.
5. Run the verification test suite:
   ```bash
   python3 scripts/verify.py
   ```

## Verification

Before opening a pull request, ensure that all tests pass:
```bash
python3 scripts/verify.py
```
This validates:
- YAML frontmatter integrity
- Uniqueness of discoverable skills
- Integrity of all Markdown cross-references
- Presence of all agent command files
- Privacy checks (no hardcoded machine paths or usernames)
