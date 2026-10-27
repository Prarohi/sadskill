#!/usr/bin/env bash
# sadskill vendor audit and catalog verification tool
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
VENDOR_DIR="${REPO_ROOT}/skills/sadskill/vendor"
SOURCES_FILE="${VENDOR_DIR}/SOURCES.md"
INDEX_FILE="${VENDOR_DIR}/INDEX.md"

echo "=== sadskill Vendor Subsystem Audit ==="

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

echo "Audit Summary:"
echo "  - Vendors Verified: ${total_vendors}"
echo "  - Neutralized References: ${total_ref_files}"
echo "  - Frontmatter Violations: ${violations}"

if [ $violations -gt 0 ]; then
  echo "Vendor subsystem verification failed with ${violations} violations." >&2
  exit 1
fi

echo "All vendor references verified successfully."
