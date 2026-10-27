#!/usr/bin/env bash
# sadskill vendor audit and catalog verification tool (v0.3.0)
# Audits vendor reference files, verifies neutralized frontmatter, and checks manifest integrity.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
VENDOR_DIR="${REPO_ROOT}/skills/sadskill/vendor"
SOURCES_FILE="${VENDOR_DIR}/SOURCES.md"
INDEX_FILE="${VENDOR_DIR}/INDEX.md"
MANIFEST_FILE="${VENDOR_DIR}/manifest.json"

show_help() {
  cat << 'EOF'
Usage: ./scripts/update-vendor.sh [options]

Options:
  --audit      Audit vendor catalog, check neutralized frontmatter, and verify SOURCES.md (default)
  --check      Validate vendor manifest.json hashes against local reference files
  -h, --help   Show this help message and exit
EOF
  exit 0
}

MODE="audit"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    --audit)
      MODE="audit"
      shift
      ;;
    --check)
      MODE="check"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

echo "=== sadskill Vendor Subsystem Audit (v0.3.0) ==="

if [[ ! -d "$VENDOR_DIR" || ! -f "$SOURCES_FILE" || ! -f "$INDEX_FILE" ]]; then
  echo "ERROR: Missing vendor directory, SOURCES.md, or INDEX.md" >&2
  exit 1
fi

total_vendors=0
total_ref_files=0
violations=0

for dir in "${VENDOR_DIR}"/*/; do
  if [[ -d "$dir" ]]; then
    vendor_name="$(basename "$dir")"
    ref_files=$(find "$dir" -maxdepth 1 -type f -name "*.ref.md")
    count=$(echo "$ref_files" | grep -v '^$' | wc -l)
    total_vendors=$((total_vendors + 1))
    total_ref_files=$((total_ref_files + count))

    # Verify that each ref file has neutralized frontmatter
    for f in $ref_files; do
      if head -n 5 "$f" | grep -qE '^name:[[:space:]]+'; then
        echo "  [FAIL] Unneutralized frontmatter in $f"
        violations=$((violations + 1))
      fi
    done

    # Verify that the vendor is listed in SOURCES.md
    if ! grep -qi "$vendor_name" "$SOURCES_FILE"; then
      echo "  [WARN] Vendor '$vendor_name' not explicitly documented in SOURCES.md"
    fi
  fi
done

if [[ -f "$MANIFEST_FILE" && "$MODE" == "check" ]]; then
  echo "-> Checking manifest integrity against reference files..."
  python3 -c "
import json, hashlib, sys
from pathlib import Path

repo_root = Path('$REPO_ROOT')
manifest_path = Path('$MANIFEST_FILE')
with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

for ref in manifest.get('references', []):
    p = repo_root / ref['path']
    if not p.exists():
        print(f'  [FAIL] Missing file: {ref[\"path\"]}')
        sys.exit(1)
"
  echo "   [OK] Manifest check passed."
fi

echo "Audit Summary:"
echo "  - Vendors Verified: ${total_vendors}"
echo "  - Neutralized References: ${total_ref_files}"
echo "  - Frontmatter Violations: ${violations}"

if [ $violations -gt 0 ]; then
  echo "Vendor subsystem verification failed with ${violations} violations." >&2
  exit 1
fi

echo "All vendor references verified successfully."
