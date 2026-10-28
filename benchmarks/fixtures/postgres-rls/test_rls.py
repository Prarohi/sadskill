#!/usr/bin/env python3
"""Native PostgreSQL policy checks in an owned, network-isolated Docker container."""

import argparse
from pathlib import Path
import shutil
import subprocess
import time
import unittest
import uuid


IMAGE = "postgres@sha256:dfbbb0ad8cab91d41e99123664e37a9b25d0413426d4fb3154e4d668e5d35246"
CONTAINER = "sadskill-rls-" + uuid.uuid4().hex
DATABASE = "sadskill_fixture"


def docker(*args, sql=None, timeout=30):
    return subprocess.run(
        ["docker", *args], input=sql, text=True, capture_output=True, timeout=timeout,
    )


def query(sql, role="sadskill_client"):
    return docker(
        "exec", "-i", CONTAINER, "psql", "-X", "-q", "-A", "-t",
        "--username", role, "--dbname", DATABASE,
        "--set", "ON_ERROR_STOP=1", "--set", "VERBOSITY=verbose", sql=sql,
    )


class NativePostgresRLS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("docker"):
            raise RuntimeError("Docker is required; native PostgreSQL checks were NOT_EXECUTED")
        # Only a successfully created container ID is eligible for cleanup.
        cls.container_id = None
        cls.addClassCleanup(cls.cleanup_container)
        started = docker(
            "run", "--detach", "--rm", "--pull=never", "--name", CONTAINER,
            "--network", "none", "--read-only", "--memory", "256m", "--pids-limit", "128",
            "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,noexec,size=128m",
            "--tmpfs", "/var/run/postgresql:rw,nosuid,noexec,size=8m",
            "--tmpfs", "/tmp:rw,nosuid,noexec,size=16m",
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "--env", f"POSTGRES_DB={DATABASE}",
            IMAGE, "-c", "listen_addresses=", "-c", "fsync=off",
        )
        if started.returncode:
            raise RuntimeError(f"Native PostgreSQL startup failed: {started.stderr.strip()}")
        cls.container_id = started.stdout.strip()
        for _ in range(100):
            process = docker("exec", CONTAINER, "cat", "/proc/1/comm")
            if process.returncode or process.stdout.strip() != "postgres":
                time.sleep(0.1)
                continue
            ready = docker("exec", CONTAINER, "pg_isready", "--username", "postgres",
                           "--dbname", DATABASE)
            if ready.returncode == 0:
                probe = query("SELECT 1;", role="postgres")
                if probe.returncode == 0:
                    break
            time.sleep(0.1)
        else:
            raise RuntimeError("Native PostgreSQL did not become ready")
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        result = query(schema, role="postgres")
        if result.returncode:
            raise RuntimeError(result.stderr)
        if cls.disable_rls:
            mutation = query("ALTER TABLE fixture.records DISABLE ROW LEVEL SECURITY;", role="postgres")
            if mutation.returncode:
                raise RuntimeError(mutation.stderr)
        version = query("SHOW server_version;", role="postgres")
        if version.returncode:
            raise RuntimeError(version.stderr)
        print(f"Native PostgreSQL {version.stdout.strip()}; image {IMAGE}", flush=True)

    @classmethod
    def cleanup_container(cls):
        if cls.container_id is None:
            return
        result = docker("rm", "--force", cls.container_id)
        if result.returncode and "No such container" not in result.stderr:
            raise RuntimeError(f"Could not clean up owned fixture {CONTAINER}: {result.stderr}")

    disable_rls = False

    def request(self, sql, user="alice", tenant="alpha", role="sadskill_client"):
        # These values are fixed test identities, never untrusted application input.
        context = ""
        if user is not None:
            context += f"SET LOCAL sadskill.user_id = '{user}';\n"
        if tenant is not None:
            context += f"SET LOCAL sadskill.tenant_id = '{tenant}';\n"
        return query(f"BEGIN;\n{context}{sql}\nROLLBACK;", role=role)

    def assert_result(self, result, expected):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), expected)

    def assert_denied(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("42501", result.stderr, result.stderr)

    def test_request_role_has_no_owner_or_bypass_privileges(self):
        result = query("""SELECT current_user, rolsuper, rolbypassrls, rolcreaterole,
            pg_has_role(current_user, 'sadskill_owner', 'MEMBER')
            FROM pg_roles WHERE rolname = current_user;""")
        self.assert_result(result, "sadskill_client|f|f|f|f")

    def test_missing_identity_sees_no_rows(self):
        self.assert_result(self.request("SELECT count(*) FROM fixture.records;", user=None), "0")

    def test_missing_tenant_sees_no_rows(self):
        self.assert_result(self.request("SELECT count(*) FROM fixture.records;", tenant=None), "0")

    def test_anonymous_has_grant_but_no_policy_access(self):
        self.assert_result(self.request("SELECT count(*) FROM fixture.records;", role="sadskill_anon"), "0")
        self.assert_denied(self.request(
            "INSERT INTO fixture.records VALUES (10, 'alpha', 'alice', 'forbidden');",
            role="sadskill_anon"))

    def test_each_owner_only_reads_own_rows_without_query_filter(self):
        for user, tenant, row in [("alice", "alpha", "1"), ("alex", "alpha", "2"), ("bob", "beta", "3")]:
            with self.subTest(user=user):
                self.assert_result(self.request("SELECT id FROM fixture.records;", user, tenant), row)

    def test_cross_tenant_id_and_nonexistent_id_both_hidden(self):
        for row in (2, 3, 999):
            with self.subTest(row=row):
                self.assert_result(self.request(f"SELECT count(*) FROM fixture.records WHERE id = {row};"), "0")

    def test_untrusted_membership_cannot_be_created(self):
        self.assert_denied(self.request("INSERT INTO fixture.memberships VALUES ('alice', 'beta');"))
        self.assert_result(self.request("SELECT count(*) FROM fixture.records;", tenant="beta"), "0")

    def test_matching_owner_and_tenant_still_require_membership(self):
        self.assert_result(self.request("SELECT count(*) FROM fixture.records WHERE id = 4;", tenant="beta"), "0")
        self.assert_denied(self.request(
            "INSERT INTO fixture.records VALUES (10, 'beta', 'alice', 'forbidden');", tenant="beta"))

    def test_insert_own_row(self):
        self.assert_result(self.request("""INSERT INTO fixture.records VALUES (10, 'alpha', 'alice', 'new');
            SELECT body FROM fixture.records WHERE id = 10;"""), "new")

    def test_insert_other_owner_or_tenant_denied(self):
        for tenant, owner in [("alpha", "alex"), ("beta", "alice")]:
            with self.subTest(tenant=tenant, owner=owner):
                self.assert_denied(self.request(
                    f"INSERT INTO fixture.records VALUES (10, '{tenant}', '{owner}', 'forbidden');"))

    def test_update_own_row(self):
        self.assert_result(self.request("UPDATE fixture.records SET body = 'edited' WHERE id = 1 RETURNING body;"), "edited")

    def test_update_other_rows_matches_zero(self):
        self.assert_result(self.request("""WITH changed AS (
            UPDATE fixture.records SET body = 'forbidden' WHERE id IN (2, 3) RETURNING id
            ) SELECT count(*) FROM changed;"""), "0")

    def test_owner_reassignment_denied(self):
        self.assert_denied(self.request("UPDATE fixture.records SET owner_id = 'alex' WHERE id = 1;"))

    def test_tenant_reassignment_denied(self):
        self.assert_denied(self.request("UPDATE fixture.records SET tenant_id = 'beta' WHERE id = 1;"))

    def test_delete_own_row_and_hide_other_rows(self):
        self.assert_result(self.request("DELETE FROM fixture.records WHERE id = 1 RETURNING id;"), "1")
        self.assert_result(self.request("""WITH removed AS (
            DELETE FROM fixture.records WHERE id IN (2, 3) RETURNING id
            ) SELECT count(*) FROM removed;"""), "0")

    def test_view_preserves_invoker_isolation(self):
        self.assert_result(self.request("SELECT id FROM fixture.record_view;"), "1")
        self.assert_result(self.request("SELECT count(*) FROM fixture.record_view;", role="sadskill_anon"), "0")

    def test_transaction_local_identity_does_not_leak(self):
        self.assert_result(query("""BEGIN;
            SET LOCAL sadskill.user_id = 'alice'; SET LOCAL sadskill.tenant_id = 'alpha';
            SELECT count(*) FROM fixture.records; COMMIT;
            SELECT count(*) FROM fixture.records;"""), "1\n0")

    def test_owner_without_request_policy_cannot_read_with_force_rls(self):
        self.assert_result(query("SET ROLE sadskill_owner; SELECT count(*) FROM fixture.records;", role="postgres"), "0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disable-rls", action="store_true", help="Negative control: deliberately break this disposable fixture; tests must fail")
    args = parser.parse_args()
    NativePostgresRLS.disable_rls = args.disable_rls
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativePostgresRLS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
