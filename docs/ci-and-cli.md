# Sadskill CI and CLI: developer reference

## CI versus CLI

**Continuous Integration (CI)** runs automated checks on pushes and pull
requests. Sadskill's GitHub Actions workflow is
[.github/workflows/ci.yml](../.github/workflows/ci.yml).
CI passing indicates these **specific checks at the checked commit** passed,
not that a model agent is better or that production behavior is guaranteed.

**Command-Line Interface (CLI)** is the local `bin/sad` executable.
It offers `sad doctor`, `sad verify`, `sad guard`, `sad memory`,
`sad bench`, `sad init` and `sad sandbox`.

## Required checks on protected main

- `Verify sadskill (Node 20)`: Python regression tests (including CLI, workflow
  and safety checks), separately discovered skill-contract tests, evidence /
  installer verification, and offline benchmark fixture contracts.
- `Verify sadskill (Node 22)`: same checks with a second Node version,
  including `skills` package single-skill discovery.
- `Native PostgreSQL RLS`: real PostgreSQL policy tests and negative control
  proving disabled RLS fails.

The workflow grants only `contents: read`, pins GitHub Actions to immutable
commits, bounds the main verification job to 30 minutes and the RLS job to 10
minutes, and cancels superseded runs for **the same** PR/branch. It does not
cancel another PR's independent checks.

Run the closest verification locally before pushing:

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests/skill-contract -p 'test_*.py' -v
python3 scripts/verify.py
python3 benchmarks/runner.py
```

The `tests/skill-contract` directory is intentionally discovered separately:
the standard `unittest discover -s tests` scan does not reliably descend into
a hyphenated, non-package directory.

## Using the CLI safely

```bash
./bin/sad --help
./bin/sad doctor
./bin/sad verify --all
./bin/sad guard 'git reset --hard HEAD~1'
./bin/sad bench --provider mock --condition sadskill --task C1-01
./bin/sad bench --provider codex --condition sadskill --task C1-01
```

**Critical benchmark limitation:** `--provider mock` deliberately creates
simulated fixtures. They are **not actual model tests** or measured token
savings. Live Codex/Claude/Gemini CLI adapters are opt-in and require an
authenticated CLI inside an external disposable isolated runner. No
independently graded paired real-agent study is published. CI green,
mock fixture passing and static contract passing do not establish
comparative superiority.

**Critical security limitation:** `sad guard` is a defense-in-depth lexical
filter, not a complete shell or SQL security boundary. Always rely on host
permissions, sandboxing and explicit consent for potentially destructive
operations.

## How to merge responsibly

PR #4 and PR #9 have already been merged into protected `main` as of
2026-10-30. New PRs should target current main and require exact-head Node
20/22 and native PostgreSQL RLS checks with resolved review threads. Request
independent review for security-sensitive changes. CodeQL also runs on PRs
and must pass before release-draft preparation; it is not currently a
main-ruleset required status check. Never infer a successful new head from
an older passing CI run.

If your GitHub connector cannot update the ruleset, do not alter the branch
through an alternate destructive ref operation. Explain the permissions
blocker and keep the PR reviewable.

## Pinned web installer: intentionally breaking security change

The former scripts/web-install.sh fetched a mutable main branch archive and
executed it without integrity checking. That behavior is now refused.
Both the exact 40-character commit SHA and a trusted, independently verified
archive SHA-256 digest are mandatory before any download or execution.

Run the script from an inspected checkout, or verify the bootstrap script
separately before using it. The following command requires real values:

```bash
bash scripts/web-install.sh --commit YOUR_40_HEX_COMMIT --sha256 YOUR_64_HEX_ARCHIVE_DIGEST -- --agent codex
```

The archive is fetched via HTTPS from the pinned codeload commit. The script
checks SHA-256 before unpacking, rejects traversal, duplicate paths, links,
special files, excessive size/count/depth, and executes the installer only
after these checks. Its code is not a substitute for a *trusted digest
distribution channel*. Do NOT calculate the checksum from the same untrusted
download and claim that this independently authenticates the release.

Tests: tests/test_web_install_security.py runs offline with a fake downloader.
Until signed/published release digests, comprehensive platform checks and
independent review are complete, issue #10 remains open.

## Release CI/CD and version automation

Every protected Node 20/22 CI run verifies version consistency using
`python3 scripts/release_gate.py check`: `VERSION`, skill frontmatter,
README, `plugin.json`, CLI banner and CHANGELOG must agree. CodeQL also runs
weekly; Dependabot proposes GitHub Actions updates for review.

The manually dispatched [draft-release workflow](../.github/workflows/release.yml)
checks exact-head CI and CodeQL, requires an existing matching tag and dated
changelog, builds reproducible archives and SHA256SUMS, and creates a **draft
only**. A maintainer must publish any release manually.

See [Release Process](release-process.md) for the promotion sequence, current
published-versus-source version distinction, and existing v0.4.0 draft warning.
