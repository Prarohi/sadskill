#!/usr/bin/env python3
"""
sadskill Doctor & Capability Diagnostic Tool (v0.3.0)

Inspects agent skill installations, command hooks, and safety registrations
across Claude Code, OpenAI Codex, Cursor, Google Antigravity, and Gemini CLI.

Hook status labels are TRUTHFUL — a local simulation can never claim the
hook is active inside a real agent host:

  NOT_INSTALLED       hook script not found on disk
  AVAILABLE           hook script present, not referenced by settings.json
  REGISTERED          a PreToolUse matcher for Bash references the hook, but
                      the script is missing or local simulation did not pass
  LOCAL_TEST_PASSED   registered AND a benign local simulation exited 0
                      (still does NOT prove the host loaded the hook)
  HOST_VERIFIED_ACTIVE  set ONLY via explicit user confirmation flag
                      (--confirm-active); never assigned automatically
  UNKNOWN             settings.json exists but could not be parsed

Claude Code hook registration uses the OFFICIAL nested settings schema:

  {"hooks": {"PreToolUse": [
      {"matcher": "Bash",
       "hooks": [{"type": "command", "command": "<abs path>"}]}
  ]}}

Legacy flat entries written by earlier sadskill versions ({"matcher": ...,
"command": ...}) are detected, migrated to the nested schema on
--enable-hooks, and remain readable for diagnostics. Registration is
idempotent (matched by resolved hook path), removes only sadskill-owned
entries on --disable-hooks, preserves all unrelated user settings and
hooks, and always backs up settings.json before any modification.
"""

import argparse
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOK_BASENAME = "git-guardrail.sh"
HOOK_FILE = Path.home() / ".claude" / "hooks" / HOOK_BASENAME
SETTINGS_FILE = Path.home() / ".claude" / "settings.json"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_CORRUPT = 3


def _is_our_command(cmd):
    """Ownership test for the exact Sadskill hook path.

    Matching only the basename could remove another tool's unrelated hook
    named git-guardrail.sh.
    """
    if not isinstance(cmd, str) or not cmd:
        return False
    try:
        expected = HOOK_FILE.resolve(strict=False)
        tokens = shlex.split(cmd)
        if not tokens:
            return False

        def resolves_to_hook(token):
            # Support the portable command shape documented for settings.json
            # without expanding arbitrary shell variables or evaluating input.
            if token in {"$HOME", "${HOME}"}:
                token = str(Path.home())
            else:
                for prefix in ("$HOME/", "${HOME}/"):
                    if token.startswith(prefix):
                        token = str(Path.home() / token[len(prefix):])
                        break
            return Path(token).expanduser().resolve(strict=False) == expected

        # A hook is owned only when the command invokes that exact path as
        # its executable, or when a supported shell directly interprets it.
        # A matching argument (for example `/bin/echo <hook path>`) is not
        # evidence of ownership and must never be removed.
        if resolves_to_hook(tokens[0]):
            return True
        if len(tokens) >= 2 and Path(tokens[0]).name in {
            "bash", "sh", "dash", "zsh", "ksh"
        }:
            return resolves_to_hook(tokens[1])
        return False
    except (OSError, ValueError):
        return False


def _iter_hook_groups(settings):
    """Yield (event, item) for every matcher-level entry in settings hooks,
    tolerating malformed shapes."""
    hooks_config = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks_config, dict):
        return
    for event, groups in hooks_config.items():
        if not isinstance(groups, list):
            continue
        for item in groups:
            if isinstance(item, dict):
                yield event, item


def _our_flat_items(settings):
    """Legacy flat entries written by older sadskill versions."""
    for _event, item in _iter_hook_groups(settings):
        if "hooks" in item:
            continue
        if _is_our_command(item.get("command")):
            yield item


def _our_nested_subhooks(settings):
    """Yield (group_item, subhook) for official-schema entries owned by
    sadskill."""
    for _event, item in _iter_hook_groups(settings):
        subhooks = item.get("hooks")
        if not isinstance(subhooks, list):
            continue
        for sub in subhooks:
            if isinstance(sub, dict) and _is_our_command(sub.get("command")):
                yield item, sub


