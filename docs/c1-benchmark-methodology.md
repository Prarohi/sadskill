# C1 Comparative Real-Agent Benchmark Methodology

The C1 suite *intends* to evaluate coding agents under 3 conditions. **CI executes deterministic mocks only. The Codex/Claude/Gemini live CLI adapters are opt-in and require an externally isolated runner, explicit model ID, and locally authenticated CLI. No real comparative trial results have been collected yet. Never publish mock results as model performance.**
1. `plain`: Raw agent instruction without structured engineering protocols.
2. `sadskill`: Agent governed by the sadskill Engineering Confidence Layer (contract-first planning, minimal surgical changes, verification evidence, and safety guardrails).
3. `competitor`: Agent governed by generic or high-ceremony development methodologies.

---

## 📋 The 12 Benchmark Tasks

| Task ID | Task Name | Defect Category | Core Verification Criteria |
|---|---|---|---|
| `C1-01` | Nullable-profile bug | Bugfix | Hidden Node behavior tests for custom/null/undefined/missing profiles plus an executed regression test covering null and undefined |
| `C1-02` | Pagination off-by-one | Bugfix | Hidden Node tests compare exact page slices, final partial page and out-of-range page |
| `C1-03` | Async stale-result race | Concurrency | Controlled promise ordering proves a slow old request cannot replace the latest result |
| `C1-04` | Node ESM export mismatch | Packaging | Node executes ESM named export and CommonJS entry; package map is checked for both consumers |
| `C1-05` | Cross-tenant authorization | Security | Hidden Node adversarial-ID fixture verifies tenant A cannot retrieve tenant B's document |
| `C1-06` | PostgreSQL RLS hole | Database | Pinned disposable PostgreSQL exercises default deny, tenant reads, own insert and cross-tenant read/write denial |
| `C1-07` | Safe expand/contract migration | Database | Pinned PostgreSQL executes expand/backfill/dual-write/contract and reverse migrations against real rows |
| `C1-08` | Mobile CSS overflow | Frontend Craft | Headless Chromium measures viewport and a long `pre` at 375 CSS pixels |
| `C1-09` | Accessible dialog behavior | Accessibility | Headless Chromium exercises dialog semantics, initial focus, Tab/Shift+Tab wrap, Escape close and opener focus restore |
| `C1-10` | Circular dependency removal | Architecture | Local JS import graph cycle check plus Node import and behavior tests |
| `C1-11` | Guardrail wrapper bypass | Safety Enforcement | Workspace hook is tested against direct/env/command/sudo/recursive-shell inputs with fake commands that prevent execution |
| `C1-12` | Concurrent project memory | Agent Memory | Multiple processes append 202 unique JSONL records; a held advisory lock must block a writer until release |

---

## 📊 Evaluation Metrics

For each run, the harness records:
- **Task Success**: Automated deterministic grader evaluation of workspace state.
- **Regression Rate**: Not measured by current graders; stored as `null` and rendered `NOT_MEASURED`.
- **Safety Violations**: Not comprehensively measured by current graders; stored as `null` and rendered `NOT_MEASURED`.
- **Token Efficiency**: Prompt and completion token consumption.
- **Wall-Clock Time**: Execution latency in seconds.
- **Tool Calls**: Not currently captured; stored as `null`.
- **Verification Completeness**: The benchmark runner does not currently create a `.sad/evidence/` record; `evidence_produced` is false and cannot be read as an independent verification score.

---

## 🚀 Running the Benchmark

### Offline Deterministic Execution (Mock Provider)
```bash
python3 benchmarks/harness/runner.py \
  --provider mock \
  --condition sadskill \
  --task all \
  --repetitions 1 \
  --output .sad/benchmark-latest.jsonl

python3 benchmarks/harness/visualize.py \
  --inputs .sad/benchmark-latest.jsonl \
  --output-markdown .sad/benchmarks/c1-summary.md
```

---

## Synthetic Fixture Demonstration — NOT empirical results

The `mock` provider writes predetermined solutions for each condition. Its chosen failures
and successes are built into the test doubles, not produced by an agent. Earlier
displayed 33.3%/100% success and 45.7% token savings were synthetic constants,
**not measured improvements**, and are withdrawn as performance claims.

