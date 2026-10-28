#!/usr/bin/env python3
"""sadskill secure updater (v0.3.0) — opt-in, transactional, rollback-capable.

Update surfaces handled:
  1. installer-managed installs  (recorded in ~/.sadskill/install-manifest.json)
  2. external-manager installs   (npx skills / skills-lock.json) — NEVER
     silently replaced; apply refuses unless the user passes --adopt to take
     explicit ownership.
  3. vendored knowledge          (NOT handled here — reviewed PRs only)

Commands:
    status     local truth only — no network, no writes
    check      query latest release; never modifies the installation
    plan       exact transition preview; zero filesystem writes
    apply      opt-in transaction: stage → verify → backup → atomic apply
    rollback   recover the last update (also works after an interrupted apply)
    history    truthful transition log

Channels: stable (GitHub latest release), beta (latest incl. prereleases),
pinned (explicit --version required; never auto-updates).

Trust model: pinned repo identity sadafbabu/sadskill, HTTPS with timeouts,
bounded redirects and sizes, SHA-256 verification when a SHA256SUMS asset is
published, strict archive validation (no traversal/symlinks/devices/abs paths/
duplicate entries), and no downloaded code is ever executed.

SADSKILL_UPDATE_API_BASE may override the GitHub API endpoint for testing —
loopback addresses only (127.0.0.1, ::1, localhost). GITHUB_TOKEN (optional)
is sent as a Bearer header and never logged.

Exit codes: 0 ok / 1 error / 2 usage / 3 network-or-corrupt / 4 integrity /
5 conflict / 6 lock contention.
"""

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sadskill_core as core  # noqa: E402

REPO = "sadafbabu/sadskill"
REPO_OWNER, REPO_NAME = REPO.split("/", 1)
MANIFEST_FILE = Path.home() / ".sadskill" / "install-manifest.json"
STATE_DIR = Path.home() / ".sadskill"
INSTALL_STATE_FILE = STATE_DIR / "install-state.json"
HISTORY_FILE = STATE_DIR / "history.jsonl"
JOURNAL_FILE = STATE_DIR / "update-journal.json"
SKILLS_LOCK_FILE = Path.home() / ".skills-lock.json"

API_BASE_DEFAULT = "https://api.github.com"
API_BASE_ENV = "SADSKILL_UPDATE_API_BASE"
FAULT_ENV = "SADSKILL_FAULT"

HTTP_TIMEOUT = 15
MAX_REDIRECTS = 3
MAX_TARBALL_BYTES = 32 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_NET, EXIT_INTEGRITY, EXIT_CONFLICT, EXIT_LOCK = (
    0, 1, 2, 3, 4, 5, 6
)

TRUTHFUL_LABELS = (
    "NOT_INSTALLED", "AVAILABLE", "REGISTERED", "LOCAL_TEST_PASSED",
    "HOST_VERIFIED_ACTIVE", "UNKNOWN", "UNSUPPORTED",
)


class NetworkError(Exception):
    """Network-level failure (offline, timeout, HTTP error, rate limit)."""


class UsageError(Exception):
    """Invalid user input for the requested operation."""


class ConflictError(Exception):
    """User modification or unresolved state refuses the transition."""


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

