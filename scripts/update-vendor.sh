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

# Do not trust nested or unlisted symlinks inside the vendor tree.
first_symlink="$(find "$VENDOR_DIR" -type l -print -quit)"
if [[ -n "$first_symlink" ]]; then
  echo "ERROR: Vendor tree contains a symlink: $first_symlink" >&2
  exit 1
fi

for dir in "${VENDOR_DIR}"/*/; do
  if [[ -d "$dir" ]]; then
    vendor_name="$(basename "$dir")"
    ref_files=$(find "$dir" -maxdepth 1 -type f -name "*.ref.md")
    count=$(echo "$ref_files" | grep -v '^$' | wc -l)
    total_vendors=$((total_vendors + 1))
    total_ref_files=$((total_ref_files + count))

    # Verify that each ref file has neutralized frontmatter
    for f in $ref_files; do
      # Detect active YAML name: anywhere in the opening frontmatter block,
      # not only in the first five lines of a reference document.
      if head -n 5 "$f" | grep -qE '^name:[[:space:]]+' ||
         ! awk 'NR == 1 && $0 != "---" { exit 0 } NR > 1 && $0 == "---" { exit 0 } NR > 1 && /^[[:space:]]*name:[[:space:]]*/ { exit 11 }' "$f"; then
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

if [[ "$MODE" == "check" ]]; then
  [[ -f "$MANIFEST_FILE" ]] || { echo "ERROR: Missing vendor manifest: $MANIFEST_FILE" >&2; exit 1; }
  echo "-> Checking vendor manifest SHA-256 digests and path containment..."
  python3 - "$REPO_ROOT" "$VENDOR_DIR" "$MANIFEST_FILE" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
vendor = Path(sys.argv[2]).resolve()
manifest_path = Path(sys.argv[3])
try:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
except (OSError, ValueError) as exc:
    sys.exit(f"FAIL: Cannot load vendor manifest: {exc}")
refs = data.get("references")
if not isinstance(refs, list) or not refs:
    sys.exit("FAIL: vendor manifest requires nonempty references array")
if data.get("total_references") != len(refs):
    sys.exit("FAIL: vendor manifest count mismatch")
seen = set()
for entry in refs:
    if not isinstance(entry, dict):
        sys.exit("FAIL: vendor manifest entry is not an object")
    rel = entry.get("path")
    digest = entry.get("sha256")
    if not isinstance(rel, str) or not rel or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        sys.exit("FAIL: invalid vendor path or SHA-256")
    if "\\" in rel:
        sys.exit("FAIL: vendor reference has backslash")
    parts = Path(rel)
    if parts.is_absolute() or ".." in parts.parts or "." in parts.parts:
        sys.exit("FAIL: unsafe vendor reference path")
    if rel in seen:
        sys.exit("FAIL: duplicate vendor reference")
    seen.add(rel)
    path = root / rel
    if path.is_symlink() or not path.is_file():
        sys.exit(f"FAIL: missing/symlink vendor reference: {rel}")
    resolved = path.resolve()
    try:
        resolved.relative_to(vendor)
    except ValueError:
        sys.exit(f"FAIL: vendor reference escapes vendor directory: {rel}")
    if not resolved.name.endswith(".ref.md"):
        sys.exit(f"FAIL: not a vendor reference: {rel}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        sys.exit(f"FAIL: SHA-256 mismatch for {rel}")
disk = {str(path.relative_to(root)) for path in vendor.rglob("*.ref.md") if path.is_file()}
if disk != seen:
    sys.exit("FAIL: vendor reference manifest/file-set mismatch")
print(f"Verified SHA-256 digests for {len(refs)} vendor references.")
PY
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
