# Assigning work to two contributors

Use issues for assignments and pull requests for reviewable delivery. Assign real people only after the owner supplies and verifies their GitHub identities. This document does not invite anyone or change repository access.

## Responsibilities

| Person | Initial work | Delivery |
|---|---|---|
| Contributor A | Skill routing, workflow clarity, command adapters, compatibility documentation | One scoped issue and PR at a time, with installed-skill checks where relevant |
| Contributor B | Regression fixtures, installer/updater edge cases, evidence documentation | A reproduced failure, focused fix or fixture, and exact verification results |
| Owner/maintainer | Priorities, cross-cutting architecture, security-sensitive integration, access and releases | Final scope decisions, review coordination and protected integration |

Contributors can review each other's changes, but must not approve their own PRs or claim that an internal AI review is a GitHub approval. Require owner review for sensitive changes as a working agreement. If it must be enforced by path, configure a tested CODEOWNERS/review policy after actual reviewer identities exist; do not invent accounts or claim the agreement is automatically enforced.

## Access setup

- External contributors can submit fork PRs without becoming organization members. For trusted branch-based collaboration, start with repository **Write** access; keep organization ownership, repository Admin and rule bypass with the owner.
- Retain protected `main`: independent approval, stale approval dismissal, latest-push approval, required current CI, resolved conversations, and no direct/force pushes. Do not temporarily relax these rules to merge an owner-authored PR.
- Use auto-merge only after review of the intended change. It waits for GitHub's required gates. Recheck the latest head and integration state after rebasing or merging a prerequisite.
- Public source cannot be made download-proof. Keep live credentials and production/private systems separately controlled. Untrusted PR jobs must not receive production secrets, a privileged repository token, Docker host credentials or personal AI authentication files. Docker-based fixture CI runs in its disposable CI runner; never mount the host socket into contributor-controlled containers.
- Review branch protection and environment permissions when a contributor joins or leaves. Remove access that is no longer needed; public copies of source cannot be revoked.

## A task that is ready to assign

State the concrete user problem, base branch, paths in scope, paths out of scope, expected behavior, failure/edge examples and completion evidence. Note whether external services or new dependencies are authorized. Use a draft PR for incomplete work and label unrun checks clearly.

Example: “From `main`, fix installer handling of a target path containing spaces. Scope: installer and its path regressions. Preserve unrelated local changes. Demonstrate the existing failure in a temporary home, add the fix, run path tests and the full installer regression suite, then submit a PR with the exact head and results. No hosted services or release changes.”

## Integration order

Review each small PR against its declared base. For stacked PRs, merge the prerequisite first and retarget/rebase dependents as needed; rerun checks on each resulting head. For a combined integration PR, close superseded component PRs after verified integration rather than merging duplicates. Keep real review findings visible and close an assigned issue only when its acceptance criteria have been met.
