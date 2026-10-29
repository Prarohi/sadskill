"""Optional guidance must be discoverable after installing a complete skill."""

from pathlib import Path
import re

from tests.helpers import REPO_ROOT, SandboxCase


class OptionalReferencePackagingTests(SandboxCase):
    def test_install_preserves_linked_reference_graph_for_each_host(self):
        source = Path(REPO_ROOT) / "skills" / "sadskill"
        router = (source / "SKILL.md").read_text(encoding="utf-8")
        links = set(re.findall(r"\]\((references/[^)#]+\.md)\)", router))
        self.assertTrue(links, "optional references must be reachable from the router")
        result = self.run_install("--agent", "all", "--target", self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        targets = [
            Path(self.home) / ".codex/skills/sadskill",
            Path(self.home) / ".claude/skills/sadskill",
            Path(self.home) / ".gemini/skills/sadskill",
            Path(self.home) / ".gemini/antigravity/skills/sadskill",
            Path(self.project) / ".cursor/skills/sadskill",
        ]
        for target in targets:
            with self.subTest(host=target):
                self.assertEqual((target / "SKILL.md").read_bytes(),
                                 (source / "SKILL.md").read_bytes())
                for link in links:
                    guide = target / link
                    self.assertEqual(guide.read_bytes(), (source / link).read_bytes())
                    for url in re.findall(r"\]\(([^)]+)\)", guide.read_text(encoding="utf-8")):
                        if url.startswith(("https://", "http://", "#", "mailto:")):
                            continue
                        local_target = (guide.parent / url.split("#", 1)[0]).resolve()
                        self.assertTrue(local_target.is_relative_to(target.resolve()))
                        self.assertTrue(local_target.exists(), str(local_target))
