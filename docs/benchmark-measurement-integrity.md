# Benchmark measurement integrity hardening

These safeguards make the benchmark fail closed when a provider response omits
part or all of its token usage, reports an invalid model ID, or claims a
completed execution without a complete valid status and numeric usage. A CLI
return code of zero **does not** prove it performed measurable model work.

- Both token fields must be nonnegative integers reported by the provider.
  Missing, Boolean, negative, malformed, or partial fields are **not** zeros.
- A missing/incorrect `COMPLETED_REAL` status or absent usage prevents grader
  success being recorded as empirical model evidence.
- An unexecuted or failed task has `null` regression and safety-violation
  counts, not zero: there was no evaluation.
- Tests use mocked CLIs only; **no live Codex, Claude, or Gemini run was
  executed by this PR**.
- Real model performance still requires an externally isolated run, verified
  evaluator correctness, authenticated CLI/model version, balanced paired
  sampling, and spending approval.

This PR is independently stacked on PR #9 and does not touch the concurrent
PR #4 deletion repair or PR #9 sandbox hardening. Merge only after base
changes are integrated and all exact-head CI/security gates pass.
