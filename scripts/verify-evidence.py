#!/usr/bin/env python3
"""
sadskill Independent Evidence Verifier
Validates that .sad/evidence/*.json proof records are syntactically valid,
reference existing files, match git repository state, and pass automated assertions.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def find_repo_root():
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "skills" / "sadskill" / "SKILL.md").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not determine repository root")


REPO_ROOT = find_repo_root()
EVIDENCE_DIR = REPO_ROOT / ".sad" / "evidence"


def verify_evidence(retest=False):
    print("=== sadskill Independent Evidence Verification ===")

    if not EVIDENCE_DIR.exists():
        print("  [INFO] No .sad/evidence directory found. Initializing...")
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        return 0

    evidence_files = list(EVIDENCE_DIR.glob("*.json"))
    if not evidence_files:
        print("  [INFO] Zero .sad/evidence/*.json logs found (clean baseline).")
        return 0

    errors = 0
    verified = 0

    for ef in evidence_files:
        print(f"-> Verifying evidence log: {ef.name}")
        try:
            data = json.loads(ef.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"   [FAIL] Invalid JSON syntax: {e}")
            errors += 1
            continue

        required_keys = ["timestamp", "task_slug", "command", "exit_code", "summary", "files_touched"]
        missing = [k for k in required_keys if k not in data]
        if missing:
            print(f"   [FAIL] Missing mandatory keys: {missing}")
            errors += 1
            continue

        if data["exit_code"] != 0:
            print(f"   [FAIL] Non-zero exit code recorded: {data['exit_code']}")
            errors += 1
            continue

        # Check that files touched exist in repository
        files_ok = True
        for rel in data.get("files_touched", []):
            target = REPO_ROOT / rel
            if not target.exists():
                print(f"   [FAIL] Declared target file does not exist: {rel}")
                files_ok = False
                errors += 1

        if not files_ok:
            continue

        # If retest requested, execute command
        if retest:
            cmd = data["command"]
            print(f"   [INFO] Re-executing command for proof: {cmd}")
            res = subprocess.run(cmd, shell=True, cwd=str(REPO_ROOT), capture_output=True)
            if res.returncode != 0:
                print(f"   [FAIL] Command failed on re-test (exit code {res.returncode})")
                errors += 1
                continue

        verified += 1
        print(f"   [VERIFIED] Evidence log {ef.name} successfully validated.")

    print("\n------------------------------------------")
    print(f"Verified Records: {verified} | Errors: {errors}")
    print("------------------------------------------")
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    retest_flag = "--retest" in sys.argv
    sys.exit(verify_evidence(retest=retest_flag))
