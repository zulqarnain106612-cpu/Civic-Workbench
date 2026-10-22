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

    def test_hardware_tx_defaults_disabled(self):
        config = (FW / "main" / "Kconfig.projbuild").read_text()
        block = config.split("config CIVIC_ALLOW_HARDWARE_CAN_TX", 1)[1].split(
            "config CIVIC_INTERLOCK_ACTIVE_LEVEL", 1
        )[0]
        self.assertIn("default n", block)
        self.assertIn("depends on CIVIC_ALLOW_HARDWARE_CAN_INIT", block)
        self.assertIn("depends on CIVIC_BITRATE_EVIDENCE_CONFIRMED", block)

    def test_bitrate_evidence_defaults_disabled(self):
        config = (FW / "main" / "Kconfig.projbuild").read_text()
        block = config.split("config CIVIC_BITRATE_EVIDENCE_CONFIRMED", 1)[1].split(
            "config CIVIC_ALLOW_HARDWARE_CAN_INIT", 1
        )[0]
        self.assertIn("default n", block)

    def test_nodemcu32s_twai_pins_are_mapped_but_safety_gates_stay_closed(self):
        config = (FW / "main" / "Kconfig.projbuild").read_text()
        tx = config.split("config CIVIC_TWAI_TX_GPIO", 1)[1].split("config ", 1)[0]
        rx = config.split("config CIVIC_TWAI_RX_GPIO", 1)[1].split("config ", 1)[0]
        gate = config.split("config CIVIC_TX_GATE_REQUEST_GPIO", 1)[1].split("config ", 1)[0]
        sense = config.split("config CIVIC_INTERLOCK_SENSE_GPIO", 1)[1].split("config ", 1)[0]
        self.assertIn("default 21", tx)
        self.assertIn("default 22", rx)
        self.assertIn("default -1", gate)
        self.assertIn("default -1", sense)
        init = config.split("config CIVIC_ALLOW_HARDWARE_CAN_INIT", 1)[1].split("\n    config ", 1)[0]
        bitrate = config.split("config CIVIC_BITRATE_EVIDENCE_CONFIRMED", 1)[1].split("\n    config ", 1)[0]
        tx_option = config.split("config CIVIC_ALLOW_HARDWARE_CAN_TX", 1)[1].split("\n    config ", 1)[0]
        self.assertIn("default n", init)
        self.assertIn("default n", bitrate)
        self.assertIn("default n", tx_option)

    def test_default_mode_is_passive_and_tx_uses_one_guarded_api(self):
        source = (FW / "main" / "civic_can.c").read_text()
        config = (FW / "main" / "Kconfig.projbuild").read_text()
        app = (FW / "main" / "app_main.c").read_text()
        transport = (FW / "main" / "civic_transport.c").read_text()
        self.assertIn("TWAI_MODE_LISTEN_ONLY", source)
        tx_option = config.split("config CIVIC_ALLOW_HARDWARE_CAN_TX", 1)[1].split(
            "config CIVIC_INTERLOCK_ACTIVE_LEVEL", 1
        )[0]
        self.assertIn("default n", tx_option)
        tx_api = source.index("esp_err_t civic_can_transmit_guarded(")
        tx_gate = source.index("#if !defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX)", tx_api)
        tx_send = source.index("twai_transmit(", tx_api)
        self.assertLess(tx_gate, tx_send)
        self.assertIn("civic_can_set_software_armed(false)", source[tx_api:tx_send])
        self.assertNotIn("twai_transmit(", app)
        self.assertNotIn("twai_transmit(", transport)

    def test_rx_ingress_is_bounded_and_exports_loss_counters(self):
        config = (FW / "main" / "Kconfig.projbuild").read_text()
        source = (FW / "main" / "civic_can.c").read_text()
        self.assertIn("config CIVIC_APP_RX_QUEUE_DEPTH", config)
        self.assertIn("config CIVIC_TWAI_RX_QUEUE_LEN", config)
        self.assertIn("xQueueCreate", source)
        self.assertIn("increment_software_drop", source)
        self.assertIn("Application RX queue overflow while armed; forcing TX inhibit", source)
        self.assertIn("software_armed_state())", source)
        self.assertIn("CIVIC_CAN_TX_ERROR_COUNTER_INHIBIT_THRESHOLD", source)
        self.assertIn("rx_missed_count", source)
        self.assertIn("rx_overrun_count", source)

    def test_bitrate_evidence_checked_before_controller_install(self):
        source = (FW / "main" / "civic_can.c").read_text()
        gate = source.index("#if !defined(CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED)")
        install = source.index("twai_driver_install")
        self.assertLess(gate, install)

    def test_runtime_gpio_guard_rejects_flash_and_strapping_pins(self):
        source = (FW / "main" / "civic_can.c").read_text()
        self.assertIn("gpio_is_flash_reserved", source)
        self.assertIn("gpio_is_strapping", source)
        self.assertIn("gpio_is_console_reserved", source)
        self.assertIn("gpio == 1 || gpio == 3", source)
        self.assertIn("GPIO mapping is unset, reused, flash/console-reserved, or strapping", source)

    def test_interlock_output_is_forced_inactive(self):
        source = (FW / "main" / "civic_safety.c").read_text()
        self.assertIn("gpio_set_level((gpio_num_t)gate_gpio, 0)", source)
        self.assertIn("GPIO_PULLDOWN_ENABLE", source)

    def test_tx_gate_output_rejects_unsafe_pins_before_gpio_config(self):
        source = (FW / "main" / "civic_safety.c").read_text()
        guard = source.index("if (gate_gpio < 0")
        configure = source.index("gpio_config(&output_config)")
        self.assertLess(guard, configure)
        self.assertIn("gate_gpio >= 6 && gate_gpio <= 11", source)
        self.assertIn("gate_gpio == 12 || gate_gpio == 15", source)
        self.assertIn("gate_gpio == 1 || gate_gpio == 3", source)
        self.assertIn("gate_gpio == CONFIG_CIVIC_TWAI_TX_GPIO", source)
        self.assertIn("gate_gpio == CONFIG_CIVIC_TWAI_RX_GPIO", source)
        self.assertIn("gate_gpio == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO", source)

    def test_hardware_notes_use_fixed_board_and_transceiver_without_enabling_tx(self):
        notes = (ROOT / "hardware" / "reference" / "safety-interlock.md").read_text()
        self.assertIn("ESP32S NodeMCU / NodeMCU-32S", notes)
        self.assertIn("GPIO21/TWAI_TX", notes)
        self.assertIn("GPIO22/TWAI_RX", notes)
        self.assertIn("NXP TJA1051 marked NXP TJA1051 25 06 ND312", notes)
        self.assertIn("not a validated schematic or assembled circuit", notes)
        self.assertIn("Pin 5 remains unconnected pending confirmation", notes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
