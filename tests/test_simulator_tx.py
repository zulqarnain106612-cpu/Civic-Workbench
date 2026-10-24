"""Deterministic simulator, bounded repeat/cancel and safety-audit tests."""
from __future__ import annotations

import tempfile
import unittest

from civic_workbench.contracts import ContractViolation
from civic_workbench.simulator import VirtualCanBus
from civic_workbench.storage import SessionStore
from civic_workbench.tx import TxScheduler
from civic_test_helpers import make_frame, seed_session, tx_request


class SimulatorAndTxTests(unittest.TestCase):
    def test_virtual_nodes_emit_timed_records_with_source_separation(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            bus = VirtualCanBus()
            session = bus.create_session(store, 500000, None)
            bus.add_node({"node_id":"counter","arbitration_id":0x100,"period_ms":100,"payload_mode":"counter"})
            bus.add_node({"node_id":"toggle","arbitration_id":0x200,"period_ms":250,"payload_mode":"toggle"})
            bus.start_nodes()
            result = bus.advance(store, 300)
            self.assertEqual(result["emitted_count"], 4)
            frames = store.get_all_frames(session["session_id"])
            self.assertEqual(len(frames), 4)
            self.assertTrue(all(f["capture_source"] == "simulator" for f in frames))
            self.assertEqual([f["captured_monotonic_ns"] for f in frames], sorted(f["captured_monotonic_ns"] for f in frames))
            self.assertEqual(result["summary"]["total_frames"], 4)

    def test_trace_replay_and_mutation_keep_original_records_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            source, frames = seed_session(store, count=5)
            original = store.get_all_frames(source["session_id"])
            bus = VirtualCanBus()
            bus.create_session(store, 500000, None)
            result = bus.replay(store, original, speed=2)
            self.assertEqual(result["scheduled_count"], 5)
            emitted = bus.advance(store, 100)
            self.assertEqual(emitted["emitted_count"], 5)
            current = store.get_all_frames(bus.session_id)
            self.assertEqual(len(current), 5)
            self.assertTrue(all(f["capture_source"] == "simulator" for f in current))
            self.assertTrue(all(f.get("source_record_ref") in {r["frame_id"] for r in original} for f in current))
            target = VirtualCanBus()
            target.create_session(store, 500000, None)
            mutated = target.mutate(store, original, [{"kind":"xor_byte","byte_offset":0,"value":255}])
            self.assertEqual(len(mutated), len(original))
            self.assertEqual(store.get_all_frames(source["session_id"]), original)

    def test_global_abort_cancels_every_pending_request_and_audits(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            bus = VirtualCanBus()
            session = bus.create_session(store, 500000, None)
            tx = TxScheduler(store, bus)
            first = tx_request(repeats=3, period_ms=100, timeout_ms=250)
            second = tx_request(identifier=0x322, repeats=2, period_ms=100, timeout_ms=200)
            tx.submit(first, "simulation", session["session_id"])
            tx.submit(second, "simulation", session["session_id"])
            tx.after_bus_step(bus.advance(store, 0)["frames"])        # first frame of each goes out
            statuses = {r["request"]["request_id"]: r["status"] for r in tx.list_requests()}
            self.assertEqual(set(statuses.values()), {"partial"})
            result = tx.abort_all("test_abort")
            self.assertEqual(sorted(result["aborted_request_ids"]),
                             sorted([first["request_id"], second["request_id"]]))
            self.assertFalse(result["physical_tx_performed"])
            self.assertEqual(bus.advance(store, 1000)["emitted_count"], 0)
            self.assertTrue(all(r["status"] == "cancelled" for r in tx.list_requests()))
            audit = store.list_tx_audit(100)
            self.assertEqual(sum(1 for a in audit if a["status"] == "cancelled"), 2)
            self.assertEqual(tx.abort_all()["aborted_count"], 0)      # idempotent

    def test_stopping_capture_aborts_pending_virtual_tx(self):
        from civic_workbench.service import WorkbenchService
        from civic_test_helpers import utc_text
        from uuid import uuid4
        with tempfile.TemporaryDirectory() as temp:
            service = WorkbenchService(temp)
            created = service.create_scenario({"name": "abort-on-stop", "nodes": []})
            sid = created["session"]["session_id"]
            request = tx_request(repeats=3, period_ms=100, timeout_ms=250)
            service.tx.submit(request, "simulation", sid)
            service.stop_capture({"schema_version": 1, "record_type": "capture_stop", "request_id": str(uuid4()),
                                  "requested_at_utc": utc_text(), "session_id": sid,
                                  "requested_by": "integration-test"})
            self.assertEqual(service.tx.list_requests()[0]["status"], "cancelled")
            self.assertEqual(service.store.get_session(sid)["record_count"], 0)

    def test_virtual_tx_repeats_audit_and_cancellation_do_not_reach_hardware(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            bus = VirtualCanBus()
            session = bus.create_session(store, 500000, None)
            tx = TxScheduler(store, bus)
            request = tx_request(repeats=3, period_ms=100, timeout_ms=250)
            result = tx.submit(request, "simulation", session["session_id"])
            self.assertEqual(result["status"], "queued")
            self.assertFalse(tx.hardware_tx_enabled)
            self.assertFalse(tx.safety_snapshot()["tx_permitted"])
            cancelled = tx.cancel(request["request_id"])
            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(cancelled["audit"]["event"]["physical_tx_performed"], False)
            step = bus.advance(store, 500)
            tx.after_bus_step(step["frames"])
            self.assertEqual(step["emitted_count"], 0)
            self.assertTrue(any(a["status"] == "cancelled" for a in store.list_tx_audit()))

    def test_hardware_target_is_rejected_and_audited(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            bus = VirtualCanBus()
            session = bus.create_session(store, 500000, None)
            tx = TxScheduler(store, bus)
            with self.assertRaises(ContractViolation):
                tx.submit(tx_request(), "hardware", session["session_id"])
            audits = store.list_tx_audit()
            self.assertEqual(audits[-1]["status"], "rejected")
            self.assertFalse(audits[-1]["event"].get("physical_tx_performed", True))

    def test_simulation_step_and_replay_have_explicit_resource_caps(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            bus = VirtualCanBus()
            bus.create_session(store, 500000, None)
            bus.add_node({"node_id":"fast","arbitration_id":0x100,"period_ms":1,"payload_mode":"counter"})
            bus.start_nodes()
            with self.assertRaises(ContractViolation):
                bus.advance(store, 3600000)
            with self.assertRaises(ContractViolation):
                bus.replay(store, [make_frame(bus.session_id, i) for i in range(100001)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