def _matcher_applies_to_bash(item):
    """Whether a matcher is restricted to the exact Bash tool name.

    Registration must not run the command guardrail on arbitrary tool input.
    Omitted, wildcard, multi-tool, and regex matchers are normalized to the
    exact Bash matcher instead of being interpreted by Python as JavaScript.
    """
    if "matcher" not in item:
        return False
    matcher = item["matcher"]
    if not isinstance(matcher, str):
        return False
    if matcher in ("", "*"):
        return False
    if re.fullmatch(r"[A-Za-z0-9_ ,|-]+", matcher):
        names = [name.strip() for name in re.split(r"[|,]", matcher)]
        return bool(names) and all(name == "Bash" for name in names)
    return False


def _group_has_our_command(item):
    """True only if this matcher group invokes Sadskill for Bash."""
    if not _matcher_applies_to_bash(item):
        return False
    if "hooks" not in item:
        return _is_our_command(item.get("command")) and "if" not in item
    subhooks = item.get("hooks")
    return isinstance(subhooks, list) and any(
        isinstance(sub, dict)
        and sub.get("type") == "command"
        and _is_our_command(sub.get("command"))
        and "if" not in sub
        for sub in subhooks
    )


def _normalize_owned_pretool_hooks(groups):
    """Leave one unrestricted Sadskill handler under an exact Bash matcher.

    Preserve unrelated matcher groups and handlers. Sadskill's own older or
    filtered registrations are safe to normalize because their command path
    identifies ownership; retaining an unverified regex beside a new exact
    registration could execute the same guardrail twice.
    """
    records = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            continue
        for sub in group["hooks"]:
            if isinstance(sub, dict) and _is_our_command(sub.get("command")):
                records.append((group, sub))
    if not records:
        return False
    if (len(records) == 1
            and _group_has_our_command(records[0][0])
            and records[0][1].get("type") == "command"
            and "if" not in records[0][1]):
        return False

    normalized = None
    common_command = None
    common_options = None
    for _group, sub in records:
        normalized = dict(sub)
        # The hook path proves ownership, but optional command arguments may
        # be user-configured. Preserve the complete command string verbatim.
        normalized["type"] = "command"
        normalized.pop("if", None)
        command = normalized.get("command")
        if not isinstance(command, str):
            return None
        options = dict(normalized)
        options.pop("command", None)
        if common_command is None:
            common_command = command
            common_options = options
        elif command != common_command or options != common_options:
            # Different arguments or execution options may be deliberate.
            # Compare command strings exactly: shell quoting can change
            # expansion even when shlex produces the same token list.
            return None

    new_groups = []
    placed = False
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            new_groups.append(group)
            continue
        owned = [
            sub for sub in group["hooks"]
            if isinstance(sub, dict) and _is_our_command(sub.get("command"))
        ]
        if not owned:
            new_groups.append(group)
            continue
        remaining = [
            sub for sub in group["hooks"]
            if not (isinstance(sub, dict) and _is_our_command(sub.get("command")))
        ]
        if remaining:
            group["hooks"] = remaining
            new_groups.append(group)
        elif not placed:
            group["matcher"] = "Bash"
            group["hooks"] = [normalized]
            new_groups.append(group)
            placed = True
        # A later group containing only Sadskill-owned entries is redundant
        # and is dropped. Mixed groups above retain every unrelated handler.

    if not placed:
        new_groups.append({
            "matcher": "Bash",
            "hooks": [normalized],
        })
    groups[:] = new_groups
    return True


def _is_registered(settings):
    """True when sadskill's hook is referenced by settings.json in either
    the official nested schema or the legacy flat format."""
    for event, item in _iter_hook_groups(settings):
        if event == "PreToolUse" and _group_has_our_command(item):
            return True
    return False


def _load_settings_for_check():
    """Returns (settings_or_None, error_or_None) without modifying anything."""
    if not SETTINGS_FILE.exists():
        return {}, None
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return None, exc
    if not isinstance(data, dict):
        return None, ValueError("settings.json is not a JSON object")
    return data, None


