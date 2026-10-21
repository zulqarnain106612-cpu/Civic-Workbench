"""Static S02 firmware configuration guard checks."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "firmware" / "esp32"


class FirmwareSourceGuardTests(unittest.TestCase):
    def test_hardware_initialization_defaults_disabled(self):
        config = (FW / "main" / "Kconfig.projbuild").read_text()
        self.assertIn("config CIVIC_ALLOW_HARDWARE_CAN_INIT", config)
        block = config.split("config CIVIC_ALLOW_HARDWARE_CAN_INIT", 1)[1].split(
            "endmenu", 1
        )[0]
        self.assertIn("default n", block)

    def test_bitrate_evidence_defaults_disabled(self):
        config = (FW / "main" / "Kconfig.projbuild").read_text()
        block = config.split("config CIVIC_BITRATE_EVIDENCE_CONFIRMED", 1)[1].split(
            "config CIVIC_ALLOW_HARDWARE_CAN_INIT", 1
        )[0]
        self.assertIn("default n", block)

    def test_pin_configuration_defaults_to_unassigned(self):
        config = (FW / "main" / "Kconfig.projbuild").read_text()
        for symbol in (
            "CIVIC_TWAI_TX_GPIO",
            "CIVIC_TWAI_RX_GPIO",
            "CIVIC_TX_GATE_REQUEST_GPIO",
            "CIVIC_INTERLOCK_SENSE_GPIO",
        ):
            block = config.split(f"config {symbol}", 1)[1].split("config ", 1)[0]
            self.assertIn("default -1", block)

    def test_s02_driver_is_listen_only_and_has_no_tx_call(self):
        source = (FW / "main" / "civic_can.c").read_text()
        self.assertIn("TWAI_MODE_LISTEN_ONLY", source)
        self.assertNotIn("twai_transmit(", source)
        self.assertNotIn("twai_transmit_v2(", source)

    def test_bitrate_evidence_checked_before_controller_install(self):
        source = (FW / "main" / "civic_can.c").read_text()
        gate = source.index("#if !defined(CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED)")
        install = source.index("twai_driver_install")
        self.assertLess(gate, install)

    def test_runtime_gpio_guard_rejects_flash_and_strapping_pins(self):
        source = (FW / "main" / "civic_can.c").read_text()
        self.assertIn("gpio_is_flash_reserved", source)
        self.assertIn("gpio_is_strapping", source)
        self.assertIn("GPIO mapping is unset, invalid for original ESP32", source)

    def test_interlock_output_is_forced_inactive(self):
        source = (FW / "main" / "civic_safety.c").read_text()
        self.assertIn("gpio_set_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO, 0)", source)
        self.assertIn("GPIO_PULLDOWN_ENABLE", source)

    def test_tx_gate_output_rejects_unsafe_pins_before_gpio_config(self):
        source = (FW / "main" / "civic_safety.c").read_text()
        guard = source.index("if (gate_gpio < 0")
        configure = source.index("gpio_config(&output_config)")
        self.assertLess(guard, configure)
        self.assertIn("gate_gpio >= 6 && gate_gpio <= 11", source)
        self.assertIn("gate_gpio == 12 || gate_gpio == 15", source)
        self.assertIn("gate_gpio == CONFIG_CIVIC_TWAI_TX_GPIO", source)
        self.assertIn("gate_gpio == CONFIG_CIVIC_TWAI_RX_GPIO", source)
        self.assertIn("gate_gpio == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO", source)

    def test_hardware_notes_do_not_claim_board_specific_gpio_values(self):
        notes = (ROOT / "hardware" / "reference" / "safety-interlock.md").read_text()
        self.assertIn("Do not choose GPIOs until exact module and pinout are identified", notes)
        self.assertIn("not a validated schematic or assembled circuit", notes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
