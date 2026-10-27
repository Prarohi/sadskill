#!/usr/bin/env bash
# sadskill git & database safety guardrail (v0.3.0)
# Intercepts and blocks destructive Git, SQL, and ref-update operations.
# Compatible with Claude Code PreToolUse hooks, Git pre-push hooks, and CLI wrappers.

set -euo pipefail

INPUT=""
if [ ! -t 0 ]; then
  INPUT=$(cat)
fi

COMMAND=""
IS_GIT_PRE_PUSH="false"

if [[ -n "$INPUT" ]]; then
  # 1. Check if input is a Git pre-push ref-update stream:
  # Lines format: <local_ref> <local_oid> <remote_ref> <remote_oid>
  # Note: local_ref may be 'refs/heads/...', '(delete)', any non-whitespace string, or omitted (leading space)
  if echo "$INPUT" | grep -qE '^[[:space:]]*([^[:space:]]+[[:space:]]+)?[0-9a-f]{40}[[:space:]]+refs/[^[:space:]]+[[:space:]]+[0-9a-f]{40}'; then
    IS_GIT_PRE_PUSH="true"
  elif echo "$INPUT" | grep -q '"tool_input"'; then
    # 2. Structured Claude Code PreToolUse JSON extraction via Python
    COMMAND=$(python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    tool_input = data.get('tool_input', {})
    if isinstance(tool_input, dict):
        print(tool_input.get('command', ''))
    elif isinstance(tool_input, str):
        print(tool_input)
except Exception:
    pass
" <<< "$INPUT" 2>/dev/null || true)
  fi

  if [[ "$IS_GIT_PRE_PUSH" != "true" && -z "$COMMAND" ]]; then
    COMMAND="$INPUT"
  fi
fi

# Detect git pre-push invocations via standard git hook arguments ($1: remote, $2: url)
if [[ "$IS_GIT_PRE_PUSH" != "true" && $# -ge 2 ]]; then
  if [[ "$2" =~ ^(https?|git|ssh|file):// || "$2" =~ ^git@ || "$2" =~ \.git$ || "$1" =~ ^(origin|upstream)$ ]]; then
    IS_GIT_PRE_PUSH="true"
  fi
fi

if [[ -z "$COMMAND" && "$IS_GIT_PRE_PUSH" != "true" && $# -gt 0 ]]; then
  COMMAND="$*"
fi

# Handle Git pre-push ref update inspection
if [[ "$IS_GIT_PRE_PUSH" == "true" ]]; then
  ZERO_OID="0000000000000000000000000000000000000000"
  while IFS= read -r line; do
    [[ -z "${line// /}" ]] && continue
    read -r -a tokens <<< "$line"
    local_ref=""
    local_oid=""
    remote_ref=""
    remote_oid=""

    if [[ ${#tokens[@]} -eq 3 ]]; then
      # 3 tokens: <local_oid> <remote_ref> <remote_oid> (empty local_ref)
      local_ref=""
      local_oid="${tokens[0]}"
      remote_ref="${tokens[1]}"
      remote_oid="${tokens[2]}"
    elif [[ ${#tokens[@]} -ge 4 ]]; then
      # 4 tokens: <local_ref> <local_oid> <remote_ref> <remote_oid>
      local_ref="${tokens[0]}"
      local_oid="${tokens[1]}"
      remote_ref="${tokens[2]}"
      remote_oid="${tokens[3]}"
    else
      continue
    fi

    # Destructive remote branch deletion check
    if [[ "$local_oid" == "$ZERO_OID" || "$local_ref" == "(delete)" ]]; then
      if [[ "$remote_ref" =~ refs/heads/(main|master|release|prod|production)$ ]]; then
        echo "BLOCKED: Force deletion of protected remote branch detected: $remote_ref" >&2
        echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
        exit 2
      fi
    fi

    # Non-fast-forward / force push verification via git merge-base if repository available
    if [[ "$remote_oid" != "$ZERO_OID" && "$local_oid" != "$ZERO_OID" ]]; then
      if [[ "$remote_ref" =~ refs/heads/(main|master|release|prod|production)$ ]]; then
        if git rev-parse --verify "$remote_oid" >/dev/null 2>&1 && git rev-parse --verify "$local_oid" >/dev/null 2>&1; then
          if ! git merge-base --is-ancestor "$remote_oid" "$local_oid" 2>/dev/null; then
            echo "BLOCKED: Non-fast-forward (force push) detected for protected branch $remote_ref." >&2
            echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
            exit 2
          fi
        fi
      fi
    fi
  done <<< "$INPUT"
  exit 0
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

  # Strip commit message content from git commit commands so commit descriptions
  # do not trigger false positive SQL or dangerous verb blocks
  local check_seg="$seg"
  if [[ "$check_seg" =~ git([[:space:]]|$) && "$check_seg" =~ commit([[:space:]]|$) ]]; then
    check_seg=$(echo "$check_seg" | sed -E 's/(-m|--message)[[:space:]=]*("[^"]*"|'\'[^\']*\'')//g')
  fi

  # 1. SQL Destructive Patterns (evaluated on code outside commit message bodies)
  if echo "$check_seg" | grep -qiE '\b(DROP[[:space:]]+(DATABASE|SCHEMA|TABLE|VIEW)|TRUNCATE[[:space:]]+TABLE|TRUNCATE[[:space:]]+[a-zA-Z0-9_]+|ALTER[[:space:]]+TABLE[[:space:]]+[a-zA-Z0-9_.]+[[:space:]]+DROP[[:space:]]+COLUMN)\b'; then
    echo "BLOCKED: Destructive SQL query detected in '$seg'." >&2
    echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
    exit 2
  fi

  # 2. Extract Git command if present
  # Strip leading environment variable assignments (e.g. GIT_PAGER=cat git ...)
  local clean_cmd
  clean_cmd=$(echo "$check_seg" | sed -E 's/^([A-Za-z_][A-Za-z0-9_]*=[^ ]*[[:space:]]+)*//')

  if [[ "$clean_cmd" =~ ^git([[:space:]]|$) ]]; then
    local stripped_git="$clean_cmd"

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

# Split chained commands (; && || |) while strictly respecting quotes
segments=()
if command -v python3 >/dev/null 2>&1; then
  while IFS= read -r line; do
    [[ -n "$line" ]] && segments+=("$line")
  done < <(python3 -c "
import sys, shlex
cmd = sys.argv[1]
try:
    lexer = shlex.shlex(cmd, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)
    current = []
    for t in tokens:
        if t in (';', '&&', '||', '|', '&'):
            if current:
                print(' '.join(current))
                current = []
        else:
            current.append(t)
    if current:
        print(' '.join(current))
except Exception:
    print(cmd)
" "$COMMAND" 2>/dev/null || echo "$COMMAND")
fi

if [ ${#segments[@]} -eq 0 ]; then
  segments=("$COMMAND")
fi

for segment in "${segments[@]}"; do
  check_segment "$segment"
done

exit 0
