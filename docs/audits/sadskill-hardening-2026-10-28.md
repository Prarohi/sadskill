# sadskill Audit & Hardening Report (2026-10-28)

- **Audited Baseline Commit**: `b1701a7576c559df0c9294614ad02886d6f5c6b0` (v0.3.0)
- **Environment**: Linux x86_64, Python 3.10+, Bash 5.2
- **Test Suite Status**: 142 / 142 verification checks passing (`scripts/verify.py`). Deterministic benchmark validation: Track A 6/6 contracts, Track B 2/2 fixtures, Track C0 catalog 24/24. Track C1 real-agent runs: **0, NOT_EXECUTED**; these checks do not establish real-agent task performance.

---

## 1. Executive Summary of Critical (P0) Repairs

### P0-01: Repaired Restore-Then-Delete Bug & Conflict-Safe Refusal (`uninstall.sh`, `scripts/manifest.py`)
- **Vulnerability**: `uninstall.sh` previously restored backup archives from the manifest, and then immediately ran legacy unconditional `rm` blocks that deleted the restored files. Furthermore, restoring over user-modified files clobbered local edits without warning.
- **Repair**: Replaced with a manifest-driven transactional manager (`scripts/manifest.py`). Restored files are marked `restored: true` and strictly preserved from subsequent cleanup. Added content hash comparison before restore/removal: user-modified files are safely preserved (`[PRESERVE-MODIFIED]`) with conflict refusal unless `--force` is explicitly provided.
- **Evidence**: Verified in `VerificationSuite.test_sandbox_installer_and_safety` (restored file content matches original bytes exactly, user-modified files preserved without `--force` and cleanly restored with `--force`).

### P0-02: Isolated Backup Cleanup (`uninstall.sh`)
- **Vulnerability**: `--clean-backups` used broad shell glob patterns (`*.bak.*`) inside shared user directories like `~/.codex/prompts/` and `~/.claude/commands/`, risking deletion of backups created by other tools.
- **Repair**: Restricted backup removal to the exact backup paths recorded in `install-manifest.json`.
- **Evidence**: Verified in `VerificationSuite.test_sandbox_installer_and_safety` (unrelated backup `other-tool.md.bak.keep` survived clean-backups).

### P0-03: Evidence Re-Test Interpreter Execution Hardening (`scripts/verify-evidence.py`)
- **Vulnerability**: `execute_safe_command` allowed arbitrary code strings via general-purpose interpreters (`python -c`, `bash -c`, `node -e`).
- **Repair**: Enforced a trusted recipe registry. Disallowed inline evaluation flags (`-c`, `-e`) and shell chaining tokens. Implemented isolated process groups with child process termination on timeout. Added support for non-executable/docs-only tasks with truthful `SKIPPED_WITH_REASON` status (V-08, T60).
- **Evidence**: Verified in `VerificationSuite.test_evidence_verifier_safety`.

### P0-04: Eliminated Unsafe Shell String Interpolation into Python Source (`install.sh`)
- **Vulnerability**: `install.sh` previously constructed Python script literals via shell variable interpolation, vulnerable to syntax errors or unexpected execution on paths containing apostrophes or quotes.
- **Repair**: Delegated manifest mutations to `scripts/manifest.py` using CLI arguments and structured JSON serialization.
- **Evidence**: Tested with unusual arguments and directory paths.

### P0-06: Preserved Pre-Existing Claude Hooks on Install (`install.sh`)
- **Vulnerability**: `install_claude()` previously copied `git-guardrail.sh` over any existing hook without creating a backup archive.
- **Repair**: Checks for pre-existing hooks and creates a timestamped `.bak` archive before replacement.
- **Evidence**: Verified in sandbox installation test suite.

### P0-08: Collision-Safe Backup Path Generation (`install.sh`)
- **Vulnerability**: `install.sh` used naive 1-second timestamps (`.bak.YYYYMMDDHHMMSS`), leading to collisions during same-second reinstalls or rapid CI test runs.
- **Repair**: Implemented `make_backup_path` helper generating unique paths with timestamp, process ID, and random retry suffix.

---

## 2. P1 Guardrails & Diagnostics

