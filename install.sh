#!/usr/bin/env bash
# sadskill installer: multi-agent installation and companion script (v0.3.0)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_AGENT="auto"
TARGET_DIR="${PWD}"
TARGET_DIR_EXPLICIT="false"
NO_BACKUP="false"
DRY_RUN="false"
MANIFEST_FILE="${HOME}/.sadskill/install-manifest.json"

show_help() {
  local exit_code="${1:-0}"
  cat << 'EOF'
Usage: ./install.sh [options]

Options:
  -a, --agent <name>     Target agent: auto, codex, claude, cursor, antigravity, gemini, all (default: auto)
  -t, --target <dir>     Target project directory for Cursor installation (default: current working dir)
      --no-backup        Overwrite existing installations without creating .bak timestamp archives
      --dry-run          Preview proposed installation changes without writing files
  -h, --help             Show this help message and exit

Primary Recommended Installation (Universal):
  npx skills add sadafbabu/sadskill
EOF
  exit "$exit_code"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help 0
      ;;
    -a|--agent)
      if [[ $# -lt 2 || "$2" =~ ^- ]]; then
        echo "Error: --agent requires a value." >&2
        show_help 2
      fi
      TARGET_AGENT="$2"
      shift 2
      ;;
    -t|--target)
      if [[ $# -lt 2 || "$2" =~ ^- ]]; then
        echo "Error: --target requires a value." >&2
        show_help 2
      fi
      TARGET_DIR="$2"
      TARGET_DIR_EXPLICIT="true"
      shift 2
      ;;
    --no-backup)
      NO_BACKUP="true"
      shift
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    auto|codex|claude|cursor|antigravity|gemini|all)
      TARGET_AGENT="$1"
      shift
      ;;
    *)
      echo "Error: Unknown argument: $1" >&2
      show_help 2
      ;;
  esac
done

echo "=== Installing sadskill (v0.3.0) ==="

if [[ "$DRY_RUN" == "true" ]]; then
  echo "   [DRY-RUN MODE] No filesystem modifications will be made."
fi

mkdir -p "${HOME}/.sadskill"

# Generate collision-safe backup paths with PID and timestamp
make_backup_path() {
  local target="$1"
  local ts
  ts="$(date +%Y%m%d%H%M%S)_$$"
  local bak="${target}.bak.${ts}"
  while [[ -e "$bak" ]]; do
    bak="${target}.bak.${ts}_${RANDOM}"
  done
  echo "$bak"
}

# Manifest tracker using robust python helper
record_manifest_entry() {
  local agent="$1"
  local dest="$2"
  local backup_path="${3:-}"

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "   [DRY-RUN MANIFEST] Would record: agent=${agent}, dest=${dest}, backup=${backup_path}"
    return 0
  fi

  if ! python3 "${SCRIPT_DIR}/scripts/manifest.py" record \
    --manifest "$MANIFEST_FILE" \
    --agent "$agent" \
    --destination "$dest" \
    --backup "$backup_path" \
    --target "$TARGET_DIR"; then
    echo "Error: Failed to record manifest entry for destination: $dest" >&2
    exit 1
  fi
}

backup_and_install_skill() {
  local agent="$1"
  local dest="$2"
  local backup_dest=""

  if [[ -d "$dest" ]]; then
    if [[ "$NO_BACKUP" == "true" ]]; then
      if [[ "$DRY_RUN" != "true" ]]; then
        rm -rf "$dest"
      else
        echo "   [DRY-RUN] Would remove existing: ${dest}"
      fi
    else
      local backup
      backup="$(make_backup_path "$dest")"
      echo "   [INFO] Preserving existing installation at ${backup}"
      if [[ "$DRY_RUN" != "true" ]]; then
        mv "$dest" "$backup"
      fi
      backup_dest="$backup"
    fi
  fi

  if [[ "$DRY_RUN" != "true" ]]; then
    mkdir -p "$(dirname "$dest")"
    cp -r "${SCRIPT_DIR}/skills/sadskill" "$dest"
  else
    echo "   [DRY-RUN] Would copy skill to ${dest}"
  fi
  record_manifest_entry "$agent" "$dest" "$backup_dest"
}

