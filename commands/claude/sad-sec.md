# sad-sec

Execute the `security` workflow of `sadskill` on: $ARGUMENTS

Follow `skills/sadskill/SKILL.md` and `skills/sadskill/modes/security.md`:
1. Check `.sad/reports/` for previous security audits.
2. Read `~/.sadskill/profile.md` if present.
3. Apply the Human-Voice protocol.
4. Perform security audit:
   - OWASP Top 10 Web & API checks (injection, auth bypass, IDOR, SSRF).
   - Secret scan (hardcoded keys, env leak, git history exposure).
   - Dependency vulnerability analysis.
   - Headers, CSP, CORS, cookie attributes.
   - 15-point launch legal checklist (privacy policy, terms, data deletion).
5. Output structured audit report to `.sad/reports/security-<YYYY-MM-DD>.md`.
6. Outline prioritized remediation plan and await approval before modifying code.