def _run_benign_simulation(hook_file):
    """Run the hook against a benign git-status payload. Returns True only
    on exit code 0. This proves the script runs; it can never prove the
    host registered or loaded it."""
    try:
        res = subprocess.run(
            ["bash", str(hook_file)],
            input='{"tool_name": "Bash", "tool_input": {"command": "git status"}}',
            text=True,
            capture_output=True,
            timeout=5,
        )
        return res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def check_claude_hook():
    """Truthful-status Claude hook inspection (official nested schema and
    legacy flat format)."""
    hook_file = HOOK_FILE
    settings_file = SETTINGS_FILE

    settings, error = _load_settings_for_check()
    if error is not None:
        return "UNKNOWN", f"Could not parse {settings_file}: {error}"

    if _is_registered(settings):
        if hook_file.exists():
            if _run_benign_simulation(hook_file):
                return "LOCAL_TEST_PASSED", (
                    "Hook is registered in settings.json and passed a benign "
                    "local simulation. This does NOT prove the Claude Code "
                    "host has loaded it; use --confirm-active after "
                    "verifying inside the host."
                )
            return "REGISTERED", (
                "Hook is registered in settings.json, but the benign local "
                "simulation did not exit 0."
            )
        return "REGISTERED", (
            f"Hook is registered in settings.json, but {hook_file} is "
            "missing on disk."
        )

    if hook_file.exists():
        return "AVAILABLE", (
            f"Hook file is placed at {hook_file}, but not yet registered in "
            f"{settings_file} PreToolUse hooks."
        )
    return "NOT_INSTALLED", f"Hook file {hook_file} not found."


def _backup_settings_bytes(original_bytes):
    """Collision-safe backup of settings.json bytes BEFORE modification.
    Returns the backup Path or raises RuntimeError."""
    stamp = time.strftime("%Y%m%d%H%M%S")
    base = f"{SETTINGS_FILE.name}.bak.{stamp}_{os.getpid()}"
    candidate = SETTINGS_FILE.with_name(base)
    counter = 0
    while candidate.exists():
        counter += 1
        candidate = SETTINGS_FILE.with_name(f"{base}_{counter}")
    try:
        fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(original_bytes)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        raise RuntimeError(f"could not write backup {candidate}: {exc}") from exc
    return candidate


