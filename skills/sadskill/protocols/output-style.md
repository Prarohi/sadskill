# Output Style & Token Efficiency Protocol

> High Information Density, Progressive Disclosure, Batched Mutations, and Minimal Token Waste

## 1. Core Token Efficiency Directives

Token consumption directly dictates latency, context exhaustion, and engineering speed. Enforce maximum efficiency across all responses:

1. **High Information Density**:
   - Deliver findings, decisions, and mutations using structured markdown tables, compact diffs, and precise bullet points.
   - Eliminate conversational fluff, repetitive acknowledgments ("Sure, I can help with that!", "As an AI..."), and narrating actions before performing them.
2. **Progressive Disclosure**:
   - Never dump entire vendor reference manuals, lengthy guidelines, or exhaustive checklists into chat.
   - Read the router, load only the operative mode and targeted reference, and cite the relative path.
   - Save multi-page architectural plans and security reports to `.sad/plans/` and `.sad/reports/`, providing chat with a 5-10 line executive summary and a direct file link.
3. **Batched Mutations**:
   - Batch edits into contiguous, cohesive blocks rather than executing multiple iterative single-line edits across the same file.
   - Every file modification must preserve existing non-affected code and docstrings without churn.
4. **Structured Status Indicators**:
   - `[PASS]` / `✓`: Verified test or policy assertion.
   - `[WARN]` / `⚠️`: Non-blocking observation or soft deprecation.
   - `[FAIL]` / `❌`: Failing test, security vulnerability, or broken constraint.
   - `[SKIP]` / `⏭️`: Gracefully bypassed check with explicit documented reason.

---

## 2. Standard Response Template

Structure execution summaries around four concise sections:

```text
Done: [1-2 sentence summary of modified files and symbols]
Verified: [Exact test commands executed with actual exit code and assertion counts]
Important note: [Surfaced ONLY for breaking changes, security warnings, or manual steps]
Suggested next move: [Single highest-leverage next command: e.g. /sad-plan, /sad-sec, or commit]
```

---

## 3. Code Block & Diff Discipline

- Always tag code blocks with precise language identifiers (`typescript`, `python`, `bash`, `sql`, `json`).
- Prepend the target file path as a header or first-line comment (`// path/to/file.ts`).
- Avoid repeating 200 lines of unchanged code surrounding a 3-line change. Use targeted diffs or contiguous replacement blocks with sufficient context to eliminate ambiguity.
