"""Serial bridge opens the port without toggling NodeMCU-32S auto-reset lines."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from unittest import mock

from civic_workbench.contracts import ContractViolation
from civic_workbench.serial_bridge import SerialBridge
from civic_workbench.storage import SessionStore
from civic_test_helpers import make_frame


class FakeSerial:
    instances: list["FakeSerial"] = []

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        self.port = None
        self.baudrate = None
        self.timeout = None
        self.write_timeout = None
        self.dtr = True
        self.rts = True
        self.is_open = False
        self.state_at_open = None
        FakeSerial.instances.append(self)

    def open(self):
        self.state_at_open = {"dtr": self.dtr, "rts": self.rts, "port": self.port, "baudrate": self.baudrate}
        self.is_open = True

    def readline(self, size=-1):
        return b""

    def write(self, data):  # pragma: no cover - the bridge must never call this
        raise AssertionError("serial bridge wrote to the firmware")

    def close(self):
        self.is_open = False


class SerialBridgeOpenTests(unittest.TestCase):
    def test_dtr_and_rts_are_deasserted_before_open(self):
        FakeSerial.instances.clear()
        fake_module = types.SimpleNamespace(Serial=FakeSerial)
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(sys.modules, {"serial": fake_module}):
            bridge = SerialBridge(SessionStore(temp))
            bridge.start("/dev/ttyUSB0", 115200)
            try:
                self.assertEqual(len(FakeSerial.instances), 1)
                port = FakeSerial.instances[0]
                self.assertEqual(port.args, ())
                self.assertNotIn("port", port.kwargs)  # constructing with a port would open immediately
                self.assertEqual(port.state_at_open,
                                 {"dtr": False, "rts": False, "port": "/dev/ttyUSB0", "baudrate": 115200})
            finally:
                bridge.stop()


class SerialBridgeProvenanceTests(unittest.TestCase):
    def test_serial_frames_must_be_hardware_rx(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            bridge = SerialBridge(store)
            sid = "00000000-0000-4000-8000-000000000001"
            with self.assertRaises(ContractViolation):
                bridge.consume(make_frame(sid, 0, capture_source="simulator"))
            self.assertFalse(store.session_exists(sid))

    def test_serial_frame_cannot_join_a_simulator_session(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            sim = store.create_session(capture_source="simulator", bitrate_bps=500000)
            bridge = SerialBridge(store)
            with self.assertRaises(ContractViolation):
                bridge.consume(make_frame(sim["session_id"], 0, capture_source="hardware",
                                          clock_source="monotonic_only"))
            self.assertEqual(store.get_session(sim["session_id"])["record_count"], 0)

    def test_valid_record_restores_connected_after_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            bridge = SerialBridge(SessionStore(temp))
            bridge._status["connected"] = False
            bridge._status["faults"] = ["serial_stream_stale"]
            bridge.consume(make_frame("00000000-0000-4000-8000-000000000002", 0, capture_source="hardware",
                                      clock_source="monotonic_only"))
            status = bridge.status()
            self.assertTrue(status["connected"])
            self.assertNotIn("serial_stream_stale", status["faults"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
