-- Disposable fixture only. These roles and objects never belong in an application DB.
CREATE ROLE sadskill_owner NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE sadskill_client LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE sadskill_anon LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE SCHEMA fixture AUTHORIZATION sadskill_owner;
GRANT USAGE ON SCHEMA fixture TO sadskill_client, sadskill_anon;

SET ROLE sadskill_owner;
CREATE TABLE fixture.memberships (
    user_id text NOT NULL,
    tenant_id text NOT NULL,
    PRIMARY KEY (user_id, tenant_id)
);
CREATE TABLE fixture.records (
    id integer PRIMARY KEY,
    tenant_id text NOT NULL,
    owner_id text NOT NULL,
    body text NOT NULL
);
INSERT INTO fixture.memberships VALUES ('alice', 'alpha'), ('alex', 'alpha'), ('bob', 'beta');
INSERT INTO fixture.records VALUES
    (1, 'alpha', 'alice', 'Alice record'),
    (2, 'alpha', 'alex', 'Alex record'),
    (3, 'beta', 'bob', 'Bob record'),
    -- Ownership and request tenant alone must not replace trusted membership.
    (4, 'beta', 'alice', 'No beta membership');

ALTER TABLE fixture.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE fixture.memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY own_memberships ON fixture.memberships FOR SELECT TO sadskill_client
    USING (user_id = current_setting('sadskill.user_id', true));

ALTER TABLE fixture.records ENABLE ROW LEVEL SECURITY;
ALTER TABLE fixture.records FORCE ROW LEVEL SECURITY;
CREATE POLICY own_records ON fixture.records TO sadskill_client
    USING (
        owner_id = current_setting('sadskill.user_id', true)
        AND tenant_id = current_setting('sadskill.tenant_id', true)
        AND EXISTS (
            SELECT 1 FROM fixture.memberships m
            WHERE m.user_id = current_setting('sadskill.user_id', true)
              AND m.tenant_id = records.tenant_id
        )
    )
    WITH CHECK (
        owner_id = current_setting('sadskill.user_id', true)
        AND tenant_id = current_setting('sadskill.tenant_id', true)
        AND EXISTS (
            SELECT 1 FROM fixture.memberships m
            WHERE m.user_id = current_setting('sadskill.user_id', true)
              AND m.tenant_id = records.tenant_id
        )
    );

-- PostgreSQL 15+ view semantics: evaluate access as the querying role.
CREATE VIEW fixture.record_view WITH (security_invoker = true) AS
    SELECT id, tenant_id, owner_id, body FROM fixture.records;
GRANT SELECT ON fixture.memberships TO sadskill_client;
GRANT SELECT, INSERT, UPDATE, DELETE ON fixture.records TO sadskill_client, sadskill_anon;
GRANT SELECT ON fixture.record_view TO sadskill_client, sadskill_anon;
RESET ROLE;
