# Reference: PostgreSQL Best Practices (Supabase Standards)

Origin: supabase/agent-skills  
License: Apache-2.0  

## Data Types & Schema Guidelines

1. **Identifiers**:
   - Prefer `bigint GENERATED ALWAYS AS IDENTITY` for high-throughput numeric IDs.
   - Use `uuid` with client-generated UUIDv7 for distributed environments needing time-sortable keys.
2. **Timestamps**:
   - Always use `timestamptz`. Never use `timestamp without time zone`, which causes timezone conversion errors during daylight savings and server migrations.
3. **Strings**:
   - Use `text`. Avoid arbitrary length limits like `varchar(255)` unless specified by external protocols.
4. **Money & Numbers**:
   - Use `numeric(12,2)` or store values as integer cents (`bigint`). Never use `float` or `real` for monetary balances.

## Indexing Quick Reference

- **Equality + Range**: Composite index with equality column first: `CREATE INDEX idx_orders ON orders (status, created_at);`
- **Soft Deletes**: Partial index: `CREATE INDEX idx_active_users ON users (email) WHERE deleted_at IS NULL;`
- **JSONB Containment**: GIN index: `CREATE INDEX idx_meta ON events USING gin (metadata);`
