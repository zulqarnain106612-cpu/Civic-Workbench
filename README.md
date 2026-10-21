# Civic-Workbench

A direct-CAN engineering workbench for investigating a Pakistan-market 2013 Honda Civic (9th generation, 1.8 L), built around the **original ESP32 with its integrated TWAI controller and the NXP TJA1051T/3 SO8 transceiver**.

## Project boundary

This repository is independent of the older build-a-web-page-for-ios project. It does not import or reuse source code or repository structure from that project.

The intended product includes live CAN frame capture, identifier and signal discovery, controlled direct-CAN transmission, capability-driven diagnostics/parameter workflows where evidenced, a browser engineering UI, local persistence, a virtual CAN lab, and a Python-generated native Proteus schematic/project.

**Current status:** S00 environment discovery, S01 contracts, S02 firmware foundation, and S03 CAN receive/guarded-TX core plus schema-v1 serial telemetry are source/build/host-mock verified. The generic original-ESP32 firmware profile compiles successfully but has not been flashed or physically validated. Hardware TX remains disabled by default; the C API for one guarded frame is not exposed as a serial command yet. Browser UI, durable persistence, signal/identifier discovery, diagnostic workflows, virtual CAN, generated native Proteus CAD, and physical operation remain outstanding. No Honda-specific CAN identifier, bit layout, scale, diagnostic service, or ECU behavior may be presented as fact without traceable evidence.

## Start here

1. Agent execution contract: CLAUDE.md
2. Master specification: docs/master-spec.md
3. Staged delivery plan: docs/staged-delivery.md
4. Requirements: project/requirements.yaml
5. Dependency DAG: project/dependencies.yaml
6. Stage definitions: project/stages.yaml
7. Hardware baseline: project/hardware.yaml
8. Safety and engineering constraints: project/constraints.yaml
9. Versioned contracts: docs/contracts-v1.md and schemas/v1/
10. Logical API contract: contracts/openapi.yaml
11. Contract tests: tests/test_contracts.py (run with `make test-contracts` or `PYTHONPATH=src python3 -m unittest discover -s tests -v`)
12. Requirements traceability: tests/requirements-traceability.yaml
13. Progress ledger: project/progress.json
14. S01 contract implementation and verification report: docs/reports/S01-contract-report.md
15. S02 firmware foundation and build report: docs/reports/S02-firmware-report.md
16. S02 hardware safety/netlist sources: hardware/reference/
17. S03 CAN core/transport implementation report: docs/reports/S03-can-transport-report.md
18. Firmware serial protocol: docs/protocol/firmware-serial-v1.md
19. Host-mocked CAN integration tests: tests/firmware/test_can_core_mock.c and tests/test_firmware_can_core.py
20. Schema-validated serial output tests: tests/firmware/test_serial_transport.c and tests/test_firmware_serial_transport.py

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
