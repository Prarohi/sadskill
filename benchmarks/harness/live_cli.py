"""Live CLI execution for C1 tasks.

CALL ONLY after explicit user opt-in, inside an external disposable VM/container.
CLI sandbox flags do not isolate Python evaluators. Never store raw transcripts
or claim an absent token measurement.
"""
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_VALID_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def build_prompt(task, condition):
    original = task["prompt"]
    if condition == "plain":
        return original
    if condition == "sadskill":
        source = (_ROOT / "skills/sadskill/SKILL.md").read_text(encoding="utf-8")
        return "Follow these Sadskill instructions:\n" + source + "\n\nTASK:\n" + original
    if condition == "competitor":
        return ("Use a generic structured engineering workflow: inspect, plan, "
                "implement, test edge cases, and report evidence.\n\nTASK:\n" + original)
    raise ValueError("Unknown benchmark condition")


def _num(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def parse_usage(name, output):
    try:
        if name == "codex":
            last = None
            for line in output.splitlines():
                if line.strip():
                    event = json.loads(line)
                    if event.get("type") == "turn.completed":
                        last = event
            if last is None:
                return None
            u = last.get("usage") or {}
            return _num(u.get("input_tokens")), _num(u.get("output_tokens"))
        result = json.loads(output)
        if not isinstance(result, dict) or result.get("error") or result.get("is_error"):
            return None
        u = result.get("usage", {}) if name == "claude" else result.get("stats", {})
        if not isinstance(u, dict):
            return None
        if name == "claude":
            return _num(u.get("input_tokens")), _num(u.get("output_tokens"))
        return (_num(u.get("inputTokens", u.get("totalInputTokens"))),
                _num(u.get("outputTokens", u.get("totalOutputTokens"))))
    except (ValueError, AttributeError, TypeError):
        return None


def execute_live(task, condition, workspace, name, model):
    if name not in ("codex", "claude", "gemini") or not _VALID_MODEL.fullmatch(model):
        return {"status": "NOT_EXECUTED_INVALID_CONFIGURATION", "reason": "Unsupported provider/model"}
    binary = shutil.which(name)
    if not binary:
        return {"status": "NOT_EXECUTED_NO_CLI", "reason": "Authenticated CLI is not installed"}
    prompt = build_prompt(task, condition)
    base = {
        "task_id": task["id"], "provider": name, "model": model,
        "condition": condition, "synthetic": False,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "input_tokens": None, "output_tokens": None, "tool_calls": None,
    }
    max_time = max(10, min(int(task.get("budget", {}).get("max_time_seconds", 60)), 180))
    if name == "codex":
        cmd = [binary, "exec", "--sandbox", "workspace-write", "--ephemeral",
               "--skip-git-repo-check", "--json", "--model", model, prompt]
    elif name == "claude":
        cmd = [binary, "-p", prompt, "--output-format", "json", "--model", model,
               "--max-turns", str(max(1, min(int(task.get("budget", {}).get("max_turns", 4)), 10))),
               "--permission-mode", "dontAsk",
               "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep"]
    else:
        cmd = [binary, "--sandbox", "--approval-mode", "auto_edit",
               "--output-format", "json", "--model", model, "--prompt", prompt]
    started = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=str(workspace), capture_output=True,
                                text=True, timeout=max_time, check=False)
    except subprocess.TimeoutExpired:
        return {**base, "status": "FAILED_TIMEOUT",
                "wall_clock_seconds": round(time.monotonic() - started, 3)}
    except OSError:
        return {**base, "status": "NOT_EXECUTED_CLI_ERROR"}
    elapsed = round(time.monotonic() - started, 3)
    if result.returncode:
        return {**base, "status": "FAILED_CLI", "exit_code": result.returncode,
                "reason": "CLI failed; raw stderr intentionally withheld",
                "wall_clock_seconds": elapsed}
    tokens = parse_usage(name, result.stdout)
    if tokens is None:
        return {**base, "status": "FAILED_UNVERIFIABLE_OUTPUT",
                "wall_clock_seconds": elapsed}
    return {**base, "status": "COMPLETED_REAL", "input_tokens": tokens[0],
            "output_tokens": tokens[1], "wall_clock_seconds": elapsed,
            "exit_code": result.returncode}
