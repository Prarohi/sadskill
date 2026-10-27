# `/sad-sec`

Execute the `security` workflow of `sadskill`.

## Instructions
1. Load and adhere to `sadskill`:
   - Inspect `.sad/` project memory (`.sad/reports/`).
   - Respect local profile if configured (`~/.sadskill/profile.md`).
   - Enforce the Human-Voice protocol.
2. Follow `skills/sadskill/modes/security.md`:
   - Perform comprehensive vulnerability audit:
     - OWASP Top 10 Web & API issues (injection, broken auth, IDOR, SSRF).
     - Hardcoded secrets, API keys, credentials, and git history leaks.
     - Dependency audit (`npm audit`, `pip check`, `cargo audit`).
     - Security headers, Content Security Policy (CSP), CORS, cookie flags.
     - 15-point application launch legal and privacy compliance checklist.
   - Write structured findings to `.sad/reports/security-<YYYY-MM-DD>.md`.
   - Provide prioritized remediation plan (Critical -> High -> Medium -> Low).
   - Await user approval before modifying code.
