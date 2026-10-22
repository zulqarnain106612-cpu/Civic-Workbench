"""CW1 input handling, packaging assets and source provenance integration tests."""
from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from pathlib import Path

from civic_workbench.contracts import ContractViolation
from civic_workbench.serial_bridge import SerialBridge
from civic_workbench.storage import SessionStore
from civic_test_helpers import make_frame


ROOT = Path(__file__).resolve().parents[1]


class ProductIntegrationTests(unittest.TestCase):
    def test_read_only_serial_bridge_ingests_valid_cw1_records_without_a_tx_route(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            bridge = SerialBridge(store)
            sid = str(uuid.uuid4())
            handshake = {
                "schema_version":1,"record_type":"handshake","agent_role":"firmware",
                "agent_id":"civic-workbench-esp32","software_version":"0.3.0-dev",
                "supported_schema_versions":{"handshake":[1],"can_frame":[1],"device_status":[1]},
                "supported_message_types":["can_frame","device_status"],
            }
            status = {
                "schema_version":1,"record_type":"device_status",
                "observed_monotonic_ns":1000,"clock_source":"monotonic_only",
                "connected":True,"controller_state":"running","firmware_version":"0.3.0-dev",
                "bitrate_bps":500000,"dropped_frames_total":0,"faults":[],
            }
            bridge.consume(handshake)
            bridge.consume(status)
            frame = make_frame(sid, 0, capture_source="hardware", clock_source="monotonic_only")
            frame.pop("captured_at_utc", None)
            bridge.consume(frame)
            state = bridge.status()
            self.assertTrue(state["connected"])
            self.assertEqual(state["firmware_version"], "0.3.0-dev")
            self.assertEqual(state["frames_received"], 1)
            self.assertEqual(store.get_all_frames(sid), [frame])
            self.assertFalse(hasattr(bridge, "transmit"))
            self.assertFalse(hasattr(bridge, "write"))

    def test_invalid_serial_records_are_rejected_by_contract_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            bridge = SerialBridge(SessionStore(temp))
            with self.assertRaises(ContractViolation):
                bridge.consume({"schema_version":1,"record_type":"can_frame","payload":[999]})

    def test_package_static_assets_exist_with_documented_entrypoint(self):
        web = ROOT / "src/civic_workbench/web"
        self.assertTrue((web / "index.html").is_file())
        self.assertTrue((web / "app.js").is_file())
        self.assertTrue((web / "styles.css").is_file())
        self.assertTrue((ROOT / "pyproject.toml").is_file())
        package_config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('civic-workbench = "civic_workbench.app:main"', package_config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
