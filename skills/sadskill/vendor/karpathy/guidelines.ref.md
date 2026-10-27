# Reference: Pragmatic AI Coding Guidelines (Karpathy)

> Source: `multica-ai/andrej-karpathy-skills` (MIT License) · Neutralized Reference

---

## ⚡ Core Heuristics

1. **Verify at Every Step**: Never assume AI-generated code works without running it. Run test suites, verify type checks, and observe outputs.
2. **Small Diffs over Rewrites**: Make targeted, minimal diffs. Avoid sweeping file rewrites that disrupt surrounding logic or introduce accidental regressions.
3. **Simplicity First**: Write readable, idiomatic, vanilla code before reaching for esoteric abstractions or premature micro-optimizations.
4. **Inspect Failures Directly**: When code fails, read the compiler output, stack trace, and logs carefully before making changes. Avoid blind trial-and-error edits.
