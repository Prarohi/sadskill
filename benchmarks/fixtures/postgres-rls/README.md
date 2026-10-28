# Native PostgreSQL RLS fixture

This opt-in Track B fixture exercises PostgreSQL 15 policies with direct connections as non-owner, non-superuser, non-`BYPASSRLS` login roles. It is separate from the SQLite simulation and from C1 real-agent evaluation.

```bash
docker pull postgres@sha256:dfbbb0ad8cab91d41e99123664e37a9b25d0413426d4fb3154e4d668e5d35246
python3 benchmarks/fixtures/postgres-rls/test_rls.py
```

The runner requires the pinned image to be cached and never pulls implicitly. It creates a uniquely named container with no network, published ports, host mounts or persistent volumes. The root filesystem is read-only and database files use disposable tmpfs. Trust authentication is restricted to the container's Unix socket; PostgreSQL does not listen on TCP. Cleanup removes only this run's container. Docker access is required; missing Docker/image/startup is an error, not a passing skip.

The SQL covers grants plus default-deny RLS, trusted memberships, ownership and tenant boundaries, CRUD, ownership/tenant reassignment, `security_invoker` views, forced owner enforcement, and transaction-local context reset. Queries intentionally omit application-side tenant filters. Every write is rolled back.

Run the negative control to prove the checks detect a broken configuration:

```bash
python3 benchmarks/fixtures/postgres-rls/test_rls.py --disable-rls
```

It must exit nonzero with policy assertion failures. A startup failure does not count as a valid negative control. Both runs create and remove their own fixture.

## Evidence limits

`sadskill.user_id` and `sadskill.tenant_id` stand in for identity set by a trusted server after verifying a session. A SQL client can set custom PostgreSQL settings itself: these settings do not authenticate an attacker with direct SQL access. The fixture tests policy semantics, not a production identity bridge, connection pool implementation, Supabase JWT/Auth/REST/Storage integration, or an application's migration. No fixture credentials, roles, schema or data are intended for live databases.

The digest pins the tested image, not a perpetual security endorsement. Update it deliberately with current PostgreSQL security guidance and rerun both controls.

Policy behavior follows the PostgreSQL 15 documentation for [row security](https://www.postgresql.org/docs/15/ddl-rowsecurity.html) and [invoker views](https://www.postgresql.org/docs/15/sql-createview.html).
