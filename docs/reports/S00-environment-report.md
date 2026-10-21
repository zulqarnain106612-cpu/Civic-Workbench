# S00 — Environment and Repository Discovery

**Snapshot date:** 2026-10-22  
**Status:** Partially completed; blocked on the user's development computer being offline.  
**Repository snapshot:** `main` at `4d81cb6d380e9168002714a087b0c259acc506f1`

## 1. Executive result

The online repository audit is complete for the inspected commit. The required hardware architecture is consistent with the official Espressif and NXP documentation: original ESP32 TWAI controller plus an external NXP TJA1051T/3 SO8 high-speed CAN transceiver.

The user's registered Desktop Commander device `s752-LIFEBOOK-S752` was reported **offline** at inspection time (last seen approximately 109 hours earlier). Consequently, no shell commands could be run on that machine. Python, Git, ESP-IDF, Arduino-ESP32, CMake/Ninja, serial ports, the exact ESP32 board/module, and the Proteus installation/version remain **not verified**. This does not mean the software is absent; it means no evidence was accessible to check it.

S00 is therefore **not complete**. The repository now records an explicit environment snapshot and risk register so work can resume without re-discovering known facts or mistaking unknowns for confirmed values.

## 2. Repository facts observed

- Repository: [Civic-Workbench](https://github.com/zulqarnain106612-cpu/Civic-Workbench)
- Default branch: `main`
- Snapshot commit: [`4d81cb6`](https://github.com/zulqarnain106612-cpu/Civic-Workbench/commit/4d81cb6d380e9168002714a087b0c259acc506f1)
- The connected GitHub integration reported admin, maintain, push, and pull permissions.
- The root tree contains the project contract/specification files, Python-oriented `.gitignore`, README, and MIT license.
- No firmware source tree, application source tree, build/test implementation, dependency lockfile, CI workflow, Proteus project/schematic, or generated artifact was present in this inspected tree.
- The project is at the specification-baseline stage; no implementation is claimed by this report.

The exact file map is in [S00 repository map](S00-repository-map.md).

## 3. Development environment findings

| Item | Finding | Evidence status |
|---|---|---|
| User development computer | `s752-LIFEBOOK-S752` listed offline | Directly observed from Desktop Commander device list |
| Shell on user computer | Not available | Direct result of device being offline |
| Operating system | Unknown | Not inspected |
| Python / Git / CMake / Ninja | Unknown on user computer | Not inspected |
| ESP-IDF installation and version | Unknown | Not inspected |
| Arduino-ESP32 installation and version | Unknown | Not inspected |
| Serial port / attached ESP32 | Unknown | Not inspected |
| Exact ESP32 module/board and exposed GPIOs | Unknown | No board or local machine access |
| Proteus installation/version and component libraries | Unknown | No local machine access |
| Native Proteus import/render test | Not performed | Requires installed application/artifact |
| Vehicle CAN bit rate/topology/capture point | Unknown | No validated capture evidence supplied |
| Vehicle CAN identifiers/signals | None observed in this repository | No raw vehicle capture in inspected tree |

A repeatable command checklist is recorded in [S00 toolchain matrix](S00-toolchain-matrix.md). It has deliberately not been marked as executed.

## 4. Official technical references checked

### ESP32 TWAI

Espressif documents the original ESP32 TWAI controller as a classical CAN controller and explicitly says the ESP32 does not contain an integrated CAN transceiver. An external transceiver is required. The documented frame identifiers are standard 11-bit or extended 29-bit, and this ESP32's TWAI controller is not CAN-FD compatible. Therefore, the eventual firmware should use the ESP-IDF TWAI driver unless local compatibility evidence establishes a compelling reason otherwise; the exact toolchain version remains unselected until the real environment is inspected.

References:
- [ESP-IDF TWAI documentation for ESP32 (release/v5.5)](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32/api-reference/peripherals/twai.html)
- [Espressif original ESP32 datasheet](https://documentation.espressif.com/esp32_datasheet_en.pdf)

### NXP TJA1051T/3 SO8

The NXP datasheet identifies the TJA1051T/3 as the variant with VIO on pin 5 and an SO8 package. It specifies VCC from 4.5 V to 5.5 V and VIO from 2.8 V to 5.5 V. Pin 5 VIO should be connected to the MCU I/O supply. Pin 8 S selects the mode: HIGH selects Silent mode and disables the transmitter while the receiver continues operating; LOW selects Normal mode. This is consistent with making hardware-defined Silent mode the default.

Reference:
- [NXP TJA1051 official datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf)

These are component-level facts only. They do not validate an assembled circuit or establish the target vehicle's bus parameters.

### Proteus and Python schematic generation

The official Labcenter pages reviewed document Proteus schematic capture, downloads/utilities, and product features. The public material inspected did **not** establish an official Python utility/API for programmatically generating a native schematic/project. This is an unresolved verification issue—not proof that no supported utility exists in a particular installed release or support package.

Required next check when the user's machine is online:
1. Record the exact Proteus version and installed documentation/help.
2. Search the installed product directory and official downloads/help for supported automation interfaces and native project formats.
3. Validate any proposed generation route with a tiny native test project before building the full circuit generator.
4. If there is no supported official API, preserve REQ-PROT-001 and document an honest, tested fallback; do not fabricate a utility name, API, or import-validation result.

References:
- [Labcenter official schematic capture page](https://www.labcenter.com/schematic/)
- [Labcenter official downloads and utilities](https://www.labcenter.com/downloads/)

## 5. Decisions supported by S00

1. Keep the fixed hardware requirement: **original ESP32 + integrated TWAI + NXP TJA1051T/3 SO8**. No substitute is introduced.
2. Prefer ESP-IDF for the firmware foundation because the official ESP-IDF documentation provides the native TWAI driver and explicit mode/error behavior. Version selection remains pending local inspection.
3. Do not assign TXD/RXD GPIO numbers until the exact module/board is identified and boot-strapping/flash-reserved pin restrictions are checked against its datasheet.
4. Keep the device in listen-only and the transceiver's S input in a hardware-defined Silent state at startup. A UI-only TX checkbox is not a safety interlock.
5. Do not infer the vehicle bit rate, CAN/CAN-FD mode, identifiers, signal meanings, or diagnostic operations from the model/year alone.
6. Treat official Python-to-Proteus schematic generation as unconfirmed until verified against the installed version's official documentation/API.

## 6. Exit criteria and remaining work

S00 exit is blocked on local environment access. When the device reconnects, gather and record:
- OS/kernel and architecture; Python, Git, CMake and Ninja versions.
- Existing ESP-IDF and Arduino-ESP32 installations without installing or changing anything first.
- Exact board/module markings, ESP32 chip family, exposed pins and any attached serial device.
- Proteus installed/version/licensing availability and official automation/help documentation.
- Local repository status and whether any implementation changes exist outside the GitHub snapshot.

After evidence is collected, update `project/environment.yaml`, this report, the risk register, and `project/progress.json`. Then mark S00 complete only after its acceptance criteria are genuinely met. S01 schema/contract implementation work should proceed only after the unresolved environment/board decisions that affect the interfaces are documented.
