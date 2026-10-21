"""Host tests validate actual firmware serial JSON records against the v1 contracts."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "firmware" / "esp32" / "main"
MOCKS = ROOT / "tests" / "firmware" / "mock_esp"
SCHEMAS = ROOT / "schemas" / "v1"


class FirmwareSerialTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary_directory = tempfile.TemporaryDirectory(prefix="civic-serial-transport-")
        executable = Path(cls._temporary_directory.name) / "serial-transport-test"
        subprocess.run(
            [
                "gcc",
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                "-pthread",
                f"-I{MOCKS}",
                f"-I{FW}",
                str(ROOT / "tests/firmware/test_serial_transport.c"),
                str(MOCKS / "mock_esp.c"),
                str(FW / "civic_transport.c"),
                str(FW / "civic_transport_format.c"),
                "-o",
                str(executable),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        completed = subprocess.run(
            [str(executable)],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        cls.lines = completed.stdout.splitlines()
        cls.records = []
        for line in cls.lines:
            if not line.startswith("CW1 "):
                raise AssertionError(f"Unframed protocol output: {line!r}")
            cls.records.append(json.loads(line[4:]))

        def load_validator(name: str) -> Draft202012Validator:
            schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
            return Draft202012Validator(schema, format_checker=FormatChecker())

        cls.validators = {
            "handshake": load_validator("handshake.schema.json"),
            "device_status": load_validator("device-status.schema.json"),
            "can_frame": load_validator("can-frame.schema.json"),
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary_directory.cleanup()

    def test_every_emitted_record_is_prefixed_and_schema_valid(self):
        self.assertEqual(len(self.records), 6)
        for record in self.records:
            self.validators[record["record_type"]].validate(record)

    def test_handshake_reports_firmware_role_and_supported_payloads(self):
        record = self.records[0]
        self.assertEqual(record["record_type"], "handshake")
        self.assertEqual(record["agent_role"], "firmware")
        self.assertIn("can_frame", record["supported_schema_versions"])
        self.assertIn("device_status", record["supported_message_types"])

    def test_disabled_and_running_status_use_monotonic_clock_and_real_bitrate(self):
        disabled, running = self.records[1:3]
        self.assertEqual(disabled["clock_source"], "monotonic_only")
        self.assertIsNone(disabled["bitrate_bps"])
        self.assertEqual(disabled["faults"], ["hardware_capture_unavailable"])

        self.assertEqual(running["controller_state"], "running")
        self.assertEqual(running["bitrate_bps"], 500000)
        self.assertTrue(running["transmit_capable"])
        self.assertTrue(running["software_armed"])
        self.assertEqual(running["dropped_frames_total"], 9)
        self.assertEqual(running["software_dropped_frames"], 2)
        self.assertEqual(running["malformed_frames"], 1)
        self.assertEqual(running["driver_rx_queue_depth"], 12)
        self.assertEqual(running["app_rx_queue_depth"], 6)
        self.assertEqual(running["tx_error_counter"], 7)
        self.assertEqual(running["rx_error_counter"], 8)
        self.assertEqual(running["arbitration_lost_count"], 5)
        self.assertEqual(running["bus_error_count"], 6)
        self.assertIn("software_rx_queue_drop", running["faults"])
        self.assertIn("twai_rx_queue_missed", running["faults"])
        self.assertIn("twai_rx_fifo_overrun", running["faults"])
        self.assertIn("twai_tx_failed", running["faults"])

    def test_recovering_status_is_not_mislabeled_as_error(self):
        recovering = self.records[3]
        self.assertEqual(recovering["controller_state"], "recovering")
        self.assertFalse(recovering["software_armed"])
        self.assertIn("twai_recovery_in_progress", recovering["faults"])
        self.assertIn("twai_error_counter_inhibit", recovering["faults"])

    def test_frame_records_preserve_recovering_controller_state(self):
        frame = self.records[4]
        self.assertEqual(frame["record_type"], "can_frame")
        self.assertEqual(frame["controller_state"], "recovering")

    def test_frame_payload_ids_timestamps_and_loss_counters_are_preserved(self):
        frame = self.records[5]
        self.assertEqual(frame["arbitration_id"], 0x123)
        self.assertEqual(frame["payload"], [0, 16, 255])
        self.assertEqual(frame["captured_monotonic_ns"], 1_234_567_000)
        self.assertEqual(frame["clock_source"], "monotonic_only")
        self.assertEqual(frame["dropped_frames_before"], 1)
        self.assertEqual(frame["dropped_frames_after"], 2)
        self.assertEqual(frame["direction"], "rx")
        self.assertEqual(frame["capture_source"], "hardware")


if __name__ == "__main__":
    unittest.main(verbosity=2)
