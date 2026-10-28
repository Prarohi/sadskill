# Sadskill Real-World Engineering Scenarios & Walkthroughs

> 10 Concrete Scenarios Demonstrating the Engineering Confidence Layer in Action Across AI Coding Agents

---

### Scenario 1: T0 Trivial Typo & Color Tweak (Mechanical Bypass)

- **User Prompt**: "Change the primary brand button color to `#2563eb` and fix the typo 'submited' in `src/components/SubmitButton.tsx`."
- **Agent Reasoning**:
  - Classify risk per [modes/plan.md](../skills/sadskill/modes/plan.md): 1 file, cosmetic styling and string fix, zero data risk, immediately reversible -> **Risk Tier: T0 (Trivial)**.
  - Bypass ceremony: Do not generate `.sad/plans/` markdown file.
- **Execution & Output**:
  ```text
  Done: Updated button background color to `#2563eb` and fixed typo ('submited' -> 'submitted') in `src/components/SubmitButton.tsx`.
  Verified: npm run lint -- src/components/SubmitButton.tsx exited 0.
  Suggested next move: Commit changes to working branch.
  ```

---

### Scenario 2: T1 Surgical Bugfix (Lean Mutation Table)

- **User Prompt**: `/sad-plan Fix race condition in AuthTokenManager where concurrent refresh requests trigger multiple token rotation calls.`
- **Agent Reasoning**:
  - Scope: `src/auth/token-manager.ts` and `tests/auth/token-manager.test.ts` (<= 2 files).
  - Risk Tier: **T1 (Surgical)**. Blast radius is contained to token manager helper; no database schema or API interface change.
  - Skip heavy Mermaid diagrams and long prose to conserve tokens. Output lean file mutation table.
- **Plan Generated (Inline Chat / Optional Record)**:
  ```text
  Goal: Deduplicate in-flight token refresh requests using a shared promise cache.
  Files Touched (2 files):
    - MODIFY src/auth/token-manager.ts (add private `refreshPromise: Promise<Token> | null`)
    - MODIFY tests/auth/token-manager.test.ts (add test: "deduplicates concurrent refresh requests")
  Verification: npm test tests/auth/token-manager.test.ts
  ```
- **Execution**: Deduplicates promise, runs test, passes with exit code 0.

---

### Scenario 3: T2 Architectural Feature (Full Change Contract)

- **User Prompt**: "Implement multi-tenant organization billing with Stripe webhooks and subscription tier enforcement."
- **Agent Reasoning**:
  - Touches database schema, payment webhooks, middleware authorization, and Stripe SDK -> **Risk Tier: T2 (Architectural)**.
  - Requires Contract-First AST signatures, Mermaid architecture flow, boundary analysis, and rollback strategy.
- **Artifact Written**: `.sad/plans/2026-10-28-org-billing.md` conforming to [templates/change-contract.template.md](../../skills/sadskill/templates/change-contract.template.md).
- **Executive Summary in Chat**:
  ```text
  [Read Full Plan (.sad/plans/2026-10-28-org-billing.md)]
  Intent: Multi-tenant subscription management with idempotent Stripe webhook ingestion.
  Architecture: Stripe Webhook -> Verify Signature -> Upsert Customer Subscription -> Enforce Tier via RLS.
  Files to create/modify: 6 files (migrations, webhook controller, subscription service, middleware, tests).
  Verification Harness: pytest tests/billing/ -k "webhook and rls"
  Rollback: migrations/20261028_billing.down.sql
  Awaiting authorization to proceed with implementation.
  ```

---

### Scenario 4: UI/UX Craft & Polish (Zero-Lift & 8 Facets)

- **User Prompt**: `/sad-design Polish our PricingCard component to make it feel premium, accessible, and responsive.`
- **Agent Reasoning**:
  - Evaluates component against the 8 Facets of Interface Quality and the Impeccable craft floor.
  - Checks touch targets (minimum 44x44px for CTA buttons and FAQ toggles).
  - Checks state coverage: Default, Hover, Active/Pressed (`scale(0.97)` micro-compression), Focus-visible (`ring-2 ring-offset-2`), Disabled (`cursor-not-allowed opacity-50`), and Loading skeleton.
  - Checks tool availability: No browser preview tool connected -> Truthfully notes `[UNVERIFIED - CODE-LEVEL ONLY]`.
- **Outcome**: Clean, zero-slop component with semantic HTML, fluid typography tokens, and accessible WCAG 2.2 AA contrast ratios.

---

### Scenario 5: Database Migration & RLS (Engine Discovery & Reversibility)

- **User Prompt**: `/sad-backend Create organization documents table with strict tenant isolation and audit timestamps.`
- **Agent Reasoning**:
  - Inspects project dependencies: identifies `pg` and `drizzle-orm` with PostgreSQL connection -> Engine: PostgreSQL.
  - Creates paired migration files:
    - `migrations/20261028_org_docs.up.sql`
    - `migrations/20261028_org_docs.down.sql`
  - Uses `timestamptz` for all timestamps (`created_at`, `updated_at`).
  - Configures native PostgreSQL Row-Level Security:
    ```sql
    ALTER TABLE org_documents ENABLE ROW LEVEL SECURITY;
    CREATE POLICY org_docs_tenant_isolation ON org_documents
      FOR ALL USING (tenant_id = current_setting('app.current_tenant_id', true));
    ```
  - Verifies migration reversibility by applying `up.sql` then `down.sql` in test sandbox.

---

### Scenario 6: Security Audit (Strictly Read-Only & Masked Proofs)

- **User Prompt**: `/sad-sec Audit our API endpoints for authentication issues, IDOR, and exposed secrets.`
- **Agent Reasoning**:
  - Operates under **Strictly Read-Only** contract. Does not mutate source code or execute destructive payloads.
  - Discovers hardcoded Stripe test key in `tests/fixtures/mock_stripe.py` and unauthenticated `GET /api/orgs/:id/export` endpoint.
- **Reporting**:
  - Masks secret proof: `sk_test_****...9a8b` (never displays raw token).
  - Categorizes findings:
    - `[CONFIRMED CRITICAL]` BOLA / IDOR on `GET /api/orgs/:id/export` (missing tenant check in `src/api/orgs.ts:84`).
    - `[CONFIRMED HIGH]` Hardcoded test secret in `tests/fixtures/mock_stripe.py:12`.
    - `[HYPOTHESIS LOW]` Missing `Permissions-Policy` header in response middleware.
  - Writes audit report to `.sad/reports/security-2026-10-28-143022.md`. Halts before applying fixes.

---

### Scenario 7: Whole-Codebase Architectural Analysis & Coverage Ledger

- **User Prompt**: `/sad-analyze Review entire repository architecture and identify maintenance bottlenecks.`
- **Agent Reasoning**:
  - Unscoped request -> Whole-codebase discovery engine per [protocols/coverage.md](../../skills/sadskill/protocols/coverage.md).
  - Enumerates 48 tracked files; excludes `node_modules/`, `dist/`.
  - Directly inspects 38 module interfaces -> Status: `PARTIAL_COVERAGE` (truthfully disclosed).
- **Findings & Phased Roadmap**:
  - Identifies "god file" in `src/services/OrderProcessor.ts` (780 LOC) with circular dependency on `src/services/InventoryService.ts`.
  - Generates phased remediation roadmap:
    - **Phase A (T0)**: Remove 4 dead export helpers in `src/utils/format.ts`.
    - **Phase B (T1)**: Add missing unit test for order cancellation edge-case.
    - **Phase C (T2)**: Extract payment orchestration into dedicated `PaymentService` to break circular import cycle.
  - Saves report to `.sad/reports/analysis-2026-10-28-150000.md`.

---

### Scenario 8: Requirement Pivot & Intent Tracking

- **User Interaction**:
  - Turn 1: User asks to design caching with Redis. Agent drafts Redis caching plan.
  - Turn 2: User says "Actually, keep it simple. We don't have Redis in production. Use in-memory LRU cache with Cloudflare KV instead."
- **Agent Reasoning**:
  - Precedence hierarchy: Latest user instruction strictly supersedes earlier assumptions and past plan notes.
  - Mentally purges Redis dependency without arguing.
  - Updates Change Contract to reflect `@cloudflare/kv` and in-memory LRU fallback.
  - Records the architecture decision in `.sad/decisions.md` (ADR-004: In-Memory / Cloudflare KV Caching).

---

### Scenario 9: Autonomous Continuation & Hard Stop Triggers

- **User Prompt**: "Refactor user authentication service to use Argon2id instead of bcrypt. Continue until done."
- **Agent Reasoning**:
  - Intent contains "continue until done" -> `execution_mode = CONTINUE_UNTIL_DONE`.
  - Phase 1: Installs `argon2`, rewrites hashing helper, updates unit tests.
  - Phase 2: Runs test suite, encounters 1 failed test due to hash parameter configuration.
  - Autonomous Retry: Adjusts memory and iteration cost parameters to match test harness; re-runs test; passes cleanly.
  - Phase 3: Identifies legacy database column `password_hash_bcrypt_backup`.
  - **Hard Stop Trigger Encountered**: Dropping this column would be an irreversible data deletion. Agent halts and prompts developer: "Argon2id migration and tests pass 100%. Do you want to drop the legacy bcrypt column, or preserve it as a fallback?"

---

### Scenario 10: Graceful Offline Degradation

- **User Prompt**: `/sad-sec Audit dependencies and routes in this air-gapped secure environment.`
- **Agent Reasoning**:
  - Runs `npm audit`; network connection times out (`ETIMEDOUT`).
  - Does NOT crash or abort the security audit.
  - Catches the timeout cleanly and marks dependency vulnerability scanning as `[SKIPPED - OFFLINE / AIR-GAPPED]`.
  - Transitions automatically to local static AST inspections: scans for hardcoded secrets, SQL injection string concatenation, and missing authorization middleware using local repository source code and bundled vendor references.
  - Produces complete, high-value static audit report.
