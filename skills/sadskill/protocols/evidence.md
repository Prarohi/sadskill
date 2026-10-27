# Protocol: Verification Evidence Standard

Autonomous coding agents frequently suffer from confirmation bias and premature task completion claims ("I have fixed the issue and everything works!"). The **Verification Evidence Standard** enforces strict zero-trust execution.

---

## 🛡️ The Core Principle

> *"Don't just claim code works. Prove it with terminal execution evidence."*

A task is **NOT complete** until the verification command has been executed in the environment, returned exit code `0`, and had its proof recorded.

---

## 📋 The Verification Workflow

### 1. Execute the Real Harness
- For frontend/full-stack: `npm test -- <path>`, `npm run build`, `npx tsc --noEmit`
- For Python: `pytest <path>`, `python3 -m unittest`
- For Rust: `cargo test -- <test_name>`, `cargo check`
- For Go: `go test -v ./...`
- For CLI/scripts: Direct script invocation with `--help` or assertion flags.

### 2. Capture Structured Evidence
Record the verification event in `.sad/evidence/<YYYYMMDD-HHMMSS>-<slug>.json`:

```json
{
  "timestamp": "2026-10-28T03:12:00Z",
  "task_slug": "feature-or-fix-slug",
  "command": "npm test -- tests/target.test.ts",
  "exit_code": 0,
  "summary": "4 tests passed, 0 failed (verified in 1.2s)",
  "files_touched": [
    "src/target/module.ts",
    "tests/target.test.ts"
  ]
}
```

### 3. Output 3-Line Terminal Execution Proof in Chat
Every mode completion must conclude with this dense, scanable proof block:

```text
✓ Command: <exact-command-run> (exit code 0)
✓ Result: <summary of passed tests / zero errors>
✓ Evidence: .sad/evidence/<YYYYMMDD-HHMMSS>-<slug>.json
```

---

## 🚫 Forbidden Completion Claims
1. **Never claim tests passed without quoting the terminal command and exit code 0.**
2. **Never skip running tests because "the change is simple enough".**
3. **If no automated test exists for a bug, write a minimal reproduction test first, verify failure, apply the fix, and verify pass.**
