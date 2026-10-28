# Developer Experience (DX), CLI & Documentation Plan

This document details the ergonomic enhancements, unified terminal CLI, and modern web documentation required to deliver a polished, delightful developer experience.

---

## 💻 Unified `sad` CLI Binary

Currently, developers interact via separate scripts (`install.sh`, `scripts/doctor.py`, `scripts/verify-evidence.py`, `scripts/sad_memory.py`, `benchmarks/harness/runner.py`).

The 10/10 target consolidates these into a single, intuitive command: `sad`.

```text
sad [command] [options]

Core Commands:
  sad init         Initialize .sad/ project memory and select engineering rules
  sad doctor       Analyze multi-agent installation health and hook status
  sad bench        Run C1 comparative agent benchmarks (mock or real LLM)
  sad verify       Verify evidence logs and cryptographic hash chains
  sad memory       Query or append to project memory and ADRs
  sad update       Check for and safely apply transactional updates
  sad audit        Run a read-only security and architecture scan
```

### Visual Terminal HUD
When commands run, display clean terminal progress badges:
```text
  [✓ PASS] C1-01: Nullable-profile bug (120ms, 450 tokens)
  [✓ PASS] C1-06: PostgreSQL RLS hole (forced RLS verified)
  [🛡️ SAFE] Blocked 'git reset --hard' (wrapper bypass prevented)
  [📦 EVIDENCE] Cryptographic proof logged: .sad/evidence/20261029-0145-C1-01.json
```

---

## 🌐 Interactive Documentation Portal

Build a high-performance documentation website hosted on GitHub Pages or Vercel using Astro / Starlight:

### Key Sections:
1. **Quickstart**: 60-second onboarding for Claude Code, Codex, and Cursor.
2. **The 5 Modes**: Interactive deep dive into `plan`, `design`, `backend`, `security`, and `analyze`.
3. **Guardrails**: How Sadskill intercepts destructive operations and protects repositories.
4. **C1 Benchmark Dashboard**: Live, interactive charts showing paired benchmark metrics across 12 tasks.
5. **Interactive Playground**: Web-based simulator demonstrating prompt-to-patch execution with Sadskill.
