#!/usr/bin/env bash
# sadskill git & database safety guardrail (v0.5.0)
# Intercepts and blocks destructive Git, SQL, filesystem, and ref-update operations.
# Features canonical AST/wrapper unwrapping (sudo, env, command, exec, bash -c, sh -c).
# Compatible with Claude Code PreToolUse hooks, Git pre-push hooks, and CLI wrappers.

set -euo pipefail

INPUT=""
if [ ! -t 0 ]; then
  INPUT=$(cat)
fi

COMMAND=""
IS_GIT_PRE_PUSH="false"
IS_JSON_INPUT="false"

if [[ -n "$INPUT" ]]; then
  # 1. Check if input is a Git pre-push ref-update stream:
  # Lines format: <local_ref> <local_oid> <remote_ref> <remote_oid>
  # Note: local_ref may be 'refs/heads/...', '(delete)', any non-whitespace string, or omitted (leading space)
  if echo "$INPUT" | grep -qE '^[[:space:]]*([^[:space:]]+[[:space:]]+)?[0-9a-f]{40}[[:space:]]+refs/[^[:space:]]+[[:space:]]+[0-9a-f]{40}'; then
    IS_GIT_PRE_PUSH="true"
  elif echo "$INPUT" | grep -q '"tool_input"'; then
    IS_JSON_INPUT="true"
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

