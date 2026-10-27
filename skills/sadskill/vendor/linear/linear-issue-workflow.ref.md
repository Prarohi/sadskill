# Reference: Linear Issue & Project Workflows

Origin: OpenAI Skills / Linear Patterns  
License: MIT  

## Issue & Sprint Management

1. **Deterministic Issue Titles**:
   - Format: `[Domain] Action Verb + Direct Object` (e.g. `[Auth] Enforce rate limiting on password reset`).
2. **Acceptance Criteria**:
   - Provide bulleted checkboxes detailing observable pass/fail conditions.
3. **Atomic Scope**:
   - An issue should represent 1 pull request. If an issue requires modifying 20 files across 3 domains, break it into smaller sub-issues.
