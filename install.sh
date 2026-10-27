#!/usr/bin/env bash
# sadskill installer: multi-agent installation script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_AGENT="${1:-auto}"

if [[ "$TARGET_AGENT" == "-h" || "$TARGET_AGENT" == "--help" ]]; then
  echo "Usage: ./install.sh [--agent <agent>]"
  echo ""
  echo "Agents:"
  echo "  auto         Detect installed agents and configure them (default)"
  echo "  codex        Configure for OpenAI Codex / ChatGPT Desktop (~/.codex)"
  echo "  claude       Configure for Claude Code (~/.claude)"
  echo "  cursor       Configure for Cursor (.cursor/rules)"
  echo "  antigravity  Configure for Google Antigravity (~/.gemini/antigravity/skills)"
  echo "  all          Configure for all supported agents"
  exit 0
fi

if [[ "$TARGET_AGENT" == "--agent" && -n "${2:-}" ]]; then
  TARGET_AGENT="$2"
fi

echo "=== Installing sadskill (v0.1.0) ==="

install_codex() {
  local codex_dir="${HOME}/.codex"
  local skills_dir="${codex_dir}/skills"
  local prompts_dir="${codex_dir}/prompts"

  echo "-> Configuring for Codex / ChatGPT Desktop..."
  mkdir -p "${skills_dir}" "${prompts_dir}"

  rm -rf "${skills_dir}/sadskill"
  cp -r "${SCRIPT_DIR}/skills/sadskill" "${skills_dir}/sadskill"

  for cmd in "${SCRIPT_DIR}/commands/codex/"*.md; do
    if [[ -f "$cmd" ]]; then
      cp "$cmd" "${prompts_dir}/$(basename "$cmd")"
    fi
  done
  echo "   [OK] Installed to ${skills_dir}/sadskill and prompts to ${prompts_dir}"
}

install_claude() {
  local claude_dir="${HOME}/.claude"
  local skills_dir="${claude_dir}/skills"
  local commands_dir="${claude_dir}/commands"

  echo "-> Configuring for Claude Code..."
  mkdir -p "${skills_dir}" "${commands_dir}"

  rm -rf "${skills_dir}/sadskill"
  cp -r "${SCRIPT_DIR}/skills/sadskill" "${skills_dir}/sadskill"

  for cmd in "${SCRIPT_DIR}/commands/claude/"*.md; do
    if [[ -f "$cmd" ]]; then
      cp "$cmd" "${commands_dir}/$(basename "$cmd")"
    fi
  done
  echo "   [OK] Installed to ${skills_dir}/sadskill and commands to ${commands_dir}"
}

install_cursor() {
  echo "-> Configuring for Cursor..."
  local cursor_rules_dir="${PWD}/.cursor/rules"
  mkdir -p "${cursor_rules_dir}"
  cp "${SCRIPT_DIR}/skills/sadskill/SKILL.md" "${cursor_rules_dir}/sadskill.mdc" 2>/dev/null || true
  echo "   [OK] Generated Cursor workspace rule at .cursor/rules/sadskill.mdc"
}

install_antigravity() {
  local agy_dir="${HOME}/.gemini/antigravity"
  local skills_dir="${agy_dir}/skills"

  echo "-> Configuring for Google Antigravity..."
  mkdir -p "${skills_dir}"

  rm -rf "${skills_dir}/sadskill"
  cp -r "${SCRIPT_DIR}/skills/sadskill" "${skills_dir}/sadskill"
  echo "   [OK] Installed to ${skills_dir}/sadskill"
}

# Ensure local profile directory exists
mkdir -p "${HOME}/.sadskill"
if [[ ! -f "${HOME}/.sadskill/profile.md" && -f "${SCRIPT_DIR}/skills/sadskill/templates/profile.template.md" ]]; then
  echo "-> Tip: You can customize your local profile by editing ~/.sadskill/profile.md"
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
    if [[ $installed_count -eq 0 ]]; then
      echo "No existing agent directory found. Installing to standard Codex and Claude locations..."
      install_codex
      install_claude
    fi
    ;;
  *)
    echo "Unknown agent: $TARGET_AGENT (valid options: auto, codex, claude, cursor, antigravity, all)"
    exit 1
    ;;
esac

echo "=== sadskill installation complete! ==="
