# Release process and CI/CD controls

Last audited: **2026-10-30**. Always compare with live GitHub before a release.

## What each version number means

The repository `VERSION` file is the source-of-truth for the **current source
candidate**. `plugin.json`, the version in `SKILL.md`, the README banner,
the `sad --version` CLI and the newest CHANGELOG heading must agree.
A source version is **not** a GitHub publication.

At this audit: v0.3.0 is the latest **published** release. GitHub also has
an unpublished **v0.4.0 draft** with stale integration/approval statements
and no corresponding Git tag. The current source is **0.5.0**, marked
**Unreleased**. Do not republish old historical artifacts as if they had
been rebuilt from current main.

## Existing automatic checks

| Event | What runs |
| --- | --- |
| Every PR to main and push to main | Node 20/22 full Python/skill checks, version metadata gate, vendor integrity, safe installer tests, deterministic benchmark fixtures, native PostgreSQL RLS and negative control, macOS/Windows smoke |
| Every PR to main and push to main | CodeQL Python security analysis |
| Weekly | CodeQL on main |
| Weekly | Dependabot proposes GitHub Actions version bumps as separate PRs |

All general CI uses a read-only repository token. The protected main
ruleset currently requires Node 20, Node 22 and PostgreSQL RLS.
The version metadata gate runs **inside the required Node jobs**.
CodeQL is additionally mandatory for creating a release draft; if you
also want to block every PR merge until CodeQL passes, add its exact job
name (`CodeQL Python security analysis`) to the ruleset in the GitHub UI
(Administration write permission required). Independent review is a
human release gate, not something CodeQL certifies.

## Preparing v0.5.0 (or any future version)

1. Finish and review security fixes. Merge only through protected main
   with exact-head green CI; independently review security-sensitive diffs.
2. Confirm every claim in CHANGELOG is supported by tests and evidence.
   Update the newest CHANGELOG version heading from `Unreleased` to the
   **actual** release date `YYYY-MM-DD`. Remove the README
   `release candidate` wording. Confirm the metadata gate passes:

   ```bash
   python3 scripts/release_gate.py check
   python3 -m unittest discover -s tests -p 'test_release_gate.py' -v
   ```

3. Merge these release-promotion edits to main. Create an immutable,
   preferably signed, annotated `v<version>` tag pointing to the exact
   reviewed `main` HEAD. Never retarget a published release tag.
4. Run GitHub Actions → **Prepare verified draft release** via
   **workflow_dispatch on main**, supplying this *existing* tag.
5. The validation job fails closed if the tag/version/changelog disagree,
   tag does not equal main HEAD, any of Node 20/22, native PostgreSQL
   RLS, CodeQL, macOS/Windows smoke is missing or non-green at that
   SHA, local tests fail, or reproducible archive comparison fails.
6. A separate job with `contents: write` downloads reviewed artifacts
   (without checking out PR code), re-verifies SHA-256 and source commit,
   refuses an existing release/draft, and creates **a draft only**.
7. A maintainer reviews release notes, source identity, archives,
   checksums, compatibility boundaries and security evidence before
   **manually publishing** the draft. This workflow never publishes
   or deploys automatically.

## The release assets

- `sadskill-<version>.tar.gz` and `sadskill-<version>.zip`, built using
  `git archive HEAD` with one canonical root directory.
- `SOURCE_COMMIT.txt` with the full immutable commit SHA.
- `SHA256SUMS.txt` with digests for both named archives, source commit
  record and generated release notes.
- `RELEASE_NOTES.md` produced directly from the current changelog.
  The notes are used for the GitHub draft body.

Archives are built twice and compared byte-for-byte. The draft job checks
SHA256SUMS again after artifact transfer. SHA-256 proves byte matching, **not
publisher identity**. No Sigstore signature or SLSA provenance attestation
is claimed by this workflow. GitHub-generated source archives may have
different digests from these specifically named assets.

## Existing v0.4.0 draft

The historical draft's original description and attached archives predate
the present main integration. The current connector can read but cannot
edit GitHub releases. Review and correct that draft **manually**, or
retire it after a documented maintainer decision; never auto-overwrite
assets or fabricate a missing `v0.4.0` tag. The new workflow refuses
duplicate tag releases, including drafts.

## Safety boundaries

No deploy, registry publication, automatic push, Git ref update, paid
AI-agent trial or release publication is authorized by this automation.
A green CI job is evidence for its own tested commit, not a blanket
security certification or proof of model-performance improvement.
