"""Tests for concurrency-safe project memory (.sad/) and immutable event logs."""

import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest

from scripts.sad_memory import append_event, list_events


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


if __name__ == "__main__":
    unittest.main()
