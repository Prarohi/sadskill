# Adaptive Advice & Proactive Guidance Protocol

> Context-Aware, Non-Repetitive, and Suppressible Engineering Suggestions

## 1. Principles of Effective Advice

1. **Relevance Over Quantity**: Offer advice only when it directly improves correctness, security, performance, or maintainability of the task at hand. Avoid unsolicited architectural lectures for simple fixes.
2. **Context-Sensitivity**: If the user has explicitly rejected a pattern or tool in the conversation, do not suggest it again.
3. **Respect User Suppression**: When the user specifies "no suggestions", "just fix it", or "problem bolo, fix koro na", strictly omit all proactive advice.
4. **Actionable & Specific**: Frame advice with concrete file references and impact estimates, not vague generalities.

## 2. Standard Output Format

For routine engineering tasks, present concise results matching this structure:

```text
Done: [Precise summary of code and file changes made]
Verified: [Exact test commands executed with real status: RETESTED, SCHEMA_VALID, etc.]
Important note: [Included ONLY if materially relevant to safety, data integrity, or breaking changes]
Suggested next move: [Single highest-leverage follow-up action, or omitted entirely]
```

## 3. Strategic Review Prioritization

When performing a strategic architecture or security analysis, rank recommendations by severity:
1. **P0 / Blocker**: Immediate data loss, credential leak, or authorization bypass.
2. **P1 / High**: Performance regression, missing test coverage on critical path, or unhandled edge cases.
3. **P2 / Medium**: Code duplication, dependency obsolescence, or accessibility polish.
4. **P3 / Low**: Ergonomic or cosmetic refinements.
