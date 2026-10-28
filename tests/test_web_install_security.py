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
            "shutil.copyfile(os.environ['WEB_TEST_TARBALL'],"
            "sys.argv[sys.argv.index('-o')+1])\n",
            encoding="utf-8",
        )
        curl.chmod(0o755)
        self.env = dict(os.environ)
        self.env["PATH"] = str(fake) + os.pathsep + self.env.get("PATH", "")
        self.env["WEB_TEST_TARBALL"] = str(self.archive)
        self.env["WEB_TEST_MARKER"] = str(self.marker)

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

    def test_duplicate_archive_path_rejected(self):
        entry = tarfile.TarInfo(ROOT + "/VERSION")
        entry.size = 0
        digest = self.prepare(special=entry)
        result = self.call(digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
