# Civic-Workbench

A direct-CAN engineering workbench for investigating a Pakistan-market 2013 Honda Civic (9th generation, 1.8 L), built around the **original ESP32 with its integrated TWAI controller and the NXP TJA1051T/3 SO8 transceiver**.

## Project boundary

This repository is independent of the older build-a-web-page-for-ios project. It does not import or reuse source code or repository structure from that project.

The intended product includes live CAN frame capture, identifier and signal discovery, controlled direct-CAN transmission, capability-driven diagnostics/parameter workflows where evidenced, a browser engineering UI, local persistence, a virtual CAN lab, and a Python-generated native Proteus schematic/project.

**Status:** this first baseline contains specifications and delivery controls only. Application code, firmware, vehicle mappings, generated CAD, and physical operation are not yet implemented or validated by this commit. No Honda-specific CAN identifier, bit layout, signal scale, diagnostic service, or ECU behavior may be presented as fact without traceable evidence.

## Start here

1. Agent execution contract: CLAUDE.md
2. Master specification: docs/master-spec.md
3. Staged delivery plan: docs/staged-delivery.md
4. Requirements: project/requirements.yaml
5. Dependency DAG: project/dependencies.yaml
6. Stage definitions: project/stages.yaml
7. Hardware baseline: project/hardware.yaml
8. Safety and engineering constraints: project/constraints.yaml
9. Requirements traceability: tests/requirements-traceability.yaml
10. Progress ledger: project/progress.json

## Required hardware baseline

- MCU: original Espressif ESP32 variant with TWAI support; no S2/S3 substitution.
- CAN physical layer: NXP TJA1051T/3 in SO8 package.
- ESP32 TWAI is the CAN protocol controller; the external transceiver provides the physical CAN interface.
- TJA1051T/3 pin 5 (VIO) is the logic-supply input and must be connected to the MCU I/O supply, subject to the datasheet.
- Default operation is passive/listen-only with transmitter inhibited. Active transmission requires separate software arming and a hardware-enforced interlock.

Official references:
- [Espressif ESP32 TWAI documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/twai.html)
- [NXP TJA1051 product datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf)
- [Labcenter CAN simulation](https://www.labcenter.com/can-sim/)
- [Labcenter schematic capture](https://www.labcenter.com/schematic/)

## Engineering rule

Observed facts, candidate interpretations, and validated mappings are separate data states. Every implementation stage must provide its tests and evidence, record what remains unknown, and update the progress ledger. A stage is not complete merely because code was written.
