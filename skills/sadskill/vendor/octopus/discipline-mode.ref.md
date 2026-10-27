# Reference: Agent Discipline & Proof of Verification (Claude-Octopus)

> **Source**: [nyldn/claude-octopus](https://github.com/nyldn/claude-octopus) (MIT License)  
> **Status**: Neutralized Reference for `sadskill`

---

## 🛡️ Discipline Principles (`/octo:discipline`)

Autonomous agents frequently declare victory prematurely without actual verification. Discipline mode enforces zero-trust execution.

### 1. Terminal Output Grounding
- **Never claim a bug is fixed without running the test command and inspecting exit code 0.**
- **Never claim a build succeeded without executing the compiler or bundler.**
- **Quote the exact terminal output** showing test suite passes rather than asserting "all tests pass".

### 2. Surgical Scope Containment
- Never modify files outside the agreed implementation matrix.
- Clean up all temporary debugging logs (`console.log`, `print`, scratch files) before declaring completion.
- Revert unintended formatting or whitespace changes in untouched files.

### 3. Verification Assertions
- If no automated test exists for the target bug or feature, write a minimal reproduction test first.
- Verify that the test fails before the fix and passes after the fix.
