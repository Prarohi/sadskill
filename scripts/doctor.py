#!/usr/bin/env python3
"""
sadskill Doctor & Capability Diagnostic Tool (v0.3.0)
Inspects agent skill installations, command hooks, and safety registrations across
Claude Code, OpenAI Codex, Cursor, Google Antigravity, and Gemini CLI.
Accurately reports status: NOT_INSTALLED, AVAILABLE, REGISTERED, ACTIVE, or UNSUPPORTED.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_claude_hook():
    home = Path.home()
    hook_file = home / ".claude" / "hooks" / "git-guardrail.sh"
    settings_file = home / ".claude" / "settings.json"

    if not hook_file.exists():
        return "NOT_INSTALLED", "Hook file ~/.claude/hooks/git-guardrail.sh not found."

    # Hook is present, check registration in settings.json
    registered = False
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            # Check for PreToolUse hook configuration
            hooks_config = settings.get("hooks", {})
            pre_tool = hooks_config.get("PreToolUse", [])
            for item in pre_tool:
                cmd_str = item.get("command", "") if isinstance(item, dict) else str(item)
                if "git-guardrail.sh" in cmd_str:
                    registered = True
                    break
        except Exception:
            pass

    if not registered:
        return (
            "AVAILABLE",
            "Hook file is placed at ~/.claude/hooks/git-guardrail.sh, but not yet registered in ~/.claude/settings.json PreToolUse hooks.",
        )

    # If registered, simulate benign execution to verify ACTIVE status
    try:
        res = subprocess.run(
            ["bash", str(hook_file)],
            input='{"tool_name": "Bash", "tool_input": {"command": "git status"}}',
            text=True,
            capture_output=True,
            timeout=5,
        )
        if res.returncode == 0:
            return "ACTIVE", "Hook is registered in ~/.claude/settings.json and actively validating tool invocations."
        else:
            return "REGISTERED", f"Hook is registered, but test execution exited with code {res.returncode}."
    except Exception as e:
        return "REGISTERED", f"Hook is registered, but test execution failed: {e}"


def enable_claude_hooks():
    """Opt-in, idempotent registration of git-guardrail.sh in ~/.claude/settings.json."""
    home = Path.home()
    hook_file = home / ".claude" / "hooks" / "git-guardrail.sh"
    settings_file = home / ".claude" / "settings.json"

    if not hook_file.exists():
        print(f"Error: Guardrail hook not found at {hook_file}. Run ./install.sh first.", file=sys.stderr)
        return 1

    settings = {}
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    settings = data
        except Exception as e:
            print(f"Warning: Could not parse existing settings.json: {e}", file=sys.stderr)

    hooks_config = settings.setdefault("hooks", {})
    if not isinstance(hooks_config, dict):
        hooks_config = {}
        settings["hooks"] = hooks_config

    pre_tool = hooks_config.setdefault("PreToolUse", [])
    if not isinstance(pre_tool, list):
        pre_tool = []
        hooks_config["PreToolUse"] = pre_tool

    already_registered = False
    for item in pre_tool:
        cmd_str = item.get("command", "") if isinstance(item, dict) else str(item)
        if "git-guardrail.sh" in cmd_str:
            already_registered = True
            break

    if not already_registered:
        hook_entry = {
            "matcher": "Bash",
            "command": str(hook_file.resolve()),
        }
        pre_tool.append(hook_entry)

        settings_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_settings = settings_file.with_name(f"{settings_file.name}.tmp.{os.getpid()}")
        try:
            with open(tmp_settings, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_settings, settings_file)
            print(f"   [SUCCESS] Registered git-guardrail.sh in {settings_file}", file=sys.stderr)
        except Exception as e:
            if tmp_settings.exists():
                tmp_settings.unlink()
            print(f"Error saving {settings_file}: {e}", file=sys.stderr)
            return 1
    else:
        print(f"   [INFO] git-guardrail.sh is already registered in {settings_file}", file=sys.stderr)

    return 0


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


def run_doctor(target_dir=None, json_output=False):
    results = {}

    status_claude, msg_claude = check_claude_hook()
    results["claude_hook"] = {"status": status_claude, "details": msg_claude}

    status_codex, msg_codex = check_codex()
    results["codex"] = {"status": status_codex, "details": msg_codex}

    status_cursor, msg_cursor = check_cursor(target_dir)
    results["cursor"] = {"status": status_cursor, "details": msg_cursor}

    status_agy, msg_agy = check_antigravity()
    results["antigravity_gemini"] = {"status": status_agy, "details": msg_agy}

    if json_output:
        print(json.dumps(results, indent=2))
        return 0

    print("==================================================")
    print("      sadskill Capability & Hook Diagnostic       ")
    print("==================================================")
    for agent, info in results.items():
        print(f"\n[{agent.upper()}] Status: {info['status']}")
        print(f"  {info['details']}")
    print("\n==================================================")
    return 0


def main():
    parser = argparse.ArgumentParser(description="sadskill Doctor Diagnostic Tool")
    parser.add_argument("--target", help="Target project workspace for Cursor inspection")
    parser.add_argument("--enable-hooks", action="store_true", help="Opt-in registration of git-guardrail.sh in ~/.claude/settings.json")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    if args.enable_hooks:
        ret = enable_claude_hooks()
        if ret != 0:
            sys.exit(ret)

    sys.exit(run_doctor(target_dir=args.target, json_output=args.json))


if __name__ == "__main__":
    main()
