"""
Database-Level Row Level Security (RLS) Engine Fixture
Implements SQLite authorization hooks and engine-level view security
to enforce multi-tenant isolation at the database engine level (simulating Postgres RLS behavior).
"""

import sqlite3
from typing import Optional, Dict, Any, List


class DatabaseRLSError(Exception):
    """Raised when a database query violates Row Level Security policies."""
    pass


class TenantDatabaseSession:
    """
    Manages an SQLite database connection with active tenant isolation policies
    enforced via authorizer callbacks, custom context functions, and view-level engine security.
    """

    def __init__(self, tenant_id: str, db_path: str = "file:shared_rls?mode=memory&cache=shared", role: str = "authenticated"):
        self.tenant_id = tenant_id
        self.role = role
        self.conn = sqlite3.connect(db_path, uri=True)
        self.conn.row_factory = sqlite3.Row
        self._register_functions()
        self._init_schema()
        self._setup_rls_authorizer()

    def _register_functions(self):
        """Registers connection-level context functions used by SQL views and policies."""
        self.conn.create_function("current_tenant", 0, lambda: self.tenant_id)
        self.conn.create_function("current_role", 0, lambda: self.role)

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS _organizations_data (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS _projects_data (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                organization_id TEXT NOT NULL,
                name TEXT NOT NULL,
                is_confidential INTEGER DEFAULT 0
            );

            -- RLS View enforcing tenant isolation at the SQL engine level
            CREATE VIEW IF NOT EXISTS projects AS
                SELECT id, tenant_id, organization_id, name, is_confidential
                FROM _projects_data
                WHERE tenant_id = current_tenant();

            -- RLS View for organizations
            CREATE VIEW IF NOT EXISTS organizations AS
                SELECT id, tenant_id, name, created_at
                FROM _organizations_data
                WHERE tenant_id = current_tenant();

            -- INSTEAD OF triggers ensuring all inserts are bound to current_tenant()
            CREATE TRIGGER IF NOT EXISTS rls_projects_insert
            INSTEAD OF INSERT ON projects
            BEGIN
                INSERT INTO _projects_data (id, tenant_id, organization_id, name, is_confidential)
                VALUES (NEW.id, current_tenant(), NEW.organization_id, NEW.name, COALESCE(NEW.is_confidential, 0));
            END;

            CREATE TRIGGER IF NOT EXISTS rls_projects_delete
            INSTEAD OF DELETE ON projects
            BEGIN
                DELETE FROM _projects_data
                WHERE id = OLD.id AND tenant_id = current_tenant();
            END;
        """)
        self.conn.commit()

    def _setup_rls_authorizer(self):
        """
        Registers an engine-level authorizer callback.
        1. Prohibits direct access to underlying raw tables (_projects_data, _organizations_data)
           forcing all queries through RLS views.
        2. Prohibits destructive schema modifications (DROP TABLE).
        """
        def authorizer(action_code, arg1, arg2, db_name, trigger_name):
            # Deny DROP TABLE
            if action_code == sqlite3.SQLITE_DROP_TABLE:
                return sqlite3.SQLITE_DENY

            # Deny direct read/write to internal data tables outside RLS views
            if arg1 in ("_projects_data", "_organizations_data"):
                if trigger_name not in ("projects", "organizations", "rls_projects_insert", "rls_projects_delete"):
                    return sqlite3.SQLITE_DENY

            return sqlite3.SQLITE_OK

        self.conn.set_authorizer(authorizer)

    def insert_project(self, project_id: str, org_id: str, name: str, is_confidential: bool = False):
        """Inserts a project strictly stamped with the active session's tenant_id via RLS view."""
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO projects (id, organization_id, name, is_confidential) VALUES (?, ?, ?, ?)",
            (project_id, org_id, name, 1 if is_confidential else 0),
        )
        self.conn.commit()

    def query_projects(self) -> List[Dict[str, Any]]:
        """
        Executes query on RLS view. The SQLite query engine itself evaluates
        WHERE tenant_id = current_tenant() and filters out all other tenants.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT id, tenant_id, organization_id, name, is_confidential FROM projects")
        return [dict(row) for row in cur.fetchall()]

    def query_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a project by ID through the RLS view.
        If row is not visible under session's tenant, checks if the row exists
        under another tenant and raises DatabaseRLSError (simulating strict Postgres RLS access denial).
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, tenant_id, organization_id, name, is_confidential FROM projects WHERE id = ?",
            (project_id,),
        )
        row = cur.fetchone()
        if row:
            return dict(row)

        # To simulate Postgres RLS denial on cross-tenant access vs true 404:
        # Temporarily query with an internal session to verify if ID exists in another tenant
        internal_conn = sqlite3.connect("file:shared_rls?mode=memory&cache=shared", uri=True)
        try:
            chk = internal_conn.cursor()
            chk.execute("SELECT tenant_id FROM _projects_data WHERE id = ?", (project_id,))
            other_row = chk.fetchone()
            if other_row and other_row[0] != self.tenant_id:
                raise DatabaseRLSError(
                    f"RLS Violation: Session tenant '{self.tenant_id}' denied access to row owned by '{other_row[0]}'"
                )
        finally:
            internal_conn.close()
        return None

    def close(self):
        self.conn.close()
