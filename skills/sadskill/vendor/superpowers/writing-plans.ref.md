# Reference: Writing Implementation Plans (Superpowers)

> Source: `obra/superpowers` (MIT License) · Neutralized Reference

---

## 🎯 Plan Structure & Guidelines

1. **Atomic Phases**: Divide work into independently verifiable increments. Each phase must leave the codebase in a building, test-passing state.
2. **Explicit Symbol Signatures**: Never write vague instructions like "update the user service". Specify the exact file path, type definitions, function signatures, and parameter types.
3. **Automated Verification Step per Phase**: Every phase must conclude with an exact terminal command that runs tests and proves the changes work.
4. **Failure Modes & Edge Cases**: Explicitly enumerate null states, empty collections, network interruptions, and concurrent writes before code is written.
