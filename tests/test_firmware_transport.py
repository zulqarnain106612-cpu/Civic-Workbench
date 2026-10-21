"""Host-compiled firmware transport contract tests."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "firmware" / "esp32"
FRAME_SCHEMA = json.loads((ROOT / "schemas/v1/can-frame.schema.json").read_text())
STATUS_SCHEMA = json.loads((ROOT / "schemas/v1/device-status.schema.json").read_text())


class FirmwareTransportFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary_directory = tempfile.TemporaryDirectory(prefix="civic-transport-test-")
        executable = Path(cls._temporary_directory.name) / "transport-harness"
        subprocess.run(
            [
                "gcc",
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                f"-I{FW / 'main'}",
                str(ROOT / "tests/firmware/test_transport_format.c"),
                str(FW / "main/civic_transport_format.c"),
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
        )
        cls.lines = completed.stdout.splitlines()
        cls.validator = Draft202012Validator(
            FRAME_SCHEMA, format_checker=FormatChecker()
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary_directory.cleanup()

    def test_standard_extended_and_remote_records_validate_against_schema(self):
        self.assertEqual(len(self.lines), 5)
        records = [json.loads(line) for line in self.lines[:4]]
        for record in records:
            self.validator.validate(record)

        standard, extended, remote, recovering = records
        self.assertEqual(standard["arbitration_id"], 0x123)
        self.assertEqual(standard["payload"], [0, 16, 255])
        self.assertEqual(extended["id_format"], "extended")
        self.assertEqual(extended["arbitration_id"], 0x1ABCDEFF)
        self.assertEqual(remote["frame_type"], "remote")
        self.assertEqual(remote["payload"], [])
        self.assertEqual(remote["dlc"], 8)
        self.assertEqual(recovering["controller_state"], "recovering")

    def test_monotonic_timestamp_and_loss_provenance_are_preserved(self):
        standard = json.loads(self.lines[0])
        self.assertEqual(standard["captured_monotonic_ns"], 1_234_567_000)
        self.assertEqual(standard["clock_source"], "monotonic_only")
        self.assertEqual(standard["dropped_frames_before"], 0)
        self.assertEqual(standard["dropped_frames_after"], 2)
        self.assertEqual(standard["capture_source"], "hardware")
        self.assertEqual(standard["direction"], "rx")

    def test_native_harness_rejects_invalid_identifier_uuid_and_small_buffer(self):
        self.assertEqual(self.lines[-1], "TRANSPORT_ASSERTIONS=7")

    def test_device_status_schema_accepts_monotonic_only_device_clock(self):
        status = {
            "schema_version": 1,
            "record_type": "device_status",
            "observed_monotonic_ns": 5_000_000,
            "clock_source": "monotonic_only",
            "connected": True,
            "controller_state": "stopped",
            "firmware_version": "0.3.0-dev",
            "bitrate_bps": None,
            "dropped_frames_total": 0,
            "faults": ["hardware_capture_unavailable"],
        }
        Draft202012Validator(
            STATUS_SCHEMA, format_checker=FormatChecker()
        ).validate(status)


if __name__ == "__main__":
    unittest.main(verbosity=2)
