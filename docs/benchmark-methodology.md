# sadskill Benchmark Methodology (v0.3.0)

This page separates repository checks from actual coding-agent evaluations. Passing this repository's deterministic checks is not evidence of agent task success or superiority.

## Tracks and allowed status labels

| Track | What runs | Status labels |
|---|---|---|
| A — static/contract checks | Deterministic rules over repository files plus a focused local guardrail invocation | `STATIC_CHECK_PASS` / `STATIC_CHECK_FAIL` |
| B — existing fixtures | Prebuilt tenant-isolation and SQLite authorizer fixture graders; no AI edits a broken project | `FIXTURE_PASS` / `FIXTURE_FAIL` |
| C0 — task catalog | Validate the 24 JSON entries, required fields, unique IDs, and category counts | `CATALOG_VALID` / `CATALOG_INVALID` |
| C1 — real-agent evaluation | Agent edits an isolated, initially broken seed repo and independent graders check its diff | `PASS` / `PARTIAL` / `FAIL` / `NOT_EXECUTED` / `INVALID_RUN` |

Run deterministic repository checks with:

```bash
python3 benchmarks/runner.py
```

The runner reports A, B, and C0 independently. It records C1 as `NOT_EXECUTED` with run count zero. It never combines those outcomes into an agent-success percentage.

The fixture at `benchmarks/fixtures/real-rls/` uses SQLite authorizer hooks to simulate database-level isolation. It is **not PostgreSQL RLS** and provides no evidence about PostgreSQL roles or policies.

## C1 requirements before reporting agent outcomes

Each runnable task must have an immutable seed snapshot with a known failing baseline, independent grader, reset procedure, expected permissions, and explicit safety scope. The runner must keep the agent worktree away from grader files, inspect the diff for unauthorized changes, and record repository/grader/skill/model IDs, environment, budget, time, and available token/cost telemetry. Unavailable telemetry is `N/A`; failed or incomplete runs remain visible.

Comparisons among PLAIN, SADSKILL, and SUPERPOWERS require the same model/version, task prompt, start SHA, tools, permissions, time/token budget, response policy, and repeated randomized trials. No paid provider calls are made by the deterministic runner. Real-agent runs require explicit provider authorization and must publish run count and uncertainty; no such run is claimed here.
