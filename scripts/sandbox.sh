#!/usr/bin/env bash
# sadskill Bubblewrap (bwrap) Linux process containment sandbox.
# Isolates tool and agent execution with read-only root/system mounts,
# protected .git history, and optional network namespace isolation.

set -euo pipefail

OFFLINE=false
RO_GIT=true
ALLOW_UNSANDBOXED=false
PROJECT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline)
      OFFLINE=true
      shift
      ;;
    --allow-git)
      RO_GIT=false
      shift
      ;;
    --allow-unsandboxed)
      ALLOW_UNSANDBOXED=true
      shift
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 [--offline] [--allow-git] [--allow-unsandboxed] [--project-dir <path>] -- <command> [args...]" >&2
  exit 1
fi

if [[ -z "$PROJECT_DIR" ]]; then
  PROJECT_DIR="$(pwd -P)"
fi

if ! command -v bwrap >/dev/null 2>&1; then
  if [[ "$ALLOW_UNSANDBOXED" != "true" ]]; then
    echo "ERROR: bubblewrap ('bwrap') is unavailable; command NOT executed. Install bwrap or explicitly choose --allow-unsandboxed (unsafe)." >&2
    exit 78
  fi
  if [[ "$OFFLINE" == "true" ]]; then
    echo "ERROR: --offline cannot be honored without bwrap; refusing unsandboxed execution." >&2
    exit 78
  fi
  echo "WARNING: --allow-unsandboxed explicitly selected; command will execute WITHOUT containment." >&2
  exec "$@"
fi

BWRAP_ARGS=(
  --ro-bind / /
  --dev /dev
  --proc /proc
  --tmpfs /tmp
  --bind "$PROJECT_DIR" "$PROJECT_DIR"
  --chdir "$PROJECT_DIR"
  --die-with-parent
)

if [[ "$RO_GIT" == "true" && -d "$PROJECT_DIR/.git" ]]; then
  BWRAP_ARGS+=(--ro-bind "$PROJECT_DIR/.git" "$PROJECT_DIR/.git")
fi

if [[ "$OFFLINE" == "true" ]]; then
  BWRAP_ARGS+=(--unshare-net)
fi

exec bwrap "${BWRAP_ARGS[@]}" "$@"
