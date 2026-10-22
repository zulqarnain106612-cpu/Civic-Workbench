# S13 — Fixed Hardware Baseline and Receive-Only Pin Map

**Status:** source/configuration mapping verified; physical bench confirmation remains pending.  
**Date:** 2026-10-22

## Fixed items — no substitutions

This project uses the owner's exact hardware baseline:

- **Controller board:** ESP32S NodeMCU / NodeMCU-32S; original/classic ESP32 with integrated TWAI. PlatformIO board identifier: nodemcu-32s.
- **CAN transceiver:** NXP TJA1051T/3, SO8 (SOT96-1), as specified in the project requirements. The owner-reported visible marking is recorded literally as NXP TJA1051 25 06 ND312; the extra marking is not treated as a different ordering code.
- No successor, predecessor, substitute board, substitute transceiver, or substitute item is authorized.

Primary part source: [NXP TJA1051 official datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf). For the specified TJA1051T/3 SO8 baseline, pin 5 is VIO and pin 8 is S (Silent-mode control). NXP documents that other TJA1051 order-code variants use NC or EN at pin 5 instead; therefore the project does not infer an order-code suffix from the additional top-marking text. The fixed TJA1051T/3 design must only be physically wired if the exact installed item matches that established baseline; if the physical marking/order evidence does not establish that, leave pin 5 unconnected and do not power the assembly until it is resolved. No alternate variant is being recommended.

## Board-to-transceiver map

| Function | NodeMCU-32S | NXP TJA1051T/3 SO8 | Purpose |
|---|---:|---:|---|
| TWAI transmit-data logic | GPIO21 | pin 1 TXD | ESP32 output into transceiver; remains non-transmitting in this phase |
| Common ground | GND | pin 2 GND | Shared logic reference |
| Transceiver supply | reviewed regulated 5 V rail | pin 3 VCC | Must stay within the official datasheet limits |
| TWAI receive-data logic | GPIO22 | pin 4 RXD | Transceiver output into ESP32 TWAI RX |
| I/O logic supply | 3.3 V rail | pin 5 VIO | Required for TJA1051T/3 logic-level adapter |
| CAN low | CAN connector low | pin 6 CANL | Physical bus low |
| CAN high | CAN connector high | pin 7 CANH | Physical bus high |
| Silent mode | no MCU GPIO connection | pin 8 S | Externally biased HIGH for the receive-only baseline |

GPIO21 and GPIO22 are available GPIOs on the classic ESP32 and are not boot-strapping pins in Espressif's GPIO documentation. The mapping reserves them for TWAI, so the project must not also use them for I2C. The mapping is encoded in project/hardware.yaml, the source netlist, and Kconfig defaults.

Sources:
- [Espressif ESP-IDF classic ESP32 GPIO documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/gpio.html)
- [NXP TJA1051 datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf)

## Safety state remains fail-closed

- Hardware initialization remains disabled by default.
- Bitrate evidence confirmation remains disabled by default; the numerical Kconfig bitrate is only a compile-time placeholder.
- Hardware TX remains disabled by default.
- Transceiver pin 8 S is externally biased HIGH for Silent mode; no direct ESP32 GPIO path to pull it LOW is assigned.
- Host-to-firmware transmit commands are not added.
- No board flashing, physical CAN transmission, vehicle connection, or live-bus claim is made by this source update.

## Bench checklist required before hardware power-up

1. Read the board silkscreen and verify it is the specified NodeMCU-32S/classic-ESP32 board, then continuity-check GPIO21 and GPIO22 against the header labels.
2. Confirm the exact SO8 footprint orientation and pin-1 indicator for the specified NXP TJA1051T/3.
3. Check for shorts between GND, 3.3 V, 5 V and CANH/CANL before applying power.
4. Review local VCC decoupling, the 3.3 V VIO rail, and the external pull-up that holds S HIGH through reset or an unpowered ESP32.
5. Use a current-limited, isolated bench supply and a controlled CAN test fixture first. Do not connect to the Civic until the circuit, bitrate and capture point have separate evidence.
6. Do not fit or enable 120-ohm termination blindly; it depends on the actual bus topology.

## Verification results

- Source guard tests cover the selected GPIO defaults and the unchanged closed hardware-init/bitrate/TX gates.
- PlatformIO compile target is now the specific nodemcu-32s board profile; build success remains compile evidence only.
- Physical header continuity, Silent bias, transceiver power sequencing, live serial, live CAN and vehicle behavior remain unverified.
