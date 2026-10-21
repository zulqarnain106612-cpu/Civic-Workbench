# S02 Hardware Foundation — TX Inhibit and Transceiver Interface

**Status:** electrical design contract; not a validated schematic or assembled circuit. Exact board, GPIOs and physical part have not been identified/inspected.

## Required controller/transceiver connections

| Function | TJA1051T/3 SO8 pin | Required relationship |
|---|---:|---|
| TXD | 1 | ESP32 TWAI TX signal through the documented logic connection |
| GND | 2 | Common logic/transceiver ground |
| VCC | 3 | Regulated supply within the NXP datasheet range, 4.5–5.5 V |
| RXD | 4 | ESP32 TWAI RX signal |
| VIO | 5 | ESP32-compatible I/O supply, normally 3.3 V for original ESP32, within datasheet range |
| CANL | 6 | Physical CAN low |
| CANH | 7 | Physical CAN high |
| S | 8 | HIGH = Silent (receiver active, transmitter disabled); LOW = Normal |

Source: [NXP TJA1051 official datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf).

## Fail-safe operating requirements

1. Pin S must have an external pull-up to the logic supply so reset, high-impedance GPIO, MCU boot and loss of firmware power default to Silent mode.
2. Do **not** connect the MCU GPIO directly to S as the only protection.
3. Implement a hardware-only path that can pull S LOW only when both (a) the external physical interlock is closed and (b) the firmware TX-enable request is asserted. Use an electrically reviewed gate/series-switch design with documented default-off bias; validate leakage, voltage domains and fault behavior before assembly.
4. The MCU TX-enable request must have an external default-off pull-down. The physical interlock must interrupt the electrical path independently of firmware. Software GPIO readback is status feedback, not the safety barrier.
5. If an interlock feedback signal is available, route it to a separately selected input GPIO. Disagreement or unknown feedback must deny TX.
6. Keep the controller in TWAI_MODE_LISTEN_ONLY for S02. S02 does not expose a frame-transmit command.
7. Do not connect CANH/CANL to GPIO. Do not add termination to an existing vehicle network without understanding the topology.
8. On reset, failure, bus-off, stop, or disarm, the firmware request must return inactive. The external circuit must still hold S HIGH without a powered MCU.
9. Do not choose GPIOs until exact module and pinout are identified, and review flash/PSRAM pins, strapping behavior and board peripherals.

## Current firmware behavior

The compile target is generic esp32dev for **original ESP32 only**. GPIOs default to -1 and CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT defaults disabled. The code must compile without an attached board; it must refuse runtime TWAI initialization until the user/engineer explicitly sets verified GPIOs, documented bitrate, bitrate evidence confirmation and the enable option. An illustrative CONFIG_CIVIC_CAN_BITRATE default is a compile-only placeholder and must never be interpreted as an established vehicle bitrate.

## Open hardware evidence

- [ ] Exact ESP32 board/module model and silicon variant.
- [ ] Confirmed board GPIO availability/strapping restrictions.
- [ ] Exact TJA1051T/3 package/part marking and pin-1 orientation.
- [ ] Reviewed full hardware TX inhibit schematic including component values.
- [ ] Bench-verified Silent-mode behavior and reset/power-loss state.
- [ ] Native Proteus generation/import verification (assigned to S09).
- [ ] Vehicle topology/bitrate/capture-point evidence (separate vehicle discovery task).