1. **Diagnostic Doctor Utility (`scripts/doctor.py`)**: Added a local capability scanner. It distinguishes `LOCAL_TEST_PASSED` from `HOST_VERIFIED_ACTIVE`; only an explicit operator confirmation can set the latter. Added ownership-aware hook registration and removal using Claude Code's nested settings schema.
2. **Git Pre-Push Ref-Update Parsing (`scripts/git-guardrail.sh`)**: Added stdin stream inspection for Git pre-push hook protocol, parsing both 4-token streams (`<local_ref> <local_oid> <remote_ref> <remote_oid>`) and 3-token / empty `local_ref` streams (such as `git push origin :main`), blocking remote branch deletions and non-fast-forward force pushes.
3. **Structured JSON Hook Parsing**: Swapped fragile single-line `sed` regex with robust Python JSON parser handling escaped characters and multi-line commands.
4. **Lexical Command Parsing & Commit Message Stripping (`scripts/git-guardrail.sh`)**: Replaced naive `tr ';|&' '\n'` with `shlex.shlex(punctuation_chars=True)` lexer to avoid breaking quoted strings containing punctuation. Stripped commit message bodies (`-m`, `--message`) before SQL analysis, eliminating false positives on architectural commit descriptions.
5. **Cursor Workspace Skill Directory Packaging & Uninstallation (`install.sh`, `scripts/manifest.py`)**: Added tracking and backup for `.cursor/skills/sadskill` alongside `.cursor/rules/sadskill.mdc`, ensuring complete transactional cleanup upon uninstall.
6. **Manifest Recording Observable Errors (`install.sh`)**: Removed error suppression (`2>/dev/null || true`); failures to record manifest entries now log to stderr and exit with code 1.
7. **Evidence Retest Environment Isolation (`scripts/verify-evidence.py`)**: Sanitized subprocess environment to prevent inheritance of arbitrary external `PYTHONPATH` or `NODE_PATH` from host environment (V-06).
8. **Guardrail Parity**: Enforced byte-for-byte identity between `scripts/git-guardrail.sh` and `skills/sadskill/hooks/git-guardrail.sh`.


---

## 3. Product Upgrades (Conversation-Aware Whole-Codebase Analysis)

1. **Context & Intent Protocol (`skills/sadskill/protocols/context.md`)**: Defines `TaskContext` interpretation, requested depth, and execution modes. User's latest explicit instructions take precedence over stale notes.
2. **Whole-Codebase Coverage & Discovery (`skills/sadskill/protocols/coverage.md`)**: Enforces systematic repository inventory, explicit exclusion tracking, and truthful `FULL_COVERAGE` vs `PARTIAL_COVERAGE` reporting.
3. **Adaptive Advice (`skills/sadskill/protocols/advice.md`)**: Non-intrusive, impact-ranked suggestions; suppressible upon user request.
4. **Autonomous Continuation (`skills/sadskill/protocols/autonomy.md`)**: Bounded continuation loops and clarification budgets across four execution modes (`REVIEW_ONLY`, `PLAN_ONLY`, `IMPLEMENT`, `CONTINUE_UNTIL_DONE`).
5. **Approved Web Research (`skills/sadskill/protocols/research.md`)**: User-authorized external documentation research with provenance tracking; protects against untrusted web prompt injection.
6. **SQLite RLS-Simulation Behavioral Fixture (`benchmarks/fixtures/real-rls/`)**: Behavioral tests exercise a SQLite authorizer simulation of tenant isolation. This is not a native PostgreSQL RLS integration test.

---

## 4. Implementation Backlog Ledger (S01–S60)

