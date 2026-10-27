#!/usr/bin/env bash
# sadskill uninstaller: clean removal from agent environments
set -euo pipefail

TARGET_DIR="${PWD}"
PURGE="false"
CLEAN_BACKUPS="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--target)
      TARGET_DIR="$2"
      shift 2
      ;;
    --purge)
      PURGE="true"
      shift
      ;;
    --clean-backups)
      CLEAN_BACKUPS="true"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

echo "=== Uninstalling sadskill ==="

# Codex removal
if [[ -d "${HOME}/.codex/skills/sadskill" ]]; then
  echo "-> Removing from OpenAI Codex / ChatGPT Desktop..."
  rm -rf "${HOME}/.codex/skills/sadskill"
  rm -f "${HOME}/.codex/prompts/sad-plan.md" \
        "${HOME}/.codex/prompts/sad-design.md" \
        "${HOME}/.codex/prompts/sad-backend.md" \
        "${HOME}/.codex/prompts/sad-sec.md" \
        "${HOME}/.codex/prompts/sad-analyze.md"
  if [[ "$CLEAN_BACKUPS" == "true" ]]; then
    rm -rf "${HOME}/.codex/skills/sadskill.bak."*
  fi
  echo "   [OK] Removed from Codex"
fi

# Claude removal
if [[ -d "${HOME}/.claude/skills/sadskill" ]]; then
  echo "-> Removing from Claude Code..."
  rm -rf "${HOME}/.claude/skills/sadskill"
  rm -f "${HOME}/.claude/commands/sad-plan.md" \
        "${HOME}/.claude/commands/sad-design.md" \
        "${HOME}/.claude/commands/sad-backend.md" \
        "${HOME}/.claude/commands/sad-sec.md" \
        "${HOME}/.claude/commands/sad-analyze.md"
  if [[ "$CLEAN_BACKUPS" == "true" ]]; then
    rm -rf "${HOME}/.claude/skills/sadskill.bak."*
  fi
  echo "   [OK] Removed from Claude Code"
fi

# Antigravity removal
if [[ -d "${HOME}/.gemini/antigravity/skills/sadskill" ]]; then
  echo "-> Removing from Google Antigravity..."
  rm -rf "${HOME}/.gemini/antigravity/skills/sadskill"
  if [[ "$CLEAN_BACKUPS" == "true" ]]; then
    rm -rf "${HOME}/.gemini/antigravity/skills/sadskill.bak."*
  fi
  echo "   [OK] Removed from Antigravity"
fi

# Cursor removal
if [[ -f "${TARGET_DIR}/.cursor/rules/sadskill.mdc" || -d "${TARGET_DIR}/.cursor/skills/sadskill" ]]; then
  echo "-> Removing Cursor workspace rule and skill in ${TARGET_DIR}..."
  rm -f "${TARGET_DIR}/.cursor/rules/sadskill.mdc"
  rm -rf "${TARGET_DIR}/.cursor/skills/sadskill"
  echo "   [OK] Removed Cursor rules and workspace skills"
fi

if [[ "$PURGE" == "true" ]]; then
  echo "-> Purging ~/.sadskill directory..."
  rm -rf "${HOME}/.sadskill"
fi

echo "=== sadskill uninstalled successfully ==="
