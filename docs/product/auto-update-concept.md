# Sadskill Auto-Update & Version Lifecycle Specification

> Conceptual Architecture for Safe Version Discovery, Opt-in Upgrades, Pinning, and Rollback

---

## 1. Problem Statement & Design Objectives

Agent skills exist at the boundary between developer workflows, agent execution environments, and git repositories. Unlike traditional software dependencies (e.g. npm packages or Python wheels) that run in isolated runtime containers, prompt-based skills directly shape how autonomous AI agents interpret intent, modify files, and enforce safety boundaries.

Uncontrolled, silent background updates introduce severe risks:
1. **Behavioral Drift Mid-Sprint**: An unexpected prompt or protocol update can alter planning depth or change how an agent structures code edits in the middle of a complex project.
2. **Hook Incompatibilities**: Silent changes to shell safety hooks (`scripts/git-guardrail.sh`) could block legitimate developer operations or break environment integrations.
3. **Ecosystem Desynchronization**: A split where `npx skills` updates `skills/sadskill/` while local companion slash commands (`~/.claude/commands/`, `~/.codex/prompts/`) remain stale.

### Core Objectives:
- **Zero Silent Mutations**: Never apply updates without explicit developer opt-in.
- **Clear Separation of Ownership**: Explicitly define what `npx skills` manages versus what `install.sh` / `scripts/doctor.py` manages.
- **Predictable Version Pinning & Instant Rollback**: Enable locking to a specific release tag and rolling back instantly if regressions appear.

---

## 2. Ownership Boundaries: `skills.sh` vs Companion Installer

To avoid conflicting update mechanisms, `sadskill` adheres to strict division of responsibility:

| Component | Managed By | Update Mechanism | Safety Constraints |
|---|---|---|---|
| **Skill Package** (`skills/sadskill/`) | `skills.sh` (`npx skills`) | `npx skills update` | Respects npm registry semver; strictly sandboxed to skill directory. |
| **Companion Slash Commands** (`~/.claude/commands/`, `~/.codex/prompts/`) | Companion Installer (`install.sh`) | `install.sh --update` | Creates timestamped backup in `~/.sadskill/backups/` before any file replacement. Refuses overwrite if user has customized prompt. |
| **Host Hooks** (`scripts/git-guardrail.sh`, Claude hooks) | Companion Installer (`install.sh`, `scripts/doctor.py`) | `python3 scripts/doctor.py --enable-hooks` | Verified byte-for-byte; retains pre-existing hooks and supports `--restore-previous`. |
| **Project Memory** (`.sad/`) | Project Git Repository | Developer git commits | Never modified or wiped by skill update scripts. Backward compatible with earlier schema versions. |

---

## 3. Two-Phase Upgrade Workflow: Check vs. Apply

Updates are decoupled into two distinct phases:

### Phase 1: Non-Invasive Update Check
`scripts/doctor.py` or `scripts/check-update.py` performs a read-only query against GitHub Releases:
- Queries the latest release tag (e.g., `v0.3.1`) via the GitHub API (with 2-second timeout and offline graceful fallback).
- Compares against local version defined in `skills/sadskill/SKILL.md` (e.g., `0.3.0`).
- If an update is available, displays a non-blocking informational notice:
  ```text
  [UPDATE AVAILABLE] sadskill v0.3.1 is available (current: v0.3.0).
  Release Highlights: Improved SQLite authorizer simulation & enhanced AST extraction.
  To upgrade, run: ./install.sh --update (or npx skills update sadafbabu/sadskill)
  ```
- **Zero Network Delay in Hot Paths**: Update checks are strictly throttled (cached for 24 hours in `~/.sadskill/cache/update_check.json`) and never block agent prompt execution.

### Phase 2: Explicit Developer Opt-In Apply
The user initiates the update explicitly:
```bash
# For companion slash commands and hooks:
./install.sh --update

# For skills.sh ecosystem:
npx skills update sadafbabu/sadskill
```

During apply:
1. **Pre-flight Integrity Check**: Verifies that existing files match expected hashes.
2. **Conflict Refusal**: If the user has modified their installed slash command or hook, the updater halts with `[CONFLICT-PRESERVED]` and requires `--force` to overwrite.
3. **Automated Backup**: Copies previous version to `~/.sadskill/backups/<timestamp>-v<old_version>/`.
4. **Post-Update Doctor Diagnostic**: Automatically runs `python3 scripts/doctor.py` to confirm that all registered commands, hooks, and discovery paths are functional.

---

## 4. Version Pinning & Reproducible Environments

For enterprise CI pipelines, teams, and regulated repositories, workflow repeatability is paramount. `sadskill` supports explicit version pinning:

### 1. Git Submodule or Vendoring
Pin to a specific git commit or release tag:
```bash
git submodule add -b v0.3.0 https://github.com/sadafbabu/sadskill.git vendor/sadskill
```

### 2. NPM / Package Pinning via `package.json`
```json
{
  "devDependencies": {
    "sadskill": "github:sadafbabu/sadskill#v0.3.0"
  }
}
```

### 3. CI Drift Prevention
In continuous integration (`.github/workflows/ci.yml`), run `scripts/verify.py` and `scripts/verify-evidence.py` against the pinned repository SHA. If any protocol or hook has drifted from the certified manifest, CI fails immediately before merging.

---

## 5. Instant Rollback Protocol

If an updated version introduces unexpected behavior, rollback is single-command and deterministic:

```bash
# Rollback companion installation to the immediate previous backup:
./uninstall.sh --restore-previous

# Or force-restore from a specific snapshot:
./install.sh --restore ~/.sadskill/backups/20261028-v0.3.0/
```

- Restores original pre-update files byte-for-byte.
- Preserves `.sad/` project memory, historical ADRs, and verification evidence intact.
- Re-verifies environment health via `scripts/doctor.py`.
