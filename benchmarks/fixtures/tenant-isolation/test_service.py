"""
Unit test suite verifying tenant isolation and access controls.
"""

import unittest
from service import TenantNoteService, AuthorizationError


class TestTenantIsolation(unittest.TestCase):
    def setUp(self):
        self.svc = TenantNoteService()
        # Seed Tenant A
        self.note_a = self.svc.create_note(
            tenant_id="tenant_alpha",
            author_id="user_alice",
            title="Alpha Strategy",
            content="Top secret alpha plans",
            is_private=True,
        )
        # Seed Tenant B
        self.note_b = self.svc.create_note(
            tenant_id="tenant_beta",
            author_id="user_bob",
            title="Beta Launch",
            content="Beta public roadmap",
            is_private=False,
        )

    def test_same_tenant_author_access(self):
        note = self.svc.get_note("tenant_alpha", "user_alice", self.note_a["id"])
        self.assertIsNotNone(note)
        self.assertEqual(note["title"], "Alpha Strategy")

    def test_cross_tenant_access_blocked(self):
        """Cross-tenant reading must raise AuthorizationError."""
        with self.assertRaises(AuthorizationError):
            self.svc.get_note("tenant_beta", "user_bob", self.note_a["id"])

    def test_cross_tenant_listing_isolated(self):
        """Tenant Beta listing must not see any notes from Tenant Alpha."""
        notes = self.svc.list_notes("tenant_beta", "user_bob")
        tenant_ids = {n["tenant_id"] for n in notes}
        self.assertEqual(tenant_ids, {"tenant_beta"})
        self.assertNotIn(self.note_a["id"], [n["id"] for n in notes])


if __name__ == "__main__":
    unittest.main()