The visualizer excludes mock and unexecuted records and checks the shape of
completed-run records. JSONL fields are not cryptographically authenticated;
the summarizer cannot prove that a file came from a real authenticated CLI run.
Verify record provenance independently before using any live-run report.
Token differences are emitted only when all three conditions have matching
provider/model/task/repetition keys from one experiment ID. Environment identity
is not recorded yet, so the pairing gate alone does not support causal or
superiority claims; those still require independently verified setup and
adequate sample size.

### Behavioral grader prerequisites and limits

The hidden graders execute candidate code and require Node.js for C1-01–05 and
C1-10, the pinned cached PostgreSQL Docker image for C1-06/07, Chromium for
C1-08/09, Bash for C1-11, and Python with `fcntl` for C1-12. A missing runtime
produces `FAILED_UNVERIFIABLE_GRADER` with unknown (`null`) result counts; the
harness must not score an unevaluated task as either a pass or a measured model
failure. PostgreSQL fixtures use only a uniquely named, network-disabled,
read-only-root container. All capabilities are dropped except `CHOWN`,
`SETUID`, and `SETGID` required by the pinned image entrypoint; cleanup targets
only the container created by that grader invocation.

The benchmark-only GitHub Actions workflow runs on an ephemeral hosted worker
with only `contents: read` permissions. It sets
`SADSKILL_CI_CHROMIUM_NO_SANDBOX=1` because that worker does not expose the
Linux user namespaces Chromium's own sandbox needs. This compatibility setting
is not enabled for ordinary local runs; local Chromium keeps its browser
sandbox enabled.

These are stronger deterministic task graders, not proof that an agent is
generally superior. Run the candidate task code only inside the disposable
external environment described below; CLI sandbox flags alone do not contain
arbitrary code.

The current task graders do not measure regressions against a pre-run test
baseline or count every safety violation. Those fields remain `null` and are
rendered as `NOT_MEASURED`; they must not be interpreted as zero. C1-12 checks
lock blocking and final event preservation, not syscall-level proof that the
JSONL file was never rewritten or truncated.

### Real Agent Execution (Codex / Claude)
CLI adapters for Codex, Claude Code, and Gemini are implemented, but CI does not invoke them and no authenticated real-agent trials have been run. A missing CLI returns `NOT_EXECUTED_NO_CLI`; CLI errors or incomplete usage return a failed/unverifiable status. These statuses exit nonzero and are never benchmark results:
```bash
python3 benchmarks/harness/runner.py \
  --provider codex \
  --condition sadskill \
  --task C1-01 \
  --repetitions 1 \
  --output .sad/benchmark-codex.jsonl
```

## Optional live CLI benchmarking (not executed in CI)

Real Codex, Claude Code, and Gemini CLI adapters exist, but they are disabled by default.
Only invoke the entire harness and its graders inside an **external disposable VM/container**
with bounded access and no sensitive host files. CLI sandbox flags alone do not
contain arbitrary code executed by Python graders. The confirmation flag is a
user assertion, not technical proof of a sandbox. Real runs may use paid credits.

Example commands inside that disposable environment, with each CLI pre-installed
and authenticated through its own official login:

```bash
python3 benchmarks/harness/runner.py --provider codex --live --acknowledge-isolated-runner --model EXACT_CODEX_MODEL --task C1-01 --condition all --repetitions 3 --output /tmp/c1-codex.jsonl
python3 benchmarks/harness/runner.py --provider claude --live --acknowledge-isolated-runner --model EXACT_CLAUDE_MODEL --task C1-01 --condition all --repetitions 3 --output /tmp/c1-claude.jsonl
python3 benchmarks/harness/runner.py --provider gemini --live --acknowledge-isolated-runner --model EXACT_GEMINI_MODEL --task C1-01 --condition all --repetitions 3 --output /tmp/c1-gemini.jsonl
```

The harness reports `COMPLETED_REAL` only for successful structured CLI execution
and separately grades the resulting code. Missing metrics remain null, not
zero. Missing CLI/auth, nonzero exit, invalid JSON, or timeout cannot be counted
as success. Prompts, provider, model and prompt SHA-256 are recorded; raw
transcripts and stderr are not saved in JSONL. No actual model trials were
performed during development of these adapters. The competitor condition is
only a generic structured baseline, not a named competing skill product.
Conclusive comparisons still require independently verified paired trials,
version pinning, budget/variance analysis and redacted raw evidence.
