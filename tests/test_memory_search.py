"""Unit tests for sadskill BM25 Memory Search and Compaction (scripts/sad_memory.py).
"""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sad_memory


class MemorySearchTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="sad_test_mem_"))
        self.sad_dir = self.test_dir / ".sad"
        self.sad_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_bm25_search_ranking(self):
        # Insert 3 ADR events with distinct topics
        sad_memory.append_event(
            self.test_dir,
            "adr",
            {
                "title": "Database Connection Pooling",
                "context": "High concurrency spikes exhaust PostgreSQL connections.",
                "decision": "Implement PgBouncer with transaction-level pooling.",
                "consequences": "Max 50 active DB connections maintained.",
            },
            task_id="DB-01",
        )

        sad_memory.append_event(
            self.test_dir,
            "adr",
            {
                "title": "Frontend State Management",
                "context": "Complex prop drilling across dashboard widgets.",
                "decision": "Adopt Zustand with persist middleware.",
                "consequences": "Single store slice per domain entity.",
            },
            task_id="UI-01",
        )

        sad_memory.append_event(
            self.test_dir,
            "milestone",
            {
                "title": "Auth Service Hardening",
                "summary": "Added advisory file locking to prevent race conditions during refresh token rotation.",
            },
            task_id="AUTH-01",
        )

        # Query 1: Search for database pooling
        results_db = sad_memory.search_memory(self.test_dir, "postgres connection pooling", top_k=2)
        self.assertTrue(len(results_db) >= 1)
        self.assertEqual(results_db[0]["task_id"], "DB-01")
        self.assertIn("Database Connection Pooling", results_db[0]["title"])

        # Query 2: Search for zustand state management
        results_ui = sad_memory.search_memory(self.test_dir, "zustand store middleware", top_k=2)
        self.assertTrue(len(results_ui) >= 1)
        self.assertEqual(results_ui[0]["task_id"], "UI-01")

        # Query 3: Search for token rotation advisory locking
        results_auth = sad_memory.search_memory(self.test_dir, "advisory locking refresh token", top_k=2)
        self.assertTrue(len(results_auth) >= 1)
        self.assertEqual(results_auth[0]["task_id"], "AUTH-01")

        # Formatter test
        ctx = sad_memory.format_memory_context(results_auth)
        self.assertIn("Relevant Project Memory", ctx)
        self.assertIn("Auth Service Hardening", ctx)

    def test_memory_compaction(self):
        # Generate 15 events
        for i in range(15):
            sad_memory.append_event(
                self.test_dir,
                "checkpoint",
                {"title": f"Checkpoint {i}", "summary": f"Progress update step {i}"},
                task_id=f"TASK-{i}",
            )

        events_before = len(list((self.sad_dir / "events").glob("*.json")))
        self.assertEqual(events_before, 15)

        # Compact keeping latest 5
        archived_count = sad_memory.compact_memory(self.test_dir, keep_latest=5)
        self.assertEqual(archived_count, 10)

        events_after = len(list((self.sad_dir / "events").glob("*.json")))
        self.assertEqual(events_after, 5)

        # Archive file should exist and contain 10 lines
        archive_dir = self.sad_dir / "events" / "archive"
        self.assertTrue(archive_dir.exists())
        archive_files = list(archive_dir.glob("*.jsonl"))
        self.assertEqual(len(archive_files), 1)

        lines = archive_files[0].read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 10)


if __name__ == "__main__":
    unittest.main()
