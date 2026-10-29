# CLI init workspace safety

`sad init` now refuses to initialize `.sad/` when its directory, one of its
managed subdirectories, or any template file is a pre-existing symlink.
Exclusive template creation prevents accidental overwrites if a file appears
during initialization. Existing regular template files are preserved.

These guards prevent ordinary redirection through malicious pre-existing
repository symlinks. **They do not claim race-proof isolation against a
concurrent hostile process** which can alter directory components during
initialization. For malicious repositories, run agents in an external
disposable workspace with appropriate OS permission boundaries.

New tests use only temporary project folders; no real user profile is edited.
Changes are intentionally isolated from PR #4's user-file deletion repair and
PR #9's sandbox hardening.
