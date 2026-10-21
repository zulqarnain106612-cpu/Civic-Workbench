"""Host-mock integration tests execute the production S03 CAN core."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "firmware" / "esp32" / "main"
MOCKS = ROOT / "tests" / "firmware" / "mock_esp"


class FirmwareCanCoreMockTests(unittest.TestCase):
    def test_production_can_core_with_mock_twai_and_freertos(self):
        with tempfile.TemporaryDirectory(prefix="civic-can-core-mock-") as tempdir:
            executable = Path(tempdir) / "can-core-mock-test"
            subprocess.run(
                [
                    "gcc",
                    "-std=c11",
                    "-D_POSIX_C_SOURCE=200809L",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-pedantic",
                    "-pthread",
                    f"-I{MOCKS}",
                    f"-I{FIRMWARE}",
                    str(ROOT / "tests/firmware/test_can_core_mock.c"),
                    str(MOCKS / "mock_esp.c"),
                    str(FIRMWARE / "civic_can.c"),
                    str(FIRMWARE / "civic_safety.c"),
                    str(FIRMWARE / "civic_safety_policy.c"),
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
            self.assertRegex(completed.stdout.strip(), r"CAN_CORE_ASSERTIONS=\d+")
            assertions = int(completed.stdout.strip().split("=")[1])
            self.assertGreaterEqual(assertions, 68)


if __name__ == "__main__":
    unittest.main(verbosity=2)
