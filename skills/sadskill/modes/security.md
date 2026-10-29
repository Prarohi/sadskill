# Mode: `/sad-sec`

Security mode conducts **evidence-driven vulnerability assessments, threat modeling, secret scanning, dependency audits, and regulatory compliance evaluations**.

By contract, `/sad-sec` operates in **Strictly Read-Only** mode by default. It observes, audits, and diagnoses without mutating application code or production state unless explicit remediation is authorized.

---

## 🛡️ Core Security Principles

1. **Strictly Read-Only Diagnostic Contract**:
   - Audits must never execute unauthorized code edits, destructive database migrations, or live exploits against third-party endpoints.
   - Any proposed remediation must be presented as an explicit plan or change contract before mutation begins.
2. **Exploitability Over Checklist Noise**:
   - Differentiate **Confirmed Vulnerabilities** (proven reachable, exploitable, or verified code flaws) from **Hypotheses & Defense-in-Depth Observations** (theoretical risk, uncalled utility methods, or missing hardening headers on internal services).
   - Never inflate cosmetic warnings (e.g., absence of `X-Powered-By` removal) into "High" or "Critical".
3. **Mandatory Secret Redaction**:
   - **NEVER** expose plaintext secrets, API keys, private keys, or passwords in chat outputs, terminal logs, or markdown reports.
   - Always redact sensitive tokens using partial masking (e.g., `sk-proj-****...a1b2`, `ghp_****...9z8y`, `postgres://user:****@db:5432/app`).
4. **Concrete `file:line` Citations**:
   - Every security finding must cite exact file paths and line numbers with actionable reproduction logic or code-level explanations.
5. **Zero-Trust Boundary Modeling**:
   - Trace untrusted inputs from the network perimeter through controllers, ORMs, subprocesses, and external API requests.

---

## 🔍 Execution Pipeline

### Phase 1: Threat Modeling & Perimeter Mapping
1. **Identify Trust Boundaries**:
   - Ingress endpoints (HTTP handlers, WebSockets, background queue consumers, webhooks).
   - Tenant isolation boundaries (shared database, tenant ID filtering, Row-Level Security).
   - Third-party integrations (webhook signature verification, external API authentication).
2. **Scan Scope & Prior History**:
   - Check `.sad/reports/` for prior security audit baselines to detect regressions.
   - Identify active authentication mechanisms (JWT, sessions, OAuth, API keys).

### Phase 2: Vulnerability Audit Checkpoints

#### 1. OWASP Top 10 (Web & API Security)
- **Injection (SQL, NoSQL, Command, Template)**:
  - Verify all database queries use parameterized placeholders or safe ORM builders.
  - Verify that system shell invocations (`exec`, `spawn`, `subprocess`) strictly avoid unescaped string concatenation.
- **Broken Object Level Authorization (BOLA / IDOR)**:
  - Verify that record lookups, updates, and deletes enforce explicit ownership (`WHERE id = :id AND user_id = :currentUser`) or database-level RLS.
- **Broken Authentication & Session Management**:
  - Verify modern password hashing algorithms (Argon2id, bcrypt; reject MD5, SHA1, plaintext).
  - Check session invalidation on logout, rotation on privilege elevation, and brute-force rate limiting.
- **Server-Side Request Forgery (SSRF)**:
  - Ensure user-provided URLs cannot reach localhost, loopback interfaces (`127.0.0.1`, `::1`), cloud metadata services (`169.254.169.254`), or private VPC CIDR ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- **Security Misconfiguration & Permissive CORS**:
  - Verify debug flags are disabled in production manifests.
  - Ensure CORS policies do not mirror arbitrary `Origin` headers while allowing `Access-Control-Allow-Credentials: true`.

#### 2. Secrets & Credential Exposure Detection
- Perform comprehensive pattern scans across all tracked files for:
  - Private keys (`BEGIN RSA PRIVATE KEY`, `BEGIN EC PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY`).
  - Provider API tokens (Anthropic, OpenAI, AWS, Stripe, GitHub, Slack, SendGrid).
  - Hardcoded connection strings with embedded credentials.
- Verify that `.env*` files containing environment secrets are strictly ignored in `.gitignore`.
- Redact all discovered candidate secrets immediately upon detection.

#### 3. Dependency Vulnerability Audit
- Run package manager vulnerability scanners when online:
  - Node / JS: `npm audit` / `pnpm audit`
  - Python: `pip-audit` / `safety check`
  - Rust: `cargo audit`
  - Go: `govulncheck ./...`
- **Graceful Offline Degradation**: In air-gapped or network-restricted environments where package registries are unreachable, catch network timeouts cleanly, mark dependency scans as `[SKIPPED - OFFLINE / AIR-GAPPED]`, and proceed with static AST and secret checks without aborting the audit.

#### 4. Security Headers & Cookie Flags
- Verify HTTP response security headers for web applications:
  - `Content-Security-Policy` (CSP)
  - `Strict-Transport-Security` (HSTS: `max-age=63072000; includeSubDomains; preload`)
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` or `SAMEORIGIN`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- Verify authentication cookies specify `Secure`, `HttpOnly`, and `SameSite=Lax` or `Strict`.

#### 5. Launch Legal & Regulatory Compliance
- Audit the application against [checklists/app-launch-legal.md](../checklists/app-launch-legal.md) to verify privacy disclosures, cookie consent compliance, and GDPR/CCPA data export and deletion endpoints.

---

## 📊 Phase 3: Reporting & Actionable Remediation

1. **Severity Classification Matrix**:
   - **Critical**: Remote Code Execution (RCE), Unauthenticated Authentication Bypass, BOLA exposing sensitive PII, live exposed cloud/production credentials.
   - **High**: Stored XSS, privilege escalation, missing RLS policies on multi-tenant tables, severe direct dependency CVEs with known public exploit.
   - **Medium**: CSRF on non-critical actions, overly permissive CORS, missing HSTS, session duration exceeding policy.
   - **Low / Informational**: Server banner fingerprinting (`Server`, `X-Powered-By`), defense-in-depth suggestions, minor hygiene issues.
2. **Report Generation**:
   - Compile findings into [templates/security-report.template.md](../templates/security-report.template.md).
   - Categorize each item as `[CONFIRMED]` (proven reachable/exploitable) or `[HYPOTHESIS]` (theoretical / unverified).
   - Save the artifact to `.sad/reports/security-<YYYY-MM-DD>-<HHMMSS>.md`.
3. **Remediation Gate**:
   - Output an executive summary in chat citing `file:line` locations and masked proofs.
   - Halt execution. Do NOT patch code automatically unless the user explicitly requests remediation (`/sad-sec remediate` or `apply security fixes`).
   - For remediation, route changes through [modes/plan.md](plan.md) using appropriate risk tiering (T1 for localized fixes, T2 for auth/schema overhauls).

---

## 🔗 Vendor Synergies
- **Supabase authorization**: Load [Supabase guidance](../references/supabase.md) when reviewing Auth, RLS, API keys, privileged functions, or Storage policies.
- **Vercel deployment credentials**: Load [Vercel guidance](../references/vercel.md) when reviewing environment variables, PR builds, or release access.
- **OWASP**: [owasp/owasp-top-10.ref.md](../vendor/owasp/owasp-top-10.ref.md) and [owasp/api-security.ref.md](../vendor/owasp/api-security.ref.md).
- **ECC Security**: [ecc/security-review.ref.md](../vendor/ecc/security-review.ref.md).
- **Database Hardening**: [supabase/rls-and-migrations.ref.md](../vendor/supabase/rls-and-migrations.ref.md).
