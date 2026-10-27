# Mode: `/sad-sec`

Security mode conducts exhaustive vulnerability assessments, secret detection, dependency audits, security header evaluations, and regulatory compliance checks.

---

## 🛡️ Execution Pipeline

### Phase 1: Threat Modeling & Scan Scope
1. Inspect `.sad/reports/` for prior security audit logs.
2. Determine audit scope:
   - Web application, API endpoints, backend services, and database security rules.
   - External dependencies and package lockfiles.
   - Authentication, authorization flows, and session state.

### Phase 2: Vulnerability Audit Checkpoints

#### 1. OWASP Top 10 (Web & API)
- **Injection**: Verify parameterized queries, ORM safety, and sanitization of system shell commands.
- **Broken Object Level Authorization (BOLA / IDOR)**: Verify that every endpoint verifies object ownership (e.g. `WHERE id = :id AND user_id = :currentUser`).
- **Broken Authentication**: Verify password hashing (bcrypt/argon2), session expiration, rate limiting on login/auth routes, and MFA flows.
- **Server-Side Request Forgery (SSRF)**: Ensure user-supplied URLs cannot access internal networks (`127.0.0.1`, `169.254.169.254`, private IP ranges).
- **Security Misconfiguration**: Verify debug flags are disabled, CORS does not permit wildcard origins with credentials, and directory listing is blocked.

#### 2. Secrets & Credential Exposure
- Scan all tracked repository files for patterns matching:
  - Private keys (`BEGIN RSA PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY`).
  - Provider tokens (OpenAI, Anthropic, AWS, Stripe, GitHub, Slack).
  - Hardcoded connection strings with passwords.
- Verify that `.env*` files containing secrets are present in `.gitignore`.

#### 3. Dependency Vulnerability Audit
- Run package manager vulnerability checks when network access is available:
  - Node: `npm audit` / `pnpm audit`
  - Python: `pip audit` / `pip check`
  - Rust: `cargo audit`
  - Go: `govulncheck`
- In offline or air-gapped environments where network registries time out, catch failures gracefully, mark dependency scan as `[SKIPPED - OFFLINE]`, and proceed with static AST and secret checks without failing.

#### 4. Security Headers & Cookie Flags
- Verify presence of essential response headers:
  - `Content-Security-Policy` (CSP)
  - `Strict-Transport-Security` (HSTS: `max-age=63072000; includeSubDomains; preload`)
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` or `SAMEORIGIN`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- Verify authentication cookies: `Secure`, `HttpOnly`, and `SameSite=Lax` or `Strict`.

#### 5. 15-Point Launch Legal & Compliance Checklist
Audit the repository against [checklists/app-launch-legal.md](../checklists/app-launch-legal.md) to ensure privacy, cookie consent, and data deletion obligations are fulfilled.

### Phase 3: Reporting & Remediation
1. Generate the structured audit report following [templates/security-report.template.md](../templates/security-report.template.md).
2. Rank findings strictly by severity:
   - **Critical**: Remote Code Execution, Auth Bypass, IDOR exposing private PII, exposed live secrets.
   - **High**: CSRF on critical actions, missing RLS policies, severe dependency CVEs.
   - **Medium**: Missing CSP/HSTS headers, overly permissive CORS, session duration too long.
   - **Low / Informational**: Minor best-practice deviations, fingerprinting headers (`X-Powered-By`).
3. Save the report to `.sad/reports/security-<YYYY-MM-DD>.md`.
4. Output a concise summary in the chat citing `file:line` references.
5. **Approval Gate**: Stop and await user authorization before implementing remediation fixes.

---

## 🔗 Vendor Synergies
- **OWASP**: [owasp/owasp-top-10.ref.md](../vendor/owasp/owasp-top-10.ref.md) and [owasp/api-security.ref.md](../vendor/owasp/api-security.ref.md).
- **ECC Security**: [ecc/security-review.ref.md](../vendor/ecc/security-review.ref.md).
- **Database Hardening**: [supabase/rls-and-migrations.ref.md](../vendor/supabase/rls-and-migrations.ref.md).
