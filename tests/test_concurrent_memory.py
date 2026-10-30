"""Tests for concurrency-safe project memory (.sad/) and immutable event logs."""

import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import sad_memory
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

    def test_list_events_does_not_create_a_lock_file_for_read_only_access(self):
        events_directory = self.root / ".sad" / "events"
        events_directory.mkdir()

        self.assertEqual(list_events(self.root), [])
        self.assertFalse((self.root / ".sad" / ".lock").exists())

    def test_interrupted_event_write_never_leaves_a_partial_json_record(self):
        events_dir = self.root / ".sad" / "events"

        def interrupt_after_partial_write(fd, content):
            os.write(fd, bytes(content[:8]))
            raise OSError("simulated interruption during event write")

        with mock.patch.object(sad_memory, "_write_all", side_effect=interrupt_after_partial_write):
            with self.assertRaisesRegex(OSError, "simulated interruption"):
                append_event(self.root, "custom", {"title": "must be atomic"})

        self.assertEqual(list(events_dir.iterdir()), [])
        self.assertEqual(list_events(self.root), [])

    def test_event_publish_does_not_overwrite_a_concurrent_destination(self):
        events_directory = self.root / ".sad" / "events"
        events_directory.mkdir()
        original_link = sad_memory._link_no_replace_at

        def create_competing_event(parent_fd, source, destination):
            fd = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=parent_fd,
            )
            try:
                os.write(fd, b"user-owned event")
            finally:
                os.close(fd)

            return original_link(parent_fd, source, destination)

        events_fd = os.open(events_directory, sad_memory._directory_flags())
        try:
            with mock.patch.object(sad_memory, "_link_no_replace_at", side_effect=create_competing_event):
                with self.assertRaises(FileExistsError):
                    sad_memory._write_file_atomically_at(
                        events_fd,
                        "collision.json",
                        b"new event contents",
                        replace=False,
                    )
        finally:
            os.close(events_fd)

        self.assertEqual(
            (events_directory / "collision.json").read_bytes(),
            b"user-owned event",
        )
        self.assertEqual(
            [path.name for path in events_directory.iterdir()],
            ["collision.json"],
        )

    def test_event_publish_recovers_if_process_stops_after_link_creation(self):
        events_directory = self.root / ".sad" / "events"
        events_directory.mkdir()
        event_id = "123e4567-e89b-12d3-a456-426614174000"
        event_name = f"20261030-120000-{event_id}.json"
        payload = json.dumps({
            "event_id": event_id,
            "timestamp": "2026-10-30T12:00:00Z",
            "type": "custom",
            "payload": {"title": "recover after crash"},
        }).encode("utf-8") + b"\n"
        repo_root = Path(__file__).resolve().parents[1]
        program = (
            "import os, sys; from pathlib import Path; from scripts import sad_memory; "
            "root=Path(sys.argv[1]); sad_fd=os.open(root/'.sad', sad_memory._directory_flags()); "
            "events_fd=os.open(root/'.sad'/'events', sad_memory._directory_flags()); "
            "lock=sad_memory.MemoryLock(sad_fd); lock.__enter__(); "
            "sad_memory._fsync_directory_fd=lambda fd: os._exit(73); "
            f"sad_memory._publish_event_atomically(events_fd, {event_name!r}, {payload!r})"
        )

        result = subprocess.run(
            [sys.executable, "-c", program, str(self.root)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=3,
        )

        self.assertEqual(result.returncode, 73, result.stderr)
        event_path = events_directory / event_name
        self.assertEqual(event_path.stat().st_nlink, 2)
        events = list_events(self.root)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "recover after crash")
        self.assertEqual(event_path.stat().st_nlink, 2)
        self.assertEqual(compact_memory(self.root, keep_latest=10), 0)
        self.assertEqual(event_path.stat().st_nlink, 1)
        self.assertEqual([path.name for path in events_directory.iterdir()], [event_name])

    def test_first_write_syncs_new_memory_directory_entries(self):
        (self.root / ".sad").rmdir()
        original_sync = sad_memory._fsync_directory_fd
        synced_directories = set()

        def record_sync(fd):
            metadata = os.fstat(fd)
            synced_directories.add((metadata.st_dev, metadata.st_ino))
            original_sync(fd)

        with mock.patch.object(sad_memory, "_fsync_directory_fd", side_effect=record_sync):
            append_event(self.root, "custom", {"title": "directory durability"})

        expected_directories = {
            (path.stat().st_dev, path.stat().st_ino)
            for path in (self.root, self.root / ".sad", self.root / ".sad" / "events")
        }
        self.assertLessEqual(expected_directories, synced_directories)

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
            "summary": (
                "Authorization: Bearer synthetic-bearer-secret-123; "
                "AWS_SECRET_ACCESS_KEY=synthetic-aws-secret-key-1234"
            ),
            "api_key": "synthetic-field-api-key",
            "token": "synthetic-field-token",
            "aws_secret_access_key": "synthetic-aws-field-secret-5678",
            "secret_access_key": "synthetic-field-secret-access-9012",
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
            "synthetic-aws-secret-key-1234", "synthetic-aws-field-secret-5678",
            "synthetic-field-secret-access-9012",
            "synthetic-private-key", "synthetic-url-password", "synthetic-client-secret",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)
                self.assertNotIn(secret, history)
        self.assertIn("[REDACTED_SECRET]", serialized)
        self.assertEqual(payload, original)

    def test_lock_symlink_is_refused_without_truncating_its_target(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            protected = Path(outside_tmp) / "important.txt"
            protected.write_text("keep this user file", encoding="utf-8")
            (self.root / ".sad" / ".lock").symlink_to(protected)

            with self.assertRaises(OSError):
                append_event(self.root, "custom", {"title": "must not write"})

            self.assertEqual(protected.read_text(encoding="utf-8"), "keep this user file")
            self.assertEqual(list((self.root / ".sad").glob("events/*.json")), [])

    def test_lock_hardlink_is_refused_without_changing_its_target(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            protected = Path(outside_tmp) / "important.txt"
            protected.write_text("keep this user file", encoding="utf-8")
            os.link(protected, self.root / ".sad" / ".lock")

            with self.assertRaises(OSError):
                append_event(self.root, "custom", {"title": "must not write"})

            self.assertEqual(protected.read_text(encoding="utf-8"), "keep this user file")
            self.assertEqual(list((self.root / ".sad").glob("events/*.json")), [])

    def test_memory_write_refuses_when_process_locking_is_unavailable(self):
        with mock.patch.object(sad_memory, "fcntl", None):
            with self.assertRaisesRegex(OSError, "safe project-memory locking"):
                append_event(self.root, "custom", {"title": "must not write"})

        self.assertEqual(list((self.root / ".sad").glob("events/*.json")), [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO tests require POSIX mkfifo")
    def test_fifo_derived_memory_file_is_rejected_without_blocking(self):
        os.mkfifo(self.root / ".sad" / "history.md")
        repo_root = Path(__file__).resolve().parents[1]
        program = (
            "import sys; from pathlib import Path; "
            "from scripts.sad_memory import append_event; "
            "append_event(Path(sys.argv[1]), 'milestone', {'title':'fifo'})"
        )

        result = subprocess.run(
            [sys.executable, "-c", program, str(self.root)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=3,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("OSError", result.stderr)
        self.assertEqual(list((self.root / ".sad").glob("events/*.json")), [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO tests require POSIX mkfifo")
    def test_fifo_append_target_is_rejected_without_blocking(self):
        history = self.root / ".sad" / "history.md"
        os.mkfifo(history)
        repo_root = Path(__file__).resolve().parents[1]
        program = (
            "import os, sys; from pathlib import Path; "
            "from scripts.sad_memory import _append_text_at, _directory_flags; "
            "fd=os.open(Path(sys.argv[1]) / '.sad', _directory_flags()); "
            "_append_text_at(fd, 'history.md', 'x'); os.close(fd)"
        )

        result = subprocess.run(
            [sys.executable, "-c", program, str(self.root)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=3,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("OSError", result.stderr)
        self.assertTrue(history.exists())

    def test_sad_directory_symlink_is_refused_without_writing_outside(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp)
            (self.root / ".sad").rmdir()
            (self.root / ".sad").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(OSError):
                append_event(self.root, "custom", {"title": "must not write"})

            self.assertEqual(list(outside.iterdir()), [])

    def test_derived_memory_symlink_is_refused_before_event_write(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            protected = Path(outside_tmp) / "history.md"
            protected.write_text("preserve user history", encoding="utf-8")
            (self.root / ".sad" / "history.md").symlink_to(protected)

            with self.assertRaises(OSError):
                append_event(self.root, "milestone", {"title": "must not append"})

            self.assertEqual(protected.read_text(encoding="utf-8"), "preserve user history")
            self.assertEqual(list((self.root / ".sad").glob("events/*.json")), [])

    def test_events_directory_symlink_is_refused_for_writes_and_reads(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp)
            sentinel = outside / "sentinel.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            (self.root / ".sad" / "events").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(OSError):
                append_event(self.root, "custom", {"title": "must not write"})
            with self.assertRaises(OSError):
                list_events(self.root)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
            self.assertEqual(list(outside.iterdir()), [sentinel])

    def test_symlinked_event_file_is_never_read_or_returned(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp) / "private.json"
            outside.write_text(
                json.dumps({
                    "event_id": "outside-secret",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "type": "custom",
                    "task_id": "private",
                    "payload": {"title": "outside-secret-sentinel"},
                }),
                encoding="utf-8",
            )
            events_dir = self.root / ".sad" / "events"
            events_dir.mkdir()
            (events_dir / "20260101-000000-deadbeef.json").symlink_to(outside)

            self.assertEqual(list_events(self.root), [])
            self.assertEqual(search_memory(self.root, "outside-secret-sentinel"), [])
            self.assertIn("outside-secret-sentinel", outside.read_text(encoding="utf-8"))

    def test_hardlinked_event_file_is_never_read_or_returned(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp) / "private.json"
            outside.write_text(
                json.dumps({
                    "event_id": "outside-secret",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "type": "custom",
                    "task_id": "private",
                    "payload": {"title": "outside-secret-sentinel"},
                }),
                encoding="utf-8",
            )
            events_dir = self.root / ".sad" / "events"
            events_dir.mkdir()
            os.link(outside, events_dir / "20260101-000000-deadbeef.json")

            self.assertEqual(list_events(self.root), [])
            self.assertEqual(search_memory(self.root, "outside-secret-sentinel"), [])
            self.assertIn("outside-secret-sentinel", outside.read_text(encoding="utf-8"))

    def test_symlinked_archive_file_is_never_read_or_returned(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp) / "private.jsonl"
            outside.write_text(
                json.dumps({"event_id": "private", "payload": {"title": "private-sentinel"}}) + "\n",
                encoding="utf-8",
            )
            archive_dir = self.root / ".sad" / "events" / "archive"
            archive_dir.mkdir(parents=True)
            (archive_dir / "events-2026-01.jsonl").symlink_to(outside)

            self.assertEqual(list_events(self.root), [])
            self.assertEqual(search_memory(self.root, "private-sentinel"), [])

    def test_symlinked_decision_document_is_not_loaded_into_search(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp) / "private.md"
            outside.write_text(
                "## ADR: outside-secret-sentinel\n- Decision: private local data\n",
                encoding="utf-8",
            )
            (self.root / ".sad" / "decisions.md").symlink_to(outside)

            with self.assertRaises(OSError):
                search_memory(self.root, "outside-secret-sentinel")
            self.assertIn("outside-secret-sentinel", outside.read_text(encoding="utf-8"))

    def test_compaction_refuses_symlinked_archive_without_touching_target(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            protected = Path(outside_tmp) / "archive.jsonl"
            protected.write_text("user archive", encoding="utf-8")
            events_dir = self.root / ".sad" / "events"
            events_dir.mkdir()
            (events_dir / "archive").symlink_to(Path(outside_tmp), target_is_directory=True)
            append_event(self.root, "custom", {"title": "needs archive"})

            with self.assertRaises(OSError):
                compact_memory(self.root, keep_latest=0)

            self.assertEqual(protected.read_text(encoding="utf-8"), "user archive")
            self.assertTrue(next(events_dir.glob("*.json")).exists())

    def test_compaction_refuses_corrupt_archive_tail_and_preserves_source_events(self):
        append_event(self.root, "custom", {"title": "preserve event one"})
        append_event(self.root, "custom", {"title": "preserve event two"})
        archive_dir = self.root / ".sad" / "events" / "archive"
        archive_dir.mkdir()
        month_slug = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
        archive_file = archive_dir / f"events-{month_slug}.jsonl"
        archive_file.write_text('{"event_id":"interrupted-tail"', encoding="utf-8")

        with self.assertRaisesRegex(OSError, "malformed JSON"):
            compact_memory(self.root, keep_latest=0)

        self.assertEqual(archive_file.read_text(encoding="utf-8"), '{"event_id":"interrupted-tail"')
        self.assertEqual(len(list((self.root / ".sad" / "events").glob("*.json"))), 2)
        self.assertEqual({event["payload"]["title"] for event in list_events(self.root)}, {
            "preserve event one", "preserve event two",
        })

    def test_compaction_refuses_corrupt_older_archive_and_preserves_source_events(self):
        append_event(self.root, "custom", {"title": "preserve event one"})
        append_event(self.root, "custom", {"title": "preserve event two"})
        archive_dir = self.root / ".sad" / "events" / "archive"
        archive_dir.mkdir()
        old_archive = archive_dir / "events-2025-12.jsonl"
        old_archive.write_text('{"event_id":"broken"', encoding="utf-8")

        with self.assertRaisesRegex(OSError, "events-2025-12.jsonl has malformed JSON"):
            compact_memory(self.root, keep_latest=0)

        self.assertEqual(old_archive.read_text(encoding="utf-8"), '{"event_id":"broken"')
        self.assertEqual(len(list((self.root / ".sad" / "events").glob("*.json"))), 2)
        self.assertEqual({event["payload"]["title"] for event in list_events(self.root)}, {
            "preserve event one", "preserve event two",
        })

    def test_compaction_separates_valid_archive_record_without_final_newline(self):
        append_event(self.root, "custom", {"title": "new source event"})
        archive_dir = self.root / ".sad" / "events" / "archive"
        archive_dir.mkdir()
        month_slug = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
        archive_file = archive_dir / f"events-{month_slug}.jsonl"
        previous = {
            "event_id": "already-archived",
            "timestamp": "2026-01-01T00:00:00Z",
            "type": "custom",
            "task_id": "prior",
            "payload": {"title": "prior archived event"},
        }
        archive_file.write_text(json.dumps(previous), encoding="utf-8")

        self.assertEqual(compact_memory(self.root, keep_latest=0), 1)

        archive_lines = archive_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(archive_lines), 2)
        self.assertTrue(archive_file.read_text(encoding="utf-8").endswith("\n"))
        events = list_events(self.root)
        self.assertEqual({event["payload"]["title"] for event in events}, {
            "prior archived event", "new source event",
        })

    def test_interrupted_archive_rewrite_preserves_archive_and_source_events(self):
        append_event(self.root, "custom", {"title": "source event one"})
        append_event(self.root, "custom", {"title": "source event two"})
        archive_dir = self.root / ".sad" / "events" / "archive"
        archive_dir.mkdir()
        month_slug = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
        archive_file = archive_dir / f"events-{month_slug}.jsonl"
        previous = {
            "event_id": "already-archived",
            "timestamp": "2026-01-01T00:00:00Z",
            "type": "custom",
            "task_id": "prior",
            "payload": {"title": "preserve prior archive"},
        }
        original_archive = json.dumps(previous, separators=(",", ":")) + "\n"
        archive_file.write_text(original_archive, encoding="utf-8")

        def interrupt_after_partial_write(fd, content):
            os.write(fd, bytes(content[:8]))
            raise OSError("simulated interruption during archive rewrite")

        with mock.patch.object(sad_memory, "_write_all", side_effect=interrupt_after_partial_write):
            with self.assertRaisesRegex(OSError, "simulated interruption"):
                compact_memory(self.root, keep_latest=0)

        self.assertEqual(archive_file.read_text(encoding="utf-8"), original_archive)
        self.assertEqual(len(list((self.root / ".sad" / "events").glob("*.json"))), 2)
        self.assertEqual({event["payload"]["title"] for event in list_events(self.root)}, {
            "preserve prior archive", "source event one", "source event two",
        })

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