# Canonical AST / recursive command inspection via Python
if command -v python3 >/dev/null 2>&1; then
  python_output=""
  exit_status=0
  python_output=$(python3 -c '
import sys, json, shlex, re, base64

cmd_str = sys.argv[1]

WRAPPER_COMMANDS = {"sudo", "env", "command", "exec", "nohup", "nice", "time", "ionice", "chroot"}
SHELL_INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh"}

def unwrap_tokens(tokens, depth=0):
    if depth > 10 or not tokens:
        return [tokens] if tokens else []
    idx = 0
    while idx < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*", tokens[idx]):
        idx += 1
    tokens = tokens[idx:]
    if not tokens:
        return []
    base_cmd = tokens[0].lower().rsplit("/", 1)[-1]
    if base_cmd in WRAPPER_COMMANDS:
        idx = 1
        if base_cmd == "env":
            while idx < len(tokens):
                tok = tokens[idx]
                if tok in ("-i", "--ignore-environment", "-0", "--null"):
                    idx += 1
                elif tok in ("-u", "--unset"):
                    idx += 2
                elif tok.startswith("-u") or tok.startswith("--unset="):
                    idx += 1
                elif tok == "--":
                    idx += 1
                    break
                elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*", tok):
                    idx += 1
                elif tok.startswith("-"):
                    idx += 1
                else:
                    break
        elif base_cmd == "sudo":
            while idx < len(tokens):
                tok = tokens[idx]
                if tok in ("-u", "-g", "-p", "-h", "-r", "-t", "-T", "-C"):
                    idx += 2
                elif tok == "--":
                    idx += 1
                    break
                elif tok.startswith("-"):
                    idx += 1
                else:
                    break
        elif base_cmd == "command":
            while idx < len(tokens):
                tok = tokens[idx]
                if tok in ("-p", "-v", "-V"):
                    idx += 1
                elif tok == "--":
                    idx += 1
                    break
                else:
                    break
        else:
            while idx < len(tokens) and tokens[idx].startswith("-"):
                if tokens[idx] == "--":
                    idx += 1
                    break
                idx += 1
        remaining = tokens[idx:]
        if remaining:
            return unwrap_tokens(remaining, depth + 1)
        return []

    if base_cmd in SHELL_INTERPRETERS:
        idx = 1
        c_arg = None
        while idx < len(tokens):
            tok = tokens[idx]
            if tok == "-c":
                if idx + 1 < len(tokens):
                    c_arg = tokens[idx + 1]
                break
            elif tok.startswith("-") and "c" in tok and not tok.startswith("--"):
                if idx + 1 < len(tokens):
                    c_arg = tokens[idx + 1]
                break
            elif tok == "--":
                if idx + 1 < len(tokens) and tokens[idx + 1] == "-c" and idx + 2 < len(tokens):
                    c_arg = tokens[idx + 2]
                break
            idx += 1
        if c_arg:
            return parse_command_string(c_arg, depth + 1)

    return [tokens]

def parse_command_string(cmd_str, depth=0):
    if depth > 10 or not cmd_str.strip():
        return []
    try:
        lexer = shlex.shlex(cmd_str, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except Exception:
        tokens = cmd_str.split()
    segments = []
    current = []
    for t in tokens:
        if t in (";", "&&", "||", "|", "&"):
            if current:
                segments.append(" ".join(current))
                current = []
        else:
            current.append(t)
    if current:
        segments.append(" ".join(current))
    results = []
    for seg in segments:
        try:
            seg_tokens = shlex.split(seg)
        except Exception:
            seg_tokens = seg.split()
        results.extend(unwrap_tokens(seg_tokens, depth))
    return results

def strip_sql_comments(sql):
    tokens = []
    i = 0
    n = len(sql)
    in_single_quote = False
    in_double_quote = False
    while i < n:
        c = sql[i]
        next_c = sql[i + 1] if i + 1 < n else ""
        if c == chr(39) and not in_double_quote:
            in_single_quote = not in_single_quote
            tokens.append(c)
            i += 1
            continue
        if c == chr(34) and not in_single_quote:
            in_double_quote = not in_double_quote
            tokens.append(c)
            i += 1
            continue
        if not in_single_quote and not in_double_quote:
            if c == "-" and next_c == "-":
                i += 2
                while i < n and sql[i] not in ("\n", "\r"):
                    i += 1
                continue
            if c == "/" and next_c == "*":
                i += 2
                while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                    i += 1
                i += 2
                tokens.append(" ")
                continue
        tokens.append(c)
        i += 1
    return "".join(tokens)

def inspect_sql(sql_query):
    clean_sql = strip_sql_comments(sql_query).strip()
    if not clean_sql:
        return False, ""
    normalized = re.sub(r"\s+", " ", clean_sql)
    drop_match = re.search(
        r"\bDROP\s+(?:DATABASE|SCHEMA|TABLE|VIEW|MATERIALIZED\s+VIEW|INDEX|COLUMN)\b",
        normalized,
        re.IGNORECASE,
    )
    if drop_match:
        return True, "Destructive SQL DROP operation detected: " + drop_match.group(0)
    if re.search(r"\bALTER\s+TABLE\s+[^\s;]+\s+DROP\s+COLUMN\b", normalized, re.IGNORECASE):
        return True, "Destructive ALTER TABLE DROP COLUMN detected"
    truncate_match = re.search(r"\bTRUNCATE\s+(?:TABLE\s+)?([\w.\"]+)\b", normalized, re.IGNORECASE)
    if truncate_match:
        return True, "Destructive SQL TRUNCATE operation detected on " + truncate_match.group(1)
    unbounded_delete = re.search(
        r"\bDELETE\s+FROM\s+[\w.\"]+\s*(?:;|$)(?!\s*WHERE\b)",
        normalized,
        re.IGNORECASE,
    )
    if unbounded_delete:
        return True, "Unbounded DELETE FROM query detected without WHERE clause"
    return False, ""

def check_base64_payloads(tokens):
    for tok in tokens:
        t = tok.strip(chr(39) + chr(34))
        if len(t) >= 8 and len(t) % 4 == 0 and re.match(r"^[A-Za-z0-9+/]+={0,2}$", t):
            try:
                decoded = base64.b64decode(t).decode("utf-8", errors="ignore")
                if decoded and any(kw in decoded.lower() for kw in ("git", "rm", "drop", "truncate", "delete")):
                    sub_cmds = parse_command_string(decoded)
                    for sc in sub_cmds:
                        b, r = check_atomic_command(sc)
                        if b:
                            return True, "Base64 encoded destructive payload detected: " + r
            except Exception:
                pass
    return False, ""

def check_atomic_command(tokens):
    if not tokens:
        return False, ""

    b64_blocked, b64_reason = check_base64_payloads(tokens)
    if b64_blocked:
        return True, b64_reason

    cmd = tokens[0].lower().rsplit("/", 1)[-1]
    if cmd == "rm":
        has_r = False
        targets = []
        for tok in tokens[1:]:
            if tok.startswith("-") and not tok.startswith("--"):
                if "r" in tok.lower() or "R" in tok:
                    has_r = True
            elif tok in ("-r", "-R", "--recursive"):
                has_r = True
            elif not tok.startswith("-"):
                targets.append(tok)
        if has_r and any(t in ("/", "~", "$HOME", "/*", "*", ".git", ".git/") for t in targets):
            return True, "Destructive file removal detected in '\''" + " ".join(tokens) + "'\''."

    if cmd == "git":
        idx = 1
        verb = ""
        args = []
        while idx < len(tokens):
            tok = tokens[idx]
            if tok in ("-C", "--git-dir", "--work-tree", "-c"):
                idx += 2
                continue
            elif tok.startswith(("--git-dir=", "--work-tree=", "-c=")) or tok in ("-p", "--no-pager"):
                idx += 1
                continue
            else:
                if not verb and not tok.startswith("-"):
                    verb = tok.lower()
                else:
                    args.append(tok)
                idx += 1

        if verb == "reset":
            if any(a == "--hard" or a.startswith("--hard") for a in args):
                return True, "'\''git reset --hard'\'' destroys working tree modifications."
        elif verb == "clean":
            for a in args:
                if a in ("-f", "-fd", "-df", "-x", "-fx", "-xf", "--force") or (a.startswith("-") and "f" in a):
                    return True, "'\''git clean'\'' permanently deletes untracked files."
        elif verb == "branch":
            if any(a in ("-D", "-f", "--force") for a in args):
                if "-D" in args or ("--delete" in args and any(f in args for f in ("-f", "--force"))):
                    return True, "Force branch deletion detected in '\''git branch " + " ".join(args) + "'\''."
        elif verb in ("checkout", "restore"):
            if any(a in (".", "*", "-A", "--all") for a in args):
                return True, "Full working tree discard detected in '\''git " + verb + " " + " ".join(args) + "'\''."
        elif verb == "stash":
            if any(a in ("drop", "clear") for a in args):
                return True, "'\''git stash " + " ".join(args) + "'\'' destroys saved stashes."
        elif verb == "config":
            cfg_val = " ".join(args).lower()
            if any(danger in cfg_val for danger in ("reset --hard", "clean -fd", "clean -f", "push --force")):
                return True, "Destructive git config alias detected in '\''git config " + " ".join(args) + "'\''."
        elif verb == "push":
            for push_arg in args:
                if push_arg.startswith("--force") or push_arg == "--delete" or push_arg.startswith("+") or push_arg.startswith(":"):
                    return True, "Destructive or force push detected in '\''git push " + " ".join(args) + "'\''."
                if re.match(r"^-[^-]*[fd]", push_arg):
                    return True, "Destructive or force push detected in '\''git push " + " ".join(args) + "'\''."
            for push_arg in args:
                if push_arg in ("--delete", "-d"):
                    return True, "Destructive branch deletion detected in '\''git push " + " ".join(args) + "'\''."
        return False, ""

    full_str = " ".join(tokens)
    sql_blocked, sql_reason = inspect_sql(full_str)
    if sql_blocked:
        return True, "Destructive SQL operation detected in '\''" + full_str + "'\'': " + sql_reason

    if re.search(r"\b(DROP\s+(DATABASE|SCHEMA|TABLE|VIEW)|TRUNCATE\s+TABLE|TRUNCATE\s+[a-zA-Z0-9_]+|ALTER\s+TABLE\s+[a-zA-Z0-9_.]+\s+DROP\s+COLUMN)\b", full_str, re.IGNORECASE):
        return True, "Destructive SQL query detected in '\''" + full_str + "'\''."

    return False, ""

atomic_cmds = parse_command_string(cmd_str)
for ac in atomic_cmds:
    blocked, reason = check_atomic_command(ac)
    if blocked:
        print("BLOCKED: " + reason)
        sys.exit(2)

sys.exit(0)
' "$COMMAND" 2>&1) || exit_status=$?

  if [ $exit_status -eq 2 ]; then
    echo "$python_output" >&2
    echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
    exit 2
  elif [ $exit_status -ne 0 ]; then
    # Python error fallback
    echo "$python_output" >&2
    exit $exit_status
  fi
  exit 0
fi

# Fallback basic inspection when python3 is not available
if echo "$COMMAND" | grep -qiE '\b(DROP[[:space:]]+(DATABASE|SCHEMA|TABLE|VIEW)|TRUNCATE[[:space:]]+TABLE)\b'; then
  echo "BLOCKED: Destructive SQL query detected in '$COMMAND'." >&2
  echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
  exit 2
fi

if [[ "$COMMAND" =~ git[[:space:]]+reset[[:space:]]+--hard ]]; then
  echo "BLOCKED: 'git reset --hard' destroys working tree modifications." >&2
  echo "Autonomous execution halted by sadskill safety guardrail (protocols/safety.md)." >&2
  exit 2
fi

exit 0
