# `/sad-backend`

Execute the `backend` workflow of `sadskill`.

## Instructions
1. Load and adhere to `sadskill`:
   - Inspect `.sad/` project memory (`.sad/decisions.md`, `.sad/history.md`).
   - Respect local profile if configured (`~/.sadskill/profile.md`).
   - Enforce the Human-Voice protocol.
2. Follow `skills/sadskill/modes/backend.md`:
   - Schema-first architecture: declare types, constraints, and relationships.
   - Write reversible migrations (up & down).
   - Enforce Row Level Security (RLS) policies and least-privilege role permissions.
   - Optimize indexes (B-tree, composite, partial, GIN) and inspect queries.
   - Structure APIs with explicit validation contracts and tests.
