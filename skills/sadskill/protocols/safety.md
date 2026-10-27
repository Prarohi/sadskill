# Protocol: Git & Database Destructive Action Guardrails

Autonomous agents must never perform irreversible destructive actions on user code, repositories, or databases without an explicit, batched user confirmation gate.

---

## 🚫 Forbidden Destructive Actions (Require Explicit Approval)

### 1. Git Destructive Operations
The following Git commands can cause permanent loss of uncommitted work or commit history. They are **strictly forbidden** from automatic execution:
- `git reset --hard` (destroys uncommitted working directory changes)
- `git push --force` or `git push -f` (overwrites remote branch history)
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

## ⚙️ Programmatic Enforcement: `scripts/git-guardrail.sh`

`sadskill` provides an executable OS-level hook script at `scripts/git-guardrail.sh` that intercepts dangerous commands and terminates with exit code 2 before they run.

### Setup for Claude Code (`.claude/settings.json`)
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/git-guardrail.sh"
          }
        ]
      }
    ]
  }
}
```

### Setup for Git Pre-Push Hook (`.git/hooks/pre-push`)
```bash
ln -s ../../scripts/git-guardrail.sh .git/hooks/pre-push
```