def _atomic_write_settings(settings):
    """Durably replace settings.json with the given dict (2-space JSON)."""
    payload = json.dumps(settings, indent=2)
    if not payload.endswith("\n"):
        payload += "\n"
    tmp = SETTINGS_FILE.with_name(f"{SETTINGS_FILE.name}.tmp.{os.getpid()}")
    try:
        mode = stat.S_IMODE(SETTINGS_FILE.stat().st_mode) if SETTINGS_FILE.exists() else 0o600
    except OSError as exc:
        raise RuntimeError(f"could not inspect {SETTINGS_FILE}: {exc}") from exc
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, SETTINGS_FILE)
        dir_fd = os.open(str(SETTINGS_FILE.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        except OSError:
            pass
        finally:
            os.close(dir_fd)
    except OSError as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise RuntimeError(f"could not save {SETTINGS_FILE}: {exc}") from exc


def _read_settings_bytes_or_fail():
    """Load settings.json for mutation. FAILS CLOSED on any parse error —
    a corrupt or malformed file is never overwritten or repaired by us."""
    if SETTINGS_FILE.is_symlink():
        print(
            f"Error: {SETTINGS_FILE} is a symlink. Refusing to replace it; "
            "symlinked settings are not supported.",
            file=sys.stderr,
        )
        return None, None
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"Error: cannot read {SETTINGS_FILE}: {exc}", file=sys.stderr)
            return None, None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            print(
                f"Error: {SETTINGS_FILE} is not valid JSON ({exc}). "
                "Refusing to modify it; fix or remove the file manually.",
                file=sys.stderr,
            )
            return None, None
        if not isinstance(data, dict):
            print(
                f"Error: {SETTINGS_FILE} is not a JSON object. "
                "Refusing to modify it.",
                file=sys.stderr,
            )
            return None, None
        return raw, data
    return None, {}


def enable_claude_hooks():
    """Opt-in, idempotent, ownership-aware registration using the official
    nested hooks schema."""
    hook_file = HOOK_FILE
    settings_file = SETTINGS_FILE

    if not hook_file.exists():
        print(f"Error: Guardrail hook not found at {hook_file}. Run ./install.sh first.", file=sys.stderr)
        return EXIT_ERROR

    raw, settings = _read_settings_bytes_or_fail()
    if settings is None:
        return EXIT_CORRUPT

    hooks_config = settings.get("hooks")
    if "hooks" in settings and not isinstance(hooks_config, dict):
        print(
            f"Error: {settings_file} hooks has an unexpected shape; "
            "refusing to modify.",
            file=sys.stderr,
        )
        return EXIT_CORRUPT
    if hooks_config is None:
        hooks_config = {}
        settings["hooks"] = hooks_config

    changed = False

    # Migrate legacy flat sadskill entries into the official nested schema.
    flat_ours = list(_our_flat_items(settings))
    if flat_ours:
        flat_ids = {id(item) for item in flat_ours}
        for event, groups in list(hooks_config.items()):
            if not isinstance(groups, list):
                continue
            migrated = []
            for item in groups:
                if not isinstance(item, dict) or id(item) not in flat_ids:
                    migrated.append(item)
                    continue
                # In the legacy layout, matcher is group-level and the other
                # fields describe the command hook. Preserve the full command
                # string and its arguments during the schema conversion.
                subhook = {key: value for key, value in item.items() if key != "matcher"}
                subhook.setdefault("type", "command")
                group = {}
                if "matcher" in item:
                    group["matcher"] = item["matcher"]
                group["hooks"] = [subhook]
                migrated.append(group)
                changed = True
            if migrated != groups:
                hooks_config[event] = migrated
        if "PreToolUse" not in hooks_config:
            hooks_config["PreToolUse"] = []
            changed = True

    pre_tool = hooks_config.setdefault("PreToolUse", [])
    if not isinstance(pre_tool, list):
        print(
            f"Error: {settings_file} hooks.PreToolUse has an unexpected "
            "shape; refusing to modify.",
            file=sys.stderr,
        )
        return EXIT_CORRUPT

    normalized = _normalize_owned_pretool_hooks(pre_tool)
    if normalized is None:
        print(
            "Error: Sadskill has conflicting owned Claude hook commands or "
            "execution options. Refusing to rewrite settings.json; resolve "
            "the registrations manually, then retry.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    changed = normalized or changed

    already = any(
        _group_has_our_command(item)
        for item in pre_tool if isinstance(item, dict)
    )
    if already:
        print(f"   [INFO] {HOOK_BASENAME} is already registered in {settings_file}", file=sys.stderr)
        if not changed:
            return EXIT_OK
    else:
        nested_entry = {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": str(hook_file)}],
        }
        pre_tool.append(nested_entry)
        changed = True

    if not changed:
        return EXIT_OK

    try:
        backup = _backup_settings_bytes(raw if raw is not None else b"")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        _atomic_write_settings(settings)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"   [SUCCESS] Registered {HOOK_BASENAME} in {settings_file} (backup: {backup.name})", file=sys.stderr)
    return EXIT_OK


def disable_claude_hooks():
    """Ownership-aware unregistration: removes ONLY sadskill-owned entries
    (nested sub-hooks and legacy flat items pointing at the git-guardrail
    hook). Unrelated user hooks and settings are untouched."""
    raw, settings = _read_settings_bytes_or_fail()
    if settings is None:
        return EXIT_CORRUPT

    hooks_config = settings.get("hooks")
    if not isinstance(hooks_config, dict):
        print(f"   [INFO] No hooks configuration found in {SETTINGS_FILE}", file=sys.stderr)
        return EXIT_OK

    changed = False

    # Remove nested sadskill sub-hooks; drop matcher groups that become empty.
    for event, groups in list(hooks_config.items()):
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for item in groups:
            if not isinstance(item, dict):
                kept_groups.append(item)
                continue
            subhooks = item.get("hooks")
            if isinstance(subhooks, list) and any(
                isinstance(sub, dict) and _is_our_command(sub.get("command"))
                for sub in subhooks
            ):
                remaining = [
                    sub for sub in subhooks
                    if not (isinstance(sub, dict) and _is_our_command(sub.get("command")))
                ]
                if remaining:
                    item["hooks"] = remaining
                    kept_groups.append(item)
                changed = True
                continue
            if "hooks" not in item and _is_our_command(item.get("command")):
                changed = True
                continue
            kept_groups.append(item)
        if kept_groups != groups:
            hooks_config[event] = kept_groups
            if not kept_groups:
                del hooks_config[event]

    if not changed:
        print(f"   [INFO] No sadskill hook entries found in {SETTINGS_FILE}", file=sys.stderr)
        return EXIT_OK

    try:
        backup = _backup_settings_bytes(raw if raw is not None else b"")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        _atomic_write_settings(settings)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"   [SUCCESS] Removed sadskill hook entries from {SETTINGS_FILE} (backup: {backup.name})", file=sys.stderr)
    return EXIT_OK


