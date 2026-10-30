# Upgrading to Sadskill 0.4.0

This is the unreleased 0.4.0 candidate. Use the reviewed repository/ref or your existing skill manager; do not replace another manager's installation silently. No update or user-home migration runs merely because this document exists.

## Directory hash migration

Older directory hashes concatenated filenames and bytes without framing. Different trees could produce the same input to SHA-256. Version 0.4.0 uses typed, length-delimited tree records, per-file digests, empty-directory records and explicit symlink targets. File SHA-256 values remain standard file hashes.

The new code cannot prove that content matching an old ambiguous directory hash is unchanged. It therefore preserves those destinations on ordinary uninstall, and refuses automatic restoration from a backup whose current digest is not verified. It never silently rewrites old hashes to declare current user content owned. An updater may report a modification conflict for a legacy tree; `--force` is an explicit override, not a migration check.

Before upgrading, keep a private copy of your existing manifest, installed directories and backups. Inspect originals and any conflicts locally. A normal companion reinstall preserves preexisting content in backups and records the new installed tree digest; it may retain an older original-backup record that still needs manual inspection. Do not delete a manifest or replace hashes just to make an integrity failure disappear. Restore reviewed legacy backup content manually if automatic verification refuses it.

Missing/empty/invalid ownership hashes and destinations outside canonical Sadskill artifacts now fail closed. A backup must be a canonical `.bak.*` sibling of its destination. These checks also apply before a forced removal/restoration.

## Orphan recovery

`adopt-orphans` inventories relevant orphan backups in the non-owning `orphan_backups` ledger. Discovery does not grant deletion or update authority over the current destination. Other tools' unrelated backups are ignored. Inspect a recovered backup and destination before manually restoring it; inventory alone does not overwrite either one.

## Host versions and release archives

Installed skill versions take precedence over stale updater state after a companion reinstall. Status/check report a mixed-version installation explicitly; a global apply refuses it until the hosts are aligned through their owning installer. This avoids treating one updated host as proof that every host is current.

For 0.4.0 releases the updater prefers the uniquely named official
`sadskill-0.4.0.tar.gz` asset and verifies its matching `SHA256SUMS.txt` entry.
A checksum for one archive never validates different source-archive bytes.

Stable, beta and explicitly pinned `plan`/`apply` operations now refuse a
release without a matching checksum before downloading its archive or writing
installation state. `check` reports `TRANSPORT_ONLY` and warns that an explicit
external digest is needed. For a legacy release only, obtain the exact archive
SHA-256 from an independent trusted source, then pass it to that one `plan` or
`apply` invocation with `--expected-sha256`. The updater verifies the fetched
archive against that digest and labels it `EXTERNAL_CHECKSUM_MATCHED`; it never
stores the digest or an override in updater state. A malformed or mismatched
published `SHA256SUMS.txt` still refuses the operation. Prefer a release with
a published checksum and use an external digest only for a one-time migration.

## Evidence records

Tracked files are now read independently of Git's `assume-unchanged` and `skip-worktree` hints. The snapshot format changed, so recapture context after upgrading. Use the installed skill's `tools/verify-evidence.py` with the consumer checkout passed as `--project-root`; the consumer need not contain a Sadskill `scripts/` directory. Host activation, cross-platform execution and C1 agent trials retain their separate evidence requirements.

## Release gates

Publishing the release requires the intended reviewed commit, green required CI, local regression/security checks and checksums for the actual archives. A draft or matching checksum does not establish an independently signed publisher identity. C1 real-agent comparisons remain NOT_EXECUTED and are not a release-performance claim.
