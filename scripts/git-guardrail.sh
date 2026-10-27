#!/usr/bin/env bash
# sadskill git & database safety guardrail
# Intercepts and blocks destructive Git and SQL operations.
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

DANGEROUS_PATTERNS=(
  "git push.*--force"
  "git push.*-f\b"
  "git reset.*--hard"
  "git clean.*-f"
  "git branch.*-D"
  "git checkout[[:space:]]+\."
  "git restore[[:space:]]+\."
  "git stash[[:space:]]+(drop|clear)"
  "DROP[[:space:]]+DATABASE"
  "DROP[[:space:]]+TABLE"
  "TRUNCATE[[:space:]]+TABLE"
  "TRUNCATE[[:space:]]+[a-zA-Z0-9_]+"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiE "$pattern"; then
    echo "BLOCKED: Command matches destructive pattern '$pattern'." >&2
    echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
    echo "If this operation is intended, execute it manually with explicit confirmation." >&2
    exit 2
  fi
done

exit 0
