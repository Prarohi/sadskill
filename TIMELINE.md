# Project Timeline & Execution Log

All major milestones, fixes, architectural evolutions, and test results for `sadskill` are chronologically recorded here.

---

### [2026-10-29 01:45:00 UTC] - Sadskill 0.5.0 World-Class Upgrade Package Implemented
- **Branch**: `upgrade/worldclass-0.5.0` based on integration candidate `be49a0f`.
- **C1 Benchmark Harness**: Built runnable 12-task comparative benchmark suite (`benchmarks/harness/runner.py`, `tasks.py`, `evaluators.py`, `providers.py`) evaluating `plain`, `sadskill`, and `competitor` conditions. Supported deterministic offline execution with `--provider mock` and truthful fail-closed handling with `--provider codex` (`NOT_EXECUTED_NO_AUTH`).
- **Canonical Guardrail Hardening**: Upgraded `scripts/git-guardrail.sh` and packaged `skills/sadskill/hooks/git-guardrail.sh` to recursively unwrap command wrappers (`sudo`, `env`, `command`, `exec`, `nohup`, `nice`) and nested shell interpreters (`bash -c`, `sh -c`, `zsh -c`), completely closing the evasion loophole.
- **Evidence v2 Cryptographic Provenance**: Enhanced `scripts/verify-evidence.py` to support Evidence v2 with SHA-256 canonical JSON digest checking, provenance hash chaining (`previous_record_hash`), and programmatic creation helper (`create_evidence_record`).
- **Concurrency-Safe Project Memory**: Implemented `scripts/sad_memory.py` with advisory file locking (`.sad/.lock`) and append-only event logs (`.sad/events/`), preventing race conditions and lost updates during multi-agent collaboration.
- **Agent Plugin Packaging**: Added root `plugin.json` supporting OpenAI Agent Plugin and Cursor standards while strictly maintaining single-skill discovery (`npx skills add . -l`).
- **Unit & Adversarial Tests**: Authored 3 new comprehensive test suites (`tests/test_guardrail_adversarial.py`, `tests/test_evidence_v2.py`, `tests/test_concurrent_memory.py`, `tests/test_c1_benchmark_harness.py`).
- **Status**: 100% passing across all regression, verification, and benchmark suites.
