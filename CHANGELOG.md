# Changelog

All notable changes to the `sadskill` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - Unreleased

### Added
- **12-Task C1 Benchmark Harness**: Deterministic mock conditions and optional real Codex, Claude and Gemini CLI adapters. No independently graded paired real-agent trial has established improved correctness or token savings.
- **Canonical Guardrail Parser**: Recursive AST command unwrapper supporting wrappers (`env`, `sudo`, `command`, `exec`, `nohup`, `nice`) and nested shell interpreters (`bash -c`, `sh -c`, `zsh -c`) to prevent evasive bypass of destructive Git, SQL, and filesystem operations.
- **Evidence v2**: Structured evidence verification and content-bound retests. A self-reported CI status or SHA-256 digest is not an authenticated publisher signature.
- **Concurrency-Safe Project Memory (`.sad/`)**: Advisory file locking and immutable append-only event log (`scripts/sad_memory.py`) preventing multi-agent race conditions or silent lost updates.
- **Agent Plugin Packaging**: Root `plugin.json` conforming to OpenAI Agent Plugin and Cursor standards while strictly maintaining single-skill discovery (`npx skills add . -l`).

### Changed
- Promoted source metadata to `0.5.0` as an **unreleased candidate**, not a published tag or GitHub release.
- Added consistent-version CI validation and manual, fail-closed draft preparation with exact-head CI/CodeQL checks, reproducible archives, SHA256SUMS and source identity.
- Hardened pre-push branch deletion and force-push checks.

## [0.4.0] - 2026-10-29

### Fixed
- Refuse missing ownership hashes, noncanonical artifacts and unrelated backup paths before destructive operations; inventory orphan recovery without claiming installed ownership.
- Verify current backup bytes before cleanup/restoration and preserve the original backup identity across updates.
- Replace ambiguous directory hashing with framed tree digests. Preserve unverifiable legacy content; see the [upgrade guide](docs/upgrade-0.4.0.md).
- Validate manifests and hold one advisory lock across installer file changes and ledger writes. Reject unsafe updater history paths before apply/rollback writes.
- Correct stable/prerelease ordering; bind evidence snapshots to actual tracked bytes despite Git index hints.
- Preserve quoted Git arguments, allow ordinary push refspecs, and reject force/deletion forms. Doctor requires real nonempty artifacts and cannot confirm a missing/failed hook active.
- Ship the evidence helper in skill-only distributions and route slash adapters through canonical modes to avoid stale approval, scan and database instructions.

### Added
- Conditional Supabase, Vercel and Bklit references; installed-reference and helper coverage for supported distributions.
- Native PostgreSQL policy tests and deliberately failing negative controls, separate from SQLite fixtures and C1 agent evaluation.
- Contributor task/PR templates, explicit public-source/service-access boundaries, and evidence limits in the README/audit ledger.
- Release version consistency independent of manifest schema version and fixed updater test-fixture versions.

### Validation limits
- C1 real-agent trials, actual workflow execution in every host, and Windows/macOS verification remain unexecuted. No comparative agent-performance claim is made.
- Main integration still requires eligible independent GitHub approval and all required CI; this candidate does not publish itself.

## [0.3.0] - 2026-10-28

