#!/usr/bin/env bash
# sadskill installer: multi-agent installation and companion script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_AGENT="auto"
TARGET_DIR="${PWD}"
TARGET_DIR_EXPLICIT="false"
NO_BACKUP="false"

show_help() {
  echo "Usage: ./install.sh [options]"
  echo ""
  echo "Options:"
  echo "  -a, --agent <name>     Target agent: auto, codex, claude, cursor, antigravity, all (default: auto)"
  echo "  -t, --target <dir>     Target project directory for Cursor installation (default: current working dir)"
  echo "      --no-backup        Overwrite existing installations without creating .bak timestamp archives"
  echo "  -h, --help             Show this help message and exit"
  echo ""
  echo "Primary Recommended Installation (Universal):"
  echo "  npx skills add sadafbabu/sadskill"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    -a|--agent)
      TARGET_AGENT="$2"
      shift 2
      ;;
    -t|--target)
      TARGET_DIR="$2"
      TARGET_DIR_EXPLICIT="true"
      shift 2
      ;;
    --no-backup)
      NO_BACKUP="true"
      shift
      ;;
    auto|codex|claude|cursor|antigravity|all)
      TARGET_AGENT="$1"
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      show_help
      ;;
  esac
done

echo "=== Installing sadskill (v0.2.0) ==="

backup_and_install_skill() {
  local dest="$1"
  if [[ -d "$dest" ]]; then
    if [[ "$NO_BACKUP" == "true" ]]; then
      rm -rf "$dest"
    else
      local backup="${dest}.bak.$(date +%Y%m%d%H%M%S)"
      echo "   [INFO] Preserving existing installation at ${backup}"
      mv "$dest" "$backup"
    fi
  fi
  mkdir -p "$(dirname "$dest")"
  cp -r "${SCRIPT_DIR}/skills/sadskill" "$dest"
}

install_codex() {
  local codex_dir="${HOME}/.codex"
  local skills_dir="${codex_dir}/skills"
  local prompts_dir="${codex_dir}/prompts"

  echo "-> Configuring for OpenAI Codex / ChatGPT Desktop..."
  mkdir -p "${skills_dir}" "${prompts_dir}"

  backup_and_install_skill "${skills_dir}/sadskill"

  for cmd in "${SCRIPT_DIR}/commands/codex/"*.md; do
    if [[ -f "$cmd" ]]; then
      local target_cmd="${prompts_dir}/$(basename "$cmd")"
      if [[ -f "$target_cmd" && "$NO_BACKUP" != "true" ]] && ! cmp -s "$cmd" "$target_cmd"; then
        mv "$target_cmd" "${target_cmd}.bak.$(date +%Y%m%d%H%M%S)"
      fi
      cp "$cmd" "$target_cmd"
    fi
  done
  echo "   [OK] Installed skill to ${skills_dir}/sadskill and prompts to ${prompts_dir}"
}

install_claude() {
  local claude_dir="${HOME}/.claude"
  local skills_dir="${claude_dir}/skills"
  local commands_dir="${claude_dir}/commands"

  echo "-> Configuring for Claude Code..."
  mkdir -p "${skills_dir}" "${commands_dir}"

  backup_and_install_skill "${skills_dir}/sadskill"

  for cmd in "${SCRIPT_DIR}/commands/claude/"*.md; do
    if [[ -f "$cmd" ]]; then
      local target_cmd="${commands_dir}/$(basename "$cmd")"
      if [[ -f "$target_cmd" && "$NO_BACKUP" != "true" ]] && ! cmp -s "$cmd" "$target_cmd"; then
        mv "$target_cmd" "${target_cmd}.bak.$(date +%Y%m%d%H%M%S)"
      fi
      cp "$cmd" "$target_cmd"
    fi
  done

  local hooks_dir="${claude_dir}/hooks"
  mkdir -p "${hooks_dir}"
  cp "${SCRIPT_DIR}/skills/sadskill/hooks/git-guardrail.sh" "${hooks_dir}/git-guardrail.sh"
  chmod +x "${hooks_dir}/git-guardrail.sh"

  echo "   [OK] Installed skill, commands, and guardrail hook to ${claude_dir}"
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
  mkdir -p "${rules_dir}" "${target_skill_dir}"

  # Deploy full skill into workspace .cursor/skills for relative link resolution
  cp -r "${SCRIPT_DIR}/skills/sadskill/"* "${target_skill_dir}/"

  cat << 'EOF' > "${rules_dir}/sadskill.mdc"
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

  echo "   [OK] Generated self-contained Cursor rule at ${rules_dir}/sadskill.mdc"
}

install_antigravity() {
  local agy_dir="${HOME}/.gemini/antigravity"
  local skills_dir="${agy_dir}/skills"

  echo "-> Configuring for Google Antigravity..."
  mkdir -p "${skills_dir}"

  backup_and_install_skill "${skills_dir}/sadskill"
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
  all)
    install_codex
    install_claude
    install_cursor
    install_antigravity
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
    if [[ -d "${TARGET_DIR}/.cursor" || -d "${HOME}/.cursor" ]]; then
      install_cursor
      installed_count=$((installed_count + 1))
    fi
    if [[ $installed_count -eq 0 ]]; then
      echo "No existing agent directory found. Installing to standard Codex, Claude, and Antigravity locations..."
      install_codex
      install_claude
      install_antigravity
    fi
    ;;
  *)
    echo "Unknown agent: $TARGET_AGENT (valid options: auto, codex, claude, cursor, antigravity, all)"
    exit 1
    ;;
esac

echo "=== sadskill installation complete! ==="
