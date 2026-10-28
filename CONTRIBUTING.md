# Contributing to `sadskill`

Thank you for contributing to `sadskill`! Our goal is to maintain a unified, high-leverage agent skill repository that works across all modern autonomous coding agents (Codex / ChatGPT, Claude Code, Cursor, Antigravity, Gemini CLI).

## Core Principles

1. **One Frontmatter Rule**: Only the root skill `skills/sadskill/SKILL.md` exposes top-level YAML frontmatter with `name: sadskill`. Vendored skills must have neutralized frontmatter (`*.ref.md` or comment blocks) so agents do not discover hundreds of separate skills.
2. **Neutral Defaults**: Defaults are strict, modern engineering standards. Zero personal preferences, machine paths, or specific username configurations belong in the repository. Personal preferences belong in the user's local `~/.sadskill/profile.md`.
3. **Human Voice**: Prompts and protocols must enforce crisp, natural, BS-free language. Never use AI filler words (e.g. "delve", "seamless", "in summary", "testament").
4. **License Compliance**: Every vendored or referenced work must be credited in `THIRD_PARTY.md` with its original license. Only permissively licensed works or open documentation standards (MIT, Apache-2.0, BSD, CC-BY, CC-BY-SA 4.0 for security standards like OWASP) are vendored in-tree.

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

Run the checks relevant to your change, and record their commands and exit codes in the PR:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/verify.py
python3 benchmarks/runner.py
git diff --check
```
The unit suite covers installer/updater regressions. The verification suite checks:
- YAML frontmatter integrity
- Uniqueness of discoverable skills
- Integrity of all Markdown cross-references
- Presence of all agent command files
- Privacy checks (no hardcoded machine paths or usernames)

The benchmark runner reports static checks, prebuilt fixtures and task-catalog validation separately. These passes are not real-agent task outcomes; do not convert them into an agent-quality percentage. If changing a runnable optional fixture, follow its README too. Report unavailable checks and the reason rather than claiming a pass.

## From assigned task to pull request

1. Start with an agreed issue containing the problem, allowed scope, acceptance examples and verification needed. Use the **Contributor task** issue form. Keep unrelated improvements in separate issues.
2. Create a short-lived branch from the issue's stated base. If you have no repository write access, use a fork. Do not push directly to `main` or rewrite another contributor's branch.
3. Reproduce a bug before fixing it. Add a meaningful regression test for changed behavior; documentation-only changes need link/content checks, not artificial tests.
4. Open a small PR using the template. Link the task, show evidence, name limitations and request a reviewer who did not author the change. Do not include secrets, local audit files, downloaded environment files or personal agent profiles.
5. Address findings with clear follow-up commits. New commits can invalidate approval; verify checks for the latest PR head, not an older green commit.
6. Merge only after required checks, independent GitHub approval and resolved review threads. Auto-merge may wait for these gates; it does not replace them. Do not bypass rules to finish a task.

For an integration stack, follow the issue's explicit PR base and merge order. Do not merge both a combined integration PR and its superseded component PRs. A green CI run on a stacked PR does not prove that the eventual updated integration head is green.

## Public source and service access

Sadskill is public and its [license](LICENSE) permits obtaining and using the source. Repository permissions cannot prevent someone from cloning, downloading or installing public code. Production data, account access, private application code and credentials are separate assets; contributing here grants no access to them. Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue with exploit data or credentials.

Maintainers can use the [two-contributor workflow](docs/contributor-workflow.md) to assign work and manage access.
