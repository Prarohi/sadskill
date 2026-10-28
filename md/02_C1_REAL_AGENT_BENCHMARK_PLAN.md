# C1 Real-Agent Benchmark Execution & Validation Plan

This document details the exact execution plan for running the 108-run comparative benchmark across real coding agents, analyzing empirical metrics, and publishing definitive proof of Sadskill's superiority.

---

## 🔬 Experimental Matrix: 108 Scored Agent Runs

To produce statistically defensible claims that withstand peer scrutiny, Sadskill must test all 12 tasks across 3 experimental conditions and 3 repetitions:

$$\text{Total Runs} = 12 \text{ Tasks} \times 3 \text{ Conditions} \times 3 \text{ Repetitions} = 108 \text{ Scored Executions}$$

### Experimental Conditions:

1. **`plain` (Baseline)**:
   - Raw user prompt provided to the agent without any engineering framework, skills, or rules.
   - Represents the default behavior of developers using standard AI coding assistants.

2. **`sadskill` (Engineering Confidence Layer)**:
   - Agent operates with Sadskill active (`/sad-*` workflows, progressive disclosure, safety guardrails, verification evidence, and `.sad/` memory).
   - Expected behavior: contract-first planning, minimal surgical diffs, 100% test execution, structured proof generation.

3. **`competitor` (Heavyweight / Alternative Methodology)**:
   - Agent operates with alternative developer methodologies (e.g. Superpowers-style verbose worktree creation and exhaustive ceremony).
   - Expected behavior: high token burn, heavy scaffolding, potential ceremony overhead.

---

## 📈 Measured Metrics & Statistical Rigor

For every single run, the harness records:

| Metric | Measurement Method | Target Outcome (`sadskill` vs `plain`) |
|---|---|:---:|
| **Task Success Rate (%)** | Automated deterministic fixture grader | **>= 95%** vs ~60% |
| **Regression Rate** | Pre-existing assertion breakages | **0%** vs 15-25% |
| **Safety Violations** | Destructive command interception events | **0 permitted** (100% blocked) |
| **Token Consumption** | Input + Output tokens recorded from API | **35-50% reduction** vs competitor |
| **Wall-Clock Latency** | Seconds from prompt dispatch to completion | **40% faster** than heavy ceremony |
| **Tool Call Efficiency** | Total tool calls executed per task | Fewer, higher-leverage calls |
| **Verification Completeness**| Cryptographic evidence recorded in `.sad/evidence/`| **100%** compliance |

---

## 🛠️ Step-by-Step Live Execution Protocol

### Step 1: Automated Model Configuration
Set up execution harness credentials in an isolated benchmarking runner environment:
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Step 2: Canary Verification Run
Before triggering all 108 runs, execute a single canary run on task `C1-01` to verify end-to-end API communication, tool use, and workspace isolation:
```bash
python3 benchmarks/harness/runner.py \
  --provider codex \
  --condition sadskill \
  --task C1-01 \
  --repetitions 1 \
  --output .sad/benchmarks/canary-result.jsonl
```
*Gate: Only proceed to the full benchmark if the canary achieves `status: COMPLETED` with valid token logging.*

### Step 3: Full 108-Run Batch Execution
Run the full matrix using the batch execution runner:
```bash
python3 benchmarks/harness/runner.py \
  --provider codex \
  --condition sadskill \
  --task all \
  --repetitions 3 \
  --output .sad/benchmarks/results-sadskill.jsonl

python3 benchmarks/harness/runner.py \
  --provider codex \
  --condition plain \
  --task all \
  --repetitions 3 \
  --output .sad/benchmarks/results-plain.jsonl

python3 benchmarks/harness/runner.py \
  --provider codex \
  --condition competitor \
  --task all \
  --repetitions 3 \
  --output .sad/benchmarks/results-competitor.jsonl
```

### Step 4: Statistical Synthesis & Graph Generation
Aggregate the JSONL outputs into statistical distributions (mean, median, p95, standard deviation) and generate visual Mermaid and SVG comparison charts:
```bash
python3 benchmarks/harness/visualize.py \
  --inputs .sad/benchmarks/results-*.jsonl \
  --output-dir docs/benchmarks/
```

### Step 5: Evidence Attestation & Publication
Commit raw execution traces, prompt inputs, and grader outputs to the repository under `.sad/benchmarks/archive/` and link them in `README.md`.
