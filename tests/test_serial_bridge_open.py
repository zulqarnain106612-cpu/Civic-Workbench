"""Serial bridge opens the port without toggling NodeMCU-32S auto-reset lines."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from unittest import mock

from civic_workbench.serial_bridge import SerialBridge
from civic_workbench.storage import SessionStore


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

    def readline(self):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
