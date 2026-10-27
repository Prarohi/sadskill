# Protocol: Output Style & Maximum Token Efficiency

Token waste directly impairs agent speed, intelligence, and cost. This protocol enforces extreme information density, clean formatting, and zero conversational waste across all responses.

---

## ⚡ Token Efficiency Directives

1. **High Information Density**:
   - Deliver findings, decisions, and code changes in structured markdown tables and bulleted lists.
   - Avoid narrative paragraphs explaining what you are "about to do" or recounting what you "just did".
2. **Progressive Disclosure**:
   - Never paste large reference manuals or entire third-party documentation files into the conversation. Load only the specific section needed, extract the operative rule, and cite the file path.
3. **Batched Mutations**:
   - When proposing or executing code changes, batch modifications into clean contiguous replacements. Never make five successive single-line edits when one cohesive block achieves the result with far fewer prompt roundtrips and minimal token overhead.
4. **Structured Status Indicators**:
   - `[OK]` / `✓`: Success or verified assertion.
   - `[WARN]` / `⚠️`: Warning or non-blocking issue.
   - `[FAIL]` / `❌`: Fatal bug or failed test.

---

## 📐 Formatting Rules

- **Direct Code Fences**: Always tag with exact language (`typescript`, `python`, `bash`, `sql`) and comment the target file path.
- **No Echo Summaries**: When finishing a task, do not write a 3-paragraph recap summarizing trivial tool outputs. State the result, show the verification output, and provide the next step.
