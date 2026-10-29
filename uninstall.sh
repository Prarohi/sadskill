#!/usr/bin/env bash
# sadskill uninstaller: clean removal from agent environments (v0.3.0)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SADSKILL_VERSION="$(<"${SCRIPT_DIR}/VERSION")"
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

echo "=== Uninstalling sadskill (v${SADSKILL_VERSION}) ==="

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
  # Removal is ownership-verified: a file is sadskill's only when it is
  # byte-identical to a file shipped in this repository; a directory is
  # sadskill's only when its entire tree matches the shipped skill tree.
  # Anything else is user content and is preserved.
  echo "-> Notice: Manifest ledger not found. Running safe fallback uninstallation..."

  remove_owned_file() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    local shipped
    for shipped in "${SCRIPT_DIR}/commands/claude/"*.md \
                   "${SCRIPT_DIR}/commands/codex/"*.md \
                   "${SCRIPT_DIR}/skills/sadskill/hooks/git-guardrail.sh"; do
      [[ -f "$shipped" ]] || continue
      if cmp -s "$file" "$shipped"; then
        echo "   [REMOVE] Removing sadskill-owned file (content-verified): $file"
        if [[ "$DRY_RUN" != "true" ]]; then
          rm -f "$file"
        fi
        return 0
      fi
    done
    echo "   [PRESERVE] File is not byte-identical to any shipped sadskill file, keeping: $file"
  }

  remove_owned_dir() {
    local dir="$1"
    [[ -d "$dir" && "$(basename "$dir")" == "sadskill" ]] || return 0
    if diff -r "$dir" "${SCRIPT_DIR}/skills/sadskill" >/dev/null 2>&1; then
      echo "   [REMOVE] Removing sadskill-owned directory (content-verified): $dir"
      if [[ "$DRY_RUN" != "true" ]]; then
        rm -rf "$dir"
      fi
    else
      echo "   [PRESERVE] Directory differs from shipped sadskill skill tree, keeping: $dir"
      echo "            (contains user modifications or a different version; remove manually if unwanted)"
    fi
  }

  remove_owned_dir "${HOME}/.codex/skills/sadskill"
  for f in "${HOME}/.codex/prompts/sad-"*.md; do
    remove_owned_file "$f"
  done

  remove_owned_dir "${HOME}/.claude/skills/sadskill"
  for f in "${HOME}/.claude/commands/sad-"*.md; do
    remove_owned_file "$f"
  done
  remove_owned_file "${HOME}/.claude/hooks/git-guardrail.sh"

  remove_owned_dir "${HOME}/.gemini/antigravity/skills/sadskill"

  remove_owned_file "${TARGET_DIR}/.cursor/rules/sadskill.mdc"
  remove_owned_dir "${TARGET_DIR}/.cursor/skills/sadskill"
fi

if [[ "$PURGE" == "true" && -f "$MANIFEST_FILE" ]]; then
  # Unresolved backups may contain user edits. Never lose their manifest
  # provenance even when purge is explicitly requested.
  if python3 - "$MANIFEST_FILE" <<'PY'
import json
from pathlib import Path
import sys
try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("invalid entries")
    unresolved = any(
        isinstance(entry, dict) and (
            any(
                isinstance(record, dict) and isinstance(record.get("path"), str)
                and Path(record["path"]).exists()
                for record in (entry.get("conflict_backups") or [])
            ) or (entry.get("backup") and Path(entry["backup"]).exists())
        ) for entry in entries
    )
except (OSError, ValueError, TypeError, KeyError):
    unresolved = True  # Corrupt manifest: refuse destructive purge
sys.exit(0 if unresolved else 1)
PY
  then
    echo "ERROR: --purge refused; unresolved user backups are still recorded in install-manifest.json." >&2
    exit 5
  fi
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
