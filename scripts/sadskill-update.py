#!/usr/bin/env python3
"""sadskill secure updater (v0.3.0) — opt-in, transactional, rollback-capable.

Update surfaces handled:
  1. installer-managed installs  (recorded in ~/.sadskill/install-manifest.json)
  2. external-manager installs   (npx skills / skills-lock.json) — NEVER
     silently replaced; apply refuses because a boolean flag is not a safe
     ownership-transfer protocol.
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

Trust model: pinned repo identity Prarohi/sadskill, HTTPS with timeouts,
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
import bz2
import contextlib
import gzip
import io
import json
import lzma
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sadskill_core as core  # noqa: E402

REPO = "Prarohi/sadskill"
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
MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 4096
MAX_ARCHIVE_DEPTH = 32
MAX_EXPANSION_RATIO = 1000
# Includes allowed file payloads plus a bounded allowance for tar headers.
# Tarfile parses PAX/GNU extension payloads internally before yielding a member,
# so member-only limits cannot bound those allocations.
MAX_ARCHIVE_STREAM_BYTES = (
    MAX_UNCOMPRESSED_BYTES + MAX_ARCHIVE_MEMBERS * 1024
)

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
GITHUB_CONTENT_HOSTS = {
    "api.github.com", "github.com", "codeload.github.com",
    "release-assets.githubusercontent.com", "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
}

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
        source = _parse_network_url(req.full_url)
        target = _parse_network_url(newurl)
        source_is_test = source.scheme == "http" and source.hostname in LOOPBACK_HOSTS
        if source_is_test:
            if target.scheme != "http" or target.hostname not in LOOPBACK_HOSTS:
                raise NetworkError("loopback test request redirected outside loopback")
        elif target.scheme != "https" or target.hostname.lower() not in GITHUB_CONTENT_HOSTS:
            raise NetworkError("redirect target is not an approved GitHub HTTPS host")
        if source.scheme == "https" and target.scheme != "https":
            raise NetworkError("HTTPS redirect downgrade refused")
        source_origin = _url_origin(source)
        target_origin = _url_origin(target)
        try:
            new = super().redirect_request(req, fp, code, msg, headers, newurl)
        except urllib.error.HTTPError as exc:
            raise NetworkError(f"redirect failed: {exc}") from exc
        if new is None:
            return None
        if source_origin != target_origin:
            for name in ("Authorization", "Cookie", "Proxy-Authorization"):
                new.remove_header(name)
                new.headers.pop(name, None)
                new.unredirected_hdrs.pop(name, None)
        new._sad_redirects = count
        return new


_OPENER = urllib.request.build_opener(_RedirectCapper())


def _loopback_allowed(base):
    try:
        parsed = _parse_network_url(base)
    except NetworkError:
        return False
    return parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS


def _parse_network_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        parsed.port  # Access validates malformed and out-of-range ports.
    except (TypeError, ValueError) as exc:
        raise NetworkError("invalid network URL") from exc
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or any(ord(char) < 0x20 for char in url)):
        raise NetworkError("unsafe network URL")
    return parsed


def _url_origin(parsed):
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme.lower(), parsed.hostname.lower(), port


def _validate_request_url(url):
    parsed = _parse_network_url(url)
    if parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS:
        return parsed
    if parsed.scheme == "https" and parsed.hostname.lower() in GITHUB_CONTENT_HOSTS:
        return parsed
    raise NetworkError("request URL is not an approved GitHub HTTPS or loopback URL")


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
    _validate_request_url(req.full_url)
    try:
        resp = _OPENER.open(req, timeout=HTTP_TIMEOUT)
    except urllib.error.HTTPError as exc:
        if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
            raise NetworkError("GitHub API rate limit exceeded") from exc
        parsed = urllib.parse.urlsplit(req.full_url)
        safe_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")
        )
        raise NetworkError(f"HTTP {exc.code} for {safe_url}") from exc
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
    parsed = _validate_request_url(url)
    api_base = _parse_network_url(_api_base())
    if _url_origin(parsed) != _url_origin(api_base):
        raise NetworkError("metadata request is outside the configured API origin")
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
    return _validate_release(release)


def _path_is_repo_release(parsed, endpoint):
    path = parsed.path.rstrip("/")
    prefix = f"/repos/{REPO}/releases/"
    if not path.startswith(prefix):
        return False
    suffix = path[len(prefix):]
    if endpoint == "api":
        return bool(re.fullmatch(r"[0-9]+", suffix))
    return endpoint == "web" and suffix.startswith("tag/") and bool(suffix[4:])


def _validate_release_url(url, kind, tag):
    if not isinstance(url, str) or not url:
        raise NetworkError(f"release metadata is missing its {kind} URL")
    parsed = _parse_network_url(url)
    host = parsed.hostname.lower()
    if kind == "api":
        valid = (
            parsed.scheme == "https" and host == "api.github.com"
            and _path_is_repo_release(parsed, "api")
        )
    elif kind == "web":
        valid = (
            parsed.scheme == "https" and host == "github.com"
            and parsed.path == f"/{REPO}/releases/tag/{tag}"
            and not parsed.query and not parsed.fragment
        )
    else:
        api_base = _parse_network_url(_api_base())
        if parsed.scheme == "http" and host in LOOPBACK_HOSTS:
            valid = (
                _url_origin(parsed) == _url_origin(api_base)
                and parsed.path.startswith("/")
            )
        elif parsed.scheme == "https" and host == "api.github.com":
            valid = parsed.path == f"/repos/{REPO}/tarball/{tag}"
        elif parsed.scheme == "https" and host == "codeload.github.com":
            valid = parsed.path in (
                f"/{REPO}/legacy.tar.gz/refs/tags/{tag}",
                f"/{REPO}/tar.gz/refs/tags/{tag}",
            )
        else:
            valid = False
    if not valid or parsed.username is not None or parsed.password is not None:
        raise NetworkError(f"release {kind} URL does not match the official repository")
    return parsed


def _validate_release_asset_url(url, tag):
    parsed = _parse_network_url(url)
    host = parsed.hostname.lower()
    api_base = _parse_network_url(_api_base())
    if parsed.scheme == "http" and host in LOOPBACK_HOSTS:
        valid = _url_origin(parsed) == _url_origin(api_base)
    else:
        valid = (
            parsed.scheme == "https" and host == "github.com"
            and parsed.path.startswith(f"/{REPO}/releases/download/{tag}/")
        )
    if not valid:
        raise core.IntegrityError("SHA256SUMS URL is not from the official release")


def _validate_release(release, expected_tag=None):
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not tag:
        raise NetworkError("release metadata is missing tag_name")
    try:
        core.parse_version(tag)
    except ValueError as exc:
        raise NetworkError("release tag is not a supported version") from exc
    if expected_tag is not None and tag != expected_tag:
        raise NetworkError("release tag does not match the requested version")
    _validate_release_url(release.get("url"), "api", tag)
    _validate_release_url(release.get("html_url"), "web", tag)
    tarball = release.get("tarball_url")
    if not isinstance(tarball, str) or not tarball:
        raise NetworkError("release has no tarball_url")
    _validate_release_url(tarball, "tarball", tag)
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise NetworkError("release assets must be a list")
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("name", ""), str):
            raise NetworkError("release asset metadata is malformed")
        if asset.get("name", "").strip().lower() == "sha256sums.txt":
            url = asset.get("browser_download_url")
            if not isinstance(url, str) or not url:
                raise core.IntegrityError("SHA256SUMS asset has no download URL")
            _validate_release_asset_url(url, tag)
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
    matches = [asset for asset in assets
               if asset.get("name", "").strip().lower() == "sha256sums.txt"]
    if len(matches) > 1:
        raise core.IntegrityError("release contains duplicate SHA256SUMS assets")
    if matches:
        url = matches[0].get("browser_download_url")
        if not url:
            raise core.IntegrityError("SHA256SUMS asset has no download URL")
        _validate_release_asset_url(url, release.get("tag_name", ""))
        data, _ = _open(urllib.request.Request(url), MAX_JSON_BYTES)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise core.IntegrityError("SHA256SUMS is not valid UTF-8") from exc
        tar_name = os.path.basename(urllib.parse.urlsplit(tarball_url).path)
        found = None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", line)
            if not match:
                raise core.IntegrityError("SHA256SUMS contains a malformed entry")
            if match.group(2).strip() == tar_name:
                if found is not None:
                    raise core.IntegrityError("SHA256SUMS has duplicate artifact entries")
                found = match.group(1).lower()
        if found is None:
            raise core.IntegrityError(
                f"SHA256SUMS does not contain the requested artifact {tar_name}"
            )
        return found
    return None


# ---------------------------------------------------------------------------
# Archive validation + staging (never executes content)
# ---------------------------------------------------------------------------

class _BoundedReader:
    """Limit bytes delivered from a decompressed tar stream to tarfile."""

    def __init__(self, source, limit):
        self.source = source
        self.limit = limit
        self.bytes_read = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = self.limit - self.bytes_read + 1
        remaining = self.limit - self.bytes_read
        data = self.source.read(min(size, remaining + 1))
        self.bytes_read += len(data)
        if self.bytes_read > self.limit:
            raise core.IntegrityError(
                "archive exceeds decompressed stream size limit"
            )
        return data

    def close(self):
        self.source.close()


def _bounded_tar_reader(tar_bytes):
    """Open supported tar compression behind a decompressed-byte cap."""
    raw = io.BytesIO(tar_bytes)
    if tar_bytes.startswith(b"\x1f\x8b"):
        source = gzip.GzipFile(fileobj=raw, mode="rb")
    elif tar_bytes.startswith(b"BZh"):
        source = bz2.BZ2File(raw, mode="rb")
    elif tar_bytes.startswith(b"\xfd7zXZ\x00"):
        source = lzma.LZMAFile(raw, mode="rb")
    else:
        source = raw
    return _BoundedReader(source, MAX_ARCHIVE_STREAM_BYTES)

def _member_ok(member, seen_names):
    name = member.name
    if not name or name.startswith("/") or "\\" in name or "\x00" in name:
        raise core.IntegrityError(f"archive member unsafe path: {name!r}")
    parts = [unicodedata.normalize("NFC", p)
             for p in name.split("/") if p not in ("", ".")]
    if (not parts or any(p in ("..", "") or ":" in p
                          or any(ord(char) < 0x20 for char in p)
                          for p in parts)):
        raise core.IntegrityError(f"archive member escapes root: {name!r}")
    norm = "/".join(parts)
    collision_key = norm.casefold()
    if collision_key in seen_names:
        raise core.IntegrityError(f"duplicate archive member: {norm}")
    if member.issym() or member.islnk():
        raise core.IntegrityError(f"archive member is a link: {name!r}")
    if member.isdev() or member.isfifo():
        raise core.IntegrityError(f"archive member is device/fifo: {name!r}")
    if member.size < 0 or member.size > MAX_TARBALL_BYTES:
        raise core.IntegrityError(f"archive member too large: {name!r}")
    if member.isdir() and member.size != 0:
        raise core.IntegrityError(
            f"archive directory member contains data: {name!r}"
        )
    if len(parts) > MAX_ARCHIVE_DEPTH:
        raise core.IntegrityError(f"archive member is nested too deeply: {name!r}")
    seen_names.add(collision_key)
    return parts, norm


def stage_archive(tar_bytes, write=True):
    """Validate an archive and optionally extract it into a fresh staging dir.

    With ``write=False`` this performs bounded, read-only metadata validation
    for plan. With ``write=True`` only validated regular files are written,
    under the private updater staging directory. Downloaded content is never
    executed.
    """
    if len(tar_bytes) > MAX_TARBALL_BYTES:
        raise core.IntegrityError("compressed archive exceeds size limit")
    seen = set()
    top_dirs = set()
    members = []
    total_size = 0
    stream_reader = _bounded_tar_reader(tar_bytes)
    try:
        with tarfile.open(fileobj=stream_reader, mode="r|") as tar:
            for member in tar:
                if len(members) >= MAX_ARCHIVE_MEMBERS:
                    raise core.IntegrityError("archive has too many members")
                parts, norm = _member_ok(member, seen)
                total_size += member.size
                if total_size > MAX_UNCOMPRESSED_BYTES:
                    raise core.IntegrityError(
                        "archive exceeds total uncompressed size limit"
                    )
                if member.isdir():
                    top_dirs.add(parts[0])
                elif not member.isfile():
                    raise core.IntegrityError(
                        f"archive member is not a regular file: {norm}"
                    )
                members.append((member, parts, norm))
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise core.IntegrityError(f"archive unreadable: {exc}") from exc
    if stream_reader.bytes_read / max(1, len(tar_bytes)) > MAX_EXPANSION_RATIO:
        raise core.IntegrityError("archive expansion ratio exceeds limit")

    rel_files = []
    strip = 0
    file_tops = {parts[0] for member, parts, norm in members if member.isfile()}
    if top_dirs:
        if len(top_dirs) == 1 and next(iter(top_dirs)) not in ("skills", "commands"):
            strip = 1
        else:
            raise core.IntegrityError(
                f"archive has unexpected top-level layout: {sorted(top_dirs)}"
            )
    elif file_tops:
        if len(file_tops) == 1 and next(iter(file_tops)) not in ("skills", "commands"):
            strip = 1
        else:
            raise core.IntegrityError(
                f"archive has unexpected top-level layout: {sorted(file_tops)}"
            )
    member_paths = {}
    for member, parts, norm in members:
        rel = "/".join(parts[strip:])
        if not rel:
            continue
        if member.isdir():
            continue
        rel_files.append(rel)
        member_paths[norm] = rel
    file_keys = {path.casefold() for path in rel_files}
    for path in rel_files:
        parts = path.split("/")
        for index in range(1, len(parts)):
            if "/".join(parts[:index]).casefold() in file_keys:
                raise core.IntegrityError(
                    f"archive file is also used as a parent directory: {path}"
                )
    if not write:
        return None, rel_files

    stage = Path(tempfile.mkdtemp(prefix="sadskill-stage.", dir=str(STATE_DIR)))
    try:
        with tarfile.open(fileobj=_bounded_tar_reader(tar_bytes), mode="r|") as tar:
            for member in tar:
                norm = "/".join(
                    unicodedata.normalize("NFC", part)
                    for part in member.name.split("/") if part not in ("", ".")
                )
                rel = member_paths.get(norm)
                if rel is None:
                    continue
                dest = stage / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                fobj = tar.extractfile(member)
                if fobj is None:
                    raise core.IntegrityError(f"cannot read member: {norm}")
                data = fobj.read(member.size + 1)
                if len(data) != member.size:
                    raise core.IntegrityError(f"archive member size mismatch: {norm}")
                with dest.open("xb") as output:
                    output.write(data)
    except (tarfile.TarError, OSError) as exc:
        shutil.rmtree(stage, ignore_errors=True)
        raise core.IntegrityError(f"archive extraction failed: {exc}") from exc
    return stage, rel_files


# ---------------------------------------------------------------------------
# Installation knowledge
# ---------------------------------------------------------------------------

_SKILL_AGENTS = ("claude", "codex", "gemini", "antigravity", "cursor_skill")
_HOME_ROOT_AGENTS = frozenset({
    "claude", "claude_command", "claude_hook", "codex", "codex_prompt",
    "gemini", "antigravity",
})

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
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise core.ManifestError(
            f"cannot safely determine external skills-manager ownership: {exc}"
        ) from exc
    if not isinstance(data, (dict, list)):
        raise core.ManifestError("external skills-manager lock has invalid structure")
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
            if len(Path(rel).parts) != 3 or not rel.endswith(".md"):
                raise core.IntegrityError(
                    f"Claude command archive path is not a direct Markdown file: {rel}"
                )
            name = os.path.basename(rel)
            for entry in by_agent.get("claude_command", []):
                if os.path.basename(entry["destination"]) == name:
                    actions.append(
                        {"source": rel,
                         "targets": [(Path(entry["destination"]), entry,
                                      "claude_command")]}
                    )
        elif rel.startswith("commands/codex/"):
            if len(Path(rel).parts) != 3 or not rel.endswith(".md"):
                raise core.IntegrityError(
                    f"Codex prompt archive path is not a direct Markdown file: {rel}"
                )
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
            dest = Path(dest)
            try:
                _assert_no_symlink_components(dest)
            except core.IntegrityError:
                conflicts.append({"destination": str(dest),
                                  "reason": "unsafe path component"})
                continue
            if dest.exists() and not dest.is_file():
                conflicts.append({"destination": str(dest),
                                  "reason": "target is not a regular file"})
                continue
            bad_parent = next((parent for parent in dest.parents
                               if parent.exists() and not parent.is_dir()), None)
            if bad_parent is not None:
                conflicts.append({"destination": str(dest),
                                  "reason": f"parent is not a directory: {bad_parent}"})
                continue

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


def validate_file_targets(actions):
    """Fail before journaling if any update target cannot be atomically replaced."""
    issues = []
    seen = set()
    for action in actions:
        for dest, _entry, _agent in action["targets"]:
            dest = Path(dest)
            if str(dest) in seen:
                continue
            seen.add(str(dest))
            try:
                _assert_no_symlink_components(dest)
            except core.IntegrityError:
                issues.append({"destination": str(dest),
                               "reason": "unsafe path component"})
                continue
            if dest.exists() and not dest.is_file():
                issues.append({"destination": str(dest),
                               "reason": "target is not a regular file"})
                continue
            bad_parent = next((parent for parent in dest.parents
                               if parent.exists() and not parent.is_dir()), None)
            if bad_parent is not None:
                issues.append({"destination": str(dest),
                               "reason": f"parent is not a directory: {bad_parent}"})
    return issues


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
        "artifact_trust": _artifact_trust_hint(release),
        "publisher_authenticated": False,
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
    else:
        target_ver = args.version
        release = _fetch_pinned(args.version)
    target_ver = core.version_text(release_version(release))
    tarball_url = release.get("tarball_url")
    tar_bytes, artifact_trust = _download_verified(release, tarball_url)
    # A plan validates the bounded archive in memory and never creates staging files.
    _stage, rel_files = stage_archive(tar_bytes, write=False)
    actions = build_transition(manifest, by_agent, rel_files)
    conflicts = conflicts_for(actions)
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
        "artifact_trust": artifact_trust,
        "publisher_authenticated": False,
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
        return tar_bytes, "SOURCE_CHECKSUM_MATCHED"
    return tar_bytes, "TRANSPORT_ONLY"


def _artifact_trust_hint(release):
    if any(asset.get("name", "").strip().lower() == "sha256sums.txt"
           for asset in release.get("assets", [])):
        return "SHA256SUMS_AVAILABLE_NOT_VALIDATED"
    return "TRANSPORT_ONLY"


def cmd_apply(args):
    if args.dry_run:
        return cmd_plan(args)[0], EXIT_OK
    with core.LockFile(MANIFEST_FILE):
        return _cmd_apply_locked(args)


def _cmd_apply_locked(args):
    channel = args.channel or read_channel() or "stable"
    if channel == "pinned" and not args.version:
        raise UsageError("pinned channel requires --version for apply")
    hosts, manifest, by_agent = detect_hosts()

    prior_journal = core.Journal.load(JOURNAL_FILE)
    if prior_journal and prior_journal.get("state") not in ("done", "rolled_back"):
        return {
            "command": "apply", "refused": True,
            "reasons": ["an unresolved updater journal requires recovery"],
            "hint": "run sadskill-update.py rollback and inspect its result",
        }, EXIT_CONFLICT

    # External manager ownership cannot be transferred by a boolean override.
    external = skills_lock_active()
    unmanaged = unmanaged_dests(manifest, by_agent)
    if external or unmanaged:
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
            "hint": "remove or update the installation through its owning manager; "
                    "safe manager transfer is not supported",
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

    tar_bytes, artifact_trust = _download_verified(release, tarball_url)
    stage, rel_files = stage_archive(tar_bytes)
    try:
        actions = build_transition(manifest, by_agent, rel_files)
        if not actions:
            return {
                "command": "apply", "refused": True,
                "reasons": ["no installer-managed destinations in manifest"],
                "hint": "run ./install.sh first or pass --adopt",
            }, EXIT_ERROR
        destinations = {}
        for action in actions:
            for dest, entry, agent in action["targets"]:
                dest = _validate_owned_destination(dest, entry)
                dest_key = str(dest)
                if dest_key in destinations:
                    raise core.IntegrityError(
                        "multiple archive files map to the same update target: "
                        f"{dest}"
                    )
                destinations[dest_key] = {
                    "agent": agent,
                    "entry_destination": entry["destination"],
                    "target_root": entry.get(
                        "target_root", str(_default_target_root(
                            entry.get("agent"), Path(entry["destination"])
                        ))
                    ),
                }
        invalid_targets = validate_file_targets(actions)
        if invalid_targets:
            raise core.IntegrityError(
                "unsafe update file target(s): "
                + "; ".join(
                    f"{item['destination']} ({item['reason']})"
                    for item in invalid_targets
                )
            )
        conflicts = conflicts_for(actions)
        if conflicts and not args.force:
            return {
                "command": "apply", "refused": True, "conflicts": conflicts,
                "hint": "user modifications detected; pass --force after "
                        "reviewing (your modifications will be backed up)",
            }, EXIT_CONFLICT

        # Reject special file modes before creating a transaction journal.
        # _backup_dest repeats this check so a chmod racing the preflight is
        # still caught before any installed file is replaced.
        for target in list(destinations) + [
            str(MANIFEST_FILE), str(INSTALL_STATE_FILE)
        ]:
            _assert_no_symlink_components(target)
            _validated_regular_file_mode(target)

        _assert_no_symlink_components(STATE_DIR)
        backups_root = STATE_DIR / "backups"
        _ensure_private_directory(backups_root, parents=True, exist_ok=True)
        backups_dir = STATE_DIR / "backups" / f"update-{to_version}-{time.time_ns()}"
        journal = Journal_path()
        journal.begin(current, to_version, str(stage), REPO, channel)
        journal.data["backups_dir"] = str(backups_dir)
        journal.data["backup_map"] = {}
        journal.data["metadata_backup_map"] = {}
        journal._flush()
        try:
            journal.step("staged", {"files": len(rel_files)})
            _ensure_private_directory(backups_dir, exist_ok=False)
            journal.step("backing_up", {"backups_dir": str(backups_dir)})

            # Exact destination->backup mapping is durable before any replacement.
            for index, (dest_str, record) in enumerate(destinations.items(), 1):
                backup = _backup_dest(dest_str, backups_dir, f"destination-{index:06d}")
                backup.update(record)
                journal.data["backup_map"][dest_str] = backup
            for key, state_path in (("manifest", MANIFEST_FILE),
                                    ("install_state", INSTALL_STATE_FILE)):
                backup = _backup_dest(
                    state_path, backups_dir, f"metadata-{key}"
                )
                journal.data["metadata_backup_map"][str(state_path)] = backup
            journal.step("backed_up", {
                "destinations": len(journal.data["backup_map"]),
                "metadata": len(journal.data["metadata_backup_map"]),
            })
            journal._flush()

            apply_failure_env_fault()  # test hook: simulated crash after backup

            applied = {}
            mutation_index = 0
            for action in actions:
                for dest, entry, agent in action["targets"]:
                    dest = _validate_owned_destination(dest, entry)
                    staged = stage / action["source"]
                    mutation_index += 1
                    backup_record = journal.data["backup_map"].get(str(dest))
                    _assert_matches_backup_snapshot(dest, backup_record)
                    old_hash = (
                        backup_record["sha256"]
                        if backup_record["existed"] else None
                    )
                    new_hash = core.compute_sha256(staged)
                    journal.step("mutation_intent", {
                        "category": "destination",
                        "destination": str(dest),
                        "entry_destination": entry["destination"],
                        "agent": agent,
                        "old_sha256": old_hash,
                        "new_sha256": new_hash,
                    })
                    written = _atomic_install_file(
                        staged, Path(dest), expected_snapshot=backup_record
                    )
                    applied[str(dest)] = core.compute_sha256(written)
                    journal.step("mutation_applied", {
                        "category": "destination",
                        "destination": str(dest),
                        "sha256": applied[str(dest)],
                    })
                    if os.environ.get(FAULT_ENV) in (
                        "after_first_replace" if mutation_index == 1 else "",
                        f"after_replace:{mutation_index}",
                    ):
                        raise RuntimeError(
                            f"simulated crash after replacement {mutation_index}"
                        )

            updated_skill_roots = {
                record["entry_destination"] for record in destinations.values()
                if record["agent"] in _SKILL_AGENTS
            }
            updated_exact = {
                dest for dest, record in destinations.items()
                if record["agent"] not in _SKILL_AGENTS
            }
            manifest_backup = journal.data["metadata_backup_map"].get(
                str(MANIFEST_FILE)
            )
            _assert_matches_backup_snapshot(MANIFEST_FILE, manifest_backup)
            manifest = core.load_manifest_data(MANIFEST_FILE)
            for entry in manifest["entries"]:
                if (not entry.get("target_root")
                        and entry.get("agent") in _HOME_ROOT_AGENTS):
                    entry["target_root"] = str(_default_target_root(
                        entry["agent"], Path(entry["destination"])
                    ))
            for entry in manifest["entries"]:
                entry_dest = entry["destination"]
                if entry.get("agent") in _SKILL_AGENTS and entry_dest in updated_skill_roots:
                    new_hash = core.compute_sha256(entry_dest)
                    new_hash_type = "tree"
                elif entry_dest in updated_exact:
                    new_hash = core.compute_sha256(entry_dest)
                    new_hash_type = "tree" if Path(entry_dest).is_dir() else "file"
                else:
                    continue
                entry["backup_hash"] = entry.get("content_hash", "")
                entry["content_hash"] = new_hash
                entry["content_hash_type"] = new_hash_type
                entry.setdefault("target_root", str(_default_target_root(
                    entry.get("agent"), Path(entry["destination"])
                )))
                entry["installed_at"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                )
                entry.setdefault("updates", []).append(
                    {"version": to_version, "at": entry["installed_at"]}
                )
            core.validate_manifest_data(manifest)
            manifest_text = json.dumps(manifest, indent=2) + "\n"
            manifest_new_hash = core.compute_sha256_of_bytes(
                manifest_text.encode("utf-8")
            )
            manifest_old_hash = (
                manifest_backup["sha256"] if manifest_backup["existed"] else None
            )
            journal.step("mutation_intent", {
                "category": "metadata", "destination": str(MANIFEST_FILE),
                "backup_key": str(MANIFEST_FILE),
                "old_sha256": manifest_old_hash,
                "new_sha256": manifest_new_hash,
            })
            _atomic_install_text(
                MANIFEST_FILE, manifest_text, expected_snapshot=manifest_backup
            )
            journal.step("mutation_applied", {
                "category": "metadata", "destination": str(MANIFEST_FILE),
                "sha256": manifest_new_hash,
            })
            journal.step("manifest_updated")

            state_text = json.dumps({
                "version": to_version,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "channel": channel,
            }, indent=2) + "\n"
            state_new_hash = core.compute_sha256_of_bytes(state_text.encode("utf-8"))
            state_backup = journal.data["metadata_backup_map"].get(
                str(INSTALL_STATE_FILE)
            )
            _assert_matches_backup_snapshot(INSTALL_STATE_FILE, state_backup)
            state_old_hash = (
                state_backup["sha256"] if state_backup["existed"] else None
            )
            journal.step("mutation_intent", {
                "category": "metadata", "destination": str(INSTALL_STATE_FILE),
                "backup_key": str(INSTALL_STATE_FILE),
                "old_sha256": state_old_hash,
                "new_sha256": state_new_hash,
            })
            _atomic_install_text(
                INSTALL_STATE_FILE, state_text, expected_snapshot=state_backup
            )
            journal.step("mutation_applied", {
                "category": "metadata", "destination": str(INSTALL_STATE_FILE),
                "sha256": state_new_hash,
            })
            journal.step("install_state_written")
            history_append({
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "action": "update", "from": current, "to": to_version,
                "channel": channel, "conflicts_forced": bool(conflicts),
                "artifact_trust": artifact_trust,
            })
            journal.finish("done")
            return {
                "command": "apply", "applied": True,
                "from_version": current, "to_version": to_version,
                "backups_dir": str(backups_dir), "conflicts_forced": bool(conflicts),
                "artifact_trust": artifact_trust,
                "publisher_authenticated": False,
            }, EXIT_OK
        except Exception as exc:
            try:
                journal.step("failure", {"error": str(exc)})
                journal.finish("interrupted")
                history_append({
                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "action": "update_interrupted", "from": current,
                    "to": to_version, "error": str(exc),
                })
            except Exception:
                # The last durable per-file intent remains the recovery source.
                pass
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
    return _validate_release(payload, expected_tag=f"v{version.lstrip('v')}")


_AGENT_PATH_MARKERS = {
    "claude": (".claude", "skills", "sadskill"),
    "codex": (".codex", "skills", "sadskill"),
    "gemini": (".gemini", "skills", "sadskill"),
    "antigravity": (".gemini", "antigravity", "skills", "sadskill"),
    "cursor_skill": (".cursor", "skills", "sadskill"),
    "claude_command": (".claude", "commands"),
    "codex_prompt": (".codex", "prompts"),
    "claude_hook": (".claude",),
}


def _has_path_marker(path, marker):
    parts = Path(path).parts
    width = len(marker)
    return any(tuple(parts[index:index + width]) == marker
               for index in range(max(0, len(parts) - width + 1)))


def _default_target_root(agent, destination):
    """Infer a legacy manifest's only safe updater root for this agent."""
    home = Path.home().resolve()
    fixed_roots = {
        "claude": home / ".claude",
        "claude_command": home / ".claude",
        "claude_hook": home / ".claude",
        "codex": home / ".codex",
        "codex_prompt": home / ".codex",
        "gemini": home / ".gemini",
        "antigravity": home / ".gemini",
    }
    if agent in fixed_roots:
        return fixed_roots[agent]
    destination = Path(destination)
    if agent == "cursor_skill" and tuple(destination.parts[-3:]) == (
            ".cursor", "skills", "sadskill"):
        return destination.parents[2]
    return home


