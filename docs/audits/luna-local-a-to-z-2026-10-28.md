# Sadskill local A-to-Z audit — 2026-10-28

## Decision

**NOT_READY.** Local fixes and tests are complete for the inspected PR work, all three current PR heads have green exact-head CI, and independent internal reviews cleared PR1, PR2, PR3, and the combined local candidate. Do not merge: GitHub has no submitted formal independent review, only the repository owner is an eligible collaborator, `main` has no branch protection, release assets contain no checksum file, and the local combined candidate has no remote CI run. Real-agent Track C1 and PostgreSQL-native RLS are also unexecuted.

## Local execution and baseline

- The attached master document was treated as the operating checklist; historical SHAs and statuses inside it were treated as leads and rechecked against live local/GitHub state.
- Work ran against the user's local Sadskill clone and local Git worktrees. No cloud checkout was used.
- Live `origin/main`: `0711f806529bc2164161d898d03561435c9d573f`.
- The original PR2 checkout was clean at the start of this continuation (`619bf47a6d091bac3889262cb4baa11d3774d3bb`). PR work used separate local worktrees; user changes in the original checkout were preserved.
- Local-only integration candidate: branch `luna/integration-candidate-2026-10-28`, tested HEAD `8966a243368aedbbd32ffd72030a8401fcd2ca73`. It merges PR1, PR2, and PR3 in the safe order, with documented README conflict resolutions. It was not pushed.
- Historical objects `63125c4e01ef0d5ce1e54518770225237fb92471` and `e7d8f2c3542af0370205a371ce9c87b8bd58fbf1` are absent from the local Git object database and all available refs/reflogs. `git cat-file` could not resolve either. The reported patch/bundle was not found in Downloads. A broader home search encountered a permission-denied unrelated data directory, so no claim is made that every inaccessible location was searched. Fixes were reconstructed and independently tested from current sources.

## Source coverage

The repository inventory contains 154 tracked paths. The current PR diffs were reviewed and tested: PR1 changes 33 paths, PR2 changes 28, and PR3 changes 11. This is a focused audit of those changes and their security boundaries, not a line-by-line audit of all 154 paths.

| Area | Coverage | Evidence |
|---|---|---|
| PR1 product contracts, modes, docs, command adapters, Claude hook ownership, CI | Inspected changed diff and focused tests | `tests/skill-contract/`, `tests/install/test_claude_settings.py`, exact PR1 CI |
| PR2 installer, manifest, doctor, updater, rollback, archive/network trust boundaries | Inspected changed diff and updater/install regression tests | `scripts/sadskill-update.py`; `tests/updater/`; `tests/install/`; exact PR2 CI |
| PR3 evidence freshness, safe retests, benchmark claims | Inspected changed diff, adversarial regressions, deterministic benchmark | `scripts/verify-evidence.py`; `tests/test_verify_evidence.py`; `benchmarks/runner.py` |
| Remaining tracked files outside these diffs | Not line-audited | Inventory only; no exhaustive-source claim |

### Key source evidence at the tested candidate

- Evidence freshness selectors: `scripts/verify-evidence.py:92-122`; validated `.gitmodules`: `:140-171`; HEAD/index Gitlinks and conflict-stage validation: `:173-207`; recursive snapshot: `:209-327`; fixed retest allowlist and process cleanup: `:438-564`.
- Updater network origin and redirect credential handling: `scripts/sadskill-update.py:122-202`; structured release identity: `:262-369`; bounded tar/PAX/archive extraction: `:421-523`; apply transaction: `:985-1298`; canonical target and symlink checks: `:1339-1470`; backup snapshot and atomic replacement: `:1527-1638`; rollback destination and restore: `:1641-1946`.
- Focused adversarial regressions include `tests/updater/test_security_boundaries.py:107-274`, `tests/updater/test_apply.py:106-575`, and `tests/test_verify_evidence.py:73-470`.

## Implemented and reviewed changes

