# Independent security review and protected release checklist

This is the current policy guidance (verified on 2026-10-30), not a
statement that every security finding is resolved.

## Current main ruleset and review

Integration PR #4 and candidate PR #9 were merged into protected main
on 2026-10-30 (Bangladesh local time). The active branch ruleset requires
successful **Verify sadskill (Node 20)**, **Verify sadskill (Node 22)**
and **Native PostgreSQL RLS** checks, forbids force-push/deletion and
requires resolution of GitHub review threads.

The current GitHub required-approvals count is **zero**. That does not
make a high-risk change independently reviewed: require a separate eligible
human reviewer by project release policy where possible. A CodeQL run
is not a human approval or proof of absence of vulnerabilities.

## Current review order

1. Review each new change against the exact latest protected main.
2. Verify installer, updater and memory safety boundary and any changed
   file ownership, restore, concurrency, sandbox or trust assumptions.
3. Request eligible independent security review for high-risk changes.
4. Ensure current-head CI and CodeQL both pass, resolve threads and preserve
   the required branch ruleset. Do not use an old-head pass.
5. For a release, verify the reviewed tag and exact-head checks through
   the [draft release workflow](../.github/workflows/release.yml) and inspect
   [release process](release-process.md) before manual publication.

## Security review focus

- Installer path traversal, ownership, symlinks, hardlinks, backups and rollback
- Memory root and .sad filesystem boundaries; live host lifecycle limits
- Updater archive identity, redirects, checksum provenance and recovery
- Command/SQL guardrail bypasses, false positives and sandbox limitations
- Evidence verifier, retest allowlist and non-empirical benchmark claims
- CodeQL alerts and repository dependency advisories (run success alone
  does not certify a clean security report)
- macOS/Windows smoke evidence and unsupported platform paths

## Historical reviewer status

An older note from 2026-10-29 said a second collaborator was needed to
satisfy a one-approval ruleset. GitHub's active ruleset changed later to
require zero approvals. Preserve independent release review as an
engineering policy, but do not represent the old API state as current.
