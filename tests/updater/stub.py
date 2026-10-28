"""Local loopback GitHub-API stub for updater tests.

Serves release metadata and tarballs over http://127.0.0.1:<port> so tests
can exercise SADSKILL_UPDATE_API_BASE without any real network access.
"""

import hashlib
import http.server
import io
import json
import socketserver
import tarfile
import threading
import time

REPO = "sadafbabu/sadskill"

SKILL_V031 = """---
name: sadskill
version: 0.3.1
author: sadafbabu
license: MIT
---

# sadskill 0.3.1 (stub)

UPDATER_V031_MARKER
NEW_VERSION_MARKER_UPDATER_TEST
"""

GUARDRAIL = "#!/usr/bin/env bash\n# stub guardrail\nexit 0\n"

COMMAND_V031 = "# sad-analyze (stub 0.3.1)\nUPD_COMMAND_MARKER\n"


def build_tarball(top_dir="sadskill-0.3.1", skill_md=SKILL_V031,
                  command_md=COMMAND_V031, guardrail=GUARDRAIL):
    """Build a codeload-style tarball in memory. Returns (bytes, per-file hashes)."""
    buf = io.BytesIO()
    files = {
        f"{top_dir}/skills/sadskill/SKILL.md": skill_md.encode(),
        f"{top_dir}/skills/sadskill/hooks/git-guardrail.sh": guardrail.encode(),
        f"{top_dir}/commands/claude/sad-analyze.md": command_md.encode(),
    }
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(data))
    hashes = {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}
    return buf.getvalue(), hashes


class _Handler(http.server.BaseHTTPRequestHandler):
    routes = {}  # class attr: {path: (status, body_bytes)}

    def do_GET(self):
        route = self.routes.get(self.path.split("?")[0])
        if route is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        status, body = route
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class GitHubStub:
    """In-process stub server. Usage:

        stub = GitHubStub()
        stub.serve_release(tag="v0.3.1", prerelease=False, tarball=b"...", sums=None)
        stub.start()
        try: ... os.environ["SADSKILL_UPDATE_API_BASE"] = stub.api_base
        finally: stub.stop()
    """

    def __init__(self):
        self._routes = {}
        self._server = None
        self._thread = None
        self._port = None
        self._release = None

    def serve_release(self, tag, tarball, prerelease=False, sums_bytes=None,
                      include_in_beta=True):
        """Configure or update the release served by this stub. Can be called before or after start()."""
        tar_url = None
        if tarball is not None:
            dl_path = f"/dl/{tag}.tar.gz"
            self._routes[dl_path] = (200, tarball)
            tar_url = f"http://127.0.0.1:__PORT__{dl_path}"
        assets = []
        if sums_bytes is not None:
            self._routes["/dl/SHA256SUMS.txt"] = (200, sums_bytes)
            assets.append(
                {
                    "name": "SHA256SUMS.txt",
                    "browser_download_url":
                        f"http://127.0.0.1:__PORT__/dl/SHA256SUMS.txt",
                }
            )
        release = {
            "tag_name": tag,
            "name": tag,
            "prerelease": prerelease,
            "draft": False,
            "url": f"https://api.github.com/repos/{REPO}/releases/1",
            "html_url": f"https://github.com/{REPO}/releases/tag/{tag}",
            "tarball_url": tar_url,
            "assets": assets,
        }
        self._release = release

        # If server is already running, update its routes with real port
        if self._server is not None:
            port = str(self._port)
            if release.get("tarball_url"):
                release["tarball_url"] = release["tarball_url"].replace("__PORT__", port)
            for asset in release.get("assets", []):
                asset["browser_download_url"] = asset["browser_download_url"].replace("__PORT__", port)

            # Update the running handler's routes for ALL paths in self._routes
            for path, (status, body) in self._routes.items():
                _Handler.routes[path] = (status, body)

            # Update the running handler's routes
            _Handler.routes[f"/repos/{REPO}/releases/latest"] = (200, json.dumps(release).encode())
            _Handler.routes[f"/repos/{REPO}/releases"] = (200, json.dumps([release]).encode())
            _Handler.routes[f"/repos/{REPO}/releases/tags/{tag}"] = (200, json.dumps(release).encode())

    def start(self):
        class Server(socketserver.TCPServer):
            allow_reuse_address = True

        # Bind first so we can fill URLs with the real port.
        self._server = Server(("127.0.0.1", 0), _Handler)
        self._port = self._server.server_address[1]
        base = f"http://127.0.0.1:{self._port}"
        # Rebuild routes with the real port.
        final_routes = {}
        for path, (status, body) in self._routes.items():
            final_routes[path] = (status, body)
        release = self._release
        if release is not None:
            # Fill the __PORT__ token with the real port.
            if release.get("tarball_url"):
                release["tarball_url"] = release["tarball_url"].replace(
                    "__PORT__", str(self._port))
            for asset in release.get("assets", []):
                asset["browser_download_url"] = asset["browser_download_url"].replace(
                    "__PORT__", str(self._port))
            final_routes[f"/repos/{REPO}/releases/latest"] = (
                200, json.dumps(release).encode())
            final_routes[f"/repos/{REPO}/releases"] = (
                200, json.dumps([release]).encode())
            final_routes[f"/repos/{REPO}/releases/tags/{release['tag_name']}"] = (
                200, json.dumps(release).encode())
        else:
            # Placeholder routes - will be filled when serve_release is called
            final_routes[f"/repos/{REPO}/releases/latest"] = (200, b'{"error":"release not configured"}')
            final_routes[f"/repos/{REPO}/releases"] = (200, b'[]')
        self._routes.update(final_routes)
        _Handler.routes = self._routes
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return base

    @property
    def api_base(self):
        return f"http://127.0.0.1:{self._port}"

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
