#!/usr/bin/env python3
"""Fail-closed Sadskill version, CI, and reproducible release packaging gates."""
import argparse
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?")
SHA = re.compile(r"[0-9a-f]{40}")
# GitHub Actions app ID. Require trusted provenance, not just a spoofable check name.
GITHUB_ACTIONS_APP_ID = 15368
REQUIRED_CHECKS = (
    "Verify sadskill (Node 20)", "Verify sadskill (Node 22)",
    "Native PostgreSQL RLS", "CodeQL Python security analysis",
    "Native macOS install/restore smoke",
    "Native Windows skill-content smoke (not companion CLI)",
)


class ReleaseError(ValueError):
    pass


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def git(*args, binary=False):
    result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=False)
    if result.returncode:
        raise ReleaseError("invalid Git checkout or missing release tag")
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def changelog(version):
    content = read("CHANGELOG.md")
    heads = list(re.finditer(r"^## \[([^\]]+)\] - ([^\n]+)$", content, re.M))
    if not heads or heads[0].group(1) != version:
        raise ReleaseError("CHANGELOG first version must match VERSION")
    if sum(head.group(1) == version for head in heads) != 1:
        raise ReleaseError("duplicate CHANGELOG version")
    status = heads[0].group(2).strip()
    if status != "Unreleased":
        try:
            if not re.fullmatch(r"20\d\d-\d{2}-\d{2}", status):
                raise ValueError("invalid release date format")
            date.fromisoformat(status)
        except ValueError as exc:
            raise ReleaseError("CHANGELOG must use Unreleased or a valid YYYY-MM-DD date") from exc
    body = content[heads[0].end():heads[1].start() if len(heads) > 1 else len(content)].strip()
    if not re.search(r"(?m)^### ", body):
        raise ReleaseError("CHANGELOG current entry needs substantive release notes")
    return status, body


def check(tag=None):
    version = read("VERSION").strip()
    if not SEMVER.fullmatch(version):
        raise ReleaseError("VERSION must be canonical SemVer without leading v")
    if json.loads(read("plugin.json")).get("version") != version:
        raise ReleaseError("plugin.json differs from VERSION")
    skill = read("skills/sadskill/SKILL.md").split("---", 2)
    if len(skill) < 3 or not re.search(rf"(?m)^  version: {re.escape(version)}\s*$", skill[1]):
        raise ReleaseError("SKILL.md differs from VERSION")
    banner = re.search(r"(?m)^> Version: `v([^`]+)`([^\n]*)", read("README.md"))
    if not banner or banner.group(1) != version:
        raise ReleaseError("README version banner differs from VERSION")
    if f'version="sadskill {version}"' not in read("scripts/sad_cli.py"):
        raise ReleaseError("CLI --version differs from VERSION")
    status, _ = changelog(version)
    if tag is not None:
        if tag != "v" + version:
            raise ReleaseError("tag must equal v + VERSION")
        if status == "Unreleased":
            raise ReleaseError("CHANGELOG release date is missing")
        if "release candidate" in banner.group(2):
            raise ReleaseError("README still claims release candidate")
        if git("rev-parse", "HEAD") != git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"):
            raise ReleaseError("tag does not match the exact HEAD")
    return version


def notes(tag):
    version = check(tag)
    _, body = changelog(version)
    return f"# Sadskill {tag}\n\n{body}\n"


def verify_checks(report, sha):
    if not SHA.fullmatch(sha) or not isinstance(report, dict) or not isinstance(report.get("check_runs"), list):
        raise ReleaseError("invalid exact-head check report")
    latest = {}
    for run in sorted(report["check_runs"], key=lambda r: r.get("id", 0), reverse=True):
        name = run.get("name")
        if (
            run.get("head_sha") == sha
            and name in REQUIRED_CHECKS
            and isinstance(run.get("app"), dict)
            and run["app"].get("id") == GITHUB_ACTIONS_APP_ID
            and name not in latest
        ):
            latest[name] = run
    for name in REQUIRED_CHECKS:
        run = latest.get(name)
        if not run or run.get("status") != "completed" or run.get("conclusion") != "success":
            raise ReleaseError("required check missing, pending or failed: " + name)


def package(tag, dest):
    version = check(tag)
    dest.mkdir(parents=True, exist_ok=True)
    prefix = f"sadskill-{version}/"
    tar_bytes = git("archive", "--format=tar", f"--prefix={prefix}", "HEAD", binary=True)
    tar_path = dest / f"sadskill-{version}.tar.gz"
    with tar_path.open("wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", filename="", mtime=0, compresslevel=9) as zipped:
            zipped.write(tar_bytes)
    zip_path = dest / f"sadskill-{version}.zip"
    zip_path.write_bytes(git("archive", "--format=zip", f"--prefix={prefix}", "HEAD", binary=True))
    (dest / "SOURCE_COMMIT.txt").write_text(git("rev-parse", "HEAD") + "\n", encoding="utf-8")
    (dest / "RELEASE_NOTES.md").write_text(notes(tag), encoding="utf-8")
    files = [tar_path, zip_path, dest / "SOURCE_COMMIT.txt", dest / "RELEASE_NOTES.md"]
    (dest / "SHA256SUMS.txt").write_text(
        "".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in files),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("check").add_argument("--tag")
    commands.add_parser("notes").add_argument("--tag", required=True)
    pack = commands.add_parser("package")
    pack.add_argument("--tag", required=True)
    pack.add_argument("--out", type=Path, required=True)
    checks = commands.add_parser("checks")
    checks.add_argument("--sha", required=True)
    checks.add_argument("--json-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "check":
            print("Release metadata valid: v" + check(args.tag))
        elif args.action == "notes":
            print(notes(args.tag), end="")
        elif args.action == "package":
            package(args.tag, args.out)
            print("Release candidate assets prepared: " + str(args.out))
        else:
            verify_checks(json.loads(args.json_file.read_text()), args.sha)
            print("Required exact-head CI checks verified")
    except (ReleaseError, OSError, ValueError) as exc:
        print("RELEASE GATE FAILED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
