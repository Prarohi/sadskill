#!/usr/bin/env bash
# sadskill one-liner web installer
# Usage: curl -fsSL https://raw.githubusercontent.com/Prarohi/sadskill/main/scripts/web-install.sh | bash
set -euo pipefail

TEMP_DIR=$(mktemp -d /tmp/sadskill-web-install.XXXXXX)
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "==> Downloading latest sadskill release..."
curl -fsSL "https://github.com/Prarohi/sadskill/archive/refs/heads/main.tar.gz" -o "$TEMP_DIR/sadskill.tar.gz"

tar -xzf "$TEMP_DIR/sadskill.tar.gz" -C "$TEMP_DIR"
SRC_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "sadskill-*" | head -n 1)

if [[ -z "$SRC_DIR" || ! -f "$SRC_DIR/install.sh" ]]; then
  echo "Error: Failed to unpack valid sadskill repository package." >&2
  exit 1
fi

echo "==> Executing sadskill installer..."
bash "$SRC_DIR/install.sh" "$@"
