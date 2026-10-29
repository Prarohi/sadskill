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
      if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then
        echo "ERROR: --project-dir needs a directory" >&2
        exit 78
      fi
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

# Resolve links before mounting; never permit a broad or protected writable root.
if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "ERROR: missing sandbox project directory: $PROJECT_DIR" >&2
  exit 78
fi
PROJECT_DIR="$(cd -- "$PROJECT_DIR" && pwd -P)"

# Git worktrees store a small .git pointer in the project and keep the actual
# metadata in a shared common Git directory. Only mount that metadata after
# validating the pointer, commondir, worktree location, and Git back-pointer.
GIT_KIND="none"
COMMON_GIT_DIR=""
WORKTREE_GIT_DIR=""
GIT_METADATA_VALID=false
GIT_METADATA_ERROR=""
if [[ -L "$PROJECT_DIR/.git" ]]; then
  GIT_METADATA_ERROR="symlinked .git entries are not supported"
elif [[ -d "$PROJECT_DIR/.git" ]]; then
  GIT_KIND="standard"
elif [[ -f "$PROJECT_DIR/.git" ]]; then
  GIT_POINTER_LINES=()
  if [[ "$(wc -c < "$PROJECT_DIR/.git")" -le 4096 ]]; then
    mapfile -t GIT_POINTER_LINES < "$PROJECT_DIR/.git"
  fi
  if [[ ${#GIT_POINTER_LINES[@]} -eq 1 && "${GIT_POINTER_LINES[0]}" == gitdir:\ * ]]; then
    GIT_DIR_INPUT="${GIT_POINTER_LINES[0]#gitdir: }"
    if [[ -n "$GIT_DIR_INPUT" ]]; then
      if [[ "$GIT_DIR_INPUT" != /* ]]; then
        GIT_DIR_INPUT="$PROJECT_DIR/$GIT_DIR_INPUT"
      fi
      if [[ -d "$GIT_DIR_INPUT" ]]; then
        WORKTREE_GIT_DIR="$(cd -- "$GIT_DIR_INPUT" && pwd -P)"
        COMMON_LINES=()
        if [[ -f "$WORKTREE_GIT_DIR/commondir" && ! -L "$WORKTREE_GIT_DIR/commondir" ]]; then
          mapfile -t COMMON_LINES < "$WORKTREE_GIT_DIR/commondir"
        fi
        if [[ ${#COMMON_LINES[@]} -eq 1 && -n "${COMMON_LINES[0]}" ]]; then
          COMMON_DIR_INPUT="${COMMON_LINES[0]}"
          if [[ "$COMMON_DIR_INPUT" != /* ]]; then
            COMMON_DIR_INPUT="$WORKTREE_GIT_DIR/$COMMON_DIR_INPUT"
          fi
          if [[ -d "$COMMON_DIR_INPUT" ]]; then
            COMMON_GIT_DIR="$(cd -- "$COMMON_DIR_INPUT" && pwd -P)"
            WORKTREE_RELATIVE=""
            case "$WORKTREE_GIT_DIR" in
              "$COMMON_GIT_DIR"/worktrees/*)
                WORKTREE_RELATIVE="${WORKTREE_GIT_DIR#"$COMMON_GIT_DIR"/worktrees/}"
                ;;
            esac
            BACK_POINTER_LINES=()
            if [[ -f "$WORKTREE_GIT_DIR/gitdir" && ! -L "$WORKTREE_GIT_DIR/gitdir" ]]; then
              mapfile -t BACK_POINTER_LINES < "$WORKTREE_GIT_DIR/gitdir"
            fi
            if [[ ${#BACK_POINTER_LINES[@]} -eq 1 && -n "${BACK_POINTER_LINES[0]}" ]]; then
              BACK_POINTER_INPUT="${BACK_POINTER_LINES[0]}"
              if [[ "$BACK_POINTER_INPUT" != /* ]]; then
                BACK_POINTER_INPUT="$WORKTREE_GIT_DIR/$BACK_POINTER_INPUT"
              fi
              BACK_POINTER_PARENT="$(dirname -- "$BACK_POINTER_INPUT")"
              if [[ -d "$BACK_POINTER_PARENT" ]]; then
                BACK_POINTER_CANONICAL="$(cd -- "$BACK_POINTER_PARENT" && pwd -P)/$(basename -- "$BACK_POINTER_INPUT")"
                if [[ "$WORKTREE_RELATIVE" != "" && "$WORKTREE_RELATIVE" != */* \
                  && -f "$COMMON_GIT_DIR/HEAD" && -d "$COMMON_GIT_DIR/objects" \
                  && -d "$COMMON_GIT_DIR/refs" && -f "$WORKTREE_GIT_DIR/HEAD" \
                  && "$BACK_POINTER_CANONICAL" == "$PROJECT_DIR/.git" ]]; then
                  GIT_KIND="worktree"
                  GIT_METADATA_VALID=true
                fi
              fi
            fi
          fi
        fi
      fi
    fi
  fi
  if [[ "$GIT_METADATA_VALID" != "true" ]]; then
    GIT_METADATA_ERROR="linked-worktree metadata failed validation"
  fi
elif [[ -e "$PROJECT_DIR/.git" || -L "$PROJECT_DIR/.git" ]]; then
  GIT_METADATA_ERROR="unsupported .git entry type"
fi
if [[ "$GIT_KIND" == "standard" ]]; then
  GIT_METADATA_VALID=true
fi
if [[ "$GIT_METADATA_VALID" != "true" && "$GIT_METADATA_ERROR" != "" ]]; then
  if [[ "$RO_GIT" == "false" ]]; then
    echo "ERROR: --allow-git requires validated repository metadata: $GIT_METADATA_ERROR" >&2
    exit 78
  fi
  if [[ -e "$PROJECT_DIR/.git" || -L "$PROJECT_DIR/.git" ]]; then
    echo "WARNING: Git metadata will not be mounted read-only: $GIT_METADATA_ERROR" >&2
  fi
fi

# The current user home is not a safe narrow project workspace.
USER_HOME=""
if [[ -n "${HOME:-}" && -d "$HOME" ]]; then
  USER_HOME="$(cd -- "$HOME" && pwd -P)"
  if [[ "$USER_HOME" == "/" ]]; then
    echo "ERROR: refusing to sandbox with the filesystem root as HOME." >&2
    exit 78
  fi
  if [[ "$PROJECT_DIR" == "$USER_HOME" ]]; then
    echo "ERROR: refusing entire HOME as writable sandbox project: $PROJECT_DIR" >&2
    exit 78
  fi
fi
case "$PROJECT_DIR" in
  /|/home|/tmp|/var|/mnt|/media|/opt|/workspace|/workspaces|/Users|/etc|/usr|/bin|/sbin|/lib|/lib64|/boot|/dev|/proc|/sys|/run|/root|/snap|/srv)
    echo "ERROR: refusing broad writable sandbox mount: $PROJECT_DIR" >&2
    exit 78
    ;;
  /etc/*|/usr/*|/bin/*|/sbin/*|/lib/*|/lib64/*|/boot/*|/dev/*|/proc/*|/sys/*|/run/*|/snap/*)
    echo "ERROR: refusing protected system workspace: $PROJECT_DIR" >&2
    exit 78
    ;;
esac

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
)

# Hide the host user's files and credentials. Recreate only the mountpoint
# path beneath an overlaid HOME or /tmp before rebinding the validated source.
ensure_sandbox_dir() {
  local target="$1"
  local base=""
  local relative=""
  local current=""
  local part=""
  local -a components=()

  if [[ -n "$USER_HOME" && "$USER_HOME" != "/tmp" && "$USER_HOME" != /tmp/* && "$target" == "$USER_HOME"/* ]]; then
    base="$USER_HOME"
    relative="${target#"$USER_HOME"/}"
  elif [[ "$target" == /tmp/* ]]; then
    base="/tmp"
    relative="${target#/tmp/}"
  else
    return 0
  fi

  current="$base"
  IFS='/' read -r -a components <<< "$relative"
  for part in "${components[@]}"; do
    [[ -z "$part" ]] && continue
    current="$current/$part"
    BWRAP_ARGS+=(--dir "$current")
  done
}

if [[ -n "$USER_HOME" && "$USER_HOME" != "/tmp" && "$USER_HOME" != /tmp/* ]]; then
  BWRAP_ARGS+=(--tmpfs "$USER_HOME")
fi

ensure_sandbox_dir "$PROJECT_DIR"
if [[ "$GIT_KIND" == "worktree" ]]; then
  ensure_sandbox_dir "$COMMON_GIT_DIR"
fi

BWRAP_ARGS+=(
  --dir /tmp/sadskill-home
  --dir /tmp/sadskill-tmp
  --bind "$PROJECT_DIR" "$PROJECT_DIR"
  --chdir "$PROJECT_DIR"
  --die-with-parent
  --clearenv
  --setenv PATH "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
  --setenv HOME /tmp/sadskill-home
  --setenv TMPDIR /tmp/sadskill-tmp
)

if [[ "$RO_GIT" == "true" ]]; then
  if [[ "$GIT_KIND" == "standard" || ( -f "$PROJECT_DIR/.git" && ! -L "$PROJECT_DIR/.git" ) ]]; then
    BWRAP_ARGS+=(--ro-bind "$PROJECT_DIR/.git" "$PROJECT_DIR/.git")
  fi
  if [[ "$GIT_KIND" == "worktree" ]]; then
    BWRAP_ARGS+=(--ro-bind "$COMMON_GIT_DIR" "$COMMON_GIT_DIR")
  fi
elif [[ "$GIT_KIND" == "worktree" ]]; then
  BWRAP_ARGS+=(--bind "$COMMON_GIT_DIR" "$COMMON_GIT_DIR")
fi

if [[ "$OFFLINE" == "true" ]]; then
  BWRAP_ARGS+=(--unshare-net)
fi

exec bwrap "${BWRAP_ARGS[@]}" "$@"