def _has_file_content(path):
    """Require an actual, nonempty local artifact rather than its directory."""
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def check_codex():
    home = Path.home()
    skill_dir = home / ".codex" / "skills" / "sadskill"
    prompts_dir = home / ".codex" / "prompts"

    artifacts = [skill_dir / "SKILL.md"] + [
        prompts_dir / f"sad-{mode}.md"
        for mode in ("plan", "design", "backend", "sec", "analyze")
    ]
    if all(_has_file_content(path) for path in artifacts):
        return "INSTALLED", f"Skill installed at {skill_dir} with prompts at {prompts_dir}."
    elif skill_dir.exists() or any(path.exists() for path in artifacts):
        return "PARTIAL", f"Codex skill or command files are missing or empty under {skill_dir} and {prompts_dir}."
    return "NOT_INSTALLED", "No Codex skill or prompt directory found."


def check_cursor(target_dir=None):
    base = Path(target_dir).resolve() if target_dir else Path.cwd().resolve()
    rule_file = base / ".cursor" / "rules" / "sadskill.mdc"
    skill_dir = base / ".cursor" / "skills" / "sadskill"

    if _has_file_content(rule_file) and _has_file_content(skill_dir / "SKILL.md"):
        return "INSTALLED", f"Cursor rule and skill files are present in workspace: {base}. Their host activation is not verified."
    elif rule_file.exists() or skill_dir.exists():
        return "PARTIAL", f"Cursor rule or SKILL.md is missing or empty in workspace: {base}."
    return "NOT_INSTALLED", f"No Cursor configuration found in workspace: {base}."


def check_antigravity():
    home = Path.home()
    agy_skill = home / ".gemini" / "antigravity" / "skills" / "sadskill"
    gemini_skill = home / ".gemini" / "skills" / "sadskill"
    agents_skill = home / ".agents" / "skills" / "sadskill"

    for loc in (agy_skill, gemini_skill, agents_skill):
        if _has_file_content(loc / "SKILL.md"):
            return "INSTALLED", f"Skill discovered at {loc}."
    if any(loc.exists() for loc in (agy_skill, gemini_skill, agents_skill)):
        return "PARTIAL", "Antigravity or Gemini CLI skill directory exists, but SKILL.md is missing or empty."
    return "NOT_INSTALLED", "No Antigravity or Gemini CLI skill installation found."


def run_doctor(target_dir=None, json_output=False, confirm_active=False):
    results = {}

    status_claude, msg_claude = check_claude_hook()
    if confirm_active and status_claude == "LOCAL_TEST_PASSED":
        status_claude = "HOST_VERIFIED_ACTIVE"
        msg_claude = (
            "User explicitly confirmed (via --confirm-active) that the "
            "Claude Code host has verified this hook as active. " + msg_claude
        )
    results["claude_hook"] = {"status": status_claude, "details": msg_claude}

    status_codex, msg_codex = check_codex()
    results["codex"] = {"status": status_codex, "details": msg_codex}

    status_cursor, msg_cursor = check_cursor(target_dir)
    results["cursor"] = {"status": status_cursor, "details": msg_cursor}

    status_agy, msg_agy = check_antigravity()
    results["antigravity_gemini"] = {"status": status_agy, "details": msg_agy}

    if json_output:
        print(json.dumps(results, indent=2))
        return EXIT_OK

    print("==================================================")
    print("      sadskill Capability & Hook Diagnostic       ")
    print("==================================================")
    for agent, info in results.items():
        print(f"\n[{agent.upper()}] Status: {info['status']}")
        print(f"  {info['details']}")
    print("\n==================================================")
    return EXIT_OK


def main():
    parser = argparse.ArgumentParser(description="sadskill Doctor Diagnostic Tool")
    parser.add_argument("--target", help="Target project workspace for Cursor inspection")
    parser.add_argument("--enable-hooks", action="store_true",
                        help="Opt-in registration of git-guardrail.sh in ~/.claude/settings.json "
                             "using the official nested hooks schema")
    parser.add_argument("--disable-hooks", action="store_true",
                        help="Ownership-aware removal of sadskill hook entries from ~/.claude/settings.json")
    parser.add_argument("--confirm-active", action="store_true",
                        help="User attestation that the host itself verified the hook as active; "
                             "sets claude_hook status to HOST_VERIFIED_ACTIVE (never automatic)")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    if args.enable_hooks and args.disable_hooks:
        parser.error("--enable-hooks and --disable-hooks are mutually exclusive")

    if args.enable_hooks:
        ret = enable_claude_hooks()
        if ret != 0:
            sys.exit(ret)

    if args.disable_hooks:
        ret = disable_claude_hooks()
        if ret != 0:
            sys.exit(ret)

    sys.exit(run_doctor(
        target_dir=args.target,
        json_output=args.json,
        confirm_active=args.confirm_active,
    ))


if __name__ == "__main__":
    main()
