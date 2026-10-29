# Protocol: Git & Database Destructive Action Guardrails

Autonomous agents must never perform irreversible destructive actions on user code, repositories, or databases without an explicit, batched user confirmation gate.

---

## 🛡️ Multi-Tier Safety Architecture

Safety in `sadskill` operates as **defense-in-depth**, not an impenetrable OS sandbox:
1. **Tier 1 (Agent Prompts & Policy)**: The agent is instructed to avoid destructive operations, prefer reversible alternatives, and request user approval for high-consequence tasks.
2. **Tier 2 (Tool-Hook Interception)**: A best-effort filter (`skills/sadskill/hooks/git-guardrail.sh`) intercepting command tokens before execution in supported agent environments.
3. **Tier 3 (Host Permissions & Isolation)**: Repository branch protections, container sandboxes, non-root execution, and least-privilege tokens.

> [!WARNING]
> The guardrail hook is a defensive filter against common accident patterns; it does **not** replace containerization, branch protections, or secure database access controls.
> Its SQL checks are lexical heuristics, not a SQL parser or authorization boundary. Use least-privilege database roles and PostgreSQL RLS to constrain actual data access.

---

## 🚫 Forbidden Destructive Actions (Require Explicit Approval)

### 1. Git Destructive Operations
The following Git commands can cause permanent loss of uncommitted work or commit history. They are **strictly forbidden** from automatic execution:
- `git reset --hard` (destroys uncommitted working directory changes)
- `git push --force`, `git push -f`, or force refspecs `+<branch>` (overwrites remote branch history)
- `git clean -fd` or `git clean -f` (permanently deletes untracked files)
- `git checkout -- .` or `git restore .` (discards all local modifications)
- `git branch -D` (force deletes unmerged branches)
- `git stash drop` or `git stash clear` (destroys saved stashes)

### 2. Database Destructive Operations
The following database queries cause irreversible data loss and must never be run autonomously:
- `DROP DATABASE ...` or `DROP TABLE ...`
- `TRUNCATE TABLE ...`
- `DELETE FROM ...` without a tight, parameterized `WHERE` clause targeting test IDs
- `ALTER TABLE ... DROP COLUMN ...` on production or shared schemas

---

## 🛡️ Safe Alternative Protocols

1. **Prefer Non-Destructive Git Workflows**:
   - Instead of `git reset --hard`, use `git stash push -m "sadskill-backup-<timestamp>"` so discarded work remains recoverable.
   - Instead of force-pushing, push to a new descriptive branch (`feature/...`, `refactor/...`).
   - Use `git status --porcelain` to inspect dirty state before taking action.
2. **Reversible Database Migrations**:
   - Write paired `up.sql` and `down.sql` migrations.
   - Test migrations inside transactions (`BEGIN; ... ROLLBACK;`) to verify syntax without mutating live records.
3. **User Approval Gate**:
   - If a destructive operation is genuinely necessary (e.g. rolling back a failed migration), halt and present:
     - The exact command to be executed.
     - The specific files or tables affected.
     - The recovery options.
     - Await explicit user confirmation (`yes`) before proceeding.

---

## ⚙️ Programmatic Enforcement: `skills/sadskill/hooks/git-guardrail.sh`

`sadskill` provides an executable hook script packaged at `skills/sadskill/hooks/git-guardrail.sh` (mirrored at `scripts/git-guardrail.sh`) that intercepts dangerous commands and terminates with exit code 2 before they run.

### Hook Integration Status
- **AVAILABLE**: Script is installed on disk but is not registered.
- **REGISTERED**: A Bash-matching `PreToolUse` entry references the hook, but its script is missing or the benign local simulation did not pass.
- **LOCAL_TEST_PASSED**: A registered hook passed a benign local simulation; this does not prove host activation.
- **HOST_VERIFIED_ACTIVE**: An operator explicitly confirmed the hook in the host. A local diagnostic cannot observe host events and must not assign this automatically.

### Setup for Claude Code (`~/.claude/settings.json`)
Register the hook under `PreToolUse` in your Claude Code settings:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME\"/.claude/hooks/git-guardrail.sh"
          }
        ]
      }
    ]
  }
}
```

### Git Hook Scope Clarification
When used as a Git hook (e.g. `.git/hooks/pre-push`), the hook can only intercept `git push` operations (blocking force-pushes or deletions); it does not intercept local working-tree commands like `git reset` or `DROP TABLE` when run through Git's push lifecycle.
