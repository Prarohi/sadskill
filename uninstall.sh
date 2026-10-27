#!/usr/bin/env bash
# sadskill uninstaller: clean removal from agent environments (v0.3.0)
set -euo pipefail

TARGET_DIR="${PWD}"
PURGE="false"
CLEAN_BACKUPS="false"
RESTORE_PREVIOUS="false"
MANIFEST_FILE="${HOME}/.sadskill/install-manifest.json"

show_help() {
  echo "Usage: ./uninstall.sh [options]"
  echo ""
  echo "Options:"
  echo "  -t, --target <dir>     Target project directory for Cursor removal (default: current working dir)"
  echo "      --restore-previous Restore original files from .bak timestamp archives if available"
  echo "      --clean-backups    Remove all .bak timestamp archives created during installation"
  echo "      --purge            Remove ~/.sadskill user profile directory"
  echo "  -h, --help             Show this help message and exit"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    -t|--target)
      if [[ $# -lt 2 ]]; then
        echo "Error: --target requires a value." >&2
        show_help
      fi
      TARGET_DIR="$2"
      shift 2
      ;;
    --restore-previous)
      RESTORE_PREVIOUS="true"
      shift
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
      echo "Unknown option: $1" >&2
      show_help
      ;;
  esac
done

echo "=== Uninstalling sadskill ==="

# Optional restoration from manifest
if [[ "$RESTORE_PREVIOUS" == "true" && -f "$MANIFEST_FILE" ]]; then
  echo "-> Attempting to restore original files from backup archives..."
  python3 -c "
import json, os, shutil
manifest_path = '$MANIFEST_FILE'
try:
    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for entry in reversed(data.get('entries', [])):
        dest = entry.get('destination')
        bak = entry.get('backup')
        if bak and os.path.exists(bak) and dest:
            print(f'   [RESTORE] Restoring {dest} from {bak}')
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            elif os.path.isfile(dest):
                os.remove(dest)
            shutil.move(bak, dest)
except Exception as e:
    print(f'   [WARN] Restoration encountered error: {e}')
" 2>/dev/null || true
fi

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
    rm -rf "${HOME}/.codex/skills/sadskill.bak."* "${HOME}/.codex/prompts/"*.bak.*
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
        "${HOME}/.claude/commands/sad-analyze.md" \
        "${HOME}/.claude/hooks/git-guardrail.sh"
  if [[ "$CLEAN_BACKUPS" == "true" ]]; then
    rm -rf "${HOME}/.claude/skills/sadskill.bak."* "${HOME}/.claude/commands/"*.bak.*
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
  if [[ "$CLEAN_BACKUPS" == "true" ]]; then
    rm -f "${TARGET_DIR}/.cursor/rules/sadskill.mdc.bak."*
  fi
  echo "   [OK] Removed Cursor rules and workspace skills"
fi

if [[ "$PURGE" == "true" ]]; then
  echo "-> Purging ~/.sadskill directory..."
  rm -rf "${HOME}/.sadskill"
fi

echo "=== sadskill uninstalled successfully ==="
