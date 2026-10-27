# Protocol: Grilling on Ambiguity

When requirements are ambiguous, trade-offs are significant, or decisions are irreversible, agents must "grill" the user rather than guessing or silently adopting risky defaults.

---

## 🎯 When to Grill

- Architectural decisions with long-term lock-in (e.g. database choice, auth provider, storage system).
- Data loss risks (e.g. schema drop columns, destructive migrations).
- Conflicting or underspecified functional requirements.

---

## 🚫 When NOT to Grill

- Discoverable facts: If something can be verified by reading files or running a tool, never ask the user. Inspect the codebase first.
- Trivial implementation details: Make sound engineering decisions without interrupting the developer.

---

## 📋 The Grilling Format

1. **One Round**: Consolidate all critical questions into a single interaction turn.
2. **Clear Options**: Provide discrete, mutually exclusive options.
3. **Always Include a Recommendation**: Prefix the recommended option with `➡️ Recommended`.
4. **Single "Yes" Acceptance**: Structure recommendations such that the developer can reply with "yes" or "proceed" to accept all recommended defaults.

### Example

```markdown
Before generating the plan, please confirm these two architectural decisions:

1. **Session Store**:
   - Option A: Redis cluster
   - Option B: Database-backed sessions in PostgreSQL
   ➡️ **Recommended**: Option B (PostgreSQL sessions) to avoid adding another infrastructure dependency.

2. **API Contract**:
   - Option A: REST with JSON schema / Zod validation
   - Option B: tRPC with shared TypeScript types
   ➡️ **Recommended**: Option A for independent client consumption.
```
