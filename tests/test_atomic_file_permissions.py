"""Private permissions for Sadskill's state-file atomic writers."""

import stat
import tempfile
import unittest
from pathlib import Path

from scripts import sadskill_core as core


class AtomicFilePermissionTests(unittest.TestCase):
    def test_atomic_text_and_bytes_default_to_owner_only(self):
        with tempfile.TemporaryDirectory(prefix="sadskill-atomic-mode-") as tmp:
            text_path = Path(tmp) / "state.json"
            bytes_path = Path(tmp) / "state.bin"

            core.atomic_write_text(text_path, "{}\n")
            core.atomic_write_bytes(bytes_path, b"private\n")

            self.assertEqual(stat.S_IMODE(text_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(bytes_path.stat().st_mode), 0o600)

    def test_atomic_writer_rejects_group_or_other_access_before_write(self):
        with tempfile.TemporaryDirectory(prefix="sadskill-atomic-mode-") as tmp:
            target = Path(tmp) / "must-not-exist.json"

            with self.assertRaisesRegex(ValueError, "owner-only"):
                core.atomic_write_text(target, "{}\n", mode=0o644)

            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
