# sadskill Threat Model & Security Boundaries (v0.3.0)

This document establishes the trust boundaries, threat vectors, privilege models, and defense-in-depth mitigations for the `sadskill` engineering workflow across host coding agents.

---

## 1. Trust Boundaries

```text
[External Internet / Web Docs]
             │ (Untrusted data, prompt injection risks)
             ▼
[Agent Runtime & LLM Context] ◄── [User Prompt / Live Conversation]
             │                     (Authorized intent, explicit constraints)
             ▼
[sadskill Protocol Layer]
 (TaskContext, Coverage, Advice, Autonomy, Safety)
             │
      ┌──────┴──────────────────────────────┐
      ▼                                     ▼
[Local Filesystem / Repository]    [Subprocess Execution Engine]
 - Manifest-driven ownership        - Trusted recipe registry
 - Strict path containment          - Process group isolation
 - Atomic file writes               - Environment sanitization
 - Private user profiles isolated   - Descendant process termination
```

### Boundary Definitions
1. **Host Agent vs Skill Runtime**: `sadskill` operates as an instruction and protocol suite on top of host agents (Claude Code, OpenAI Codex, Cursor, Google Antigravity, Gemini CLI). Host safety boundaries and permissions remain authoritative over skill prompt instructions.
2. **Untrusted Web Content vs Command Authority**: External documentation or web pages retrieved during authorized research are treated strictly as data. Web content cannot trigger autonomous tool calls, execute commands, or extract environment credentials.
3. **Repository Workspace vs User Home**: `sadskill` artifacts installed in agent configurations (`~/.codex`, `~/.claude`, `~/.gemini`) are tracked in `~/.sadskill/install-manifest.json` with SHA-256 digests. Files outside these canonical roots cannot be modified or removed by install/uninstall operations.
4. **Verification Evidence vs Proof**: Agent-generated logs in `.sad/evidence/` represent claims (`REPORTED` / `SCHEMA_VALID`). Freshness binds the project identity, exact commit, and a digest of tracked/untracked checkout content plus relevant ignored test sources, configs, and fixtures outside `.sad/evidence/`, including initialized submodules recursively. Gitlinks in `HEAD` and the index must match `.gitmodules`; a mismatch, unmerged index, uninitialized or unsafe submodule makes the snapshot unavailable. Standard generated dependency/build directories are excluded unless nested below an explicit test or fixture directory. Only independent execution through fixed trusted recipes achieves `RETESTED` status.

---

## 2. Threat Vectors & Mitigations

### T-01: Destructive Git and Database Execution
- **Risk**: Agents executing `git reset --hard`, `git push --force`, `git clean -fd`, or SQL `DROP TABLE` destroying uncommitted code or production data.
- **Mitigation**: Dual-layer guardrail (`scripts/git-guardrail.sh` and PreToolUse hooks) intercepts destructive commands and exits with code 2. Real Git `pre-push` inspection verifies non-fast-forward updates and remote branch deletions.

### T-02: Data Loss During Installation / Restoration
- **Risk**: Uninstallation or reinstallation overwriting pre-existing user configurations or deleting restored backup files.
- **Mitigation**: Manifest ledger tracks prior file state, content hashes, and backup locations. Uninstaller restores original files atomically and preserves them from removal. Clean-backups targets only sadskill-owned timestamp archives.

### T-03: Arbitrary Command Execution via Evidence Retest
- **Risk**: Malicious evidence logs executing arbitrary code via general-purpose interpreters (`python -c`, `bash -c`, `node -e`).
- **Mitigation**: Verification engine restricts retests to a trusted recipe registry and rejects all custom-script bypasses. Inline evaluation flags and shell chaining tokens are rejected. Because registered tests execute repository code as the current user, use retests only in a checkout whose source you trust; the sanitized environment and process-group timeout are not an OS sandbox.

### T-04: Credential and Secret Exposure
- **Risk**: Accidental commitment of API keys, tokens, or private conversational details into `.sad/` version control.
- **Mitigation**: Scoped storage separation. Private user workstation profiles live outside git (`~/.sadskill/profile.md`). Project memory in `.sad/` is restricted to non-sensitive architecture decisions, coverage ledgers, and anonymized verification proofs.

### T-05: Path Traversal and Symlink Escapes
- **Risk**: Malicious evidence records or manifests referencing paths outside the repository (e.g. `../../etc/passwd`).
- **Mitigation**: Strict canonical path containment checks reject traversal tokens (`..`), absolute paths outside roots, and symlinks resolving outside the project root.

### T-06: Update Release and Artifact Trust
- **Scope reviewed**: updater branch head `177c33dbaacb9e45306e01db2dd7bc93f4a1d8e3` (PR #2; not yet merged at this audit).
- **Network trust**: update metadata is fetched from canonical GitHub release/API locations. Production redirects are restricted to approved HTTPS content hosts, cross-origin authorization is removed, and artifact downloads do not receive the GitHub API token. Loopback redirects are only accepted by the local test stub.
- **Release identity**: API, HTML, tag, tarball, and asset identity/host are cross-checked. A repository name appearing only in an arbitrary response body is not sufficient to establish provenance.
- **Integrity limits**: a matched GitHub-provided digest/checksum can establish byte equality with that source. `TRANSPORT_ONLY` and `SOURCE_CHECKSUM_MATCHED` are distinct labels. Neither establishes a publisher signature or independent origin authenticity. No signed release provenance is claimed.
- **Archive abuse**: compressed size, expanded size, expansion ratio, member count, nesting depth, duplicate/colliding names, symlinks, and special files are bounded or rejected before installation. `plan` validates archive structure without installing files.
- **Execution**: downloaded source is not executed by the updater. It is installed as skill content; later host execution remains subject to the host's own behavior and trust model.

### T-07: Update Ownership, Concurrent Mutation, and Recovery
- **Ownership conflicts**: malformed external manager locks fail closed. `--adopt` does not override an ownership refusal. Managed-file changes are handled as conflicts and are preserved for review.
- **Concurrency**: apply and rollback hold the shared manifest lock for the transaction. This coordinates Sadskill writers; it cannot prevent an unrelated process from directly changing the same filesystem paths.
- **Recovery journal**: journal v2 records exact destination-to-backup and metadata paths. Rollback validates paths and backup content, preserves conflicting user edits before forced replacement, refuses ambiguous legacy journals, and is idempotent after completion.
- **Crash boundary**: interrupted replacement is recoverable from the durable journal and exact backups. Backups are verified before use. A damaged/missing backup causes refusal rather than guessed basename restoration.
- **Residual filesystem risk**: path checks and the shared lock reduce races, but an unrelated process with write access can still race filesystem operations outside the updater lock. The updater does not claim kernel-enforced isolation from other same-user processes.

### T-08: Evidence and Benchmark Claims
- Agent-supplied `ci_attestation.verified: true` is untrusted metadata and must remain `CI_CLAIMED` until an external verifier checks the actual GitHub repository, run, workflow/job conclusion, and head SHA.
- The deterministic runner's catalog check is not an agent run. Track C1 remains `NOT_EXECUTED` (0 runs). The SQLite authorizer fixture is a simulation, not PostgreSQL RLS.
