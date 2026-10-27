# sad-backend

Execute the `backend` workflow of `sadskill` on target schema or API: $ARGUMENTS

## Instructions
1. **Locate sadskill Configuration**:
   - Check local workspace: `./skills/sadskill/SKILL.md` (or global `~/.claude/skills/sadskill/SKILL.md`).
   - Check `.sad/decisions.md` (ADRs) and `.sad/history.md`.
   - Check local profile `~/.sadskill/profile.md` if present.
2. **Schema-First Design & Reversible Migrations**:
   - Primary Keys: Use `bigint GENERATED ALWAYS AS IDENTITY` or UUIDv7.
   - Timestamps: Always `timestamptz`. Never naive timestamps.
   - Text & Decimals: Use `text` with check constraints; integer cents or `numeric(10,2)` for money.
   - Reversible Migrations: Always write paired `up.sql` and `down.sql`. Use expand/contract pattern for non-null additions.
3. **Row Level Security & Safe Query Analysis**:
   - Zero-Trust RLS: `ENABLE ROW LEVEL SECURITY;` + `FORCE ROW LEVEL SECURITY;`. Write granular `SELECT`, `INSERT`, `UPDATE`, `DELETE` policies.
   - Safe Performance Inspection: Run `EXPLAIN (ANALYZE, BUFFERS)` for `SELECT` queries. For write queries, use `EXPLAIN (BUFFERS)` or wrap in `BEGIN; ... ROLLBACK;` to prevent unintended mutations.
4. **Validation & Verification Evidence**:
   - Validate API payloads with runtime schemas (Zod, Pydantic).
   - Execute integration tests, record proof in `.sad/evidence/<timestamp>-backend.json`, and output 3-line terminal execution proof in chat.
