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


class FirmwareReceiveOnlyBenchTests(unittest.TestCase):
    """Hardware Rev B: listen-only startup without TX gate/interlock GPIOs; TX not compiled."""

    def test_receive_only_build_starts_listen_only_and_cannot_transmit(self):
        with tempfile.TemporaryDirectory(prefix="civic-can-rx-only-") as tempdir:
            executable = Path(tempdir) / "can-rx-only-test"
            subprocess.run(
                ["gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-Wall", "-Wextra", "-Werror", "-pedantic",
                 "-pthread", f"-I{ROOT / 'tests/firmware/mock_esp_rx_only'}", f"-I{MOCKS}", f"-I{FIRMWARE}",
                 str(ROOT / "tests/firmware/test_can_rx_only_mock.c"), str(MOCKS / "mock_esp.c"),
                 str(FIRMWARE / "civic_can.c"), str(FIRMWARE / "civic_safety.c"),
                 str(FIRMWARE / "civic_safety_policy.c"), "-o", str(executable)],
                check=True, capture_output=True, text=True,
            )
            completed = subprocess.run([str(executable)], check=True, capture_output=True, text=True, timeout=5)
            self.assertRegex(completed.stdout.strip(), r"CAN_RX_ONLY_ASSERTIONS=\d+")
            self.assertGreaterEqual(int(completed.stdout.strip().split("=")[1]), 12)

    def test_receive_only_and_tx_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory(prefix="civic-can-rx-only-tx-") as tempdir:
            override = Path(tempdir) / "sdkconfig.h"
            override.write_text((ROOT / "tests/firmware/mock_esp_rx_only/sdkconfig.h").read_text()
                                + "#define CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX 1\n")
            completed = subprocess.run(
                ["gcc", "-std=c11", "-fsyntax-only", f"-I{tempdir}", f"-I{MOCKS}", f"-I{FIRMWARE}",
                 str(FIRMWARE / "civic_can.c")],
                capture_output=True, text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("mutually exclusive", completed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
