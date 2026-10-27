"""
Multi-Tenant Note Service Fixture
Demonstrates multi-tenant isolation enforcement and RLS-equivalent access controls.
"""

from typing import Dict, List, Optional


class AuthorizationError(Exception):
    pass


class TenantNoteService:
    def __init__(self):
        # In-memory storage: id -> note dict
        self._notes: Dict[str, dict] = {}
        self._next_id = 1

    def create_note(self, tenant_id: str, author_id: str, title: str, content: str, is_private: bool = True) -> dict:
        if not tenant_id or not author_id:
            raise ValueError("tenant_id and author_id are required")

        note_id = str(self._next_id)
        self._next_id += 1

        note = {
            "id": note_id,
            "tenant_id": tenant_id,
            "author_id": author_id,
            "title": title,
            "content": content,
            "is_private": is_private,
        }
        self._notes[note_id] = note
        return dict(note)

    def get_note(self, requesting_tenant_id: str, requesting_user_id: str, note_id: str) -> Optional[dict]:
        note = self._notes.get(note_id)
        if not note:
            return None

        # Zero-trust multi-tenant isolation check:
        # Cross-tenant access is strictly prohibited
        if note["tenant_id"] != requesting_tenant_id:
            raise AuthorizationError(f"Cross-tenant access denied: tenant {requesting_tenant_id} cannot access tenant {note['tenant_id']} resources")

        # Privacy check within tenant
        if note["is_private"] and note["author_id"] != requesting_user_id:
            raise AuthorizationError(f"Private note access denied for user {requesting_user_id}")

        return dict(note)

    def list_notes(self, requesting_tenant_id: str, requesting_user_id: str) -> List[dict]:
        # Filter strictly by tenant_id
        results = []
        for note in self._notes.values():
            if note["tenant_id"] == requesting_tenant_id:
                if not note["is_private"] or note["author_id"] == requesting_user_id:
                    results.append(dict(note))
        return results