class _RedirectCapper(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        count = getattr(req, "_sad_redirects", 0) + 1
        if count > MAX_REDIRECTS:
            raise NetworkError(f"too many redirects (>{MAX_REDIRECTS})")
        try:
            new = super().redirect_request(req, fp, code, msg, headers, newurl)
        except urllib.error.HTTPError as exc:
            raise NetworkError(f"redirect failed: {exc}") from exc
        new._sad_redirects = count
        return new


_OPENER = urllib.request.build_opener(_RedirectCapper())


def _loopback_allowed(base):
    parsed = urllib.parse.urlparse(base)
    return parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS


def _api_base():
    base = os.environ.get(API_BASE_ENV, "").strip()
    if base:
        if not _loopback_allowed(base):
            raise UsageError(
                f"{API_BASE_ENV} must be a loopback http URL for testing"
            )
        return base.rstrip("/")
    return API_BASE_DEFAULT


def _open(req, size_cap, dest_bytes=False):
    """Perform request with timeout; enforce response size cap."""
    try:
        resp = _OPENER.open(req, timeout=HTTP_TIMEOUT)
    except urllib.error.HTTPError as exc:
        if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
            raise NetworkError("GitHub API rate limit exceeded") from exc
        raise NetworkError(f"HTTP {exc.code} for {req.full_url}") from exc
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as exc:
        raise NetworkError(f"network error: {exc}") from exc

    chunks = []
    total = 0
    try:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > size_cap:
                raise NetworkError(
                    f"response exceeds {size_cap} byte limit"
                )
            chunks.append(chunk)
    except (socket.timeout, ConnectionError, OSError) as exc:
        raise NetworkError(f"network error during read: {exc}") from exc
    finally:
        resp.close()
    return b"".join(chunks), total


def http_get_json(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data, _ = _open(req, MAX_JSON_BYTES)
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NetworkError(f"invalid JSON from {url}: {exc}") from exc


def http_download(url, size_cap=MAX_TARBALL_BYTES):
    req = urllib.request.Request(url)
    token = os.environ.get("GITHUB_TOKEN", "")
    if token and urllib.parse.urlparse(url).hostname not in LOOPBACK_HOSTS:
        req.add_header("Authorization", "Bearer " + token)
    data, _ = _open(req, size_cap)
    return data


def fetch_release(channel):
    """Fetch release metadata for the channel; verifies repo identity."""
    base = _api_base()
    if channel == "stable":
        url = f"{base}/repos/{REPO}/releases/latest"
    elif channel == "beta":
        url = f"{base}/repos/{REPO}/releases?per_page=1"
    else:
        raise UsageError(f"channel {channel!r} does not support network checks")
    payload = http_get_json(url)
    release = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(release, dict):
        raise NetworkError("unexpected release payload")
    # Repo identity verification: release API URLs must reference our repo.
    evidence = json.dumps(release)
    if f"/repos/{REPO}/" not in evidence and f"/repos/{REPO}" not in evidence:
        raise NetworkError(
            f"release metadata does not reference {REPO}; refusing"
        )
    return release


def release_version(release):
    tag = release.get("tag_name") or ""
    try:
        return core.parse_version(tag)
    except ValueError as exc:
        raise NetworkError(f"release tag unparsable: {tag!r}") from exc


def release_digest(release, tarball_url):
    """Return expected sha256 for the tarball from a SHA256SUMS asset, else None."""
    assets = release.get("assets") or []
    for asset in assets:
        name = asset.get("name", "")
        if name.strip().lower() == "sha256sums.txt":
            url = asset.get("browser_download_url")
            if not url:
                return None
            data, _ = _open(
                urllib.request.Request(url), MAX_JSON_BYTES
            )
            text = data.decode("utf-8", errors="replace")
            tar_name = os.path.basename(urllib.parse.urlparse(tarball_url).path)
            for line in text.splitlines():
                fields = line.split()
                if len(fields) == 2 and fields[1] == tar_name:
                    return fields[0].lower()
            return None
    return None


# ---------------------------------------------------------------------------
# Archive validation + staging (never executes content)
# ---------------------------------------------------------------------------

def _member_ok(member, seen_names):
    name = member.name
    if name.startswith("/") or "\\" in name:
        raise core.IntegrityError(f"archive member unsafe path: {name!r}")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise core.IntegrityError(f"archive member escapes root: {name!r}")
    norm = "/".join(parts)
    if norm in seen_names:
        raise core.IntegrityError(f"duplicate archive member: {norm}")
    if member.issym() or member.islnk():
        raise core.IntegrityError(f"archive member is a link: {name!r}")
    if member.isdev() or member.isfifo():
        raise core.IntegrityError(f"archive member is device/fifo: {name!r}")
    if member.size > MAX_TARBALL_BYTES:
        raise core.IntegrityError(f"archive member too large: {name!r}")
    seen_names.add(norm)
    return parts, norm


def stage_archive(tar_bytes):
    """Validate + extract into a fresh staging dir. Returns (stage_dir, rel_files).

    Only regular files are written. Never writes outside the staging dir and
    never executes anything.
    """
    stage = Path(tempfile.mkdtemp(prefix="sadskill-stage.", dir=str(STATE_DIR)))
    seen = set()
    top_dirs = set()
    members = []
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar:
            for member in tar:
                parts, norm = _member_ok(member, seen)
                if member.isdir():
                    top_dirs.add(parts[0])
                members.append((member, parts, norm))
    except (tarfile.TarError, EOFError, OSError) as exc:
        shutil.rmtree(stage, ignore_errors=True)
        raise core.IntegrityError(f"archive unreadable: {exc}") from exc

    rel_files = []
    strip = 0
    file_tops = {parts[0] for member, parts, norm in members if member.isfile()}
    if top_dirs:
        if len(top_dirs) == 1 and next(iter(top_dirs)) not in ("skills", "commands"):
            strip = 1
        else:
            shutil.rmtree(stage, ignore_errors=True)
            raise core.IntegrityError(
                f"archive has unexpected top-level layout: {sorted(top_dirs)}"
            )
    elif file_tops:
        if len(file_tops) == 1 and next(iter(file_tops)) not in ("skills", "commands"):
            strip = 1
        else:
            shutil.rmtree(stage, ignore_errors=True)
            raise core.IntegrityError(
                f"archive has unexpected top-level layout: {sorted(file_tops)}"
            )
    for member, parts, norm in members:
        rel = "/".join(parts[strip:])
        if not rel:
            continue
        if member.isdir():
            (stage / rel).mkdir(parents=True, exist_ok=True)
            continue
        if not member.isfile():
            shutil.rmtree(stage, ignore_errors=True)
            raise core.IntegrityError(
                f"archive member is not a regular file: {norm}"
            )
        dest = stage / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        fobj = None
        try:
            with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar2:
                fobj = tar2.extractfile(member)
                if fobj is None:
                    raise core.IntegrityError(f"cannot read member: {norm}")
                dest.write_bytes(fobj.read())
        except (tarfile.TarError, OSError) as exc:
            shutil.rmtree(stage, ignore_errors=True)
            raise core.IntegrityError(f"archive extraction failed: {exc}") from exc
        rel_files.append(rel)
    return stage, rel_files


# ---------------------------------------------------------------------------
# Installation knowledge
# ---------------------------------------------------------------------------

_SKILL_AGENTS = ("claude", "codex", "gemini", "antigravity", "cursor_skill")

_AGENT_DIRS = {
    "claude": Path.home() / ".claude" / "skills" / "sadskill",
    "codex": Path.home() / ".codex" / "skills" / "sadskill",
    "gemini": Path.home() / ".gemini" / "skills" / "sadskill",
    "antigravity": Path.home() / ".gemini" / "antigravity" / "skills" / "sadskill",
    "cursor_skill": None,  # target-dependent, discovered from manifest
}


def detect_hosts():
    """Existing sadskill skill dirs + command/prompt files across hosts."""
    hosts = []
    manifest = core.load_manifest_data(MANIFEST_FILE)
    by_agent = {}
    for entry in manifest["entries"]:
        by_agent.setdefault(entry.get("agent", ""), []).append(entry)
    for agent, default in _AGENT_DIRS.items():
        candidates = [entry["destination"] for entry in by_agent.get(agent, [])]
        if default is not None:
            candidates.append(str(default))
        for cand in candidates:
            if cand and Path(cand).is_dir():
                hosts.append(agent)
                break
    for agent in ("claude_command", "codex_prompt", "claude_hook"):
        if by_agent.get(agent):
            hosts.append(agent)
    return sorted(set(hosts)), manifest, by_agent


def skills_lock_active():
    """True when a non-empty skills-lock.json exists (external manager)."""
    if not SKILLS_LOCK_FILE.exists():
        return False
    try:
        data = json.loads(SKILLS_LOCK_FILE.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return bool(data)


def installed_version(manifest):
    """Version from install-state.json, else SKILL.md frontmatter, else None."""
    try:
        state = json.loads(INSTALL_STATE_FILE.read_bytes().decode("utf-8"))
        if isinstance(state, dict) and state.get("version"):
            return str(state["version"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    for agent in _SKILL_AGENTS:
        default = _AGENT_DIRS.get(agent)
        candidates = [entry["destination"] for entry in manifest["entries"]
                      if entry.get("agent") == agent]
        if default is not None:
            candidates.append(str(default))
        for cand in candidates:
            skill_md = Path(cand) / "SKILL.md"
            if not cand or not skill_md.is_file():
                continue
            try:
                head = skill_md.read_text(
                    encoding="utf-8", errors="replace"
                )[:2048]
            except OSError:
                continue
            m = re.search(r"^\s*version:\s*['\"]?([0-9][0-9A-Za-z.+-]*)['\"]?\s*$",
                          head, re.MULTILINE)
            if m:
                return m.group(1)
    return None


def read_channel():
    try:
        state = json.loads(INSTALL_STATE_FILE.read_bytes().decode("utf-8"))
        if isinstance(state, dict) and state.get("channel"):
            return str(state["channel"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return None


def unmanaged_dests(manifest, by_agent):
    """Dest dirs that exist but have no manifest entry (unknown ownership)."""
    unmanaged = []
    known = {agent: {e["destination"] for e in entries}
             for agent, entries in by_agent.items()}
    all_known = set()
    for entries in known.values():
        all_known.update(entries)
    for agent, default in _AGENT_DIRS.items():
        if default is None:
            continue
        if default.is_dir() and str(default) not in all_known:
            unmanaged.append(("unmanaged", agent, str(default)))
    return unmanaged


# ---------------------------------------------------------------------------
# Update plan mapping
# ---------------------------------------------------------------------------

def build_transition(manifest, by_agent, rel_files):
    """Map staged rel paths → (destinations, manual steps, per-file actions)."""
    actions = []
    for rel in rel_files:
        if rel.startswith("skills/sadskill/"):
            inner = rel[len("skills/sadskill/"):]
            mapped = []
            for agent in _SKILL_AGENTS:
                for entry in by_agent.get(agent, []):
                    mapped.append(
                        (Path(entry["destination"]) / inner, entry, agent)
                    )
            if mapped:
                actions.append({"source": rel, "targets": mapped})
        elif rel.startswith("commands/claude/"):
            name = os.path.basename(rel)
            for entry in by_agent.get("claude_command", []):
                if os.path.basename(entry["destination"]) == name:
                    actions.append(
                        {"source": rel,
                         "targets": [(Path(entry["destination"]), entry,
                                      "claude_command")]}
                    )
        elif rel.startswith("commands/codex/"):
            name = os.path.basename(rel)
            for entry in by_agent.get("codex_prompt", []):
                if os.path.basename(entry["destination"]) == name:
                    actions.append(
                        {"source": rel,
                         "targets": [(Path(entry["destination"]), entry,
                                      "codex_prompt")]}
                    )
        if rel == "skills/sadskill/hooks/git-guardrail.sh":
            for entry in by_agent.get("claude_hook", []):
                actions.append(
                    {"source": rel,
                     "targets": [(Path(entry["destination"]), entry,
                                  "claude_hook")]}
                )
    return actions


def conflicts_for(actions):
    """User-modified destinations: current hash != manifest content_hash."""
    conflicts = []
    seen_entries = set()
    for action in actions:
        for dest, entry, agent in action["targets"]:
            entry_id = id(entry)
            # For skill directory entries, the manifest entry destination is a directory
            # and content_hash is the hash of the entire directory. Avoid checking
            # multiple files against the same directory entry.
            if entry_id in seen_entries:
                continue
            seen_entries.add(entry_id)

            # Use the manifest entry's destination for hash comparison
            manifest_dest = Path(entry["destination"])
            try:
                current = core.compute_sha256(manifest_dest)
            except core.IntegrityError:
                conflicts.append({"destination": str(manifest_dest),
                                  "reason": "unreadable"})
                continue
            recorded = entry.get("content_hash") or ""
            if recorded and current != recorded:
                conflicts.append({"destination": str(manifest_dest),
                                  "reason": "user modification"})
    return conflicts


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def history_append(record):
    line = json.dumps(record, sort_keys=True) + "\n"
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def apply_failure_env_fault():
    if os.environ.get(FAULT_ENV) == "after_backup":
        raise RuntimeError("simulated crash after backup (SADSKILL_FAULT)")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_status(args):
    hosts, manifest, by_agent = detect_hosts()
    version = installed_version(manifest)
    channel = read_channel()
    external = skills_lock_active()
    if external:
        ownership = "external-manager"
    elif unmanaged_dests(manifest, by_agent):
        ownership = "unmanaged"
    elif manifest["entries"]:
        ownership = "installer-managed"
    else:
        ownership = "unknown"
    result = {
        "command": "status",
        "version": version,
        "channel": channel,
        "hosts": hosts,
        "ownership": ownership,
        "manifest_entries": len(manifest["entries"]),
        "install_state": _read_json(INSTALL_STATE_FILE),
        "network_accessed": False,
    }
    return result, EXIT_OK


def cmd_check(args):
    channel = args.channel or read_channel() or "stable"
    if channel == "pinned":
        if not args.version:
            return {
                "command": "check", "channel": "pinned",
                "message": "pinned channel never auto-updates; pass --version "
                           "explicitly to inspect that release",
            }, EXIT_OK
        result = {
            "command": "check", "channel": "pinned", "version": args.version,
            "message": "pinned channel: updates are always explicit",
        }
        return result, EXIT_OK
    release = fetch_release(channel)
    latest = core.version_text(release_version(release))
    hosts, manifest, _ = detect_hosts()
    current = installed_version(manifest)
    up_to_date = current is not None and core.parse_version(
        current
    ) >= release_version(release)
    return {
        "command": "check",
        "repo": REPO,
        "channel": channel,
        "current": current,
        "latest": latest,
        "up_to_date": up_to_date,
        "release_url": release.get("html_url"),
        "modified_installation": False,
    }, EXIT_OK


def cmd_plan(args):
    channel = args.channel or read_channel() or "stable"
    if channel == "pinned" and not args.version:
        raise UsageError("pinned channel requires --version")
    hosts, manifest, by_agent = detect_hosts()
    current = installed_version(manifest)
    if channel in ("stable", "beta"):
        release = fetch_release(channel)
        target_ver = core.version_text(release_version(release))
        tarball_url = release.get("tarball_url")
        if not tarball_url:
            raise NetworkError("release has no tarball_url")
    else:
        target_ver = args.version
        tarball_url = None
    # Download + stage without writing outside ~/.sadskill staging.
    if tarball_url:
        tar_bytes = _download_verified(release, tarball_url)
        stage, rel_files = stage_archive(tar_bytes)
    else:
        raise UsageError("pinned channel plans require a network release lookup")
    try:
        actions = build_transition(manifest, by_agent, rel_files)
        conflicts = conflicts_for(actions)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {
        "command": "plan",
        "from_version": current,
        "to_version": target_ver,
        "files_affected": [
            {
                "source": a["source"],
                "destinations": [str(t[0]) for t in a["targets"]],
                "agents": [t[2] for t in a["targets"]],
            }
            for a in actions
        ],
        "manual_steps": _manual_steps(by_agent),
        "conflicts": conflicts,
        "backup_strategy": "per-destination copies under "
                           "~/.sadskill/backups/update-<version>-<ts>/",
        "rollback": "sadskill-update.py rollback (journal-based)",
        "zero_writes": True,
    }, EXIT_OK


def _manual_steps(by_agent):
    steps = []
    for agent in ("cursor",):
        for entry in by_agent.get(agent, []):
            steps.append(
                "cursor rule regeneration is manual: re-run ./install.sh "
                f"-a cursor for {entry['destination']}"
            )
    return steps


def _download_verified(release, tarball_url):
    tar_bytes, _ = _open(urllib.request.Request(tarball_url), MAX_TARBALL_BYTES)
    expected = release_digest(release, tarball_url)
    if expected is not None:
        actual = core.compute_sha256_of_bytes(tar_bytes)
        if actual != expected:
            raise core.IntegrityError(
                f"tarball digest mismatch: expected {expected}, got {actual}"
            )
    return tar_bytes


def cmd_apply(args):
    if args.dry_run:
        return cmd_plan(args)[0], EXIT_OK
    channel = args.channel or read_channel() or "stable"
    if channel == "pinned" and not args.version:
        raise UsageError("pinned channel requires --version for apply")
    hosts, manifest, by_agent = detect_hosts()

    # Ownership preflight.
    external = skills_lock_active()
    unmanaged = unmanaged_dests(manifest, by_agent)
    if (external or unmanaged) and not args.adopt:
        reasons = []
        if external:
            reasons.append(
                "external-manager detected (~/.skills-lock.json): silent "
                "replacement is not allowed"
            )
        for kind, agent, dest in unmanaged:
            reasons.append(f"{kind} install at {dest} (agent {agent})")
        return {
            "command": "apply", "refused": True,
            "reasons": reasons,
            "hint": "pass --adopt to take explicit ownership of these files",
        }, EXIT_ERROR

    if channel in ("stable", "beta"):
        release = fetch_release(channel)
        to_version = core.version_text(release_version(release))
        tarball_url = release.get("tarball_url")
        if not tarball_url:
            raise NetworkError("release has no tarball_url")
    else:
        # Pinned: resolve an explicit release by version tag (network).
        release = _fetch_pinned(args.version)
        to_version = args.version
        tarball_url = release.get("tarball_url")
        if not tarball_url:
            raise NetworkError("release has no tarball_url")

    current = installed_version(manifest)
    if current is not None and channel != "pinned":
        if core.parse_version(current) >= release_version(release):
            return {
                "command": "apply", "already_up_to_date": True,
                "version": current,
                "message": f"installation already at {current}; nothing to do",
            }, EXIT_OK

    tar_bytes = _download_verified(release, tarball_url)
    stage, rel_files = stage_archive(tar_bytes)
    try:
        actions = build_transition(manifest, by_agent, rel_files)
        if not actions:
            return {
                "command": "apply", "refused": True,
                "reasons": ["no installer-managed destinations in manifest"],
                "hint": "run ./install.sh first or pass --adopt",
            }, EXIT_ERROR
        conflicts = conflicts_for(actions)
        if conflicts and not args.force:
            return {
                "command": "apply", "refused": True, "conflicts": conflicts,
                "hint": "user modifications detected; pass --force after "
                        "reviewing (your modifications will be backed up)",
            }, EXIT_CONFLICT

        journal = Journal_path()
        journal.begin(current, to_version, str(stage), REPO, channel)
        try:
            journal.step("staged", {"files": len(rel_files)})
            backups_dir = STATE_DIR / "backups" / f"update-{to_version}-{time.time_ns()}"
            backups_dir.mkdir(parents=True, exist_ok=False)
            journal.step("backing_up", {"backups_dir": str(backups_dir)})

            # Pre-change checkpoints: copy each affected destination BEFORE apply.
            for action in actions:
                for dest, entry, agent in action["targets"]:
                    _backup_dest(dest, backups_dir, agent)
            journal.step("backed_up", {"backups_dir": str(backups_dir)})
            journal.data["backups_dir"] = str(backups_dir)
            journal._flush()

            apply_failure_env_fault()  # test hook: simulated crash after backup

            applied = {}
            for action in actions:
                for dest, entry, agent in action["targets"]:
                    staged = stage / action["source"]
                    written = _atomic_install_file(staged, Path(dest))
                    applied[str(dest)] = core.compute_sha256(written)
            journal.step("applied", {"destinations": applied})

            # Manifest update under the exclusive lock.
            with core.LockFile(MANIFEST_FILE):
                manifest = core.load_manifest_data(MANIFEST_FILE)
                for dest_str, new_hash in applied.items():
                    for entry in manifest["entries"]:
                        if entry["destination"] == dest_str or (
                            entry.get("agent") in _SKILL_AGENTS
                            and dest_str.endswith("/SKILL.md")
                            and Path(dest_str).parent == Path(entry["destination"])
                        ):
                            entry["backup_hash"] = entry.get("content_hash", "")
                            entry["content_hash"] = new_hash
                            entry["installed_at"] = time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                            )
                            entry.setdefault("updates", []).append(
                                {"version": to_version,
                                 "at": entry["installed_at"]}
                            )
                core.save_manifest_data(MANIFEST_FILE, manifest)
            journal.step("manifest_updated")

            core.atomic_write_text(
                INSTALL_STATE_FILE,
                json.dumps(
                    {
                        "version": to_version,
                        "updated_at": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                        ),
                        "channel": channel,
                    },
                    indent=2,
                )
                + "\n",
            )
            journal.step("install_state_written")
            journal.finish("done")
            history_append(
                {
                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "action": "update",
                    "from": current,
                    "to": to_version,
                    "channel": channel,
                    "conflicts_forced": bool(conflicts),
                }
            )
            return {
                "command": "apply", "applied": True,
                "from_version": current, "to_version": to_version,
                "backups_dir": str(backups_dir), "conflicts_forced": bool(conflicts),
            }, EXIT_OK
        except Exception as exc:
            journal.step("failure", {"error": str(exc)})
            journal.finish("interrupted")
            history_append(
                {
                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "action": "update_interrupted",
                    "from": current, "to": to_version,
                    "error": str(exc),
                }
            )
            if isinstance(exc, (core.IntegrityError, NetworkError, core.LockError, ConflictError)):
                raise
            raise ApplyFailure(str(exc)) from exc
    finally:
        shutil.rmtree(stage, ignore_errors=True)


class ApplyFailure(Exception):
    pass


def Journal_path():
    return core.Journal(JOURNAL_FILE)


def _fetch_pinned(version):
    try:
        core.parse_version(version)
    except ValueError as exc:
        raise UsageError(f"invalid pinned version: {exc}") from exc
    url = f"{_api_base()}/repos/{REPO}/releases/tags/v{version.lstrip('v')}"
    payload = http_get_json(url)
    if not isinstance(payload, dict) or "tag_name" not in payload:
        raise NetworkError(f"no release found for version {version}")
    evidence = json.dumps(payload)
    if f"/repos/{REPO}/" not in evidence:
        raise NetworkError(f"release metadata does not reference {REPO}")
    return payload


def _backup_dest(dest, backups_dir, agent):
    dest = Path(dest)
    if not dest.exists():
        return None
    rel = dest.name or "file"
    target = backups_dir / f"{agent}--{rel}"
    n = 1
    while target.exists():
        n += 1
        target = backups_dir / f"{agent}--{rel}--{n}"
    if dest.is_dir():
        shutil.copytree(dest, target, symlinks=True)
    else:
        shutil.copy2(dest, target)
    return target


def _atomic_install_file(staged, dest):
    """Copy a staged file to dest atomically; returns written path."""
    dest = Path(dest)
    if dest.exists() and dest.is_dir():
        dest = dest / staged.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".update-tmp.", dir=str(dest.parent))
    os.close(fd)
    shutil.copyfile(staged, tmp)
    if staged.name == "git-guardrail.sh":
        os.chmod(tmp, 0o755)
    os.replace(tmp, str(dest))
    core.fsync_dir(dest.parent)
    return dest


def cmd_rollback(args):
    journal_data = core.Journal.load(JOURNAL_FILE)
    if journal_data is None:
        return {
            "command": "rollback", "performed": False,
            "reason": "no update journal found",
        }, EXIT_ERROR
    backups_dir = journal_data.get("backups_dir")
    if not backups_dir or not Path(backups_dir).is_dir():
        return {
            "command": "rollback", "performed": False,
            "reason": "journal has no usable backups directory",
        }, EXIT_ERROR
    # Restore: journal 'applied' step lists post-apply hashes; backups map
    # agent--<name> files created pre-apply.
    applied = {}
    for step in journal_data.get("steps", []):
        if step.get("name") == "applied":
            applied = step.get("payload", {}).get("destinations", {})
    hosts, manifest, by_agent = detect_hosts()
    conflicts = []
    for dest_str, applied_hash in applied.items():
        dest = Path(dest_str)
        if not dest.exists():
            continue
        try:
            current_hash = core.compute_sha256(dest)
        except core.IntegrityError:
            conflicts.append(str(dest))
            continue
        if current_hash != applied_hash:
            conflicts.append(str(dest))
    if conflicts and not args.force:
        return {
            "command": "rollback", "performed": False,
            "conflicts": conflicts,
            "hint": "post-apply user modifications detected; pass --force "
                    "to back them up and roll back anyway",
        }, EXIT_CONFLICT

    # Copy each backup over its destination.
    backups = Path(backups_dir)
    restored = []
    for backup_file in sorted(backups.rglob("*")):
        if not backup_file.is_file() or backup_file.name.startswith("."):
            continue
        parts = backup_file.name.split("--")
        if len(parts) < 2:
            continue
        agent, orig_name = parts[0], "--".join(parts[1:])
        for dest_str in applied:
            dest = Path(dest_str)
            if dest.name == orig_name:
                if dest.is_dir():
                    shutil.rmtree(dest)
                    shutil.copytree(backup_file, dest)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    fd, tmp = tempfile.mkstemp(
                        prefix=".rollback-tmp.", dir=str(dest.parent)
                    )
                    os.close(fd)
                    shutil.copyfile(backup_file, tmp)
                    os.replace(tmp, str(dest))
                    core.fsync_dir(dest.parent)
                restored.append(dest_str)
                break

    # Re-sync manifest content hashes to the restored (pre-update) content.
    with core.LockFile(MANIFEST_FILE):
        manifest = core.load_manifest_data(MANIFEST_FILE)
        for entry in manifest["entries"]:
            if entry["destination"] in restored:
                try:
                    entry["content_hash"] = core.compute_sha256(
                        entry["destination"]
                    )
                except core.IntegrityError:
                    pass
        core.save_manifest_data(MANIFEST_FILE, manifest)

    journal = core.Journal.load(JOURNAL_FILE)
    journal = core.Journal(JOURNAL_FILE)
    journal.data = journal_data
    journal.finish("rolled_back")
    history_append(
        {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": "rollback",
            "restored": restored,
            "forced": bool(conflicts and args.force),
        }
    )
    return {
        "command": "rollback", "performed": True,
        "restored": restored, "backups_dir": backups_dir,
    }, EXIT_OK


def cmd_history(args):
    records = []
    if HISTORY_FILE.exists():
        try:
            lines = HISTORY_FILE.read_bytes().decode("utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise core.ManifestError(f"unreadable history: {exc}") from exc
        for line in lines:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise core.ManifestError(
                        f"history line unparsable: {exc}"
                    ) from exc
    return {"command": "history", "records": records}, EXIT_OK


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _emit(result, as_json):
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human(result)


def _print_human(result):
    cmd = result.get("command", "")
    if cmd == "status":
        print(f"version: {result.get('version') or 'unknown'}")
        print(f"channel: {result.get('channel') or 'unknown'}")
        print(f"hosts:   {', '.join(result['hosts']) or 'none'}")
        print(f"ownership: {result['ownership']}")
    elif cmd == "check":
        if result.get("message"):
            print(result["message"])
        else:
            print(f"current: {result.get('current') or 'unknown'}")
            print(f"latest:  {result.get('latest')}")
            state = "up to date" if result.get("up_to_date") else "update available"
            print(f"state:   {state} ({result.get('channel')})")
    elif cmd == "plan":
        print(f"transition: {result.get('from_version')} -> {result.get('to_version')}")
        print(f"files affected: {len(result.get('files_affected', []))}")
        for c in result.get("conflicts", []):
            print(f"  conflict: {c['destination']} ({c['reason']})")
        for s in result.get("manual_steps", []):
            print(f"  manual: {s}")
    elif cmd == "apply":
        if result.get("already_up_to_date"):
            print(result.get("message", "already up to date"))
        elif result.get("refused"):
            for r in result.get("reasons", []):
                print(f"refused: {r}")
            print(result.get("hint", ""))
        else:
            print(f"applied: {result.get('from_version')} -> {result.get('to_version')}")
            print(f"backups: {result.get('backups_dir')}")
    elif cmd == "rollback":
        if result.get("performed"):
            print(f"rolled back to pre-update state; backups at {result['backups_dir']}")
        else:
            print(f"not performed: {result.get('reason') or result.get('hint', '')}")
            for c in result.get("conflicts", []):
                print(f"  conflict: {c}")
    elif cmd == "history":
        for r in result.get("records", []):
            print(json.dumps(r, sort_keys=True))


def _read_json(path):
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("--dry-run", action="store_true", help="preview changes without writing")
    common.add_argument("--channel", choices=["stable", "beta", "pinned"],
                        help="update channel (default: stored channel or stable)")
    common.add_argument("--version", help="explicit version (pinned channel)")
    common.add_argument("--force", action="store_true",
                        help="proceed over detected user modifications "
                             "(after backing them up)")
    common.add_argument("--adopt", action="store_true",
                        help="take ownership of external-manager/unmanaged installs")

    parser = argparse.ArgumentParser(
        prog="sadskill-update.py",
        description="secure opt-in updater for sadskill installations",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", parents=[common], help="local truth; no network")
    sub.add_parser("check", parents=[common], help="query latest release; no writes")
    sub.add_parser("plan", parents=[common], help="preview exact transition; zero writes")
    sub.add_parser("apply", parents=[common], help="opt-in transactional update")
    sub.add_parser("rollback", parents=[common], help="recover the last update")
    sub.add_parser("history", parents=[common], help="transition log")
    args = parser.parse_args(argv)

    commands = {
        "status": cmd_status,
        "check": cmd_check,
        "plan": cmd_plan,
        "apply": cmd_apply,
        "rollback": cmd_rollback,
        "history": cmd_history,
    }
    handler = commands[args.command]
    try:
        result, rc = handler(args)
    except UsageError as exc:
        print(f"Usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except core.ManifestError as exc:
        print(f"Corrupt data: {exc}", file=sys.stderr)
        return EXIT_NET
    except NetworkError as exc:
        result = {"command": args.command, "error": "network", "details": str(exc)}
        _emit(result, args.json)
        return EXIT_NET
    except core.IntegrityError as exc:
        result = {"command": args.command, "error": "integrity", "details": str(exc)}
        _emit(result, args.json)
        return EXIT_INTEGRITY
    except ConflictError as exc:
        result = {"command": args.command, "error": "conflict", "details": str(exc)}
        _emit(result, args.json)
        return EXIT_CONFLICT
    except core.LockError as exc:
        result = {"command": args.command, "error": "lock", "details": str(exc)}
        _emit(result, args.json)
        return EXIT_LOCK
    except ApplyFailure as exc:
        print(f"Update failed and was left recoverable: {exc}", file=sys.stderr)
        return EXIT_ERROR
    _emit(result, args.json)
    return rc


if __name__ == "__main__":
    sys.exit(main())
