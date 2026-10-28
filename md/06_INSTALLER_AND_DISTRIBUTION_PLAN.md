# Multi-Agent Distribution, Installer & Registry Plan

This document details the multi-channel distribution strategy to position Sadskill as the default engineering confidence skill across the global AI coding agent ecosystem.

---

## 🌐 Distribution Channels

```
                           sadskill
                              │
     ┌────────────────┬───────┴────────┬────────────────┐
     ▼                ▼                ▼                ▼
skills.sh          Cursor         OpenAI Agent        PyPI &
Registry         Marketplace         Plugin         One-Liner CLI
```

### 1. `skills.sh` Registry Listing
- Canonical install command:
  ```bash
  npx skills add Prarohi/sadskill
  ```
- Validation criteria:
  - Exactly 1 skill discovered (`skills/sadskill/SKILL.md`).
  - No extraneous root `SKILL.md` files.
  - Verified clean execution under Antigravity, Claude Code, and Codex.

### 2. Cursor Marketplace & MDC Rule
- Packaged at `.cursor/rules/sadskill.mdc`.
- Root `plugin.json` compatible with Cursor's Agent Plugin standard.
- Automatic context rule loading when developers open a project with `.sad/`.

### 3. OpenAI Agent Plugin
- Root `plugin.json` conforming to the OpenAPI/ChatGPT Agent standard.
- Allows team enterprise deployments where agents auto-discover Sadskill capabilities from the repo root.

### 4. Signed One-Liner Web Installer
Provide a curl-pipe-bash installer with cryptographic checksum pre-verification:
```bash
curl -fsSL https://raw.githubusercontent.com/Prarohi/sadskill/main/install.sh | bash
```
Features:
- Detects installed agent hosts (Claude Code, OpenAI Codex, Cursor, Gemini CLI, Antigravity).
- Installs atomic backups of pre-existing configs.
- Writes verifiable installation manifest in `~/.sadskill/manifest.json`.

---

## 📦 Automated Release Pipeline

1. **Tag Push**: Triggered on `git tag v*`.
2. **Reproducible Tarball Creation**: Generates `sadskill-<version>.tar.gz` and `.zip`.
3. **SHA-256 Checksums**: Emits `SHA256SUMS.txt`.
4. **Cosign & GitHub Attestation**: Signs the checksum file and binary assets.
5. **Draft Release Publication**: Publishes release notes to GitHub Releases.
