"""Defect class 7: two simultaneous processes on the same manifest.

Current behavior: manifest.py has no locking, so concurrent record
operations lose updates (last writer wins).
"""

import os
import unittest

from tests.helpers import SandboxCase

DEST_A = ".claude/skills/sadskill"
DEST_B = ".codex/skills/sadskill"


class ConcurrencyTests(SandboxCase):
    def test_parallel_record_keeps_both_destinations(self):
        dest_a = os.path.join(self.home, DEST_A)
        dest_b = os.path.join(self.home, DEST_B)
        os.makedirs(dest_a)
        os.makedirs(dest_b)

        # Initialize the manifest deterministically.
        rc = self.run_manifest(
            "record", "--manifest", self.manifest_path(),
            "--agent", "claude", "--destination", dest_a,
            "--backup", "", "--target", self.project,
        )
        self.assertEqual(rc.returncode, 0, rc.stderr)

        procs = [
            self.spawn_manifest(
                "record", "--manifest", self.manifest_path(),
                "--agent", agent, "--destination", dest,
                "--backup", "", "--target", self.project,
            )
            for agent, dest in (("codex", dest_a), ("cursor", dest_b))
        ]
        outs = [p.communicate() for p in procs]
        for p, (out, err) in zip(procs, outs):
            self.assertEqual(
                p.returncode, 0,
                f"concurrent record failed: {out} {err}",
            )

        manifest = self.load_manifest()
        destinations = {e["destination"] for e in manifest["entries"]}
        self.assertIn(dest_a, destinations, "lost update: dest A missing")
        self.assertIn(dest_b, destinations, "lost update: dest B missing")


if __name__ == "__main__":
    unittest.main()
