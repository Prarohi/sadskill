"""
Integration tests for database-level Row Level Security (RLS) enforcement.
"""

import unittest
from db_rls import TenantDatabaseSession, DatabaseRLSError


class TestDatabaseRLS(unittest.TestCase):
    def setUp(self):
        # Create session for Tenant Alpha
        self.session_a = TenantDatabaseSession(tenant_id="tenant_alpha")
        cur = self.session_a.conn.cursor()
        cur.execute("DELETE FROM projects")
        self.session_a.conn.commit()

        self.session_a.insert_project("proj_a1", "org_alpha", "Alpha Roadmap", is_confidential=True)

        # Create session for Tenant Beta connecting to the same shared database
        self.session_b = TenantDatabaseSession(tenant_id="tenant_beta")
        self.session_b.insert_project("proj_b1", "org_beta", "Beta Launch", is_confidential=False)

    def tearDown(self):
        self.session_a.close()
        self.session_b.close()

    def test_tenant_can_read_own_records(self):
        projects = self.session_a.query_projects()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Alpha Roadmap")
        self.assertEqual(projects[0]["tenant_id"], "tenant_alpha")

    def test_tenant_cannot_read_other_tenant_records(self):
        projects = self.session_b.query_projects()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Beta Launch")
        self.assertEqual(projects[0]["tenant_id"], "tenant_beta")

    def test_direct_id_cross_tenant_access_denied(self):
        # Session A attempts to fetch Tenant Beta's project
        with self.assertRaises(DatabaseRLSError):
            self.session_a.query_project_by_id("proj_b1")

    def test_destructive_schema_modification_denied_by_authorizer(self):
        # Database authorizer blocks DROP TABLE
        with self.assertRaises(Exception):
            cur = self.session_a.conn.cursor()
            cur.execute("DROP TABLE projects")

    def test_view_and_trigger_tampering_is_denied(self):
        import sqlite3
        for statement in (
            "DROP VIEW projects",
            "CREATE TEMP VIEW projects AS SELECT * FROM _projects_data",
            "DROP TRIGGER rls_projects_insert",
        ):
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.DatabaseError):
                    self.session_b.conn.execute(statement)

    def test_authorizer_cannot_be_disabled_via_public_session(self):
        with self.assertRaises(DatabaseRLSError):
            self.session_b.conn.set_authorizer(None)

    def test_direct_table_bypass_denied_by_engine_authorizer(self):
        # Database authorizer blocks direct access to underlying raw table
        import sqlite3
        with self.assertRaises(sqlite3.DatabaseError):
            cur = self.session_a.conn.cursor()
            cur.execute("SELECT * FROM _projects_data")


if __name__ == "__main__":
    unittest.main()
