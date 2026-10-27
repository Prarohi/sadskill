#!/usr/bin/env bash
# sadskill uninstaller: clean removal from agent environments (v0.3.0)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${PWD}"
PURGE="false"
CLEAN_BACKUPS="false"
RESTORE_PREVIOUS="false"
DRY_RUN="false"
MANIFEST_FILE="${HOME}/.sadskill/install-manifest.json"

show_help() {
  local exit_code="${1:-0}"
  cat << 'EOF'
Usage: ./uninstall.sh [options]

Options:
  -t, --target <dir>     Target project directory for Cursor removal (default: current working dir)
      --restore-previous Restore original files from .bak timestamp archives if available
      --clean-backups    Remove .bak timestamp archives created by sadskill
  -f, --force            Force removal or restoration of files even if modified since installation
      --dry-run          Preview actions without modifying or removing files
      --purge            Remove ~/.sadskill user profile directory
  -h, --help             Show this help message and exit
EOF
  exit "$exit_code"
}

FORCE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help 0
      ;;
    -t|--target)
      if [[ $# -lt 2 || "$2" =~ ^- ]]; then
        echo "Error: --target requires a value." >&2
        show_help 2
      fi
      TARGET_DIR="$2"
      shift 2
      ;;
    --restore-previous)
      RESTORE_PREVIOUS="true"
      shift
      ;;
    -f|--force)
      FORCE="true"
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
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    *)
      echo "Error: Unknown option: $1" >&2
      show_help 2
      ;;
  esac
done

echo "=== Uninstalling sadskill (v0.3.0) ==="

if [[ "$DRY_RUN" == "true" ]]; then
  echo "   [DRY-RUN MODE] No files will be removed or modified."
fi

# Use manifest-driven uninstaller if manifest exists
if [[ -f "$MANIFEST_FILE" ]]; then
  echo "-> Processing uninstallation via verified manifest ledger..."
  opts=(--manifest "$MANIFEST_FILE" --target "$TARGET_DIR")
  if [[ "$RESTORE_PREVIOUS" == "true" ]]; then
    opts+=(--restore-previous)
  fi
  if [[ "$CLEAN_BACKUPS" == "true" ]]; then
    opts+=(--clean-backups)
  fi
  if [[ "$FORCE" == "true" ]]; then
    opts+=(--force)
  fi
  if [[ "$DRY_RUN" == "true" ]]; then
    opts+=(--dry-run)
  fi

  python3 "${SCRIPT_DIR}/scripts/manifest.py" uninstall "${opts[@]}"
else
  # Fallback for unmanaged/legacy installs without a manifest:
  # Check and remove only verified sadskill installations without deleting restored or unrelated files.
  echo "-> Notice: Manifest ledger not found. Running safe fallback uninstallation..."

  remove_safe_file() {
    local file="$1"
    if [[ -f "$file" ]]; then
      if grep -q "sadskill" "$file" 2>/dev/null; then
        echo "   [REMOVE] Removing verified sadskill file: $file"
        if [[ "$DRY_RUN" != "true" ]]; then
          rm -f "$file"
        fi
      else
        echo "   [PRESERVE] Skipping file without sadskill signature: $file"
      fi
    fi
  }

  remove_safe_dir() {
    local dir="$1"
    if [[ -d "$dir" && "$(basename "$dir")" == "sadskill" ]]; then
      echo "   [REMOVE] Removing sadskill directory: $dir"
      if [[ "$DRY_RUN" != "true" ]]; then
        rm -rf "$dir"
      fi
    fi
  }

  remove_safe_dir "${HOME}/.codex/skills/sadskill"
  for f in "${HOME}/.codex/prompts/sad-"*.md; do
    remove_safe_file "$f"
  done

  remove_safe_dir "${HOME}/.claude/skills/sadskill"
  for f in "${HOME}/.claude/commands/sad-"*.md; do
    remove_safe_file "$f"
  done
  remove_safe_file "${HOME}/.claude/hooks/git-guardrail.sh"

  remove_safe_dir "${HOME}/.gemini/antigravity/skills/sadskill"

  remove_safe_file "${TARGET_DIR}/.cursor/rules/sadskill.mdc"
  remove_safe_dir "${TARGET_DIR}/.cursor/skills/sadskill"
fi

if [[ "$PURGE" == "true" ]]; then
  echo "-> Purging ~/.sadskill user profile directory..."
  if [[ "$DRY_RUN" != "true" ]]; then
    rm -rf "${HOME}/.sadskill"
  else
    echo "   [DRY-RUN] Would remove ${HOME}/.sadskill"
  fi
fi

echo "=== sadskill uninstalled successfully ==="
