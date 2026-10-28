#!/usr/bin/env python3
"""
sadskill Doctor & Capability Diagnostic Tool (v0.3.0)

Inspects agent skill installations, command hooks, and safety registrations
across Claude Code, OpenAI Codex, Cursor, Google Antigravity, and Gemini CLI.

Hook status labels are TRUTHFUL — a local simulation can never claim the
hook is active inside a real agent host:

  NOT_INSTALLED       hook script not found on disk
  AVAILABLE           hook script present, not referenced by settings.json
  REGISTERED          referenced by settings.json (official nested schema or
                      legacy flat format), local simulation not passed
  LOCAL_TEST_PASSED   registered AND a benign local simulation exited 0
                      (still does NOT prove the host loaded the hook)
  HOST_VERIFIED_ACTIVE  set ONLY via explicit user confirmation flag
                      (--confirm-active); never assigned automatically
  UNKNOWN             settings.json exists but could not be parsed
  UNSUPPORTED         host/config combination not understood by this tool

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
import shutil
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
    """Ownership test: an entry belongs to sadskill when it points at the
    git-guardrail hook by basename (robust across sandboxed homes)."""
    if not isinstance(cmd, str) or not cmd:
        return False
    return Path(cmd).name == HOOK_BASENAME


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


def _is_registered(settings):
    """True when sadskill's hook is referenced by settings.json in either
    the official nested schema or the legacy flat format."""
    for _event, item in _iter_hook_groups(settings):
        if "hooks" in item:
            subhooks = item.get("hooks")
            if isinstance(subhooks, list) and any(
                isinstance(sub, dict) and _is_our_command(sub.get("command"))
                for sub in subhooks
            ):
                return True
        elif _is_our_command(item.get("command")):
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
        with open(candidate, "wb") as fh:
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
        with open(tmp, "w", encoding="utf-8") as fh:
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
    if not isinstance(hooks_config, dict):
        hooks_config = {}
        settings["hooks"] = hooks_config

    changed = False

    # Migrate legacy flat sadskill entries into the official nested schema.
    flat_ours = list(_our_flat_items(settings))
    if flat_ours:
        for event, groups in list(hooks_config.items()):
            if not isinstance(groups, list):
                continue
            kept = [
                item for item in groups
                if not (isinstance(item, dict) and "hooks" not in item
                        and _is_our_command(item.get("command")))
            ]
            if len(kept) != len(groups):
                hooks_config[event] = kept
                changed = True
        if not hooks_config.get("PreToolUse"):
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

    already = any(
        isinstance(sub, dict) and _is_our_command(sub.get("command"))
        for item in pre_tool if isinstance(item, dict)
        for sub in (item.get("hooks") or [])
    )
    if already:
        print(f"   [INFO] {HOOK_BASENAME} is already registered in {settings_file}", file=sys.stderr)
        return EXIT_OK

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


def check_codex():
    home = Path.home()
    skill_dir = home / ".codex" / "skills" / "sadskill"
    prompts_dir = home / ".codex" / "prompts"

    if skill_dir.exists() and (prompts_dir / "sad-plan.md").exists():
        return "INSTALLED", f"Skill installed at {skill_dir} with prompts at {prompts_dir}."
    elif skill_dir.exists():
        return "PARTIAL", f"Skill installed at {skill_dir}, prompts missing."
    return "NOT_INSTALLED", "No Codex skill or prompt directory found."


def check_cursor(target_dir=None):
    base = Path(target_dir).resolve() if target_dir else Path.cwd().resolve()
    rule_file = base / ".cursor" / "rules" / "sadskill.mdc"
    skill_dir = base / ".cursor" / "skills" / "sadskill"

    if rule_file.exists() and skill_dir.exists():
        return "INSTALLED", f"Cursor rule and skill active in workspace: {base}."
    elif rule_file.exists():
        return "PARTIAL", f"Cursor rule present at {rule_file}, workspace skill directory missing."
    return "NOT_INSTALLED", f"No Cursor configuration found in workspace: {base}."


def check_antigravity():
    home = Path.home()
    agy_skill = home / ".gemini" / "antigravity" / "skills" / "sadskill"
    gemini_skill = home / ".gemini" / "skills" / "sadskill"
    agents_skill = home / ".agents" / "skills" / "sadskill"

    for loc in (agy_skill, gemini_skill, agents_skill):
        if loc.exists():
            return "INSTALLED", f"Skill discovered at {loc}."
    return "NOT_INSTALLED", "No Antigravity or Gemini CLI skill installation found."


def run_doctor(target_dir=None, json_output=False, confirm_active=False):
    results = {}

    status_claude, msg_claude = check_claude_hook()
    if confirm_active and status_claude in ("REGISTERED", "LOCAL_TEST_PASSED"):
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
