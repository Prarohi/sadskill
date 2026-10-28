# Security & Guardrails 10/10 Hardening Plan

This document outlines the architectural upgrade path to elevate Sadskill's execution guardrails from command interception to full **defense-in-depth security**.

---

## 🛡️ Current Architecture (v0.5.0) vs 10/10 Standard

```
+--------------------------------------------------------------+
| Current (v0.5.0)                                             |
| [Input Command] -> [Canonical AST Unwrapper]                 |
|                   ├── Peels wrappers: sudo, env, exec, nohup  |
|                   ├── Recursively unwraps: bash -c, sh -c    |
|                   └── Evaluates Git, SQL, and rm tokens      |
+--------------------------------------------------------------+
                               |
                               v (Upgrade to 10/10)
+--------------------------------------------------------------+
| Target (10/10) Defense-in-Depth                              |
| Layer 1: Canonical AST Unwrapper (Command level)             |
| Layer 2: SQL Semantic AST Parser (SQLglot / SQLite AST)      |
| Layer 3: OS Containerized Sandbox (bubblewrap / seccomp)      |
| Layer 4: Cryptographic Pre-Push Verification                 |
+--------------------------------------------------------------+
```

---

## 🔒 Layer 2: Semantic SQL AST Verification

### The Limitation of Regex Inspection
Regex patterns like `DROP TABLE` or `TRUNCATE` can be circumvented via SQL string concatenation, CTEs, dynamic execution (`EXECUTE format(...)`), or multi-line comment obfuscation:
```sql
/* safe comment */ DROP/**/TABLE/**/users;
```

### The 10/10 Solution:
Implement a standalone Python SQL AST tokenizer in `scripts/sql_guard.py`:
1. Parse the SQL string using a lightweight SQL AST parser.
2. Walk the statement syntax tree and identify root statement types (`Drop`, `Truncate`, `AlterTableDropColumn`).
3. Refuse any statement whose AST contains destructive mutating nodes unless explicitly annotated with a signed migration contract.

---

## 📦 Layer 3: OS-Level Filesystem & Process Sandboxing

### The Challenge:
Even if a shell command appears safe, an agent could run a script (`python3 script.py` or `node build.js`) that performs destructive actions internally without emitting shell commands.

### The 10/10 Solution: Bubblewrap Containment
Provide an optional execution sandbox wrapper for Linux environments using Bubblewrap (`bwrap`):
1. **Read-Only System Mounts**: Mount `/usr`, `/bin`, `/lib` as strictly read-only (`--ro-bind`).
2. **Isolated Worktree Access**: Bind only the current project directory with read-write access (`--bind . .`).
3. **Protected `.git` Directory**: Mount the `.git` directory as read-only during normal build/test execution so untrusted scripts cannot alter git history directly.
4. **Network Restrictions**: Unshare network namespace (`--unshare-net`) for offline tests to prevent secret exfiltration.

```bash
# Example bubblewrap sandbox invocation
bwrap \
  --ro-bind / / \
  --dev /dev \
  --proc /proc \
  --bind "$PROJECT_ROOT" "$PROJECT_ROOT" \
  --ro-bind "$PROJECT_ROOT/.git" "$PROJECT_ROOT/.git" \
  --unshare-net \
  --chdir "$PROJECT_ROOT" \
  "$@"
```

---

## 🚨 Layer 4: Adversarial Test Expansion

Expand `tests/test_guardrail_adversarial.py` to include:
- Base64 encoded payload execution: `echo "..." | base64 -d | sh`
- Dynamic variable expansion: `CMD="git reset --hard"; $CMD`
- Escaped SQL comments and null-byte injection attempts.
- Git config tampering: `git config alias.st "reset --hard"` followed by `git st`.