install_codex() {
  local codex_dir="${HOME}/.codex"
  local skills_dir="${codex_dir}/skills"
  local prompts_dir="${codex_dir}/prompts"

  echo "-> Configuring for OpenAI Codex / ChatGPT Desktop..."
  if [[ "$DRY_RUN" != "true" ]]; then
    mkdir -p "${skills_dir}" "${prompts_dir}"
  fi

  backup_and_install_skill "codex" "${skills_dir}/sadskill"

  for cmd in "${SCRIPT_DIR}/commands/codex/"*.md; do
    if [[ -f "$cmd" ]]; then
      local target_cmd="${prompts_dir}/$(basename "$cmd")"
      local cmd_backup=""
      if [[ -f "$target_cmd" && "$NO_BACKUP" != "true" ]] && ! cmp -s "$cmd" "$target_cmd"; then
        cmd_backup="$(make_backup_path "$target_cmd")"
        if [[ "$DRY_RUN" != "true" ]]; then
          mv "$target_cmd" "$cmd_backup"
        fi
      fi
      if [[ "$DRY_RUN" != "true" ]]; then
        cp "$cmd" "$target_cmd"
      else
        echo "   [DRY-RUN] Would install prompt to ${target_cmd}"
      fi
      record_manifest_entry "codex_prompt" "$target_cmd" "$cmd_backup"
    fi
  done
  echo "   [OK] Installed skill to ${skills_dir}/sadskill and prompts to ${prompts_dir}"
}

install_claude() {
  local claude_dir="${HOME}/.claude"
  local skills_dir="${claude_dir}/skills"
  local commands_dir="${claude_dir}/commands"
  local hooks_dir="${claude_dir}/hooks"

  echo "-> Configuring for Claude Code..."
  if [[ "$DRY_RUN" != "true" ]]; then
    mkdir -p "${skills_dir}" "${commands_dir}" "${hooks_dir}"
  fi

  backup_and_install_skill "claude" "${skills_dir}/sadskill"

  for cmd in "${SCRIPT_DIR}/commands/claude/"*.md; do
    if [[ -f "$cmd" ]]; then
      local target_cmd="${commands_dir}/$(basename "$cmd")"
      local cmd_backup=""
      if [[ -f "$target_cmd" && "$NO_BACKUP" != "true" ]] && ! cmp -s "$cmd" "$target_cmd"; then
        cmd_backup="$(make_backup_path "$target_cmd")"
        if [[ "$DRY_RUN" != "true" ]]; then
          mv "$target_cmd" "$cmd_backup"
        fi
      fi
      if [[ "$DRY_RUN" != "true" ]]; then
        cp "$cmd" "$target_cmd"
      else
        echo "   [DRY-RUN] Would install command to ${target_cmd}"
      fi
      record_manifest_entry "claude_command" "$target_cmd" "$cmd_backup"
    fi
  done

  # Safe guardrail hook installation with backup
  local guardrail_target="${hooks_dir}/git-guardrail.sh"
  local hook_backup=""
  if [[ -f "$guardrail_target" && "$NO_BACKUP" != "true" ]] && ! cmp -s "${SCRIPT_DIR}/skills/sadskill/hooks/git-guardrail.sh" "$guardrail_target"; then
    hook_backup="$(make_backup_path "$guardrail_target")"
    echo "   [INFO] Preserving existing Claude hook at ${hook_backup}"
    if [[ "$DRY_RUN" != "true" ]]; then
      mv "$guardrail_target" "$hook_backup"
    fi
  fi
  if [[ "$DRY_RUN" != "true" ]]; then
    cp "${SCRIPT_DIR}/skills/sadskill/hooks/git-guardrail.sh" "$guardrail_target"
    chmod +x "$guardrail_target"
  else
    echo "   [DRY-RUN] Would install guardrail hook to ${guardrail_target}"
  fi
  record_manifest_entry "claude_hook" "$guardrail_target" "$hook_backup"

  echo "   [OK] Installed skill, commands, and guardrail hook to ${claude_dir}"
  echo "   [HOOK STATUS: AVAILABLE] File placed at ${guardrail_target}."
  echo "   [NOTE] To activate hook in Claude Code, add PreToolUse configuration to ~/.claude/settings.json."
}

