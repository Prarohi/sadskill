# Mode: `/sad-backend`

Backend mode enforces schema-first engineering, engine-aware migrations, zero-trust tenant isolation, safe query performance, concurrency discipline, and contract-validated APIs.

---

## ⚙️ The Engine-Aware Backend Philosophy

1. **Database Engine Discovery First**:
   - Never assume PostgreSQL or Prisma blindly. Inspect `package.json`, `pyproject.toml`, `Cargo.toml`, configuration files, and environment markers to identify the real database and ORM:
     - **PostgreSQL**: Native Row Level Security (RLS), `timestamptz`, JSONB, `EXPLAIN (ANALYZE, BUFFERS)`.
     - **SQLite / libSQL**: File/embedded database, authorizer callbacks, filtered views, transaction concurrency (`WAL` mode).
     - **MySQL / MariaDB**: Engine locking, generated columns, foreign key indexing nuances.
     - **Document Stores (MongoDB / Firestore)**: Indexing paths, atomic updates (`$set`, transactions), security rules.
2. **Honest Reversibility & Data Preservation**:
   - A schema reversal (`down.sql`) that drops tables or columns does **not** restore lost user data.
   - For destructive operations, use the **Expand / Migrate / Contract** multi-phase pattern rather than sudden column drops.
   - Never claim an irreversible operation is "100% reversible" without a snapshot restore procedure.
3. **Concurrency, Idempotency & Boundaries**:
   - Design state mutations with atomic transactions (`BEGIN ... COMMIT`).
   - Use idempotency keys (`idempotency_key` unique constraints) for payment, webhook, and external side-effect endpoints.
   - Guard against race conditions using `SELECT ... FOR UPDATE` (PostgreSQL) or optimistic locking versions (`version = version + 1`).
4. **Tenant Isolation Architecture**:
   - **PostgreSQL Native RLS**: `ALTER TABLE orgs ENABLE ROW LEVEL SECURITY;` + `CREATE POLICY ... USING (tenant_id = current_setting('app.current_tenant_id'));`
   - **SQLite / Embedded Simulation**: Filtered views with authorizer callbacks or application-layer scoped repositories.
   - **Application-Layer Enforcement**: Explicit parameterization and query scoping when the underlying database lacks native engine RLS.

---

## 🛠️ Execution Pipeline

### Phase 1: Database & Framework Discovery
1. Detect database engine, driver, and migration tool:
   - Migration tools: Supabase CLI, Prisma, Drizzle, Alembic, Flyway, Django, Diesel, Go-Migrate.
2. Inspect connection models: serverless pooled connections (PgBouncer, Supabase Pooler) vs persistent connection pools. Note that session-level `SET` commands behave differently under transaction-mode poolers.

### Phase 2: Schema-First Design
1. **Declare Strict Data Models**:
   - **Primary Keys**: `bigint GENERATED ALWAYS AS IDENTITY` or `uuid` (UUIDv7 preferred for time-sortable indexing).
   - **Timestamps**: Always `timestamptz` (timestamp with time zone). Naive timestamps without time zones are strictly prohibited.
   - **Text & Strings**: Use `text` with `CHECK (char_length(col) <= N)` rather than arbitrary `varchar(255)`.
   - **Financial Decimals**: Use `numeric(12,2)` or integer minor units (cents). Floating-point (`real`, `float`) numbers are banned for money.
   - **Enums vs Lookup Tables**: Prefer small reference tables or check constraints over rigid database ENUMs that require locking schema alterations to extend.

### Phase 3: Engine-Specific Tenant Isolation & RLS
1. **For PostgreSQL**:
   ```sql
   ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
   ALTER TABLE public.organizations FORCE ROW LEVEL SECURITY;

   CREATE POLICY tenant_isolation_select ON public.organizations
     FOR SELECT USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
   ```
2. **For SQLite / Embedded Databases**:
   - Document that SQLite lacks native engine-level `ALTER TABLE ... ENABLE RLS`.
   - Implement isolation via SQLite authorizer callbacks, session functions, or tenant-scoped query builders with explicit unit test verification.
3. **Impersonation Testing**:
   - Every tenant policy must be accompanied by an integration test proving Tenant A cannot read, mutate, or delete Tenant B's records.

### Phase 4: Migration Strategy & Expand/Contract
1. Paired migration scripts:
   - `up.sql`: Forward schema evolution.
   - `down.sql`: Reversal logic (reverse constraint drops, reverse foreign keys, drop created views/tables).
2. **Safe Schema Evolution (Expand / Contract)**:
   - **Step 1 (Expand)**: Add new column as nullable or with safe default.
   - **Step 2 (Migrate)**: Dual-write or backfill in bounded key batches. For PostgreSQL, select a limited batch of keys in a CTE, then update those keys; do not append unsupported `LIMIT` syntax directly to `UPDATE`.
   - **Step 3 (Contract)**: Add `NOT NULL` constraint and drop obsolete columns after verification.

### Phase 5: Query Performance & Indexing Strategy
1. **Indexing Discipline**:
   - Index all foreign key columns involved in joins.
   - Composite indexes: Equality columns first (`tenant_id`, `status`), then range/sort columns (`created_at DESC`).
   - Partial indexes: Use `WHERE deleted_at IS NULL` to keep indexes small and hot in cache.
2. **Safe Query Performance Analysis**:
   - Start with plan-only `EXPLAIN` (for PostgreSQL, `EXPLAIN (COSTS, VERBOSE) ...`) when execution is not authorized. Check syntax against the detected engine/version.
   - `ANALYZE` executes the statement, including functions invoked by a `SELECT`. Measure runtime/buffers only in an authorized disposable database with controlled side effects. Transaction rollback does not undo every sequence change or external trigger/function effect.
   - In that disposable database, a transactional write measurement can use:
     ```sql
     BEGIN;
     EXPLAIN (ANALYZE, BUFFERS) DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '90 days';
     ROLLBACK;
     ```
   - Consult the official [PostgreSQL EXPLAIN documentation](https://www.postgresql.org/docs/15/sql-explain.html) for the actual engine version; do not treat a rollback wrapper as permission to execute production writes.

### Phase 6: API Contracts, Idempotency & Observability
1. Validate incoming payloads using runtime schemas (Zod, Pydantic, TypeBox).
2. Implement structured pagination (`cursor-based` using indexed timestamp + ID; avoid `OFFSET N` on large tables).
3. Include structured error responses, request IDs, and query duration metrics.

---

## 🔗 Vendor Synergies
- **Supabase-specific work**: Load [Supabase guidance](../references/supabase.md) for Auth, API grants, RLS, migrations, or connected project operations.
- **Vercel-hosted backend work**: Load [Vercel guidance](../references/vercel.md) for runtime/environment/deployment decisions; detect the actual framework first.
- **Supabase & Postgres**: [supabase/postgres-best-practices.ref.md](../vendor/supabase/postgres-best-practices.ref.md) and [supabase/rls-and-migrations.ref.md](../vendor/supabase/rls-and-migrations.ref.md).
- **Edge Infrastructure**: [cloudflare/edge-workers-d1.ref.md](../vendor/cloudflare/edge-workers-d1.ref.md).
- **Architecture & TDD**: [mattpocock/codebase-design.ref.md](../vendor/mattpocock/codebase-design.ref.md) and [mattpocock/tdd.ref.md](../vendor/mattpocock/tdd.ref.md).
