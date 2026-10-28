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
simulated fixture solutions. They are **not actual model tests** and carry no
measured agent token savings. `--provider codex/claude/gemini` currently fails
closed without a working real-agent adapter. CI green, mock fixture passing,
and static contract passing are distinct from empirical superiority.

**Critical security limitation:** `sad guard` is a defense-in-depth lexical
filter, not a complete shell or SQL security boundary. Always rely on host
permissions, sandboxing and explicit consent for potentially destructive
operations.

## How to merge responsibly

Use a stable base and correct stacked order: PR #4 (0.4 integration), then
retarget PR #9 (0.5 candidate) onto main. Require exact-head CI, independent
review or an *explicitly authorized and recorded owner PR-only bypass*,
resolved conversations and intact branch protection. PR-only bypass does not
turn unrun checks into passing checks.

If your GitHub connector cannot update the ruleset, do not alter the branch
through an alternate destructive ref operation. Explain the permissions
blocker and keep the PR reviewable.
