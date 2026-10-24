"""SQLite durability, immutable raw records and safe bundle round-trip tests."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from civic_workbench.contracts import ContractViolation
from civic_workbench.storage import Conflict, NotFound, SessionStore
from civic_test_helpers import make_frame, seed_session


class SessionStorageTests(unittest.TestCase):
    def test_batch_append_order_pagination_finalization_and_checksum(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            manifest = store.create_session(capture_source="simulator", bitrate_bps=500000, mode="simulated")
            frames = [make_frame(manifest["session_id"], i) for i in range(23)]
            self.assertEqual(store.add_frames(frames), list(range(23)))
            self.assertEqual(store.list_frames(manifest["session_id"], limit=7)["items"][0]["sequence"], 0)
            page1 = store.list_frames(manifest["session_id"], limit=7)
            page2 = store.list_frames(manifest["session_id"], limit=7, after_sequence=page1["next_sequence"])
            self.assertEqual([item["sequence"] for item in page2["items"]], list(range(7, 14)))
            raw_before = json.dumps(store.get_all_frames(manifest["session_id"]), sort_keys=True)
            finished = store.finish_session(manifest["session_id"])
            raw_path = Path(temp) / finished["raw_capture"]["relative_path"]
            raw_bytes = raw_path.read_bytes()
            self.assertEqual(hashlib.sha256(raw_bytes).hexdigest(), finished["raw_capture"]["sha256"])
            self.assertEqual(len(raw_bytes), finished["raw_capture"]["bytes"])
            self.assertEqual(len(raw_bytes.splitlines()), 23)
            with self.assertRaises(Conflict):
                store.add_frame(frames[0])
            reopened = SessionStore(temp)
            self.assertEqual(json.dumps(reopened.get_all_frames(manifest["session_id"]), sort_keys=True), raw_before)

    def test_bundle_round_trip_preserves_raw_frame_fields_and_imports_transactionally(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as destination_dir:
            source = SessionStore(source_dir)
            manifest, frames = seed_session(source, count=12)
            source.finish_session(manifest["session_id"])
            bundle = source.export_bundle(manifest["session_id"])
            destination = SessionStore(destination_dir)
            imported = destination.import_bundle(bundle)
            self.assertEqual(imported["capture_source"], "import")
            self.assertEqual(imported["record_count"], len(frames))
            actual = destination.get_all_frames(manifest["session_id"])
            self.assertEqual(actual, frames)
            self.assertEqual(imported["raw_capture"]["sha256"], destination.get_session(manifest["session_id"])["raw_capture"]["sha256"])
            with self.assertRaises(Conflict):
                destination.import_bundle(bundle)

    def test_invalid_bundle_does_not_create_partial_session(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as destination_dir:
            source = SessionStore(source_dir)
            manifest, frames = seed_session(source, count=3)
            bundle = source.export_bundle(manifest["session_id"])
            broken = json.loads(json.dumps(bundle))
            broken["frames"][1]["arbitration_id"] = 0x800
            target = SessionStore(destination_dir)
            with self.assertRaises(ContractViolation):
                target.import_bundle(broken)
            with self.assertRaises(NotFound):
                target.get_session(manifest["session_id"])
            self.assertEqual(target.list_sessions()["items"], [])

    def test_unique_mapping_versions_and_explicit_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            manifest, frames = seed_session(store, count=4)
            definition = {
                "name": "test-byte",
                "start_bit": 0,
                "bit_length": 8,
                "byte_order": "little_endian",
                "signed": False,
                "scale": 1,
                "offset": 0,
                "unit": None,
            }
            first = store.save_parameter_mapping(manifest["session_id"], definition, [frames[0]["frame_id"]], "explicit byte decoder")
            second = store.save_parameter_mapping(manifest["session_id"], definition, [frames[1]["frame_id"]], "explicit byte decoder")
            self.assertEqual((first["version"], second["version"]), (1, 2))
            self.assertEqual(first["status"], "candidate")
            with self.assertRaises(ContractViolation):
                store.validate_parameter_mapping(first["mapping_id"], "", [], None)
            validated = store.validate_parameter_mapping(
                first["mapping_id"], "independent bench comparison",
                ["lab-record-17", "independent-reference-2"], "reviewer",
            )
            self.assertEqual(validated["status"], "validated")
            self.assertEqual(len(store.list_parameter_mappings(manifest["session_id"])), 2)
            self.assertEqual(store.list_parameter_mappings(manifest["session_id"])[0]["status"], "validated")

    def test_findings_must_reference_frames_in_the_same_session(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            manifest, frames = seed_session(store, count=2)
            foreign = str(__import__("uuid").uuid4())
            finding = {
                "schema_version": 1,
                "record_type": "analysis_finding",
                "finding_id": str(__import__("uuid").uuid4()),
                "created_at_utc": "2026-01-01T00:00:00Z",
                "finding_kind": "payload_change",
                "status": "observed",
                "summary": "Test evidence linking",
                "evidence_frame_ids": [foreign],
                "method": "synthetic test",
                "confidence": 0.5,
                "arbitration_id": 0x123,
                "id_format": "standard",
            }
            with self.assertRaises(ContractViolation):
                store.save_finding(manifest["session_id"], finding)


class StorageSchemaVersionTests(unittest.TestCase):
    def test_new_store_is_stamped_and_reopens(self):
        import sqlite3
        from civic_workbench.storage import STORAGE_SCHEMA_VERSION
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            sid = store.create_session(capture_source="simulator", bitrate_bps=500000)["session_id"]
            with sqlite3.connect(store.db_path) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], STORAGE_SCHEMA_VERSION)
            self.assertTrue(SessionStore(temp).session_exists(sid))

    def test_newer_storage_schema_is_refused(self):
        import sqlite3
        from civic_workbench.storage import StorageError
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            with sqlite3.connect(store.db_path) as db:
                db.execute("PRAGMA user_version=99")
            with self.assertRaises(StorageError):
                SessionStore(temp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
