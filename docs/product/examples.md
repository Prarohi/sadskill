# Sadskill Real-World Engineering Scenarios & Walkthroughs

> 10 Concrete Scenarios Demonstrating the Engineering Confidence Layer in Action Across AI Coding Agents

> **Illustrative only:** scenarios, paths, commands, outputs, durations, and findings below are fictional examples. They are not evidence that these tasks were run or that the named project files exist. A real result must use current repository evidence and the status labels in `protocols/evidence.md`.

---

### Scenario 1: T0 Trivial Typo & Color Tweak (Mechanical Bypass)

- **User Prompt**: "Change the primary brand button color to `#2563eb` and fix the typo 'submited' in `src/components/SubmitButton.tsx`."
- **Agent Reasoning**:
  - Classify risk per [modes/plan.md](../../skills/sadskill/modes/plan.md): 1 file, cosmetic styling and string fix, zero data risk, immediately reversible -> **Risk Tier: T0 (Trivial)**.
  - Bypass ceremony: Do not generate `.sad/plans/` markdown file.
- **Execution & Output**:
  ```text
  Done: Updated button background color to `#2563eb` and fixed typo ('submited' -> 'submitted') in `src/components/SubmitButton.tsx`.
  Example verification command (NOT_EXECUTED): npm run lint -- src/components/SubmitButton.tsx
  Suggested next move: Commit changes to working branch.
  ```

---

### Scenario 2: T1 Surgical Bugfix (Lean Mutation Table)

- **User Prompt**: `/sad-plan Create a plan to fix the race condition in AuthTokenManager where concurrent refresh requests trigger multiple token rotation calls. Do not implement it.`
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
- **Execution mode**: The request explicitly asks for a plan and says not to implement, so use `PLAN_ONLY` and stop after presenting it. If the request instead asks to fix the race condition, classify it as `IMPLEMENT` and proceed with the authorized change.

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
  Verification Harness (NOT_EXECUTED example): pytest tests/billing/ -k "webhook and rls"
  Rollback: migrations/20261028_billing.down.sql
  Execution mode: IMPLEMENT, because the prompt explicitly asks to implement.
  Proceed with source changes and sandbox tests. Do not run live Stripe calls
  or a production database migration; those are hard stops requiring explicit
  confirmation. If the user instead requested PLAN_ONLY, stop after this plan.
  ```

---

### Scenario 4: UI/UX Craft & Polish (Zero-Lift & 8 Facets)

- **User Prompt**: `/sad-design Polish our PricingCard component to make it feel premium, accessible, and responsive.`
- **Agent Reasoning**:
  - Evaluates component against the 8 Facets of Interface Quality and the Impeccable craft floor.
  - Prefer 44x44 CSS-pixel touch targets. WCAG 2.2 AA SC 2.5.8 specifies 24x24 CSS pixels or a spacing exception; 44x44 is a stronger design target, not the AA minimum. [W3C SC 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum)
  - Checks state coverage: Default, Hover, Active/Pressed (`scale(0.97)` micro-compression), Focus-visible (`ring-2 ring-offset-2`), Disabled (`cursor-not-allowed opacity-50`), and Loading skeleton.
  - Checks tool availability: No browser preview tool connected -> Truthfully notes `[UNVERIFIED - CODE-LEVEL ONLY]`.
- **Illustrative checklist outcome (NOT_EXECUTED)**: Review semantic HTML, fluid typography, focus/disabled/loading states, and calculate applicable contrast ratios. No rendered or accessibility result is claimed.

---

### Scenario 5: Database Migration & RLS (Illustrative; NOT_EXECUTED)

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
  - Example verification only; no migration was applied and no sandbox run is claimed.

---

### Scenario 6: Security Audit (Illustrative; NOT_EXECUTED)

- **User Prompt**: `/sad-sec Audit our API endpoints for authentication issues, IDOR, and exposed secrets.`
- **Agent Reasoning**:
  - Operates under **Strictly Read-Only** contract. Does not mutate source code or execute destructive payloads.
  - The paths, token, and vulnerability statements below are fictional placeholders, not findings from a repository scan.
- **Reporting**:
  - A real audit must mask any secret evidence and support each severity with inspected source or runtime evidence.
  - No report was written. `REVIEW_ONLY` means no repository mutation; save a report only when explicitly requested.

---

### Scenario 7: Whole-Codebase Architectural Analysis (Illustrative; NOT_EXECUTED)

- **User Prompt**: `/sad-analyze Review entire repository architecture and identify maintenance bottlenecks.`
- **Agent Reasoning**:
  - Unscoped request -> Whole-codebase discovery engine per [protocols/coverage.md](../../skills/sadskill/protocols/coverage.md).
  - A real run must enumerate the current tracked files and exclusions; no counts or coverage status are asserted here.
- **Findings & Phased Roadmap**:
  - The example paths and architecture findings are fictional placeholders. Inspect actual modules before reporting findings.
  - Generates phased remediation roadmap:
    - **Phase A (T0)**: Remove 4 dead export helpers in `src/utils/format.ts`.
    - **Phase B (T1)**: Add missing unit test for order cancellation edge-case.
    - **Phase C (T2)**: Extract payment orchestration into dedicated `PaymentService` to break circular import cycle.
  - No analysis report was generated or saved.

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

### Scenario 9: Autonomous Continuation & Hard Stop Triggers (Illustrative; NOT_EXECUTED)

- **User Prompt**: "Refactor user authentication service to use Argon2id instead of bcrypt. Continue until done."
- **Agent Reasoning**:
  - Intent contains "continue until done" -> `execution_mode = CONTINUE_UNTIL_DONE`.
  - Example phases only: a real implementation must inspect dependencies and run its actual tests; no package install or test result is claimed here.
  - The legacy column name is fictional. Inspect the actual schema before proposing any destructive migration.
  - **Hard Stop Trigger Encountered**: Dropping this column would be an irreversible data deletion. Agent halts and prompts developer: "Argon2id migration and tests pass 100%. Do you want to drop the legacy bcrypt column, or preserve it as a fallback?"

---

### Scenario 10: Graceful Offline Degradation

- **User Prompt**: `/sad-sec Audit dependencies and routes in this air-gapped secure environment.`
- **Agent Reasoning**:
  - Runs `npm audit`; network connection times out (`ETIMEDOUT`).
  - Does NOT crash or abort the security audit.
  - Catches the timeout cleanly and marks dependency vulnerability scanning as `[SKIPPED - OFFLINE / AIR-GAPPED]`.
  - If the selected checks and parsers exist, inspect local source. Otherwise report which checks were not run and continue only with supported read-only checks.
  - Mark every skipped check `NOT_EXECUTED`; a static source review is not a complete dependency or runtime audit.