def _assert_no_symlink_components(path):
    path = Path(path)
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise core.IntegrityError(f"cannot inspect path component {current}: {exc}") from exc
        if stat.S_ISLNK(mode):
            raise core.IntegrityError(f"symlink path component is not safe: {current}")


def _assert_no_symlinks_below(path):
    path = Path(path)
    _assert_no_symlink_components(path)
    if not path.is_dir():
        return
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            if (Path(root) / name).is_symlink():
                raise core.IntegrityError(
                    f"symlink inside managed destination is not safe: {Path(root) / name}"
                )


def _validate_owned_destination(dest, entry):
    dest = Path(dest)
    root = Path(entry.get("destination", ""))
    agent = entry.get("agent", "")
    if not dest.is_absolute() or ".." in dest.parts:
        raise core.IntegrityError(f"destination is not a canonical absolute path: {dest}")
    marker = _AGENT_PATH_MARKERS.get(agent)
    if not marker or not _has_path_marker(root, marker):
        raise core.IntegrityError(
            f"manifest path does not match the recorded {agent!r} installation type"
        )
    if agent in _SKILL_AGENTS:
        if root.name != "sadskill" or (dest != root and root not in dest.parents):
            raise core.IntegrityError("skill update target is outside its owned root")
    elif agent == "claude_hook":
        expected_hook = (
            Path.home() / ".claude" / "hooks" / "git-guardrail.sh"
        ).resolve(strict=False)
        if root.resolve(strict=False) != expected_hook:
            raise core.IntegrityError(
                "Claude hook manifest destination is not the canonical guardrail path"
            )
    elif dest != root:
        raise core.IntegrityError("non-skill update target differs from its manifest path")

    # A manifest's target_root is ownership metadata, not authority to send an
    # updater write anywhere on disk. HOME-hosted agents must use their fixed
    # HOME roots. Cursor is workspace-scoped, so its root must be exactly the
    # parent of the workspace's canonical .cursor installation path.
    home = Path.home().resolve()
    fixed_skill_roots = {
        "claude": home / ".claude" / "skills" / "sadskill",
        "codex": home / ".codex" / "skills" / "sadskill",
        "gemini": home / ".gemini" / "skills" / "sadskill",
        "antigravity": home / ".gemini" / "antigravity" / "skills" / "sadskill",
    }
    target_root = Path(
        entry.get("target_root") or _default_target_root(agent, root)
    )
    if not target_root.is_absolute() or ".." in target_root.parts:
        raise core.IntegrityError(
            f"target root is not a canonical absolute path: {target_root}"
        )
    _assert_no_symlink_components(target_root)
    _assert_no_symlink_components(root)
    _assert_no_symlink_components(dest)
    if agent == "cursor_skill":
        expected_cursor_root = target_root / ".cursor" / "skills" / "sadskill"
        if root.resolve(strict=False) != expected_cursor_root.resolve(strict=False):
            raise core.IntegrityError(
                "Cursor target root does not match its workspace skill destination"
            )
    elif agent in _HOME_ROOT_AGENTS:
        expected_root = _default_target_root(agent, root)
        if target_root.resolve(strict=False) != expected_root:
            raise core.IntegrityError(
                f"target root for {agent} must be its canonical HOME root "
                f"{expected_root}"
            )
    elif agent != "cursor_skill":
        raise core.IntegrityError(f"unsupported update installation type: {agent}")
    if agent in fixed_skill_roots and root.resolve(strict=False) != fixed_skill_roots[agent]:
        raise core.IntegrityError(
            f"skill destination for {agent} must be its canonical HOME path "
            f"{fixed_skill_roots[agent]}"
        )

    try:
        dest.resolve(strict=False).relative_to(target_root.resolve(strict=False))
    except ValueError as exc:
        raise core.IntegrityError(
            f"destination is outside its recorded target root {target_root}: {dest}"
        ) from exc
    if not entry.get("target_root"):
        try:
            dest.resolve(strict=False).relative_to(Path.home().resolve())
        except ValueError as exc:
            raise core.IntegrityError(
                f"legacy manifest destination outside HOME is untrusted: {dest}"
            ) from exc
    return dest


