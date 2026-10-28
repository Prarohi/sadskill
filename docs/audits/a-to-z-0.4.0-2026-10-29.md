# Sadskill 0.4.0 local regression audit

Date: 2026-10-29. Scope: local source, disposable-home lifecycle tests, fresh Git consumer projects, loopback release servers and the disposable PostgreSQL fixture. Existing local audit files and user changes were preserved.

## Reproduced defects and repairs

| Area | Reproduced problem | Repair and regression coverage |
|---|---|---|
| Manifest authority | Missing ownership hashes allowed removal; broad roots admitted unrelated agent configuration | Require complete SHA-256 metadata and canonical Sadskill destinations before removal/restoration, including forced operations |
| Restore paths | An unrelated configuration could be named as a backup | Require a canonical nonsymlink `.bak.*` sibling; preserve config, destination and ledger on refusal |
| Orphan recovery | Backup discovery enrolled current user files as installed ownership | Inventory recovery separately in `orphan_backups`; ignore unrelated tools' backup names |
| Backup cleanup | Stored hash equality hid changes made to a backup after recording | Hash current backup bytes before cleanup and preserve unresolved backup references |
| Update metadata | Apply replaced the original user-backup hash with an installed-content hash | Retain the original backup reference/hash across update and subsequent cleanup |
| Tree identity | Trees `{a: bc}` and `{ab: c}` produced the same hash input | Typed, length-framed tree records and per-file digests; legacy tree hashes preserve content for review |
| Installer sequencing | A corrupt manifest was discovered after files were replaced | Preflight before agent writes and hold one shared advisory lock across shell changes and ledger updates |
| History path | An updater history symlink appended JSON to an unrelated file | Reject unsafe history paths before apply/rollback mutation and before history append |
| Version order | Stable/prerelease and numeric/alphabetic prerelease precedence were reversed | Ordered version keys with boundary/round-trip and real updater checks |
| Installed version | Reinstall left stale updater state; a mixed installation was reported globally current | Prefer observed skill versions; expose mixed versions and refuse ambiguous global apply pending reconciliation |
| Release archives | Checksums for a named uploaded archive could be applied to a different source archive | Select one exact official named archive, validate its URL and checksum entry, reject duplicates/foreign URLs |
| Evidence bytes | Git index hints hid changed tracked files | Hash actual HEAD/index path content, including missing paths and recursive Gitlinks |
| Evidence links/drivers | Symlink targets escaped freshness binding; configured Git programs ran during capture | Bind supported internal targets, refuse escapes, and disable configured snapshot-time execution paths with marker regressions |
| Git command filter | Quoted global arguments bypassed checks; ordinary refspecs were blocked | Preserve parsed argv and distinguish ordinary refspecs from force/deletion forms in both byte-identical hooks |
| Doctor | Missing/empty artifacts and failed hooks could receive stronger status labels | Require nonempty skill/adapter files and a passing local simulation before explicit host confirmation |
| Distribution | Skill-only installs lacked the prescribed evidence verifier | Bundle the standalone helper, enforce source parity, and exercise fresh consumers without a repository `scripts/` directory |
| Command adapters | Duplicated slash workflows drifted from canonical planning/security/backend rules | Load the canonical mode/protocols through thin adapters; clarify source-only versus installed-helper commands |

Each behavioral fix has a failing-before/passing-after regression or an independently reproduced disposable probe. Exact final counts and commit/CI identity belong in the release PR's evidence section; an earlier green commit does not validate later edits.

## Coverage and release boundary

- Reviewed surfaces include installer/uninstaller, manifests/locks, tree hashes, update identity/download/archive/recovery, evidence schema/snapshots, hooks, doctor, command adapters, packaging, CI and release version metadata.
- Native PostgreSQL remains a separate Track B fixture. Static contracts, prebuilt fixtures and the 24-entry catalog remain distinct from C1 agent execution.
- C1 real-agent trials, actual execution inside every supported agent host and Windows/macOS verification remain unexecuted.
- Advisory locks coordinate cooperating Sadskill processes. Multi-file installer interruption may require recovery from preserved backups; no kernel isolation from unrelated same-user processes is claimed.
- Read the [0.4.0 upgrade guide](../upgrade-0.4.0.md) before relying on legacy directory hashes or orphan recovery.
- Main integration and public release require current-head green checks and eligible independent GitHub approval. Internal AI review is recorded separately. Draft artifacts/checksums do not establish a signed publisher identity.
