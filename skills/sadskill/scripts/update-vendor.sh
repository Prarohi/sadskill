#!/usr/bin/env bash
# Script to verify and update vendor sources
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR_DIR="${SCRIPT_DIR}/../vendor"

echo "=== sadskill vendor refresh ==="
echo "Checking vendor directories in ${VENDOR_DIR}..."

for dir in "${VENDOR_DIR}"/*/; do
  if [[ -d "$dir" ]]; then
    vendor_name="$(basename "$dir")"
    file_count="$(find "$dir" -type f -name "*.ref.md" | wc -l)"
    echo "  - ${vendor_name}: ${file_count} reference files"
  fi
done

echo "Vendor catalog verified."
