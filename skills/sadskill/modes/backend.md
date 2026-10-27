# Mode: `/sad-backend`

Backend mode enforces schema-first engineering, reversible migrations, zero-trust Row Level Security (RLS), intelligent indexing, and contract-validated APIs.

---

## ⚙️ Execution Pipeline

### Phase 1: Schema-First Design
1. **Declare Strict Data Models**:
   - Primary Keys: Use `bigint GENERATED ALWAYS AS IDENTITY` or `uuid` (UUIDv7 preferred for sortability).
   - Timestamps: Always use `timestamptz` (timestamp with time zone). Never naive timestamps.
   - Text & Strings: Use `text` rather than arbitrary `varchar(255)`. Add explicit check constraints if length limits are needed.
   - Financial & Decimal: Use `numeric(10,2)` or integer cents. Never floating point numbers.
   - Enums vs Foreign Keys: Prefer small lookup tables or check constraints over hardcoded database enums that hinder migration.

### Phase 2: Reversible Migrations & Data Safety
1. Paired migration scripts:
   - `up.sql`: Applies the forward schema changes.
   - `down.sql`: Exact reversal logic (drops tables, restores columns, drops constraints in reverse order).
2. For irreversible operations (e.g. dropping data columns or truncating tables):
   - Document explicit backup requirements and snapshot restore procedures.
   - Use the expand/contract pattern for schema evolution:
     - Add column as nullable.
     - Backfill default values in manageable transaction batches.
     - Add `NOT NULL` constraint and application validation.

### Phase 3: Row Level Security (RLS) & Access Control
1. **Zero-Trust Baseline**:
   ```sql
   ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
   ALTER TABLE public.organizations FORCE ROW LEVEL SECURITY;
   ```
2. **Explicit Granular Policies**:
   - Write separate policies for `SELECT`, `INSERT`, `UPDATE`, and `DELETE`.
   - Never write a catch-all `ALL` policy unless universally applicable.
   - Verify that non-authenticated requests cannot bypass authorization filters.
   - Validate RLS in a real database environment with role impersonation tests (e.g. Tenant A vs Tenant B).

### Phase 4: Indexing & Query Performance
1. **Rule of Indexing**:
   - Foreign keys: Index columns used in `REFERENCES` joins where workload indicates write costs are outweighed by join query speed.
   - Composite indexes: Order equality columns first (`status = 'active'`), then range columns (`created_at > ...`).
   - Partial indexes: Use `WHERE deleted_at IS NULL` or `WHERE is_active = true` to keep index trees compact.
   - JSONB / Search: Use `GIN` index for containment (`@>`) or full-text search.
2. **Safe Query Performance Analysis**:
   - For read queries (`SELECT`): Run `EXPLAIN (ANALYZE, BUFFERS)` to verify index scans over sequential scans on large tables.
   - For write queries (`INSERT`, `UPDATE`, `DELETE`): Use `EXPLAIN (BUFFERS)` without `ANALYZE` in production, or test inside staging transactions with explicit rollback:
     ```sql
     BEGIN;
     EXPLAIN (ANALYZE, BUFFERS) DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '90 days';
     ROLLBACK;
     ```

### Phase 5: API Contracts & Integration Tests
1. Validate all request payloads using runtime schemas (e.g. Zod, Pydantic).
2. Write integration tests verifying:
   - Happy path CRUD operations.
   - Cross-tenant authorization denial (verifying Tenant A cannot view Tenant B's data).
   - Invalid payload rejection with clean, structured error responses.

---

## 🔗 Vendor Synergies
- **Supabase & Postgres**: [supabase/postgres-best-practices.ref.md](../vendor/supabase/postgres-best-practices.ref.md) and [supabase/rls-and-migrations.ref.md](../vendor/supabase/rls-and-migrations.ref.md).
- **Edge Infrastructure**: [cloudflare/edge-workers-d1.ref.md](../vendor/cloudflare/edge-workers-d1.ref.md).
- **Architecture & TDD**: [mattpocock/codebase-design.ref.md](../vendor/mattpocock/codebase-design.ref.md) and [mattpocock/tdd.ref.md](../vendor/mattpocock/tdd.ref.md).
