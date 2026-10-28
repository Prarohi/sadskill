# Supabase tasks

Use for Supabase Auth, database access, RLS, migrations, Storage, Realtime, functions, CLI, or MCP. Keep the project's selected framework, database, and account/session contracts until the task actually changes them. Supabase tool availability does not select a provider or authorize remote writes.

## Discover and check current guidance

Inspect the existing adapter, schema, migration history, exposed schemas, and development environment. Identify the exact project and environment before using connected tools. Use installed Supabase guidance or documentation search when available; otherwise consult the official sources below. Check the changelog for relevant breaking changes and discover CLI commands with `--help`.

Use local or disposable test data for development. Keep existing local PostgreSQL setups intact; adding a Supabase reference to a project does not migrate its database, replace its authentication system, or create a hosted project.

## Authorization and keys

- A publishable key is intended for public clients; authorization still depends on grants and policies. Keep secret and legacy `service_role` keys on trusted servers, out of client bundles, logs, and committed examples.
- Enable RLS on tables in exposed schemas and grant only the required operations. API exposure/grants and row policies are separate controls.
- Derive authorization from verified identity and trusted membership data. User-editable metadata is not an authorization source. JWT authorization claims can remain stale until token refresh.
- Scope policies to the real ownership or membership model. A role such as `authenticated` alone does not prove row ownership; anonymous sign-ins can also use that role.
- For updates, review both `USING` and `WITH CHECK`, along with the SELECT policy needed to find the row. Test attempts to change an ownership or tenant field.
- Review views and privileged functions separately: views may bypass RLS unless configured appropriately for the PostgreSQL version; `SECURITY DEFINER` needs an explicit reason, restricted execution grants, and a controlled search path.

## Migrate and verify

Use the repository's migration workflow. For Supabase CLI migrations, create the file through `supabase migration new` rather than inventing its naming convention. Preserve data with additive migrations and verify recovery before destructive changes; a reverse schema script does not restore deleted rows.

Test with actual request roles, not only a superuser, table owner, or `BYPASSRLS` role. Cover unauthenticated access, valid ownership, another user/tenant, insert, update, delete, ownership reassignment, views/functions, and any storage operation touched. Record the engine, role and policies exercised. A local PostgreSQL policy test does not by itself validate hosted Auth, REST, Storage or Realtime integration; SQLite simulation is not native PostgreSQL RLS evidence.

## Official sources

Reviewed 2026-10-28; refresh relevant documentation when implementing a task.

- [Changelog](https://supabase.com/changelog)
- [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [API keys](https://supabase.com/docs/guides/api/api-keys)
- [Security guidance](https://supabase.com/docs/guides/security/product-security)
- [Local development and migrations](https://supabase.com/docs/guides/local-development)
- [Backend workflow](../modes/backend.md)