install_cursor() {
  local target_path="$TARGET_DIR"

  # Safety check: if target is sadskill source repo itself and not explicitly overridden
  if [[ "$target_path" == "$SCRIPT_DIR" && "$TARGET_DIR_EXPLICIT" != "true" ]]; then
    echo "-> Skipping Cursor workspace installation (inside sadskill source repo; specify --target <dir>)"
    return 0
  fi

  local rules_dir="${target_path}/.cursor/rules"
  local target_skill_dir="${target_path}/.cursor/skills/sadskill"
  echo "-> Configuring for Cursor in: ${target_path}..."

  local skill_backup=""
  if [[ -d "$target_skill_dir" && "$NO_BACKUP" != "true" ]]; then
    skill_backup="$(make_backup_path "$target_skill_dir")"
    echo "   [INFO] Preserving existing Cursor skill directory at ${skill_backup}"
    if [[ "$DRY_RUN" != "true" ]]; then
      mv "$target_skill_dir" "$skill_backup"
    fi
  elif [[ -d "$target_skill_dir" && "$NO_BACKUP" == "true" ]]; then
    if [[ "$DRY_RUN" != "true" ]]; then
      rm -rf "$target_skill_dir"
    fi
  fi

  if [[ "$DRY_RUN" != "true" ]]; then
    mkdir -p "${rules_dir}" "${target_skill_dir}"
    cp -r "${SCRIPT_DIR}/skills/sadskill/." "${target_skill_dir}/"
  else
    echo "   [DRY-RUN] Would create ${rules_dir} and ${target_skill_dir}"
  fi
  record_manifest_entry "cursor_skill" "$target_skill_dir" "$skill_backup"

  local rule_file="${rules_dir}/sadskill.mdc"
  local rule_backup=""
  if [[ -f "$rule_file" && "$NO_BACKUP" != "true" ]]; then
    rule_backup="$(make_backup_path "$rule_file")"
    if [[ "$DRY_RUN" != "true" ]]; then
      mv "$rule_file" "$rule_backup"
    fi
  fi

  if [[ "$DRY_RUN" != "true" ]]; then
    cat << 'EOF' > "${rule_file}"
---
description: "sadskill: Unified autonomous engineering workflow (plan, design, backend, sec, analyze)"
globs: "*"
alwaysApply: false
---

# sadskill: Unified Engineering Workflow

> *"One engineering workflow. Any coding agent. Turn AI-generated code into verified, maintainable software."*
> *"Don't just generate code. Engineer it, verify it, and remember why."*

## 🧭 Workflow Commands
- `/sad-plan`: Adaptive 2-tier planning.
  - **Tier 1 (Surgical)**: <= 2 files/bugfix/CSS. Single-turn, concise diff table, test assertion.
  - **Tier 2 (Architectural)**: Multi-file features/migrations. Pre-declared AST contracts, Mermaid graph, boundary failure analysis. Output to `.sad/plans/`.
- `/sad-design`: Craft floor UI/UX, Zero-Lift hover rule (card float `translateY` banned, `scale(0.97)` click compression; drawers/tooltips permitted), natural image aspect ratios, 20 UI polish tips. Record choices in `.sad/design-memory.md`.
- `/sad-backend`: Schema-first migrations (`up.sql`/`down.sql`), zero-trust Row Level Security, safe query performance (`EXPLAIN (BUFFERS)`).
- `/sad-sec`: Strictly read-only OWASP Top 10 web & API audit, secrets scanning, offline-resilient dependency check, 15-point launch legal compliance. Output to `.sad/reports/security-<date>-<time>.md`.
- `/sad-analyze`: Scoped (`/sad-analyze <path>`) or full repo scan, John Ousterhout deep module analysis, coupling, dead code. Output to `.sad/reports/analysis-<date>-<time>.md`.

## 🛡️ Global Protocols
1. **Project Memory (`.sad/`)**: Inspect `.sad/` at project root before changes. Update `.sad/history.md`, `.sad/decisions.md`, and `.sad/design-memory.md`.
2. **Verification Evidence**: Never claim completion without executing test or build commands with exit code 0. Record structured log in `.sad/evidence/` and output a 3-line terminal proof in chat.
3. **Safety Guardrails**: Never execute destructive operations (`git reset --hard`, `git push -f`, `git clean -fd`, `DROP TABLE`) without explicit user authorization.
4. **Human Voice**: Lead with answers, strip AI buzzwords ("delve", "seamless"), maintain technical density.
EOF
  else
    echo "   [DRY-RUN] Would write Cursor rule to ${rule_file}"
  fi

  record_manifest_entry "cursor_rule" "$rule_file" "$rule_backup"
  echo "   [OK] Generated self-contained Cursor rule at ${rule_file}"
}

