# C1 Comparative Real-Agent Benchmark Methodology

The C1 suite *intends* to evaluate coding agents under 3 conditions. **The current provider only runs predetermined synthetic mock solutions; Codex/Claude/Gemini live execution is not implemented. Do not publish mock outputs as real agent performance.**
1. `plain`: Raw agent instruction without structured engineering protocols.
2. `sadskill`: Agent governed by the sadskill Engineering Confidence Layer (contract-first planning, minimal surgical changes, verification evidence, and safety guardrails).
3. `competitor`: Agent governed by generic or high-ceremony development methodologies.

---

## 📋 The 12 Benchmark Tasks

| Task ID | Task Name | Defect Category | Core Verification Criteria |
|---|---|---|---|
| `C1-01` | Nullable-profile bug | Bugfix | Optional chaining / null-guard fallback on `user.profile?.avatarUrl` with regression test |
| `C1-02` | Pagination off-by-one | Bugfix | Correct boundary slicing `(page - 1) * pageSize` to `start + pageSize` without item duplication |
| `C1-03` | Async stale-result race | Concurrency | Request sequencing / cancellation token to discard stale asynchronous query results |
| `C1-04` | Node ESM export mismatch | Packaging | Explicit named exports conforming to package.json `type: module` with CJS compatibility |
| `C1-05` | Cross-tenant authorization | Security | Enforcing `tenant_id` scoping on database retrieval to block cross-tenant information disclosure |
| `C1-06` | PostgreSQL RLS hole | Database | `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and tenant policy verification |
| `C1-07` | Safe expand/contract migration | Database | Two-phase rolling migration (add column/view, dual-write backfill, drop old column) |
| `C1-08` | Mobile CSS overflow | Frontend Craft | `max-width: 100%`, `overflow-wrap: break-word` eliminating horizontal viewport scrolling at <= 375px |
| `C1-09` | Accessible dialog behavior | Accessibility | Focus trapping, Escape key dismiss, `role="dialog"`, and `aria-modal="true"` |
| `C1-10` | Circular dependency removal | Architecture | Clean architectural decoupling of mutual dependency via shared types module |
| `C1-11` | Guardrail wrapper bypass | Safety Enforcement | Command interception blocking destructive execution wrapped in `env`, `sudo`, or `bash -c` |
| `C1-12` | Concurrent project memory | Agent Memory | Concurrency-safe advisory locking and immutable event logs with zero lost writes |

---

## 📊 Evaluation Metrics

For each run, the harness records:
- **Task Success**: Automated deterministic grader evaluation of workspace state.
- **Regression Rate**: Number of pre-existing assertions broken by the change.
- **Safety Violations**: Interception of destructive Git, SQL, or filesystem operations.
- **Token Efficiency**: Prompt and completion token consumption.
- **Wall-Clock Time**: Execution latency in seconds.
- **Tool Calls**: Number of tool invocations performed.
- **Verification Completeness**: Cryptographic evidence record generated in `.sad/evidence/`.

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

The visualizer excludes mock and unexecuted records from empirical statistics.
Only real, authenticated, executed agent runs with measured usage may count.
Even those require independently verified paired setup and adequate sample size
before causal/superiority claims.

### Real Agent Execution (Codex / Claude)
The live adapters are not yet implemented. Without credentials the result is `NOT_EXECUTED_NO_AUTH`; with credentials it is `NOT_EXECUTED_NOT_IMPLEMENTED`. In both cases the runner exits nonzero and no measured result exists:
```bash
python3 benchmarks/harness/runner.py \
  --provider codex \
  --condition sadskill \
  --task C1-01 \
  --repetitions 1 \
  --output .sad/benchmark-codex.jsonl
```
