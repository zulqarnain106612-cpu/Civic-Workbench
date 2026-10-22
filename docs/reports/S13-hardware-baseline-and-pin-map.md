# S13 — Exact Physical Marking and NodeMCU-32S Receive-Only Pin Map

**Status:** source/configuration mapping verified; physical transceiver variant and bench validation remain blocked.
**Date:** 2026-10-22

## Fixed hardware — no substitutes

- **Controller:** ESP32S NodeMCU / NodeMCU-32S, classic ESP32 with integrated TWAI. PlatformIO board identifier: `nodemcu-32s`.
- **Transceiver:** the exact physical NXP component marked **`NXP TJA1051 25 06 ND312`**. That complete text is the owner-supplied visible marking and is preserved literally.
- No alternative transceiver, substitute board, successor, or predecessor is authorized.

## Correction to the previous report

The prior sentence saying the `25 06 ND312` text “is not treated as a different ordering code” was unsupported and is withdrawn. I had no manufacturer evidence to classify those characters as extra marking, date/lot information, or non-orderable text. The previous project label `TJA1051T/3` also was not established from the visible marking alone and must not be presented as a confirmed suffix.

NXP's [TJA1051 datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf) distinguishes variants that use pin 5 for VIO from variants that use pin 5 for EN. NXP support has also said publicly that it does not decode top markings in the public forum and directs marking-confirmation requests to its support channel: [NXP TJA1051T/3 marking-code discussion](https://community.nxp.com/t5/Other-NXP-Products/TJA1051T-3-Marking-Code/m-p/1381153). Therefore **the pin-5 function of the exact marked physical device is not established here**.

## Board-to-transceiver signal map

| Function | NodeMCU-32S | NXP TJA1051 | State |
|---|---:|---:|---|
| TWAI TX logic | GPIO21 | pin 1 TXD | Source-mapped; physical pin-1 orientation check pending |
| Common ground | GND | pin 2 GND | Do not power the circuit until the complete pinout is confirmed |
| Transceiver supply | reviewed regulated supply | pin 3 VCC | No physical power-up yet |
| TWAI RX logic | GPIO22 | pin 4 RXD | Source-mapped; physical pin-1 orientation check pending |
| **Variant-dependent pin** | **not connected** | **pin 5** | **Unresolved: do not connect to VIO or EN and do not power the assembly until NXP confirms the exact variant** |
| CAN low | CAN connector low | pin 6 CANL | Connector/protection review pending |
| CAN high | CAN connector high | pin 7 CANH | Connector/protection review pending |
| Silent mode | no direct MCU GPIO | pin 8 S | Receive-only design intent, pending confirmation of the exact pinout and circuit review |

GPIO21/TWAI_TX and GPIO22/TWAI_RX remain the source mapping for the specified NodeMCU-32S. Their physical header continuity and the board revision have not been measured.

## Mandatory confirmation before power-up

1. Preserve the full visible marking `NXP TJA1051 25 06 ND312`; do not reinterpret or abbreviate it.
2. Obtain written confirmation from NXP support for the exact orderable variant/pinout corresponding to that marking. A datasheet for a guessed suffix is not sufficient.
3. Confirm SO8 footprint, pin-1 orientation, and physical pin numbering.
4. **Keep pin 5 unconnected and do not energize the transceiver circuit until its function is confirmed.** In particular, do not wire it as VIO based only on the prior `/3` label.
5. After manufacturer confirmation, update the netlist and generator from that evidence, then review VCC, logic rail, decoupling, Silent bias, connector protection and topology-specific termination on an isolated bench.
6. Keep the firmware hardware-initialization, bitrate-evidence and physical-TX gates disabled until the exact circuit and bitrate have independently reviewed evidence.

## Verification results and boundaries

- The source mapping for NodeMCU-32S GPIO21/GPIO22 was compiled and source-guard tested.
- Hardware initialization and physical TX remain disabled. Build success is not physical validation.
- No firmware was flashed; no physical transceiver was powered; no live CAN or Civic bus was tested.
- Native Proteus import/render remains separately blocked; generated source artifacts are not a native Proteus project.
