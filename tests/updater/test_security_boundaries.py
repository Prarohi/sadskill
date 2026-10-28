"""Regression tests for updater trust boundaries and resource limits."""

import http.server
import importlib.util
import io
import json
import os
import socketserver
import sys
import tarfile
import threading
import unittest
from unittest.mock import patch

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from helpers import SandboxCase  # noqa: E402
from tests.updater.stub import GitHubStub, build_tarball  # noqa: E402

_UPDATER_PATH = os.path.join(REPO_ROOT, "scripts", "sadskill-update.py")
_UPDATER_SPEC = importlib.util.spec_from_file_location(
    "sadskill_update_test_module", _UPDATER_PATH
)
_UPDATER = importlib.util.module_from_spec(_UPDATER_SPEC)
_UPDATER_SPEC.loader.exec_module(_UPDATER)


def _handler(callback):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            status, headers, body = callback(self)
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return Handler


class _ThreadingHTTPServer(socketserver.ThreadingMixIn,
                           http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class RedirectCredentialTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.run_install("-a", "claude")
        self.foreign_authorization = []
        release = {
            "tag_name": "v0.3.1",
            "url": "https://api.github.com/repos/sadafbabu/sadskill/releases/1",
            "html_url": "https://github.com/sadafbabu/sadskill/releases/tag/v0.3.1",
            "tarball_url": "https://api.github.com/repos/sadafbabu/sadskill/tarball/v0.3.1",
            "assets": [],
        }

        def foreign_request(request):
            self.foreign_authorization.append(
                request.headers.get("Authorization")
            )
            return 200, {"Content-Type": "application/json"}, json.dumps(
                release
            ).encode()

        try:
            self.foreign = _ThreadingHTTPServer(
                ("127.0.0.2", 0), _handler(foreign_request)
            )
        except OSError as exc:
            self.skipTest(f"loopback alias unavailable for redirect test: {exc}")
        self.foreign_thread = threading.Thread(
            target=self.foreign.serve_forever, daemon=True
        )
        self.foreign_thread.start()
        self.addCleanup(self.foreign.shutdown)
        self.addCleanup(self.foreign.server_close)

        foreign_url = f"http://127.0.0.2:{self.foreign.server_port}/release"

        def redirect_request(_request):
            return 302, {"Location": foreign_url}, b""

        self.origin = _ThreadingHTTPServer(
            ("127.0.0.1", 0), _handler(redirect_request)
        )
        self.origin_thread = threading.Thread(
            target=self.origin.serve_forever, daemon=True
        )
        self.origin_thread.start()
        self.addCleanup(self.origin.shutdown)
        self.addCleanup(self.origin.server_close)
        self.env["SADSKILL_UPDATE_API_BASE"] = (
            f"http://127.0.0.1:{self.origin.server_port}"
        )
        self.env["GITHUB_TOKEN"] = "DUMMY_TOKEN_NEVER_REAL"

    def test_cross_origin_redirect_never_receives_bearer_token(self):
        result = self.run_update("check", "--json")
        self.assertNotIn("DUMMY_TOKEN_NEVER_REAL", result.stdout + result.stderr)
        self.assertTrue(
            all(value is None for value in self.foreign_authorization),
            "a cross-origin redirect received the API bearer token",
        )


class ReleaseIdentityTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.run_install("-a", "claude")
        self.stub = GitHubStub()
        self.stub.serve_release("v0.3.1", build_tarball()[0])
        self.base = self.stub.start()
        self.addCleanup(self.stub.stop)
        self.env["SADSKILL_UPDATE_API_BASE"] = self.base

    def test_repository_string_in_body_does_not_prove_release_identity(self):
        self.stub._routes["/repos/sadafbabu/sadskill/releases/latest"] = (
            200,
            json.dumps({
                "tag_name": "v9.9.9",
                "body": "unrelated text /repos/sadafbabu/sadskill/releases",
                "url": "https://api.github.com/repos/attacker/other/releases/1",
                "html_url": "https://evil.example/releases/tag/v9.9.9",
                "tarball_url": "https://evil.example/archive.tar.gz",
                "assets": [],
            }).encode(),
        )
        result = self.run_update("check", "--json")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_official_release_identity_with_untrusted_artifact_url_is_rejected(self):
        self.stub._routes["/repos/sadafbabu/sadskill/releases/latest"] = (
            200,
            json.dumps({
                "tag_name": "v0.3.1",
                "url": "https://api.github.com/repos/sadafbabu/sadskill/releases/1",
                "html_url": "https://github.com/sadafbabu/sadskill/releases/tag/v0.3.1",
                "tarball_url": "https://evil.example/archive.tar.gz",
                "assets": [],
            }).encode(),
        )
        result = self.run_update("check", "--json")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)


class ArchiveResourceLimitTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.run_install("-a", "claude")
        self.stub = GitHubStub()
        self.base = self.stub.start()
        self.addCleanup(self.stub.stop)
        self.env["SADSKILL_UPDATE_API_BASE"] = self.base

    def test_aggregate_decompression_limit_rejects_before_installation_change(self):
        buf = io.BytesIO()
        payload = b"Z" * (4 * 1024 * 1024)
        with tarfile.open(fileobj=buf, mode="w:gz") as archive:
            for index in range(17):
                member = tarfile.TarInfo(
                    f"project/skills/sadskill/blob-{index}.dat"
                )
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
        compressed = buf.getvalue()
        self.assertLess(len(compressed), 1024 * 1024)
        self.stub.serve_release("v9.9.9", compressed)

        before = self.home_snapshot()
        result = self.run_update("apply", "--json")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertEqual(self.home_snapshot(), before)

    def test_directory_payload_cannot_bypass_decompression_limits(self):
        buf = io.BytesIO()
        payload = b"Z" * (4 * 1024 * 1024)
        with tarfile.open(fileobj=buf, mode="w:gz") as archive:
            for index in range(17):
                directory = tarfile.TarInfo(f"project/dir-{index}/")
                directory.type = tarfile.DIRTYPE
                directory.size = len(payload)
                archive.addfile(directory, io.BytesIO(payload))
            skill = tarfile.TarInfo("project/skills/sadskill/SKILL.md")
            skill.size = len(b"version: 0.3.1\n")
            archive.addfile(skill, io.BytesIO(b"version: 0.3.1\n"))
        compressed = buf.getvalue()
        self.assertLess(len(compressed), 1024 * 1024)

        with self.assertRaisesRegex(
            _UPDATER.core.IntegrityError, "directory member contains data"
        ):
            _UPDATER.stage_archive(compressed, write=False)

    def test_pax_extension_payload_is_bounded_before_tarfile_parses_it(self):
        value = b"X" * (2 * 1024 * 1024)
        length = len(value) + 32
        while True:
            record = str(length).encode() + b" comment=" + value + b"\n"
            if len(record) == length:
                break
            length = len(record)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as archive:
            pax = tarfile.TarInfo("PaxHeader")
            pax.type = tarfile.XHDTYPE
            pax.size = len(record)
            archive.addfile(pax, io.BytesIO(record))
            skill_bytes = b"version: 0.3.1\n"
            skill = tarfile.TarInfo("project/skills/sadskill/SKILL.md")
            skill.size = len(skill_bytes)
            archive.addfile(skill, io.BytesIO(skill_bytes))
        compressed = buf.getvalue()
        self.assertLess(len(compressed), 64 * 1024)

        with patch.object(_UPDATER, "MAX_ARCHIVE_STREAM_BYTES", 1024 * 1024):
            with self.assertRaisesRegex(
                _UPDATER.core.IntegrityError,
                "decompressed stream size limit",
            ):
                _UPDATER.stage_archive(compressed, write=False)

    def test_symlinked_backups_parent_is_rejected_before_any_write(self):
        self.stub.serve_release("v0.3.1", build_tarball()[0])
        backups_root = os.path.join(self.home, ".sadskill", "backups")
        outside = os.path.join(os.path.dirname(self.home), "outside-backups")
        os.mkdir(outside)
        os.symlink(outside, backups_root)
        before = self.home_snapshot()

        result = self.run_update("apply", "--json")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("symlink path component", result.stdout)
        self.assertEqual(self.home_snapshot(), before)
        self.assertEqual(os.listdir(outside), [])
        self.assertFalse(
            os.path.exists(os.path.join(self.home, ".sadskill", "update-journal.json"))
        )


class ChecksumTrustTests(SandboxCase):
    def setUp(self):
        super().setUp()
        self.run_install("-a", "claude")
        self.stub = GitHubStub()
        self.tarball, self.hashes = build_tarball(top_dir="sadskill-0.3.1")
        self.stub.serve_release("v0.3.1", self.tarball)
        self.base = self.stub.start()
        self.addCleanup(self.stub.stop)
        self.env["SADSKILL_UPDATE_API_BASE"] = self.base

    def test_check_discloses_transport_only_when_checksum_asset_is_absent(self):
        result = self.run_update("check", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout).get("artifact_trust"),
                         "TRANSPORT_ONLY")

    def test_malformed_published_checksum_fails_closed(self):
        self.stub.serve_release(
            "v0.3.1", self.tarball, sums_bytes=b"not-a-sha256sum\n"
        )
        result = self.run_update("apply", "--json")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)

    def test_published_checksum_missing_requested_archive_fails_closed(self):
        self.stub.serve_release(
            "v0.3.1", self.tarball,
            sums_bytes=("0" * 64 + "  unrelated.tar.gz\n").encode(),
        )
        result = self.run_update("apply", "--json")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
