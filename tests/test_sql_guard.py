"""Unit tests for sadskill SQL Safety Guard (scripts/sql_guard.py).
Validates detection of destructive SQL mutations, comment stripping,
and tolerance for safe read/write queries.
"""

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sql_guard


class SQLGuardTests(unittest.TestCase):
    def test_benign_queries_allowed(self):
        safe_queries = [
            "SELECT * FROM users;",
            "SELECT id, name FROM accounts WHERE status = 'active';",
            "INSERT INTO logs (event, ts) VALUES ('login', 12345);",
            "UPDATE users SET email = 'test@example.com' WHERE id = 42;",
            "DELETE FROM session_tokens WHERE expires_at < NOW();",
            "CREATE TABLE IF NOT EXISTS temp_metrics (id INT, val FLOAT);",
        ]
        for q in safe_queries:
            with self.subTest(query=q):
                destructive, reason = sql_guard.inspect_sql(q)
                self.assertFalse(destructive, f"Safe query unexpectedly blocked: {q} ({reason})")

    def test_destructive_drop_queries_blocked(self):
        dangerous_drops = [
            "DROP TABLE users;",
            "DROP SCHEMA public CASCADE;",
            "DROP DATABASE production;",
            "DROP VIEW active_users_v2;",
            "DROP MATERIALIZED VIEW aggregated_metrics;",
            "DROP INDEX idx_users_email;",
            "/* safe comment */ DROP/**/TABLE/**/users;",
            "-- leading comment\nDROP TABLE sensitive_data;",
        ]
        for q in dangerous_drops:
            with self.subTest(query=q):
                destructive, reason = sql_guard.inspect_sql(q)
                self.assertTrue(destructive, f"Destructive drop query was not blocked: {q}")
                self.assertIn("DROP", reason)

    def test_destructive_truncate_queries_blocked(self):
        dangerous_truncates = [
            "TRUNCATE TABLE users;",
            "TRUNCATE accounts;",
            "/* test */ TRUNCATE/**/audit_log;",
            "truncate table orders cascade;",
        ]
        for q in dangerous_truncates:
            with self.subTest(query=q):
                destructive, reason = sql_guard.inspect_sql(q)
                self.assertTrue(destructive, f"Destructive truncate query was not blocked: {q}")
                self.assertIn("TRUNCATE", reason)

    def test_destructive_alter_drop_column_blocked(self):
        dangerous_alters = [
            "ALTER TABLE users DROP COLUMN password_hash;",
            "ALTER TABLE accounts DROP COLUMN ssn;",
            "/* comment */ ALTER/**/TABLE users DROP/**/COLUMN token;",
        ]
        for q in dangerous_alters:
            with self.subTest(query=q):
                destructive, reason = sql_guard.inspect_sql(q)
                self.assertTrue(destructive, f"Destructive alter table drop column was not blocked: {q}")

    def test_unbounded_delete_blocked(self):
        unbounded_deletes = [
            "DELETE FROM users;",
            "DELETE FROM accounts",
            "delete from sessions;",
        ]
        for q in unbounded_deletes:
            with self.subTest(query=q):
                destructive, reason = sql_guard.inspect_sql(q)
                self.assertTrue(destructive, f"Unbounded delete was not blocked: {q}")
                self.assertIn("unbounded", reason.lower())

    def test_bounded_delete_allowed(self):
        bounded_deletes = [
            "DELETE FROM users WHERE id = 10;",
            "DELETE FROM sessions WHERE expired = true;",
            "DELETE FROM cache WHERE created_at < 1000;",
        ]
        for q in bounded_deletes:
            with self.subTest(query=q):
                destructive, reason = sql_guard.inspect_sql(q)
                self.assertFalse(destructive, f"Bounded delete query was blocked: {q} ({reason})")

    def test_unbounded_delete_variants_blocked(self):
        cases = [
            "DELETE FROM users RETURNING id;",
            "DELETE FROM users USING accounts;",
            "WITH cte AS (SELECT 1) DELETE FROM users RETURNING *;",
            "DELETE FROM users WHERE TRUE;",
            "DELETE FROM users WHERE 1=1;",
            "SELECT 1; DELETE FROM users RETURNING *;",
            'DELETE FROM "accounts";',
            "ALTER TABLE users DROP CONSTRAINT important;",
        ]
        for query in cases:
            with self.subTest(query=query):
                self.assertTrue(sql_guard.inspect_sql(query)[0])

    def test_strings_and_comments_are_not_sql_commands(self):
        safe = [
            "SELECT 'DROP TABLE users; DELETE FROM accounts';",
            "SELECT $TRUNCATE TABLE users;$;",
            "SELECT $tag$DELETE FROM users;$tag$;",
            'SELECT "DROP TABLE" FROM users;',
            "SELECT 'it''s DROP TABLE users';",
            "SELECT /* outer /* inner */ */ 1;",
            "SELECT 1 -- DROP TABLE users\n;",
        ]
        for query in safe:
            with self.subTest(query=query):
                self.assertFalse(sql_guard.inspect_sql(query)[0])

    def test_unterminated_literals_and_comments_fail_closed(self):
        for query in ("SELECT 'oops", "SELECT /* oops", "SELECT $tag$oops"):
            with self.subTest(query=query):
                self.assertTrue(sql_guard.inspect_sql(query)[0])

    def test_cli_execution_codes(self):
        # Test CLI exit code 0 for safe query
        res_safe = subprocess.run(
            [sys.executable, str(ROOT / "scripts/sql_guard.py"), "SELECT 1;"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_safe.returncode, 0)
        self.assertIn("ALLOWED", res_safe.stdout)

        # Test CLI exit code 2 for destructive query
        res_destr = subprocess.run(
            [sys.executable, str(ROOT / "scripts/sql_guard.py"), "DROP TABLE users;"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_destr.returncode, 2)
        self.assertIn("BLOCKED", res_destr.stderr)


if __name__ == "__main__":
    unittest.main()