| ID | Priority | Description | Affected Paths | Acceptance Evidence | Status |
|---|---|---|---|---|---|
| S01 | P0 | Fix restore-then-delete bug | `uninstall.sh`, `scripts/manifest.py` | Byte-identical prompt restored without deletion | **FIXED** |
| S02 | P0 | Limit backup removal to owned files | `uninstall.sh`, `scripts/manifest.py` | Unrelated backups survive `--clean-backups` | **FIXED** |
| S03 | P0 | Remove arbitrary evidence command replay | `scripts/verify-evidence.py` | Untrusted interpreter `-c` flag rejected | **FIXED** |
| S04 | P0 | Replace unsafe manifest Python interpolation | `install.sh`, `scripts/manifest.py` | Structured CLI arguments with atomic writes | **FIXED** |
| S05 | P0 | Verify manifest ownership and path containment | `scripts/manifest.py` | Path traversal and escapes outside roots rejected | **FIXED** |
| S06 | P0 | Preserve existing Claude hook | `install.sh`, `scripts/manifest.py` | Pre-existing hook backed up before install | **FIXED** |
| S07 | P0 | Stop filename-only uninstall deletion | `uninstall.sh`, `scripts/manifest.py` | Manifest and content-signature verified | **FIXED** |
| S08 | P0 | Atomic installer transaction / collision | `scripts/manifest.py` | Atomic temp file write + rename with SHA-256 | **FIXED** |
| S09 | P1 | Correct purge/no-backup user experience | `install.sh`, `uninstall.sh` | Added `--dry-run` and clear warnings | **FIXED** |
| S10 | P1 | Hook active-state doctor | `scripts/doctor.py` | Local simulations never claim host activation; confirmation is explicit | **FIXED** |
| S11 | P1 | Correct Git pre-push ref handling | `scripts/git-guardrail.sh` | Ref update stream parsed for force push & delete | **FIXED** |
| S12 | P1 | Structured Claude JSON parser | `scripts/git-guardrail.sh` | Escaped quotes and multi-line payloads parsed | **FIXED** |
| S13 | P1 | Guardrail classifier hardening | `scripts/git-guardrail.sh` | Dangerous keywords inside `-m` messages allowed | **FIXED** |
| S14 | P1 | Eliminate duplicate hook drift | `scripts/git-guardrail.sh`, `hooks/` | Byte-for-byte identity enforced in CI verify | **FIXED** |
| S15 | P1 | Host-specific tool coverage matrix | `docs/compatibility.md` | Documented supported discovery & invocation | **FIXED** |
| S16 | P1 | Verify 5 workflow invocations per host | `commands/`, `skills/sadskill/SKILL.md` | Slash commands and universal triggers documented | **FIXED** |
| S17 | P1 | Correct Gemini CLI and Antigravity paths | `install.sh`, `docs/compatibility.md` | Discovered at standard `~/.gemini/skills` | **FIXED** |
| S18 | P1 | Correct auto/all target semantics | `install.sh` | Cursor clearly skipped with note inside repo | **FIXED** |
| S19 | P1 | Correct CLI error exit codes | `install.sh`, `uninstall.sh` | Invalid options exit 2, `--help` exits 0 | **FIXED** |
| S20 | P2 | Cross-platform install tests | `tests/`, `scripts/verify.py` | Portable path resolution using Pathlib | **FIXED** |
| S21 | P1 | Strict evidence schema validation | `scripts/verify-evidence.py` | Non-int exit_code and non-list files rejected | **FIXED** |
| S22 | P1 | Implement provenance state transitions | `scripts/verify-evidence.py` | REPORTED vs RETESTED vs CI_ATTESTED | **FIXED** |
| S23 | P1 | Retest recipe registry + sandbox | `scripts/verify-evidence.py` | Trusted recipes only; process group isolation | **FIXED** |
| S24 | P2 | Correct evidence `--json` stdout | `scripts/verify-evidence.py` | Stdout is parseable standalone JSON (logs on stderr) | **FIXED** |
| S25 | P2 | Bound timeout and process tree killing | `scripts/verify-evidence.py` | 1-300s validation; os.killpg on timeout | **FIXED** |
| S26 | P2 | Restrict evidence root and symlinks | `scripts/verify-evidence.py` | External symlinks escaping root rejected | **FIXED** |
| S27 | P2 | Tie evidence to commit/dirty state | `scripts/verify-evidence.py` | Records project git state when available | **FIXED** |
| S28 | P2 | Optional CI attestation validation | `scripts/verify-evidence.py` | Validates CI attestation dictionary metadata | **FIXED** |
| S29 | P1 | Separate contract checks from real benchmarks | `benchmarks/runner.py`, `docs/` | Contract checks clearly distinguished in docs | **FIXED** |
| S30 | P1 | Build behavioral benchmark fixtures | `benchmarks/fixtures/` | Grader harnesses for real code behavior | **FIXED** |
| S31 | P1 | Hidden behavioral graders | `benchmarks/fixtures/` | Test suites fail intentionally broken submissions | **FIXED** |
| S32 | P1 | Plain-agent and control baselines | `docs/benchmark-methodology.md` | Documented methodology for matched comparisons | **FIXED** |
| S33 | P1 | Record token/cost/time honestly | `docs/benchmark-methodology.md` | Unavailable metrics reported as N/A | **FIXED** |
| S34 | P2 | Expand benchmark task suite | `benchmarks/tasks.json` | 6 core contract checks + behavioral fixtures | **FIXED** |
| S35 | P2 | Repeated runs and variance | `docs/benchmark-methodology.md` | Defined repeated evaluation procedures | **FIXED** |
| S36 | P1 | Conversation-aware intent model | `skills/sadskill/protocols/context.md` | TaskContext and instruction precedence rules | **FIXED** |
| S37 | P1 | Whole-codebase discovery | `skills/sadskill/protocols/coverage.md` | Repository mapping and entry point discovery | **FIXED** |
| S38 | P1 | Coverage ledger with exclusions | `templates/coverage-ledger.template.json` | Explicit tracked vs excluded path accounting | **FIXED** |
| S39 | P1 | Deep security/architecture data trace | `skills/sadskill/modes/analyze.md` | Multi-dimensional defect and coupling analysis | **FIXED** |
| S40 | P1 | Context-aware prioritized advice | `skills/sadskill/protocols/advice.md` | Relevant, impact-ranked, suppressible advice | **FIXED** |
| S41 | P1 | Bounded continue-until-done policy | `skills/sadskill/protocols/autonomy.md` | Clarification budgets without repeated approvals | **FIXED** |
| S42 | P1 | Separate review/plan/implement modes | `skills/sadskill/protocols/autonomy.md` | 4 execution modes with strict boundaries | **FIXED** |
| S43 | P1 | Approved web/research workflow | `skills/sadskill/protocols/research.md` | Authorized external documentation & citations | **FIXED** |
| S44 | P2 | Creative inspiration decision flow | `skills/sadskill/modes/design.md` | Design principles without asset copying | **FIXED** |
| S45 | P1 | Shared memory/cross-mode handoffs | `templates/context-handoff.template.json` | Structured JSON schema for mode handoffs | **FIXED** |
| S46 | P2 | Memory secret filtering + provenance | `skills/sadskill/protocols/memory.md` | Scoped storage and credential redaction | **FIXED** |
| S47 | P2 | Concurrent memory writers handling | `skills/sadskill/protocols/memory.md` | Atomic append and superseding decision tracking | **FIXED** |
| S48 | P2 | Proportional planning overhead | `skills/sadskill/modes/plan.md` | Tiny tasks vs Tier 1 vs Tier 2 plans | **FIXED** |
| S49 | P2 | Adaptive frontend design requirements | `skills/sadskill/modes/design.md` | WCAG 2.2 SC 2.5.8 nuance & Zero-Lift style rule | **FIXED** |
| S50 | P1 | SQLite RLS-simulation tests | `benchmarks/fixtures/real-rls/` | Fixture is labeled SQLite simulation; native PostgreSQL RLS is not claimed | **FIXED** |
| S51 | P2 | Migration/backfill safety rules | `skills/sadskill/modes/backend.md` | Irreversible migrations and backup requirements | **FIXED** |
| S52 | P2 | Update OWASP Top 10 to 2025 | `vendor/owasp/owasp-top-10.ref.md` | Updated to official OWASP Top 10:2025 standard | **FIXED** |
| S53 | P2 | Vendor provenance + license audit | `skills/sadskill/vendor/manifest.json` | 40 references tracked with licenses and hashes | **FIXED** |
| S54 | P2 | Rename/fix misleading vendor updater | `scripts/update-vendor.sh` | Accurate audit tool with `--check` manifest flag | **FIXED** |
| S55 | P1 | Skill metadata and relative link validation | `scripts/verify.py` | 100% relative link resolution verified | **FIXED** |
| S56 | P2 | Check compatibility & releases | `docs/compatibility.md`, `CHANGELOG.md` | Matrix and release changelog created | **FIXED** |
| S57 | P2 | Threat model & security boundaries | `docs/threat-model.md` | Documented trust boundaries and attack vectors | **FIXED** |
| S58 | P2 | Supply-chain & privacy scanning | `scripts/verify.py` | Privacy and portability scan passing 100% | **FIXED** |
| S59 | P2 | Docs/claim verification | `README.md` | Honest capabilities without unproven marketing | **FIXED** |
| S60 | P2 | Audit and verification reporting | `docs/audits/` | Full traceability report published | **FIXED** |
