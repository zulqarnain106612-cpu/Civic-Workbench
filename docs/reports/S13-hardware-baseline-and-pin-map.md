# S13 — Fixed Hardware Baseline and Receive-Only Pin Map

**Status:** source/configuration mapping verified; physical bench confirmation remains pending.  
**Date:** 2026-10-22

## Fixed items — no substitutions

This project uses the owner's exact hardware baseline:

- **Controller board:** ESP32S NodeMCU / NodeMCU-32S; original/classic ESP32 with integrated TWAI. PlatformIO board identifier: nodemcu-32s.
- **CAN transceiver:** NXP TJA1051, SO8 (SOT96-1), as specified in the project requirements. The owner-reported visible marking is recorded literally as NXP TJA1051 25 06 ND312; the extra marking is not treated as a different ordering code.
- No successor, predecessor, substitute board, substitute transceiver, or substitute item is authorized.

Primary part source: [NXP TJA1051 official datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf). The exact physical item is NXP TJA1051 marked NXP TJA1051 25 06 ND312; no substitute is permitted. The marking is not decoded here, and no orderable suffix is inferred. Since TJA1051 variants can differ at pin 5, the project does not assign its function: leave it unconnected and do not power the assembly until the exact pinout is established for this item.

## Board-to-transceiver map

| Function | NodeMCU-32S | NXP TJA1051 SO8 | Purpose |
|---|---:|---:|---|
| TWAI transmit-data logic | GPIO21 | pin 1 TXD | ESP32 output into transceiver; remains non-transmitting in this phase |
| Common ground | GND | pin 2 GND | Shared logic reference |
| Transceiver supply | reviewed regulated 5 V rail | pin 3 VCC | Must stay within the official datasheet limits |
| TWAI receive-data logic | GPIO22 | pin 4 RXD | Transceiver output into ESP32 TWAI RX |
| Variant-dependent pin | not connected | pin 5 | Unresolved for the exact marked item; do not connect or power until confirmed |
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
2. Confirm the exact SO8 footprint orientation and pin-1 indicator for the specified NXP TJA1051.
3. Check for shorts between GND, 3.3 V, 5 V and CANH/CANL before applying power.
4. Review local VCC decoupling, the exact marked device’s confirmed pin-5 function, and the external pull-up that holds S HIGH through reset or an unpowered ESP32.
5. Use a current-limited, isolated bench supply and a controlled CAN test fixture first. Do not connect to the Civic until the circuit, bitrate and capture point have separate evidence.
6. Do not fit or enable 120-ohm termination blindly; it depends on the actual bus topology.

## Verification results

- Source guard tests cover the selected GPIO defaults and the unchanged closed hardware-init/bitrate/TX gates.
- PlatformIO compile target is now the specific nodemcu-32s board profile; build success remains compile evidence only.
- Physical header continuity, Silent bias, transceiver power sequencing, live serial, live CAN and vehicle behavior remain unverified.
