# Design Memory: `sadskill`

Documented design tokens, terminal output aesthetics, and approved/rejected communication patterns.

---

## 🎨 Terminal UX & Output Formatting

- **Color Palette (CLI Status)**:
  - Green / `[OK]` / `✓`: Verified test pass or successful operation.
  - Yellow / `[WARN]` / `⚠️`: Non-fatal warning or fallback mode triggered.
  - Red / `[BLOCKED]` / `❌`: Blocked destructive command or test failure.
- **Density Rules**:
  - No conversational conversational filler ("Certainly!", "I'm happy to help").
  - Lead with the answer or action immediately before commentary.
  - Use structured markdown tables and contiguous code blocks.
  - Append 3-line verification proof on task completion.

---

## 🚫 Rejected Patterns
- **Do NOT flood chat transcripts with full reference documentation dumps**.
- **Do NOT generate code without pre-declaring test assertions**.
- **Do NOT claim a task is complete without quoting exit code 0**.
