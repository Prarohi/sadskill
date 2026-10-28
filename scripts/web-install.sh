#!/usr/bin/env bash
# Verified opt-in archive installer. Unsafe moving-main archives are refused.
# Usage: bash scripts/web-install.sh --commit SHA40 --sha256 DIGEST64 -- [installer args]
set -euo pipefail
umask 077
usage() {
  echo 'Usage: web-install.sh --commit <40-hex-SHA> --sha256 <64-hex-digest> -- [install.sh args]' >&2
  echo 'Commit and digest must be independently verified before invocation.' >&2
}
COMMIT=""
EXPECTED=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      COMMIT="$2"; shift 2 ;;
    --sha256)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      EXPECTED="$2"; shift 2 ;;
    --)
      shift; break ;;
    --help|-h) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
if [[ ! "$COMMIT" =~ ^[0-9a-fA-F]{40}$ || ! "$EXPECTED" =~ ^[0-9a-fA-F]{64}$ ]]; then
  echo 'ERROR: both an exact commit and archive SHA-256 digest are required.' >&2
  exit 2
fi
for cmd in curl python3 bash; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: missing $cmd" >&2; exit 78; }
done
WORKDIR="$(mktemp -d /tmp/sadskill-verified-install.XXXXXXXX)"
trap 'rm -rf -- "$WORKDIR"' EXIT
ARCHIVE="$WORKDIR/source.tar.gz"
URL="https://codeload.github.com/Prarohi/sadskill/tar.gz/$COMMIT"
curl --proto '=https' --proto-redir '=https' --tlsv1.2 \
  --fail --location --silent --show-error --max-time 45 \
  --max-filesize 33554432 -o "$ARCHIVE" "$URL"

python3 - "$ARCHIVE" "$WORKDIR/verified" "$EXPECTED" <<'PY'
import hashlib
import hmac
from pathlib import Path
import shutil
import sys
import tarfile

archive = Path(sys.argv[1])
dest_root = Path(sys.argv[2])
expected = sys.argv[3].lower()
if archive.stat().st_size > 32 * 1024 * 1024:
    raise SystemExit("ERROR: archive exceeds compressed size limit")
actual = hashlib.sha256(archive.read_bytes()).hexdigest()
if not hmac.compare_digest(actual, expected):
    raise SystemExit("ERROR: archive SHA-256 mismatch; nothing executed")
entries = []
seen = set()
root = None
total = 0
with tarfile.open(archive, mode="r:gz") as tar:
    for member in tar:
        if len(entries) >= 4096:
            raise SystemExit("ERROR: too many archive entries")
        name = member.name.rstrip("/")
        parts = name.split("/")
        if not name or name.startswith("/") or any(p in ("", ".", "..") for p in parts):
            raise SystemExit("ERROR: unsafe archive path")
        if root is None:
            root = parts[0]
            if not root.startswith("sadskill-"):
                raise SystemExit("ERROR: unexpected archive root")
        if parts[0] != root or len(parts) > 33:
            raise SystemExit("ERROR: mixed archive roots or excessive depth")
        if not (member.isfile() or member.isdir()):
            raise SystemExit("ERROR: archive link or special file refused")
        relative = tuple(parts[1:])
        if relative in seen:
            raise SystemExit("ERROR: duplicate archive member")
        seen.add(relative)
        if not relative and not member.isdir():
            raise SystemExit("ERROR: archive root must be a directory")
        if member.isfile():
            if member.size < 0 or member.size > 16 * 1024 * 1024:
                raise SystemExit("ERROR: archive file exceeds size limit")
            total += member.size
            if total > 64 * 1024 * 1024:
                raise SystemExit("ERROR: total extracted size exceeds limit")
        entries.append((member, relative))
    dest_root.mkdir(mode=0o700)
    for member, relative in entries:
        target = dest_root.joinpath(*relative)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
        else:
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            payload = tar.extractfile(member)
            if payload is None:
                raise SystemExit("ERROR: invalid archive payload")
            with payload, target.open("xb") as output:
                shutil.copyfileobj(payload, output, length=65536)
            if target.stat().st_size != member.size:
                raise SystemExit("ERROR: truncated archive payload")
if not (dest_root / "install.sh").is_file() or not (dest_root / "VERSION").is_file():
    raise SystemExit("ERROR: verified archive has no installer or VERSION")
print("Archive digest and safe extraction verified")
PY
bash "$WORKDIR/verified/install.sh" "$@"
