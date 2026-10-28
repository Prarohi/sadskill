# Protocol: Verification Evidence Standard

Autonomous coding agents frequently suffer from confirmation bias and premature task completion claims ("I have fixed the issue and everything works!"). The **Verification Evidence Standard** enforces zero-trust verification and truthful provenance reporting.

---

## 🛡️ The Core Principle

> *"Don't just claim code works. Prove it with demonstrable execution evidence, and report provenance truthfully."*

A task is **NOT complete** until the verification command has been executed in the environment, returned exit code `0`, and had its proof recorded.

---

## 📊 Verification Provenance States

Evidence records distinguish between self-reported logs and independently verified executions:

| State | Definition | Display / Wording |
|---|---|---|
| `not_run` | No verification command attempted | Not verified |
| `reported` | Agent claims execution in conversation | Agent-reported result |
| `schema_valid` | Required types, timestamp, project identity, current commit, dirty state, and contained paths match | Evidence format verified (unexecuted; does not prove the command ran) |
| `retested` | Independently executed by authorized verifier (`verify-evidence.py --retest`) | Retest passed in target environment |
| `ci_claimed` | Evidence includes self-reported CI metadata | CI claim recorded but not independently verified |
| `ci_attested` | Independent trusted verifier fetched and validated repository, workflow, run/job conclusion, and exact head SHA | CI check passed for commit X |
| `skipped_with_reason` | Non-test task (docs-only, research, read-only analysis) | Documented non-runnable task |
| `failed` | Non-zero exit code or broken test assertion | Verification failed |

---

## 📋 The Verification Workflow

### 1. Execute the Real Harness
- For frontend/full-stack: `npm test -- <path>`, `npm run build`, `npx tsc --noEmit`
- For Python: `pytest <path>`, `python3 -m unittest`
- For Rust: `cargo test -- <test_name>`, `cargo check`
- For Go: `go test -v ./...`
- For CLI/scripts: Direct script invocation with `--help` or assertion flags.
- For documentation-only, research, or read-only tasks where no runnable harness exists: Record `status: "SKIPPED_WITH_REASON"`, `exit_code: null`, and document the reason in `summary`. Never fabricate fake tests or dummy commands to produce artificial green results.

### 2. Capture Structured Evidence
Record the verification event in `.sad/evidence/<YYYYMMDD-HHMMSS>-<slug>.json`:

Before creating a record, run `python3 scripts/verify-evidence.py --print-context`. Copy its `project_id`, exact `commit_sha`, `worktree_dirty`, and `worktree_digest` fields into the record. The project identity is a SHA-256 digest of the canonical local checkout path; records are bound to that checkout's tracked and untracked content plus relevant ignored test sources, configs (including Rust toolchain pins), and fixtures outside `.sad/evidence/`. Initialized submodule worktrees are included recursively; Gitlinks in `HEAD` and the index must match `.gitmodules`, and a mismatch, unmerged index, uninitialized or unsafe submodule makes the snapshot unavailable. Standard generated dependency/build directories are excluded unless nested below an explicit test or fixture directory. The verifier excludes `.sad/evidence/` itself when comparing dirty state.

```json
{
  "timestamp": "2026-10-28T03:12:00Z",
  "project_id": "<copy project_id from --print-context>",
  "commit_sha": "<copy commit_sha from --print-context>",
  "worktree_dirty": false,
  "worktree_digest": "<copy worktree_digest from --print-context>",
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

#### Strict Path Containment:
- All entries in `files_touched` must be relative to the project root.
- Absolute paths (e.g. `/etc/...`, `/tmp/...`) and path traversal segments (`..`) are strictly prohibited and will be rejected by `scripts/verify-evidence.py`.

Evidence retests can select only registered recipes. Raw command strings must exactly match a fixed recipe; caller-supplied paths, selectors, manifests, and test names are rejected. There is no `--allow-custom-retest` escape hatch because checking that a script is inside the repository is not a sandbox for executing it.

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
4. **Never fabricate artificial test passes for docs-only or research tasks; accurately declare `SKIPPED_WITH_REASON` or `NOT_APPLICABLE`.**
