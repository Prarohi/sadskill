# Persistent Project Memory & Semantic Search 10/10 Plan

This document describes how Sadskill's project memory (`.sad/`) scales to support long-running, multi-week engineering projects with hundreds of historical decisions without context window explosion.

---

## 🧠 The Long-Term Memory Challenge

In large repositories with dozens of architectural decision records (ADRs), full-text injection of `.sad/` consumes thousands of unnecessary prompt tokens per turn.

The 10/10 target introduces **Local Zero-Dependency Semantic Search & Memory Compaction**:

```
+-----------------------------------------------------------+
| Incoming Agent Query (e.g. "auth service refactoring")    |
+-----------------------------------------------------------+
                             │
                             ▼
+-----------------------------------------------------------+
| BM25 + Recency Semantic Filter (.sad/index.json)          |
| - Evaluates term frequency, inverse document frequency   |
| - Boosts recent and active ADR decisions                  |
| - Filters out superseded or rejected options              |
+-----------------------------------------------------------+
                             │
                             ▼
+-----------------------------------------------------------+
| Compact Context Injection (<= 400 tokens)                 |
| - Injects ONLY the 2-3 relevant ADRs                      |
| - Injects approved design tokens & rejected anti-patterns |
+-----------------------------------------------------------+
```

---

## 📂 Search & Index Architecture (`scripts/sad_memory.py`)

### 1. In-Memory BM25 Scoring
A zero-dependency Python implementation embedded directly into `scripts/sad_memory.py`:
- Tokenizes ADR titles, contexts, decisions, and consequences.
- Calculates BM25 score against the current task prompt.
- Ranks candidate decisions and selects the top $K$ records (default $K=3$).

### 2. Automated Memory Compaction (`sad memory compact`)
When events in `.sad/events/` exceed 100 entries:
- Consolidates chronological checkpoints into a single monthly milestone ledger.
- Retains all immutable ADRs and security reports intact.
- Updates `.sad/history.md` with high-level summaries while preserving the raw event archive.

---

## 🔒 Multi-Agent Concurrency Invariants

- **Advisory File Lock**: Every read/write operation locks `.sad/.lock` with non-blocking retry timeout (5 seconds).
- **UUID Event Naming**: Events are named `<timestamp>-<uuid>.json` ensuring no two concurrent agents can overwrite the same file name even if they write in the exact same millisecond.
- **Git Commit Provenance**: Every event records the `base_commit` SHA of the working tree at the time of writing.
