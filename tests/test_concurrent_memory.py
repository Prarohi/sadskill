"""Tests for concurrency-safe project memory (.sad/) and immutable event logs."""

import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest

from scripts.sad_memory import append_event, compact_memory, list_events, search_memory


class ConcurrentMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".sad").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_event_recording(self):
        out = append_event(
            self.root,
            event_type="milestone",
            payload={"title": "Setup Complete", "summary": "Initial project setup."},
            actor="agent-alpha",
            task_id="setup-01",
        )
        self.assertTrue(out.exists())
        events = list_events(self.root)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["actor"], "agent-alpha")
        self.assertEqual(events[0]["type"], "milestone")

        history_file = self.root / ".sad" / "history.md"
        self.assertTrue(history_file.exists())
        history_text = history_file.read_text(encoding="utf-8")
        self.assertIn("Setup Complete", history_text)
        self.assertIn("agent-alpha", history_text)

    def test_concurrent_multi_agent_writes_no_loss(self):
        total_writers = 20

        def write_worker(idx):
            append_event(
                self.root,
                event_type="milestone",
                payload={"title": f"Milestone from agent {idx}", "summary": f"Worker {idx} done."},
                actor=f"agent-{idx:02d}",
                task_id=f"concurrent-{idx}",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(write_worker, i) for i in range(total_writers)]
            concurrent.futures.wait(futures)

        events = list_events(self.root)
        self.assertEqual(len(events), total_writers, f"Expected {total_writers} events, found {len(events)}")

        history_file = self.root / ".sad" / "history.md"
        self.assertTrue(history_file.exists())
        history_content = history_file.read_text(encoding="utf-8")
        for i in range(total_writers):
            self.assertIn(f"Milestone from agent {i}", history_content)

    def test_memory_redacts_common_secret_fields_and_patterns(self):
        payload = {
            "title": "Credential hygiene",
            "summary": "Authorization: Bearer synthetic-bearer-secret-123",
            "api_key": "synthetic-field-api-key",
            "token": "synthetic-field-token",
            "private_key": "-----BEGIN PRIVATE KEY-----\nsynthetic-private-key\n-----END PRIVATE KEY-----",
            "url": "https://service:synthetic-url-password@example.invalid/resource",
            "nested": [{"clientSecret": "synthetic-client-secret"}],
        }
        original = dict(payload)
        append_event(self.root, "milestone", payload)

        stored = list_events(self.root)[0]["payload"]
        serialized = json.dumps(stored, sort_keys=True)
        history = (self.root / ".sad" / "history.md").read_text(encoding="utf-8")
        for secret in (
            "synthetic-bearer-secret-123", "synthetic-field-api-key", "synthetic-field-token",
            "synthetic-private-key", "synthetic-url-password", "synthetic-client-secret",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)
                self.assertNotIn(secret, history)
        self.assertIn("[REDACTED_SECRET]", serialized)
        self.assertEqual(payload, original)

    def test_design_token_labels_are_not_treated_as_credentials(self):
        append_event(
            self.root,
            "design_token",
            {
                "token": "color.primary",
                "value": "#6EA291",
                "note": "approved accent",
                "fallback": {"token": "synthetic-private-token-value"},
            },
        )
        stored = list_events(self.root)[0]["payload"]
        self.assertEqual(stored["token"], "color.primary")
        self.assertEqual(stored["fallback"]["token"], "[REDACTED_SECRET]")
        self.assertIn("color.primary", (self.root / ".sad" / "design-memory.md").read_text())

    def test_compaction_keeps_archived_events_listable_and_searchable(self):
        for index in range(3):
            append_event(
                self.root,
                "custom",
                {"title": f"archived milestone {index}", "summary": f"retained memory needle {index}"},
            )
        expected_ids = {event["event_id"] for event in list_events(self.root)}

        self.assertEqual(compact_memory(self.root, keep_latest=1), 2)
        after_compaction = list_events(self.root)
        self.assertEqual({event["event_id"] for event in after_compaction}, expected_ids)
        matches = search_memory(self.root, "retained memory needle", top_k=10)
        self.assertEqual({match["raw"]["event_id"] for match in matches}, expected_ids)

        archive_file = next((self.root / ".sad" / "events" / "archive").glob("events-*.jsonl"))
        self.assertEqual(len(archive_file.read_text(encoding="utf-8").splitlines()), 2)
        self.assertEqual(compact_memory(self.root, keep_latest=1), 0)
        self.assertEqual(len(archive_file.read_text(encoding="utf-8").splitlines()), 2)

    def test_compaction_retry_removes_already_archived_source_without_duplication(self):
        for index in range(3):
            append_event(self.root, "custom", {"title": f"retry event {index}"})
        compact_memory(self.root, keep_latest=1)
        archive_file = next((self.root / ".sad" / "events" / "archive").glob("events-*.jsonl"))
        archived = json.loads(archive_file.read_text(encoding="utf-8").splitlines()[0])
        duplicate_source = self.root / ".sad" / "events" / f"00000000-000000-{archived['event_id'][:8]}.json"
        duplicate_source.write_text(json.dumps(archived), encoding="utf-8")

        self.assertEqual(compact_memory(self.root, keep_latest=1), 0)
        self.assertFalse(duplicate_source.exists())
        self.assertEqual(len(archive_file.read_text(encoding="utf-8").splitlines()), 2)
        self.assertEqual(len(list_events(self.root)), 3)

    def test_compaction_can_archive_everything_and_rejects_negative_retention(self):
        for index in range(2):
            append_event(self.root, "custom", {"title": f"archive all {index}"})
        with self.assertRaises(ValueError):
            compact_memory(self.root, keep_latest=-1)

        self.assertEqual(compact_memory(self.root, keep_latest=0), 2)
        self.assertEqual(len(list_events(self.root)), 2)
        self.assertEqual(list((self.root / ".sad" / "events").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
