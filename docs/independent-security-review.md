# Independent security review and protected merge checklist

An automated CodeQL analysis is not a qualifying independent GitHub approval.
Only a reviewer who is not the PR author/last pusher can satisfy the current
protected-main requirement. Do not weaken GitHub rulesets to call a release ready.

## Required order

1. Review and merge PR #4 into protected main after approval and exact-head checks.
2. Retarget PR #9 onto main, resolve conflicts, and rerun all required CI.
3. Obtain fresh independent approval for PR #9 at its final head.
4. Merge only after GitHub's protected ruleset is satisfied and verify main.

## Security review topics

- Installer symlink and parent traversal checks, backups and user-file preservation
- Force restore, clean backups, uninstall purge and failed/partial rollback
- Manifest destination ownership, Cursor workspace path containment and hashes
- Git guardrail wrapper/subshell/alias bypasses and false positives
- SQL guard edge cases and native PostgreSQL RLS negative control
- Evidence retest path/recipe restrictions and honest benchmark metrics
- Vendored reference integrity, attribution and upstream license checks
- Native macOS smoke, Windows support limits and exact-head CI
- CodeQL findings (triage alerts: passing upload alone is not a clean security verdict)

## Reviewer availability blocker

On 2026-10-29, the repository collaborator API returned only sadafbabu,
who authored both PRs. Invite a trusted additional GitHub user with review
permissions and have that person submit an actual approval on each PR.
