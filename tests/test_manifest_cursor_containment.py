"""Cursor workspace authorization must never leak across unrelated directories."""
from pathlib import Path
import tempfile
import unittest

from scripts import manifest


class CursorContainmentTests(unittest.TestCase):
    def test_unrelated_cursor_workspace_is_not_implicitly_authorized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected"
            selected.mkdir()
            other_rule = root / "other" / ".cursor" / "rules" / "sadskill.mdc"
            other_rule.parent.mkdir(parents=True)
            other_rule.write_text("not owned", encoding="utf-8")
            selected_rule = selected / ".cursor" / "rules" / "sadskill.mdc"
            selected_rule.parent.mkdir(parents=True)
            selected_rule.write_text("owned", encoding="utf-8")
            roots = manifest.get_allowed_roots(str(selected))
            self.assertTrue(manifest.is_path_contained_in_roots(selected_rule, roots))
            self.assertFalse(manifest.is_path_contained_in_roots(other_rule, roots))
            self.assertFalse(manifest.is_path_contained_in_roots(other_rule,
                manifest.get_allowed_roots()))

    def test_directory_digest_tracks_added_empty_directory_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("# test", encoding="utf-8")
            original = manifest.compute_sha256(skill)
            (skill / "empty").mkdir()
            self.assertNotEqual(original, manifest.compute_sha256(skill))
            (skill / "empty").rmdir()
            (skill / "link").symlink_to(root / "missing")
            self.assertNotEqual(original, manifest.compute_sha256(skill))


if __name__ == "__main__":
    unittest.main()