install_antigravity() {
  local agy_dir="${HOME}/.gemini/antigravity"
  local skills_dir="${agy_dir}/skills"

  echo "-> Configuring for Google Antigravity..."
  if [[ "$DRY_RUN" != "true" ]]; then
    mkdir -p "${skills_dir}"
  fi

  backup_and_install_skill "antigravity" "${skills_dir}/sadskill"
  echo "   [OK] Installed skill to ${skills_dir}/sadskill"
}

install_gemini() {
  local gemini_dir="${HOME}/.gemini"
  local skills_dir="${gemini_dir}/skills"

  echo "-> Configuring for Gemini CLI..."
  if [[ "$DRY_RUN" != "true" ]]; then
    mkdir -p "${skills_dir}"
  fi

  backup_and_install_skill "gemini" "${skills_dir}/sadskill"
  echo "   [OK] Installed skill to ${skills_dir}/sadskill"
}

# Ensure workstation profile template is discoverable
mkdir -p "${HOME}/.sadskill"
if [[ ! -f "${HOME}/.sadskill/profile.md" && -f "${SCRIPT_DIR}/skills/sadskill/templates/profile.template.md" ]]; then
  echo "-> Tip: You can customize your local workstation profile by editing ~/.sadskill/profile.md"
fi

case "$TARGET_AGENT" in
  codex)
    install_codex
    ;;
  claude)
    install_claude
    ;;
  cursor)
    install_cursor
    ;;
  antigravity)
    install_antigravity
    ;;
  gemini)
    install_gemini
    ;;
  all)
    install_codex
    install_claude
    install_cursor
    install_antigravity
    install_gemini
    ;;
  auto)
    installed_count=0
    if [[ -d "${HOME}/.codex" ]]; then
      install_codex
      installed_count=$((installed_count + 1))
    fi
    if [[ -d "${HOME}/.claude" ]]; then
      install_claude
      installed_count=$((installed_count + 1))
    fi
    if [[ -d "${HOME}/.gemini/antigravity" ]]; then
      install_antigravity
      installed_count=$((installed_count + 1))
    fi
    if [[ -d "${HOME}/.gemini/skills" || (-d "${HOME}/.gemini" && ! -d "${HOME}/.gemini/antigravity") ]]; then
      install_gemini
      installed_count=$((installed_count + 1))
    fi
    if [[ -d "${TARGET_DIR}/.cursor" || -d "${HOME}/.cursor" ]]; then
      install_cursor
      installed_count=$((installed_count + 1))
    fi
    if [[ $installed_count -eq 0 ]]; then
      echo "No existing agent directory found. Installing to standard Codex, Claude, Gemini CLI, and Antigravity locations..."
      install_codex
      install_claude
      install_gemini
      install_antigravity
    fi
    ;;
  *)
    echo "Error: Unknown agent: $TARGET_AGENT (valid options: auto, codex, claude, cursor, antigravity, gemini, all)" >&2
    exit 2
    ;;
esac

echo "=== sadskill installation complete! ==="
