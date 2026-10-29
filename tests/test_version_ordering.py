"""Release precedence must not skip a stable upgrade after a prerelease."""

import unittest

from scripts.sadskill_core import parse_version, version_text


class VersionOrderingTests(unittest.TestCase):
    def test_prerelease_precedence_and_release_roundtrip(self):
        ordered = ["0.3.0-1", "0.3.0-alpha", "0.3.0-alpha.1",
                   "0.3.0-alpha.beta", "0.3.0-beta", "0.3.0-beta.2",
                   "0.3.0-beta.11", "0.3.0-rc.1", "0.3.0", "0.3.1"]
        for first, second in zip(ordered, ordered[1:]):
            with self.subTest(first=first, second=second):
                self.assertLess(parse_version(first), parse_version(second))
        for text in ordered:
            self.assertEqual(version_text(parse_version("v" + text)), text)
