# S14 — Receive-only interface Rev B and audit remediation

**Date:** 2026-10-23. **Status:** source design, firmware and host fixes implemented and tested on the host. Native Proteus project and physical bench remain open.

## Why Rev B

The 2026-10-23 audit found the Rev A interface unsafe for the plain TJA1051T (pin 5 n.c.), which is the part shown in the owner-supplied datasheet and AH1014 pages (`docs/reference/`):

| Finding | Evidence | Rev A | Rev B |
|---|---|---|---|
| S VIH = 0.7 x VCC = 3.5 V | datasheet Table 7; AH1014 Fig 13 (VIO = VCC) | S pulled to 3.3 V: Silent not guaranteed | R1 10k to +5V_CAN |
| TXD VIH = 3.5 V | same | GPIO21 (3.3 V) drives TXD: undefined level | GPIO21 not connected; R2 10k holds TXD recessive |
| RXD output at VCC (~5 V) | same | RXD direct to GPIO22: exceeds ESP32 limits | R3 12k / R4 20k divider: 2.81-3.44 V over VCC 4.5-5.5 V |
| Pin 5 unresolved, blocking power-up | AH1014 Table 21 | do not power | left open; fail-safe for n.c., VIO and EN variants |
| Decoupling undefined | AH1014 7.1.1, Table 14 | — | C1 100 nF, C2 10 uF |
| Termination | AH1014 7.4, Fig 45 | — | split 2 x 60R + 4.7 nF, 100 pF bus caps, all DNP by default |

The design source is `hardware/reference/esp32-tja1051-netlist.yaml`; `make design-source` regenerates the schematic SVG, netlist, BOM, `design-checks.json` (all pass) and `PROTEUS-CAPTURE.md`.

## Audit items closed

1. **Hardware level/Silent safety** — Rev B above.
2. **Receive-only firmware could not start** — new `CONFIG_CIVIC_RECEIVE_ONLY_BENCH` starts TWAI in listen-only mode without TX-gate/interlock GPIOs. Combining it with `CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX` is a Kconfig dependency and a compile `#error`.
3. **Serial connect reset the board** — `serial_bridge.py` now deasserts DTR/RTS before opening the port.
4. **Firmware TX lacked rate bound and audit** — `CONFIG_CIVIC_TX_MIN_INTERVAL_MS` (default 100) and `CONFIG_CIVIC_TX_MAX_FRAMES_PER_ARM` (default 10, then disarm); every attempt emits a `TX_AUDIT` log line. TX stays compiled out by default.
5. **Bench needs an ACKing node** — recorded in the netlist open items, the schematic notes and the checklist below.

## Tests

- `tests/test_proteus_generator.py`: determinism, committed bundle matches the generator, all electrical checks, receive-only topology, BOM/DNP, native project not fabricated.
- `tests/test_firmware_can_core.py::FirmwareReceiveOnlyBenchTests`: production `civic_can.c` in the receive-only profile starts listen-only, cannot arm or transmit, still receives; RX-only plus TX fails to compile.
- `tests/firmware/test_can_core_mock.c`: rate-limit rejection without disarm, per-arm budget disarm, gate released.
- `tests/test_serial_bridge_open.py`: DTR/RTS false at open, port not opened by the constructor.

## Native Proteus

Not created. The installed Proteus 8.3 is registry-labelled "Demonstration", the native DSN is a proprietary binary with no official Python writer, and this session had no shell on the Proteus host. Next action: capture from `PROTEUS-CAPTURE.md` in a licensed Proteus and commit the `.pdsprj` with import/render evidence.

## Bench checklist (receive-only, Rev B)

1. Continuity: NodeMCU header 33 = GPIO21, 36 = GPIO22, 38 = GND. SO8 pin-1 orientation.
2. Power U1 alone from a current-limited 5.0 V supply (150 mA limit); GPIO22 not yet connected.
3. Measure: +5V_CAN 4.5-5.5 V; S >= 3.5 V; TXD ≈ VCC; RXD_3V3 <= 3.6 V with the bus idle.
4. Connect GPIO22 and common GND. Flash a build with `RECEIVE_ONLY_BENCH`, `ALLOW_HARDWARE_CAN_INIT` and `BITRATE_EVIDENCE_CONFIRMED` set for the bench bitrate only.
5. Bench bus: at least two other nodes (one sender plus one ACKing node), terminated at both ends. Never connect to the vehicle in this stage.
6. Record captures and measurements as evidence before marking S14 bench-complete.

## EAGLE schematic export (added 2026-10-23)

`tools/generate_eagle_schematic.py` writes `hardware/proteus/generated/civic-workbench-rev-b.sch`, a self-contained EAGLE XML schematic (embedded library, 15 parts, net labels), from the same netlist. It is for Proteus "Import EAGLE" (newer Proteus 8 releases; not present in the installed 8.3) and any EAGLE-compatible tool.

Import evidence: KiCad 7.0.11's EAGLE importer loaded the file; its exported netlist matches the reviewed netlist exactly (9 nets, U1 pin 5 and J1 GPIO21 unconnected, part values intact). `tests/test_eagle_schematic.py` checks structure, reference resolution, connectivity and determinism on every run.
