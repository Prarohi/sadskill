# Actionable Execution Roadmap & Release Gates to 10/10

This document outlines the concrete phased milestones, gates, and verification commands to take Sadskill from its current 8.9/10 score to a world-class **10.0/10 standard**.

---

## 📅 Phased Execution Roadmap

```
Phase 1: Consolidation & Release Gates (Current -> 9.2/10)
   ├── Merge PR #9 (World-Class Upgrade Package 0.5.0)
   ├── Run full 193-test regression suite
   └── Tag official v0.5.0 release

Phase 2: Live Real-Agent C1 Benchmark Execution (Target: 9.5/10)
   ├── Execute the 108 live LLM runs across 12 tasks
   ├── Measure paired tokens, regressions, and safety violations
   └── Publish empirical comparison charts in README and docs

Phase 3: Deep Security Hardening & Semantic Memory (Target: 9.7/10)
   ├── Implement SQLglot AST tokenizer in scripts/sql_guard.py
   ├── Add optional Linux bubblewrap sandbox runner
   └── Add zero-dependency BM25 memory retrieval in scripts/sad_memory.py

Phase 4: Unified CLI & Developer Ergonomics (Target: 9.9/10)
   ├── Consolidate scripts into the unified `sad` CLI binary
   ├── Publish pip-installable package (`pip install sadskill`)
   └── Add terminal visual HUD and interactive doctor

Phase 5: Global Registry Distribution & Docs Portal (Target: 10.0/10)
   ├── Launch Astro/Starlight documentation portal
   ├── Complete official listings on skills.sh and Cursor Directory
   └── Enable GitHub Artifact Attestation verification in public releases
```

---

## 🚦 Phase Release Gates & Verification Commands

Every milestone must satisfy its strict release gate before being marked complete:

### Gate 1: Deterministic Quality Gate
```bash
git diff --check
python3 -m compileall -q scripts benchmarks tests skills/sadskill/tools
bash -n install.sh uninstall.sh scripts/git-guardrail.sh skills/sadskill/hooks/git-guardrail.sh
python3 -m unittest discover -s tests -v
python3 scripts/verify.py
```
*Criteria: 0 failures, 0 syntax warnings, 100% assertions passing.*

### Gate 2: Benchmark Gate
```bash
python3 benchmarks/runner.py --output .sad/benchmark-latest.json
python3 benchmarks/harness/runner.py --provider mock --condition sadskill --task all --repetitions 1
```
*Criteria: 12/12 C1 tasks pass cleanly under mock provider.*

### Gate 3: Packaging & Single-Skill Discovery Gate
```bash
npx --yes skills@1.7.4 add . -l
```
*Criteria: Discovers exactly 1 skill (`sadskill`) with zero extraneous skill detections.*

### Gate 4: Privacy & Leakage Gate
```bash
git diff | grep -iE "/home/[a-zA-Z0-9_-]+" || true
```
*Criteria: Exactly 0 local absolute path leaks or private machine identifiers.*
