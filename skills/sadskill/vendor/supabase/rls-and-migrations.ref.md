# Reference: Row Level Security & Migrations (Supabase Standards)

Origin: supabase/agent-skills  
License: Apache-2.0  

## Row Level Security (RLS) Protocol

1. **Enable RLS on Every Table**:
   ```sql
   ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
   ALTER TABLE public.documents FORCE ROW LEVEL SECURITY;
   ```
2. **Granular Policies**:
   - Write separate policies for each command (`SELECT`, `INSERT`, `UPDATE`, `DELETE`).
   - Example SELECT policy:
     ```sql
     CREATE POLICY "Users can view documents in their organization"
     ON public.documents
     FOR SELECT
     TO authenticated
     USING (organization_id = (SELECT org_id FROM user_profiles WHERE id = auth.uid()));
     ```
3. **Never Allow Public Write Access**:
   - Restrict write operations strictly to authenticated roles or specific service roles.

## Reversible Migration Directives

- Never run migrations without verifying the rollback script.
- Separate schema definitions (`up.sql`) from seed or backfill operations.
- When renaming columns, avoid immediate drops: create new column, double-write, backfill, deprecate old column.
