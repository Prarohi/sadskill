#!/usr/bin/env bash
# sadskill git & database safety guardrail (v0.2.1)
# Intercepts and blocks destructive Git and SQL operations with robust tokenization.
# Compatible with Claude Code PreToolUse hooks, Git pre-push hooks, and CLI wrappers.

set -euo pipefail

INPUT=""
if [ ! -t 0 ]; then
  INPUT=$(cat)
fi

COMMAND=""
if [[ -n "$INPUT" ]]; then
  # Check if input is Claude Code JSON hook payload
  if echo "$INPUT" | grep -q '"tool_input"'; then
    COMMAND=$(echo "$INPUT" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' 2>/dev/null || true)
  fi
  if [[ -z "$COMMAND" ]]; then
    COMMAND="$INPUT"
  fi
fi

if [[ -z "$COMMAND" && $# -gt 0 ]]; then
  COMMAND="$*"
fi

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# Function to inspect a single atomic command segment
check_segment() {
  local seg="$1"
  # Trim leading and trailing whitespace
  seg="$(echo "$seg" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

  if [[ -z "$seg" ]]; then
    return 0
  fi

  # 1. SQL Destructive Patterns
  if echo "$seg" | grep -qiE '\b(DROP[[:space:]]+(DATABASE|SCHEMA|TABLE|VIEW)|TRUNCATE[[:space:]]+TABLE|TRUNCATE[[:space:]]+[a-zA-Z0-9_]+|ALTER[[:space:]]+TABLE[[:space:]]+[a-zA-Z0-9_.]+[[:space:]]+DROP[[:space:]]+COLUMN)\b'; then
    echo "BLOCKED: Destructive SQL query detected in '$seg'." >&2
    echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
    exit 2
  fi

  # 2. Extract Git command if present
  # Strip leading environment variable assignments (e.g. GIT_PAGER=cat git ...)
  local clean_cmd
  clean_cmd=$(echo "$seg" | sed -E 's/^([A-Za-z_][A-Za-z0-9_]*=[^ ]*[[:space:]]+)*//')

  if [[ "$clean_cmd" =~ ^git([[:space:]]|$) ]]; then
    # Tokenize arguments while ignoring commit message bodies (-m "...")
    # Strip -m "..." or -m '...' so text inside messages does not trigger false positives
    local stripped_git
    stripped_git=$(echo "$clean_cmd" | sed -E 's/-m[[:space:]]*("[^"]*"|'\'[^\']*\'')//g')

    # Remove global flags: -C <path>, --git-dir=<path>, --git-dir <path>, --work-tree=<path>, -c <key>=<val>, -p, --no-pager
    local tokens=()
    read -r -a raw_tokens <<< "$stripped_git"
    local idx=1
    local verb=""
    local args=()

    while [ $idx -lt ${#raw_tokens[@]} ]; do
      local tok="${raw_tokens[$idx]}"
      case "$tok" in
        -C|--git-dir|--work-tree|-c)
          idx=$((idx + 2))
          continue
          ;;
        --git-dir=*|--work-tree=*|-c=*|--no-pager|-p)
          idx=$((idx + 1))
          continue
          ;;
        *)
          if [[ -z "$verb" && ! "$tok" =~ ^- ]]; then
            verb="$tok"
          else
            args+=("$tok")
          fi
          idx=$((idx + 1))
          ;;
      esac
    done

    local args_str="${args[*]:-}"

    # Check dangerous Git verbs
    case "$verb" in
      reset)
        if [[ "$args_str" =~ --hard ]]; then
          echo "BLOCKED: 'git reset --hard' destroys working tree modifications." >&2
          echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
          exit 2
        fi
        ;;
      push)
        if [[ "$args_str" =~ (--force|-f\b|--force-with-lease|--delete\b) ]] || [[ "$args_str" =~ (\+[a-zA-Z0-9_\/\.-]+|:[a-zA-Z0-9_\/\.-]+) ]]; then
          echo "BLOCKED: Destructive or force push detected in 'git $args_str'." >&2
          echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
          exit 2
        fi
        ;;
      clean)
        if [[ "$args_str" =~ (-f|-fd|-df|-x) ]]; then
          echo "BLOCKED: 'git clean' permanently deletes untracked files." >&2
          echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
          exit 2
        fi
        ;;
      branch)
        if [[ "$args_str" =~ (-D|--delete[[:space:]]+-f) ]]; then
          echo "BLOCKED: Force branch deletion detected in 'git branch $args_str'." >&2
          echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
          exit 2
        fi
        ;;
      checkout|restore)
        if [[ "$args_str" =~ (^|[[:space:]])(\.|\*|-A)($|[[:space:]]) ]]; then
          echo "BLOCKED: Full working tree discard detected in 'git $verb $args_str'." >&2
          echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
          exit 2
        fi
        ;;
      stash)
        if [[ "$args_str" =~ (drop|clear) ]]; then
          echo "BLOCKED: 'git stash $args_str' destroys saved stashes." >&2
          echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
          exit 2
        fi
        ;;
    esac
  fi
}

# Split chained commands (; && || |) to prevent hiding destructive commands behind compound expressions
# We replace delimiters with newlines and check each segment
echo "$COMMAND" | tr ';&|' '\n' | while IFS= read -r segment; do
  check_segment "$segment"
done

exit 0