- PR1 corrected product/update claims, package-relative hook references, change-contract documentation, and Claude hook schema/ownership/matcher handling. Exact-head internal review reported no remaining actionable findings. The portable `$HOME` hook form is recognized for doctor status, idempotent enable, and disable.
- PR2 hardened redirect token handling, release identity and checksum labeling, archive/PAX/decompression caps, private and durable backups, canonical install/rollback targets, post-backup race checks, duplicate archive destinations, force rollback preservation, and transaction recovery. Exact-head internal review reported no remaining actionable findings.
- PR3 now binds evidence to relevant ignored inputs including Go `testdata`, Cargo config, and Rust toolchain pins; recursively hashes initialized submodules; reconciles Gitlinks in HEAD/index with `.gitmodules`; refuses missing/edited configuration, uninitialized/unsafe submodules, and any unmerged index stage; keeps C1 and SQLite-vs-PostgreSQL claims truthful. Exact-head internal review at `c48df79032fb1d52f58adcc1ec526735fe1ec1b3` reported no remaining actionable findings.
- PR descriptions were updated with current heads, tests, CI, and limitations. No GitHub PR was merged.

## Verification ledger

| Target | Exact SHA | Result |
|---|---|---|
| PR1 | `66231109e63a9148b6a16838ab872020f781177b` | Contract 18 + install/hook 28 tests; `verify.py` 142/142; CI run `40651587108` Node 20/22 green; internal review clear |
| PR2 | `619bf47a6d091bac3889262cb4baa11d3774d3bb` | Python suite 85 passed; `verify.py` 142/142; CI run `40648870888` Node 20/22 green; internal review clear |
| PR3 | `c48df79032fb1d52f58adcc1ec526735fe1ec1b3` | Python suite 25 passed; `verify.py` 142/142; benchmarks A 6/6, B 2/2, C0 24/24; CI run `40650632383` Node 20/22 green; internal review clear |
| Local combined candidate | `8966a243368aedbbd32ffd72030a8401fcd2ca73` | Combined Python suite 132 passed; `verify.py` 142/142; benchmarks A 6/6, B 2/2, C0 24/24; compile, Bash syntax, diff checks passed; no remote CI because branch is local-only |

Track C1: **0 real-agent runs, NOT_EXECUTED**. PostgreSQL-native RLS: **NOT_RUN**; the existing database authorization fixture uses SQLite and is only a simulation. Python 3.14 was the local runtime.

## L-001–L-030 gate classification

| ID | Status | Evidence / remaining limit |
|---|---|---|
| L-001 | PASS | Cross-origin redirect test confirms bearer token is not forwarded. |
| L-002 | PASS | Repository substring in unrelated release metadata is rejected. |
| L-003 | PASS | Aggregate decompression, directory payload and PAX bounds covered. |
| L-004 | PASS | Missing checksum is explicitly labeled transport-only. |
| L-005 | PASS | Malformed/missing requested checksum refuses apply. |
| L-006 | PASS | Forced rollback preserves post-apply user edit and exact destination. |
| L-007 | PASS | Duplicate skill basenames restore to exact paths. |
| L-008 | NOT_RUN | Full directory-entry digest and post-rollback validation were not independently fault-tested as a dedicated matrix. |
| L-009 | NOT_RUN | Lock contention is tested; full apply-vs-apply/rollback/uninstall interleaving matrix was not run. |
| L-010 | NOT_RUN | Recovery after first replacement is covered; crash injection at every replacement boundary was not run. |
| L-011 | PASS | Archive symlinks, symlinked backup parent, canonical roots and containment refusal have regressions; full OS race matrix remains unrun. |
| L-012 | PASS | Reinstall preserves user-modified content and original backup. |
| L-013 | PASS | Unresolved restore conflict survives backup cleanup; unrelated backups survive. |
| L-014 | PASS | Orphan/legacy paths preserve backups and explicit orphan adoption is tested. |
| L-015 | PASS | Malformed, duplicate, symlinked and newer-version manifests fail closed. |
| L-016 | PASS | Install/uninstall dry-run and updater plan/check no-write behavior tested. |
| L-017 | PASS | External `npx skills` manager ownership is refused even with adoption requested. |
| L-018 | NOT_RUN | Exact unmanaged standalone install adoption provenance and complete reversible transfer were not separately exercised. |
| L-019 | PASS | Nested Claude hook schema and preservation tested locally; no host activation claim. |
| L-020 | PASS | Packaged hook links and relative links resolve; source-only companion limitations are documented. |
| L-021 | PASS | Forged `ci_attestation.verified` remains a claim, not attestation. |
| L-022 | PASS | Arbitrary evidence-provided retest commands/arguments are rejected. |
| L-023 | NOT_RUN | Live agent proportionality for a mid-conversation one-line intent change was not benchmarked. |
| L-024 | NOT_RUN | Exhaustive whole-repository analysis behavior/coverage ledger was not run. |
| L-025 | PASS | SQLite is named as simulation; native PostgreSQL RLS remains NOT_RUN. |
| L-026 | PASS | C0 validates 24 catalog entries; it is not reported as 24 agent runs. |
| L-027 | PASS | Combined local suite ran at the exact local candidate SHA above: 132 passed. |
| L-028 | PASS | All three current PR heads have green exact-head Node 20/22 CI. The local-only combined candidate has no CI; its internal integration review is clear. |
| L-029 | BLOCKED | No GitHub review is submitted; only the owner is an eligible collaborator. No merge was performed. |
| L-030 | NOT_RUN | Local repository/worktrees are present and persistent now; restart/reopen recovery was not simulated. |

