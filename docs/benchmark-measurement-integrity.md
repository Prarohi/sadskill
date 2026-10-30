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

PR #4 and PR #9 are already integrated into `main`. This PR was
retargeted directly to protected `main` on 2026-10-30. An older benchmark
CI pass on a former merge base is not an exact-head main-integration pass.
Require current Node 20/22, native PostgreSQL, CodeQL, benchmark checks and
eligible independent review before considering integration.

The live-run acknowledgment flag is an operator declaration, **not** a
technical sandbox guarantee. Candidate code may be executed by graders;
run it only in an externally isolated, disposable VM/container with
separately restricted credentials, network access, and filesystem scope.
No competitive accuracy, token savings, safety improvement, or model
superiority is established until independently graded real-agent trials run.
