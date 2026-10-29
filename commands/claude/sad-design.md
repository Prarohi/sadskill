# sad-design

Execute the `design` workflow of `sadskill` on the requested scope: $ARGUMENTS

## Instructions

1. Locate the `SKILL.md` loaded for this task. Check the project-vendored `./skills/sadskill/SKILL.md`, the companion path `~/.claude/skills/sadskill/SKILL.md`, or the host's configured skill directory (which may be `~/.agents/skills/sadskill`).
2. Read that `SKILL.md`, then load `modes/design.md` relative to its containing skill directory. Resolve linked protocols, references, templates and tools against that same installed directory. The canonical mode supplies the workflow; this adapter does not replace it.
3. Follow current user instructions, scope and execution permissions. Load only the relevant linked guidance and project memory; report unavailable tools or checks without claiming they ran.
4. Preserve the existing stack and approved design tokens. Use the canonical accessibility requirements and distinguish rendered evidence from source inspection.
