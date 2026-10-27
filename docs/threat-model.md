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
4. **Verification Evidence vs Proof**: Agent-generated logs in `.sad/evidence/` represent claims (`REPORTED` / `SCHEMA_VALID`). Only independent execution through trusted recipe registries achieves `RETESTED` status.

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
- **Mitigation**: Verification engine restricts retests to a trusted recipe registry (`pytest`, standard test runners) within project boundaries. Inline evaluation flags and shell chaining tokens are strictly rejected.

### T-04: Credential and Secret Exposure
- **Risk**: Accidental commitment of API keys, tokens, or private conversational details into `.sad/` version control.
- **Mitigation**: Scoped storage separation. Private user workstation profiles live outside git (`~/.sadskill/profile.md`). Project memory in `.sad/` is restricted to non-sensitive architecture decisions, coverage ledgers, and anonymized verification proofs.

### T-05: Path Traversal and Symlink Escapes
- **Risk**: Malicious evidence records or manifests referencing paths outside the repository (e.g. `../../etc/passwd`).
- **Mitigation**: Strict canonical path containment checks reject traversal tokens (`..`), absolute paths outside roots, and symlinks resolving outside the project root.
