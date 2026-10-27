# sad-sec

Execute the `security` workflow of `sadskill` on target scope: $ARGUMENTS

## Instructions
1. **Locate sadskill Configuration**:
   - Check local workspace: `./skills/sadskill/SKILL.md` (or global `~/.claude/skills/sadskill/SKILL.md`).
   - Check `.sad/reports/` for prior audit baselines.
   - Strictly Read-Only: Never mutate production code or execute writes during an audit.
2. **Comprehensive Security & Legal Audit**:
   - OWASP Top 10 Web & API: SQL/command injection, broken auth, IDOR, SSRF, mass assignment.
   - Secret & Token Exposure: Scan for private keys, provider API tokens, hardcoded credentials.
   - Dependency Vulnerability Scan: `npm audit`, `pip audit`, `cargo audit` (gracefully flag `[SKIPPED - OFFLINE]` if network times out).
   - Security Headers & Cookies: CSP, HSTS, `X-Content-Type-Options: nosniff`, `SameSite=Lax/Strict`, `Secure`.
   - 15-Point Launch Legal & Compliance Checklist: Privacy policy, terms, GDPR erasure, cookie banner conformance.
3. **Collision-Proof Reporting & Remediation Gate**:
   - Save report to `.sad/reports/security-<YYYY-MM-DD>-<HHMMSS>.md`.
   - Rank findings strictly by severity (Critical -> High -> Medium -> Low).
   - Stop and await explicit user approval before executing any remediation fixes.
