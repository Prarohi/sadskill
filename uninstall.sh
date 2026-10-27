#!/usr/bin/env bash
# sadskill uninstaller: clean removal from agent environments
set -euo pipefail

echo "=== Uninstalling sadskill ==="

# Codex removal
if [[ -d "${HOME}/.codex/skills/sadskill" ]]; then
  echo "-> Removing from Codex / ChatGPT Desktop..."
  rm -rf "${HOME}/.codex/skills/sadskill"
  rm -f "${HOME}/.codex/prompts/sad-plan.md" \
        "${HOME}/.codex/prompts/sad-design.md" \
        "${HOME}/.codex/prompts/sad-backend.md" \
        "${HOME}/.codex/prompts/sad-sec.md" \
        "${HOME}/.codex/prompts/sad-analyze.md"
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
  echo "   [OK] Removed from Claude"
fi

if [[ "${1:-}" == "--purge" ]]; then
  echo "-> Purging ~/.sadskill directory..."
  rm -rf "${HOME}/.sadskill"
fi

echo "=== sadskill uninstalled successfully ==="
