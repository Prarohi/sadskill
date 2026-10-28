"""Fixed older-install fixture, independent of the checkout's release version."""

import json
from pathlib import Path
import re

from scripts.sadskill_core import compute_sha256
from tests.helpers import SandboxCase


class UpdaterSandboxCase(SandboxCase):
    def run_install(self, *args):
        result = super().run_install(*args)
        if result.returncode:
            return result
        self.set_installed_version("0.3.0")
        return result

    def set_installed_version(self, version):
        manifest_path = Path(self.manifest_path())
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest["entries"]:
            root = Path(entry["destination"])
            if not root.is_dir() or not (root / "SKILL.md").is_file():
                continue
            skill = root / "SKILL.md"
            text = skill.read_text()
            skill.write_text(re.sub(r"(?m)^([ \t]*)version:[^\n]*$", lambda match: match.group(1) + "version: " + version, text, count=1))
            entry["content_hash"] = compute_sha256(root)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
