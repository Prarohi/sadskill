# sad-plan

Execute the `plan` workflow of `sadskill` on the requested scope: $ARGUMENTS

## Instructions

1. Locate the `SKILL.md` loaded for this task. Check the project-vendored `./skills/sadskill/SKILL.md`, the companion path `~/.claude/skills/sadskill/SKILL.md`, or the host's configured skill directory (which may be `~/.agents/skills/sadskill`).
2. Read that `SKILL.md`, then load `modes/plan.md` relative to its containing skill directory. Resolve linked protocols, references, templates and tools against that same installed directory. The canonical mode supplies the workflow; this adapter does not replace it.
3. Follow current user instructions, scope and execution permissions. Load only the relevant linked guidance and project memory; report unavailable tools or checks without claiming they ran.
4. Use the canonical risk tiers and execution-mode handoff; a small mechanical edit may be T0, and file count alone does not determine risk.