def _sync_file(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sync_directory(path):
    """Durably sync a directory or fail before relying on its entries."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(str(path), flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_private_directory(path, *, parents=False, exist_ok=True):
    path = Path(path)
    _assert_no_symlink_components(path)
    if parents:
        if path.exists() and not exist_ok:
            raise FileExistsError(str(path))
        missing = []
        current = path
        while not current.exists():
            missing.append(current)
            if current.parent == current:
                raise FileNotFoundError(str(current))
            current = current.parent
        for directory in reversed(missing):
            try:
                directory.mkdir(mode=0o700)
            except FileExistsError:
                if not directory.is_dir():
                    raise
            else:
                # Persist each new directory entry through its parent before
                # any backup or destination replacement can depend on it.
                _sync_directory(directory.parent)
    else:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            if not exist_ok:
                raise
            if not path.is_dir():
                raise
        else:
            _sync_directory(path.parent)
    os.chmod(path, 0o700)
    _sync_directory(path)
    return path


def _validated_regular_file_mode(path):
    path = Path(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise core.IntegrityError(f"backup target is not a regular file: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & ~0o777:
        raise core.IntegrityError(
            f"unsupported special permission bits on updater target: {path}"
        )
    return mode


def _assert_matches_backup_snapshot(dest, record):
    """Refuse to replace a target changed since its verified backup was taken."""
    dest = Path(dest)
    _assert_no_symlink_components(dest)
    current_mode = _validated_regular_file_mode(dest)
    current_hash = core.compute_sha256(dest) if current_mode is not None else None
    if not isinstance(record, dict) or not isinstance(record.get("existed"), bool):
        raise core.IntegrityError(f"backup snapshot is malformed for {dest}")
    expected_hash = record.get("sha256") if record["existed"] else None
    expected_mode = record.get("mode") if record["existed"] else None
    if current_hash != expected_hash or current_mode != expected_mode:
        raise core.IntegrityError(
            f"update target changed after its backup snapshot: {dest}"
        )


def _backup_dest(dest, backups_dir, backup_id):
    dest = Path(dest)
    _assert_no_symlink_components(dest)
    if not dest.exists():
        return {"existed": False, "backup_path": None, "sha256": None,
                "kind": None, "mode": None}
    mode = _validated_regular_file_mode(dest)
    before = dest.stat()
    target_dir = Path(backups_dir) / "destinations"
    _ensure_private_directory(target_dir, parents=True, exist_ok=True)
    target = target_dir / f"{backup_id}.backup"
    shutil.copy2(dest, target)
    os.chmod(target, 0o600)
    _sync_file(target)
    _sync_directory(target_dir)
    original_hash = core.compute_sha256(dest)
    backup_hash = core.compute_sha256(target)
    if not original_hash or original_hash != backup_hash:
        raise core.IntegrityError(f"backup verification failed for {dest}")
    after = dest.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
         stat.S_IMODE(before.st_mode)) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
             stat.S_IMODE(after.st_mode))):
        raise core.IntegrityError(f"backup target changed while being snapshotted: {dest}")
    return {"existed": True, "backup_path": str(target),
            "sha256": original_hash, "kind": "file", "mode": mode}


def _atomic_install_file(staged, dest, *, expected_snapshot=None):
    """Copy a staged file to dest atomically; returns written path."""
    dest = Path(dest)
    _assert_no_symlink_components(dest)
    if dest.exists() and not dest.is_file():
        raise core.IntegrityError(f"update target is not a regular file: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".update-tmp.", dir=str(dest.parent))
    try:
        os.close(fd)
        shutil.copyfile(staged, tmp)
        if dest.exists():
            mode = stat.S_IMODE(dest.stat().st_mode)
        else:
            mode = 0o755 if staged.name == "git-guardrail.sh" else 0o644
        os.chmod(tmp, mode)
        _sync_file(tmp)
        if expected_snapshot is not None:
            _assert_matches_backup_snapshot(dest, expected_snapshot)
        os.replace(tmp, str(dest))
        _sync_directory(dest.parent)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return dest


def _atomic_install_text(dest, text, *, expected_snapshot=None):
    """Atomically write updater metadata after verifying its backup snapshot."""
    dest = Path(dest)
    _assert_no_symlink_components(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".update-tmp.", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(tmp, 0o644)
        if expected_snapshot is not None:
            _assert_matches_backup_snapshot(dest, expected_snapshot)
        os.replace(tmp, str(dest))
        _sync_directory(dest.parent)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return dest


def cmd_rollback(args):
    with core.LockFile(MANIFEST_FILE):
        return _cmd_rollback_locked(args)


def _rollback_backup_record(record, backups_dir):
    """Validate and verify an exact journal backup before any rollback write."""
    if not isinstance(record, dict) or not isinstance(record.get("existed"), bool):
        raise core.IntegrityError("rollback backup record is malformed")
    if not record["existed"]:
        if record.get("backup_path") is not None or record.get("sha256") is not None:
            raise core.IntegrityError("absent rollback backup has unexpected data")
        return None
    backup_path = record.get("backup_path")
    if not isinstance(backup_path, str) or not backup_path:
        raise core.IntegrityError("rollback backup path is missing")
    backup = Path(backup_path)
    root = Path(backups_dir).resolve(strict=True)
    _assert_no_symlink_components(backup)
    try:
        backup.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise core.IntegrityError("rollback backup escapes the journal backup directory") from exc
    if record.get("kind") != "file" or not backup.is_file():
        raise core.IntegrityError("rollback backup is not a regular file")
    if "mode" in record and (
        type(record["mode"]) is not int or record["mode"] < 0
        or record["mode"] & ~0o777
    ):
        raise core.IntegrityError("rollback backup mode is malformed")
    expected = record.get("sha256")
    actual = core.compute_sha256(backup)
    if not isinstance(expected, str) or actual != expected:
        raise core.IntegrityError(f"rollback backup verification failed: {backup}")
    return backup


def _rollback_current_hash(dest):
    dest = Path(dest)
    _assert_no_symlink_components(dest)
    if not dest.exists():
        return None
    if not dest.is_file():
        raise core.IntegrityError(f"rollback target is not a regular file: {dest}")
    return core.compute_sha256(dest)


def _validate_rollback_destination(intent, manifest_data):
    """Authorize journal targets against current owned installs before writes."""
    category = intent.get("category")
    destination = intent.get("destination")
    if not isinstance(destination, str):
        raise core.IntegrityError("journal rollback destination is malformed")
    dest = Path(destination)
    if not dest.is_absolute() or ".." in dest.parts or str(dest) != destination:
        raise core.IntegrityError("journal rollback destination is not canonical")

    metadata_targets = {str(MANIFEST_FILE), str(INSTALL_STATE_FILE)}
    if category == "metadata":
        if destination not in metadata_targets:
            raise core.IntegrityError(
                "journal metadata destination is not an updater metadata file"
            )
        return
    if category != "destination" or destination in metadata_targets:
        raise core.IntegrityError("journal rollback category is invalid")

    agent = intent.get("agent")
    entry_destination = intent.get("entry_destination")
    if not isinstance(agent, str) or not isinstance(entry_destination, str):
        raise core.IntegrityError("journal rollback ownership metadata is missing")
    matches = [
        entry for entry in manifest_data["entries"]
        if entry.get("agent") == agent
        and entry.get("destination") == entry_destination
    ]
    if len(matches) != 1:
        raise core.IntegrityError(
            f"journal rollback target has no exact manifest owner: {destination}"
        )
    if agent in _SKILL_AGENTS and dest == Path(entry_destination):
        raise core.IntegrityError(
            "journal rollback target cannot be an installation directory"
        )
    _validate_owned_destination(dest, matches[0])


def _restore_rollback_file(dest, record, backup):
    dest = Path(dest)
    _assert_no_symlink_components(dest)
    if not record["existed"]:
        try:
            dest.unlink()
        except FileNotFoundError:
            pass
        _sync_directory(dest.parent)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".rollback-tmp.", dir=str(dest.parent))
    try:
        os.close(fd)
        shutil.copyfile(backup, tmp)
        restore_mode = record.get("mode", stat.S_IMODE(backup.stat().st_mode))
        os.chmod(tmp, restore_mode)
        _sync_file(tmp)
        os.replace(tmp, str(dest))
        _sync_directory(dest.parent)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _cmd_rollback_locked(args):
    journal_data = core.Journal.load(JOURNAL_FILE)
    if journal_data is None:
        return {
            "command": "rollback", "performed": False,
            "reason": "no update journal found",
        }, EXIT_ERROR
    if journal_data.get("state") == "rolled_back":
        return {
            "command": "rollback", "performed": False,
            "reason": "the last update is already rolled back",
        }, EXIT_OK
    if (journal_data.get("journal_version") != 2
            or not isinstance(journal_data.get("backup_map"), dict)
            or not isinstance(journal_data.get("metadata_backup_map"), dict)):
        return {
            "command": "rollback", "performed": False,
            "reason": "journal predates exact backup mappings; automatic rollback is unsafe",
            "hint": "preserve the installation and recover its paths from the saved backup manually",
        }, EXIT_ERROR
    backups_dir = journal_data.get("backups_dir")
    if not isinstance(backups_dir, str):
        return {
            "command": "rollback", "performed": False,
            "reason": "journal has no usable backups directory",
        }, EXIT_ERROR
    backups = Path(backups_dir)
    _assert_no_symlink_components(backups)
    expected_backups_root = (STATE_DIR / "backups").resolve(strict=False)
    try:
        backups.resolve(strict=True).relative_to(expected_backups_root)
    except (OSError, ValueError) as exc:
        raise core.IntegrityError("journal backup directory is outside Sadskill state") from exc
    if not backups.is_dir():
        return {
            "command": "rollback", "performed": False,
            "reason": "journal has no usable backups directory",
        }, EXIT_ERROR

    manifest_data = core.load_manifest_data(MANIFEST_FILE)

    steps = journal_data.get("steps")
    if not isinstance(steps, list):
        raise core.IntegrityError("journal steps must be a list")
    intent_by_target = {}
    for step in steps:
        if not isinstance(step, dict) or step.get("name") != "mutation_intent":
            continue
        payload = step.get("payload")
        if not isinstance(payload, dict):
            raise core.IntegrityError("journal mutation intent is malformed")
        category = payload.get("category")
        dest_str = payload.get("destination")
        if category not in ("destination", "metadata") or not isinstance(dest_str, str):
            raise core.IntegrityError("journal mutation intent has invalid target")
        dest = Path(dest_str)
        if not dest.is_absolute() or ".." in dest.parts:
            raise core.IntegrityError("journal mutation target is not an absolute safe path")
        _validate_rollback_destination(payload, manifest_data)
        old_hash = payload.get("old_sha256")
        new_hash = payload.get("new_sha256")
        if old_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", str(old_hash)):
            raise core.IntegrityError("journal old hash is malformed")
        if not re.fullmatch(r"[0-9a-f]{64}", str(new_hash)):
            raise core.IntegrityError("journal new hash is malformed")
        key = (category, dest_str)
        intent = {"category": category, "destination": dest_str,
                  "old_sha256": old_hash, "new_sha256": new_hash,
                  "agent": payload.get("agent"),
                  "entry_destination": payload.get("entry_destination")}
        prior = intent_by_target.get(key)
        if prior is not None and prior != intent:
            raise core.IntegrityError("journal has inconsistent mutation intents")
        intent_by_target[key] = intent

    rollback_targets = []
    for (category, dest_str), intent in intent_by_target.items():
        mapping_name = "backup_map" if category == "destination" else "metadata_backup_map"
        mapping = journal_data[mapping_name]
        record = mapping.get(dest_str)
        if record is None:
            raise core.IntegrityError(f"journal has no exact backup mapping for {dest_str}")
        backup = _rollback_backup_record(record, backups)
        if record["existed"] != (intent["old_sha256"] is not None):
            raise core.IntegrityError(f"backup existence does not match journal intent for {dest_str}")
        if record["existed"] and record["sha256"] != intent["old_sha256"]:
            raise core.IntegrityError(f"backup hash does not match journal intent for {dest_str}")
        current_hash = _rollback_current_hash(dest_str)
        allowed_hashes = {intent["old_sha256"], intent["new_sha256"]}
        if current_hash not in allowed_hashes:
            rollback_targets.append({"category": category, "destination": dest_str,
                                     "intent": intent, "record": record,
                                     "backup": backup, "current_hash": current_hash})
        else:
            rollback_targets.append({"category": category, "destination": dest_str,
                                     "intent": intent, "record": record,
                                     "backup": backup, "current_hash": current_hash})

    conflicts = [item["destination"] for item in rollback_targets
                 if item["current_hash"] not in {
                     item["intent"]["old_sha256"], item["intent"]["new_sha256"]
                 }]
    if conflicts and not args.force:
        return {
            "command": "rollback", "performed": False,
            "conflicts": conflicts,
            "hint": "post-update changes detected; pass --force to preserve them in a conflict backup before rollback",
        }, EXIT_CONFLICT

    journal = core.Journal(JOURNAL_FILE)
    journal.data = journal_data
    conflict_backups = journal.data.setdefault("rollback_conflict_backups", {})
    if conflicts and args.force:
        # Preserve every conflicting current file and durably record all copies
        # before restoring any destination or metadata file.
        pending = {}
        conflict_dir = backups / "rollback-conflicts"
        _ensure_private_directory(conflict_dir, parents=True, exist_ok=True)
        for index, item in enumerate(rollback_targets, 1):
            if item["destination"] not in conflicts:
                continue
            existing = conflict_backups.get(item["destination"])
            if existing and item["current_hash"] == existing.get("sha256"):
                continue
            snapshot = _backup_dest(
                item["destination"], conflict_dir,
                f"conflict-{index:06d}-{time.time_ns()}"
            )
            if snapshot["existed"] and snapshot["sha256"] != item["current_hash"]:
                raise core.IntegrityError(
                    f"rollback conflict changed while backing up: {item['destination']}"
                )
            pending[item["destination"]] = snapshot
        conflict_backups.update(pending)
        journal.step("rollback_conflicts_backed_up", {
            "destinations": sorted(pending),
        })

    journal.step("rollback_started", {"forced": bool(conflicts and args.force)})
    restored = []
    # Restore managed files first; exact saved metadata is restored last so it
    # continues to describe the final pre-update filesystem state.
    rollback_targets.sort(key=lambda item: item["category"] == "metadata")
    for item in rollback_targets:
        dest_str = item["destination"]
        current_hash = _rollback_current_hash(dest_str)
        old_hash = item["intent"]["old_sha256"]
        if current_hash == old_hash:
            continue  # already restored, or an interrupted apply never wrote it
        if current_hash != item["intent"]["new_sha256"]:
            # A forced conflict was backed up above. If it changed again while
            # rollback was running, stop before overwriting that new edit.
            saved_conflict = conflict_backups.get(dest_str)
            saved_hash = (saved_conflict.get("sha256")
                          if isinstance(saved_conflict, dict) else object())
            if not (args.force and dest_str in conflicts
                    and current_hash == saved_hash):
                raise ConflictError(
                    f"rollback target changed during recovery: {dest_str}"
                )
        journal.step("rollback_intent", {
            "category": item["category"], "destination": dest_str,
            "current_sha256": current_hash, "restore_sha256": old_hash,
        })
        _restore_rollback_file(dest_str, item["record"], item["backup"])
        if _rollback_current_hash(dest_str) != old_hash:
            raise core.IntegrityError(f"rollback restore verification failed: {dest_str}")
        journal.step("rollback_applied", {
            "category": item["category"], "destination": dest_str,
            "sha256": old_hash,
        })
        restored.append(dest_str)

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
        "restored": restored, "backups_dir": str(backups),
        "conflict_backups": sorted(conflict_backups),
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
                        help="deprecated; external-manager installs remain refused")

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
