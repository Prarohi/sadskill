# `/sad-sec`

Execute the `security` workflow of `sadskill` on the requested scope: $ARGUMENTS
*(Invocation: `/sad-sec` or `/prompts:sad-sec`)*

## Instructions

1. Locate the `SKILL.md` loaded for this task. Check the project-vendored `./skills/sadskill/SKILL.md`, the companion path `~/.codex/skills/sadskill/SKILL.md`, or the host's configured skill directory (which may be `~/.agents/skills/sadskill`).
2. Read that `SKILL.md`, then load `modes/security.md` relative to its containing skill directory. Resolve linked protocols, references, templates and tools against that same installed directory. The canonical mode supplies the workflow; this adapter does not replace it.
3. Follow current user instructions, scope and execution permissions. Load only the relevant linked guidance and project memory; report unavailable tools or checks without claiming they ran.
4. The default audit is Strictly Read-Only. Preserve explicit no-write constraints and require authorization for remediation; use the dependency scanner named by the canonical security mode.