## Additional release gates

| Gate | Status | Evidence |
|---|---|---|
| Local execution and source preservation | PASS | Actual local Git checkout/worktrees used; original checkout remained clean. |
| Reported historical commits recovered | BLOCKED | Both object IDs absent from local database/refs/reflogs. |
| Historical patch/bundle found | BLOCKED | Not found in Downloads; broader search was incomplete because of an unrelated permission-denied path. |
| Current exact-head PR CI | PASS | PR1, PR2, PR3 run IDs listed above. |
| Independent internal code review | PASS | Separate reviewer cleared each current PR head. |
| Eligible independent GitHub approval | BLOCKED | Collaborator API returned only `sadafbabu`; PR review lists are empty. |
| Main branch protection | FAIL | GitHub API returned 404 “Branch not protected.” |
| Published release checksums | FAIL | GitHub releases `v0.3.0` and `v0.2.1` have zero assets. |
| Real-agent benchmark C1 | NOT_RUN | Zero paired/real-agent runs. |
| PostgreSQL-native RLS | NOT_RUN | No native PostgreSQL execution; SQLite simulation only. |
| Combined candidate GitHub CI | NOT_RUN | Candidate branch intentionally remains local-only. |
| Full tracked-source line audit | NOT_RUN | 154 paths inventoried; review focused on 72 PR path changes and linked security boundaries. |

## Evidence-bound ratings

| Category | Score | Basis |
|---|---:|---|
| Updater safety and local regressions | 8/10 | Extensive adversarial tests and exact CI; full crash/concurrency matrix and formal external approval absent. |
| Product/workflow and portability contracts | 7/10 | Focused tests, exact CI and internal review; live host behavior and real-agent task behavior unmeasured. |
| Evidence verifier and deterministic benchmark honesty | 8/10 | Adversarial freshness tests and A/B/C0 pass; C1 remains unexecuted. |
| Real-agent effectiveness evidence | 0/10 | No real-agent runs were performed. |
| Release/merge readiness | 2/10 | Three PR CI heads are green, but external approval, release checksum assets, native RLS evidence and combined-branch CI are absent. |

`READY_FOR_RELEASE` and `READY_WITH_DOCUMENTED_LIMITATIONS` are not justified. Current state remains **NOT_READY**. Reopen release review after an eligible independent GitHub reviewer is available, required artifact checksum assets are published, the requested real-agent/native-PostgreSQL gates are executed or formally scoped out by the owner, and the combined candidate receives exact-head CI.