### Security & Safety (P0 / P1 Repairs)
- **Transactional Manifest Manager (`scripts/manifest.py`)**: Replaced direct shell string interpolation into Python source with a standalone, atomic manifest manager tracking installed file digests and original backups.
- **Fixed Restore-Then-Delete Bug (`uninstall.sh`)**: Uninstallation now uses verified manifest ledgers to restore backed up user files and preserves them from subsequent removal.
- **Isolated Backup Removal (`uninstall.sh`)**: Replaced broad shell globs (`*.bak.*`) with exact manifest-recorded backup paths, ensuring unrelated backup files belonging to other tools or users are never deleted.
- **Trusted Evidence Recipe Registry (`scripts/verify-evidence.py`)**: Re-test execution now strictly enforces a trusted recipe registry. Arbitrary inline code execution flags (`-c`, `-e`) and shell chaining tokens are rejected.
- **Subprocess Environment Sanitization (`scripts/verify-evidence.py`)**: Isolated test execution environment so external `PYTHONPATH` and `NODE_PATH` from the host cannot hijack verification modules (V-06).
- **Process Group Isolation & Timeout Termination**: Evidence retests execute in independent process groups (`start_new_session=True`), ensuring child process trees are terminated on timeout without orphan processes.
- **Existing Hook Backup on Install (`install.sh`)**: When installing Claude Code hooks, pre-existing hooks are now backed up to a timestamped archive before replacement.
- **Git Pre-Push Hook Ref-Update Interception (`scripts/git-guardrail.sh`)**: Added support for standard Git `pre-push` stdin ref update streams (`<local_ref> <local_oid> <remote_ref> <remote_oid>`), blocking force branch deletions and non-fast-forward updates to protected branches.
- **Structured JSON Hook Payload Parsing**: Replaced fragile `sed` regex with structured JSON parsing for Claude Code `PreToolUse` events.
- **Lexical Command Tokenization & Commit Parsing (`scripts/git-guardrail.sh`)**: Upgraded command splitting from `tr ';|&' '\n'` to `shlex.shlex(punctuation_chars=True)` lexer, preserving quoted arguments and eliminating false positive blockages on SQL keywords inside commit messages.
- **Cursor Workspace Skill Directory Packaging & Cleanup (`install.sh`, `scripts/manifest.py`)**: Backs up and records `.cursor/skills/sadskill` in the install manifest alongside `.cursor/rules/sadskill.mdc`, allowing complete transactional uninstallation.
- **Observable Manifest Errors (`install.sh`)**: Replaced silent error suppression with stderr diagnostic logging and exit code 1.

### Added Capabilities
- **Context & Intent Interpretation (`skills/sadskill/protocols/context.md`)**: Structured `TaskContext` extracting user goals, requested depth, and execution modes from live conversation; explicit user instructions override past memory.
- **Whole-Codebase Coverage & Discovery (`skills/sadskill/protocols/coverage.md`)**: Systematic repository inventory, explicit exclusion tracking, and truthful `FULL_COVERAGE` vs `PARTIAL_COVERAGE` reporting with `templates/coverage-ledger.template.json`.
- **Adaptive Advice Protocol (`skills/sadskill/protocols/advice.md`)**: Impact-ranked, non-repetitive suggestions; easily suppressible when the user requests direct execution without advice.
- **Autonomous Continuation (`skills/sadskill/protocols/autonomy.md`)**: Predictable 4-mode execution contract (`REVIEW_ONLY`, `PLAN_ONLY`, `IMPLEMENT`, `CONTINUE_UNTIL_DONE`) with clarification budgets.
- **Approved Web Research Protocol (`skills/sadskill/protocols/research.md`)**: User-authorized external documentation research with citation provenance and untrusted web content boundaries.
- **Capability Diagnostic Tool (`scripts/doctor.py`)**: CLI diagnostic utility reporting hook and installation status across Claude Code, Codex, Cursor, and Antigravity/Gemini.
- **Database Row Level Security Fixture (`benchmarks/fixtures/real-rls/`)**: Behavioral tests verifying database engine-level tenant isolation using SQLite authorizers, connection-level tenant functions, and triggers.
- **Expanded 24-Task Evaluation Benchmark Suite (`benchmarks/tasks/suite_24.json`, `benchmarks/runner.py`)**: 3-Track evaluation suite featuring Track A (Contract Checks), Track B (Behavioral Fixture Graders), and Track C (24-Task Comprehensive Specification).
- **Gemini CLI Standard Skill Discovery (`install.sh`, `scripts/doctor.py`)**: Added `--agent gemini` target installing to `~/.gemini/skills/sadskill`.
- **Vendor Subsystem Manifest (`skills/sadskill/vendor/manifest.json`)**: Versioned metadata tracking licenses, authors, and source URLs for all 40 reference documents.

### Changed
- **OWASP Top 10 Update**: Updated `skills/sadskill/vendor/owasp/owasp-top-10.ref.md` to reflect the official OWASP Top 10:2025 standard.
- **Vendor Updater Script (`scripts/update-vendor.sh`)**: Converted to an honest audit tool with `--audit` and `--check` modes.
- **CLI Exit Codes**: Argument parsing in `install.sh` and `uninstall.sh` now returns exit code 2 on invalid options, while `--help` returns exit code 0.
- **Verification Suite (`scripts/verify.py`)**: Expanded test suite to 126 automated checks covering P0 repairs, P1 guardrails, lexical splitting, environment isolation, and multi-agent installations.

