#!/usr/bin/env python3
"""
Automated Grader for Tenant Isolation Benchmark Fixture
Executes test_service.py in an isolated subprocess and reports behavioral pass/fail.
"""

import subprocess
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent


def grade_fixture():
    print(f"-> Executing real behavioral tests in {FIXTURE_DIR.name}...")
    res = subprocess.run(
        [sys.executable, "-m", "unittest", "test_service.py"],
        cwd=str(FIXTURE_DIR),
        capture_output=True,
        text=True,
        timeout=15,
    )

    if res.returncode == 0:
        print("  ✓ PASS: All tenant isolation tests passed cleanly.")
        return 0
    else:
        print(f"  ❌ FAIL: Tenant isolation tests failed (exit code {res.returncode}):")
        print(res.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(grade_fixture())
