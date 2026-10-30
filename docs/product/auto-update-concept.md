# Sadskill Auto-Update & Version Lifecycle Proposal

> Design proposal for opt-in update discovery, planning, applying, version pinning, and recovery.

## Status and scope

This document describes the updater interface and safety contract. It does not by itself provide an updater. Only run a command below when `scripts/sadskill-update.py` exists in the checkout you are using; `install.sh --update`, `install.sh --restore`, `scripts/check-update.py`, and an assumed `skills update` subcommand are not Sadskill interfaces.

Updates must be explicit. A check or plan must not modify installed files. An updater must identify the owning installer, verify the release and archive, preserve each exact destination before replacement, and leave enough journal data to recover an interrupted update. It must refuse ambiguous ownership or untrusted artifacts.

## Ownership boundaries

| Surface | Owner | Safe boundary |
|---|---|---|
| Skill package and vendored sources | Sadskill repository and the installation method selected by the user | Keep version selection explicit. Do not assume a third-party package manager has a particular update command or semantics. |
| Companion commands, prompts, and hooks | Sadskill installer manifest | Update only destinations recorded as Sadskill-owned; refuse user-modified files unless the exact current contents are backed up first. |
| Claude Code hook registration | `scripts/doctor.py` | `--enable-hooks` registers the hook; `--disable-hooks` removes only Sadskill-owned entries. A local script simulation does not prove the host loaded or invoked it. |
| Project memory (`.sad/`) | Project Git repository | Never modify it as a side effect of updating installed skill files. |

## Proposed updater workflow

The following commands are available only in a checkout that contains `scripts/sadskill-update.py`:

```bash
python3 scripts/sadskill-update.py check
python3 scripts/sadskill-update.py plan --json
python3 scripts/sadskill-update.py apply --json
python3 scripts/sadskill-update.py rollback --json
```

`check` reports release availability and whether a source checksum is present; it does not download or validate the archive. `plan` describes exact source files and destinations and performs no filesystem writes. `apply` is an explicit mutation and verifies the archive before checking destination ownership, backing up exact paths, writing a recovery journal, or changing installed files. Missing, malformed, or mismatched checksums fail closed. For a legacy release without `SHA256SUMS`, the user must pass an independently sourced archive digest with `--expected-sha256`; the updater verifies fetched bytes against it and records `EXTERNAL_CHECKSUM_MATCHED`. A checksum match is not an authenticated publisher signature.

On a user modification, the updater refuses by default. A force option is acceptable only when it preserves the exact current content before replacement and reports the conflict. A malformed release identity, checksum, archive, ownership record, or recovery journal must fail closed.

## Version selection and CI

For repeatable environments, pin the repository to a reviewed commit or release tag using the installation method actually present in the project. Do not claim that CI checks evidence or a certified manifest unless the workflow at `.github/workflows/ci.yml` runs those checks. Workflow runs must be associated with the exact commit SHA under review; a successful run from an earlier head does not verify a later change. [GitHub documents that workflow runs use the workflow and commit associated with the triggering event.](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows)

## Recovery

Use the updater's `rollback` command only when its journal contains exact destination-to-backup mappings and each backup verifies. Recovery must restore the original manifest and install state from their saved copies. Before a forced rollback overwrites post-update edits, it must save and verify those current edits in a conflict backup. It must refuse older or ambiguous journals instead of guessing from filenames.

The updater does not run downloaded code. Host health checks are separate from the update transaction, and their reports must distinguish local tests from host-confirmed activation. For Claude Code hook lifecycle and configuration, follow the [official hooks reference](https://code.claude.com/docs/en/hooks).
