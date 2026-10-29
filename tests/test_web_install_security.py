"""Offline negative controls for pinned web installer. No real downloads."""
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

WEB = Path(__file__).resolve().parents[1] / "scripts" / "web-install.sh"
SHA = "a" * 40
ROOT = "sadskill-" + SHA


def tar_bytes(files, special=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        directory = tarfile.TarInfo(ROOT)
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        for path, payload in files.items():
            content = payload.encode("utf-8")
            entry = tarfile.TarInfo(ROOT + "/" + path)
            entry.size = len(content)
            entry.mode = 0o755 if path.endswith(".sh") else 0o644
            archive.addfile(entry, io.BytesIO(content))
        if special is not None:
            archive.addfile(special)
    return stream.getvalue()


class VerifiedWebInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.archive = self.dir / "fixture.tar.gz"
        self.marker = self.dir / "executed"
        fake = self.dir / "bin"
        fake.mkdir()
        curl = fake / "curl"
        curl.write_text(
            "#!/usr/bin/env python3\n"
            "import os, shutil, sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "output = Path(args[args.index('-o') + 1])\n"
            "Path(os.environ['WEB_TEST_CURL_CALLED']).write_text('called')\n"
            "Path(os.environ['WEB_TEST_WORKDIR_MARKER']).write_text(str(output.parent))\n"
            "Path(os.environ['WEB_TEST_CURL_ARGS']).write_text('\\n'.join(args))\n"
            "if os.environ.get('WEB_TEST_CURL_FAIL') == '1':\n"
            "    output.write_bytes(b'partial archive')\n"
            "    sys.exit(22)\n"
            "if os.environ.get('WEB_TEST_CURL_REDIRECT') == '1':\n"
            "    limit = args.index('--max-redirs') + 1\n"
            "    sys.exit(47 if args[limit] == '0' else 0)\n"
            "shutil.copyfile(os.environ['WEB_TEST_TARBALL'], output)\n",
            encoding="utf-8",
        )
        curl.chmod(0o755)
        self.env = dict(os.environ)
        self.env["PATH"] = str(fake) + os.pathsep + self.env.get("PATH", "")
        self.env["WEB_TEST_TARBALL"] = str(self.archive)
        self.env["WEB_TEST_MARKER"] = str(self.marker)
        self.env["WEB_TEST_CURL_CALLED"] = str(self.dir / "curl-called")
        self.env["WEB_TEST_WORKDIR_MARKER"] = str(self.dir / "workdir-path")
        self.env["WEB_TEST_CURL_ARGS"] = str(self.dir / "curl-args")

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, files=None, special=None):
        if files is None:
            files = {
                "VERSION": "0.5.0\n",
                "install.sh": '#!/bin/bash\nprintf "%s" "$*" > "$WEB_TEST_MARKER"\n',
            }
        blob = tar_bytes(files, special)
        self.archive.write_bytes(blob)
        return hashlib.sha256(blob).hexdigest()

    def call(self, digest, *args):
        return subprocess.run(
            ["/bin/bash", str(WEB), "--commit", SHA, "--sha256", digest, "--", *args],
            env=self.env, text=True, capture_output=True, timeout=20,
        )

    def assert_workdir_removed(self):
        marker = Path(self.env["WEB_TEST_WORKDIR_MARKER"])
        workdir = Path(marker.read_text(encoding="utf-8"))
        self.assertFalse(workdir.exists(), f"temporary download directory leaked: {workdir}")

    def test_missing_sha_does_not_download_or_execute(self):
        run = subprocess.run(["/bin/bash", str(WEB)], env=self.env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertFalse(self.marker.exists())

    def test_verified_source_executes_pinned_installer(self):
        digest = self.prepare()
        result = self.call(digest, "--agent", "codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), "--agent codex")
        self.assertIn("safe extraction verified", result.stdout)
        curl_args = self.env["WEB_TEST_CURL_ARGS"]
        args = Path(curl_args).read_text(encoding="utf-8").splitlines()
        self.assertIn("--max-redirs", args)
        self.assertEqual(args[args.index("--max-redirs") + 1], "0")
        self.assertEqual(args[0], "--disable")
        self.assertIn(f"https://codeload.github.com/Prarohi/sadskill/tar.gz/{SHA}", args)
        self.assert_workdir_removed()

    def test_verified_helper_retains_executable_permission(self):
        digest = self.prepare({
            "VERSION": "0.5.0\n",
            "install.sh": '#!/bin/bash\n[ -x "$(dirname "$0")/helper.sh" ] && printf ok > "$WEB_TEST_MARKER"\n',
            "helper.sh": "#!/bin/bash\nexit 0\n",
        })
        result = self.call(digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), "ok")

    def test_mismatched_digest_prevents_execution(self):
        self.prepare()
        result = self.call("0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mismatch", result.stderr)
        self.assertFalse(self.marker.exists())
        self.assert_workdir_removed()

    def test_invalid_digest_is_rejected_before_download(self):
        self.prepare()
        result = self.call("not-a-digest")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(Path(self.env["WEB_TEST_CURL_CALLED"]).exists())
        self.assertFalse(self.marker.exists())

    def test_download_failure_cleans_partial_archive_and_never_executes(self):
        self.prepare()
        self.env["WEB_TEST_CURL_FAIL"] = "1"
        result = self.call(hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(Path(self.env["WEB_TEST_CURL_CALLED"]).exists())
        self.assertFalse(self.marker.exists())
        self.assert_workdir_removed()

    def test_redirect_is_refused_without_following_it(self):
        self.prepare()
        self.env["WEB_TEST_CURL_REDIRECT"] = "1"
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertIn("--max-redirs\n0", Path(self.env["WEB_TEST_CURL_ARGS"]).read_text())
        self.assert_workdir_removed()

    def test_path_traversal_rejected_after_digest_verification(self):
        digest = self.prepare({
            "VERSION": "0.5.0\n",
            "install.sh": "exit 0\n",
            "../outside": "danger",
        })
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe archive path", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_symlink_rejected_even_if_digest_matches(self):
        entry = tarfile.TarInfo(ROOT + "/link")
        entry.type = tarfile.SYMTYPE
        entry.linkname = "/etc/passwd"
        digest = self.prepare(special=entry)
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("link or special file", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_hardlink_rejected_even_if_digest_matches(self):
        entry = tarfile.TarInfo(ROOT + "/hardlink")
        entry.type = tarfile.LNKTYPE
        entry.linkname = ROOT + "/VERSION"
        digest = self.prepare(special=entry)
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("link or special file", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_device_member_rejected_even_if_digest_matches(self):
        entry = tarfile.TarInfo(ROOT + "/device")
        entry.type = tarfile.CHRTYPE
        entry.devmajor = 1
        entry.devminor = 3
        digest = self.prepare(special=entry)
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("link or special file", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_duplicate_archive_path_rejected(self):
        entry = tarfile.TarInfo(ROOT + "/VERSION")
        entry.size = 0
        digest = self.prepare(special=entry)
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_single_oversized_member_rejected(self):
        files = {
            "VERSION": "0.5.0\n",
            "install.sh": "exit 0\n",
            "large.bin": "x" * (16 * 1024 * 1024 + 1),
        }
        digest = self.prepare(files)
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("file exceeds size limit", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_total_expanded_size_limit_rejected(self):
        files = {"VERSION": "0.5.0\n", "install.sh": "exit 0\n"}
        files.update({f"payload-{index}.bin": "z" * (13 * 1024 * 1024) for index in range(5)})
        digest = self.prepare(files)
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("total extracted size exceeds limit", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_missing_installer_or_version_is_rejected(self):
        cases = (
            {"VERSION": "0.5.0\n", "README.md": "no installer"},
            {"install.sh": 'printf executed > "$WEB_TEST_MARKER"\n'},
        )
        for files in cases:
            with self.subTest(files=sorted(files)):
                digest = self.prepare(files)
                result = self.call(digest)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("no installer or VERSION", result.stderr)
                self.assertFalse(self.marker.exists())

    def test_unicode_and_spaced_archive_paths_are_preserved_safely(self):
        helper = "helpers/with space/বাংলা-helper.sh"
        installer = (
            "#!/bin/bash\n"
            'base="$(cd -- "$(dirname -- "$0")" && pwd -P)"\n'
            f'test -x "$base/{helper}" && printf ok > "$WEB_TEST_MARKER"\n'
        )
        digest = self.prepare({
            "VERSION": "0.5.0\n",
            "install.sh": installer,
            helper: "#!/bin/bash\nexit 0\n",
        })
        result = self.call(digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), "ok")
        self.assert_workdir_removed()


if __name__ == "__main__":
    unittest.main()
