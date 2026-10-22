# S00 — Environment and Repository Discovery

**Status: COMPLETE (2026-10-22).** S00 acceptance criteria are satisfied: the local checkout and repository map were inspected, host/tool availability was recorded, the ESP32 framework options were investigated, and Proteus availability and the schematic-generation gap were documented. Open board-specific and vendor-API questions are assigned to downstream stages; they do not make the environment inventory itself incomplete.

## 1. Repository and local checkout

- Repository: [Civic-Workbench](https://github.com/zulqarnain106612-cpu/Civic-Workbench)
- Local project path: `/home/s752/Civic-Workbench`
- Branch: `main`, tracking `origin/main`
- Snapshot before S00 completion commit: `e1da89a9cf60b3982f7a40a9536b044d331b3f32`
- Initial inspection found the requested local directory empty, with no files or Git metadata. It was therefore safe to clone the remote repository into that empty directory. Clone completed successfully and local `main` matched `origin/main`.
- The existing `/home/s752/Workspace` Git repository was left untouched.
- This is an independent repository; no source was copied from `build-a-web-page-for-ios`.

## 2. Host facts observed directly

| Item | Observed value |
|---|---|
| Hostname | `s752-LIFEBOOK-S752` |
| Operating system | Ubuntu 26.04.1 LTS |
| Kernel | Linux 7.0.0-38-generic |
| Architecture | x86-64 |
| Python | 3.14.4 |
| pip | 25.1.1 |
| Git | 2.53.0 |
| PyYAML | 6.0.3 |
| pyserial | 3.5 |
| pytest | Not installed in system Python |
| python-can | Not installed in system Python |
| esptool in system Python | Not installed |

`cmake`, `ninja`, `idf.py`, `esptool.py`, and `arduino-cli` were not found on `PATH`. `IDF_PATH` and `VIRTUAL_ENV` were unset. This is a snapshot of the current shell; it is not a claim that a utility cannot exist in any unsearched path.

## 3. ESP32 firmware environment

The machine has a PlatformIO package cache under `/home/s752/.platformio`, but the `pio`/PlatformIO CLI is not available on `PATH`. Inspected package manifests reported:

- PlatformIO `espressif32` platform: `6.9.0`.
- Arduino framework package `framework-arduinoespressif32`: `3.20017.241212+sha.dcc1105b`.
- PlatformIO `tool-esptoolpy`: `1.40501.0`.
- Cached Xtensa compiler package is for **ESP32-S3**, version `8.4.0+2021r2-patch5`.
- Cached RISC-V compiler package is `toolchain-riscv32-esp`, version `8.4.0+2021r2-patch5`.
- No classic ESP32 `toolchain-xtensa-esp32` package or standalone ESP-IDF installation was found in the inspected locations.

**Decision:** do not begin a firmware build on the assumption that this is already a configured original-ESP32 environment. The target remains the original ESP32 with integrated TWAI; not ESP32-S3/C3. S02 must install/select a reproducible toolchain after the exact target configuration is confirmed. Keep the source project portable and lock exact versions in repository configuration as part of S02.

## 4. Connected hardware

No `/dev/ttyUSB*` or `/dev/ttyACM*` device was present at inspection time, and `lsusb` showed no Espressif device or recognizable USB-UART bridge. Therefore:
- An ESP32 board was not connected/detected during this inspection.
- Exact board/module, chip marking, accessible GPIOs, and strap/flash-reserved pins remain unknown.
- Physical possession of the required NXP TJA1051 SO8 is not verified.
- The vehicle bus bit rate, topology, frame format, connector/capture point, and identifiers have not been measured.

These are recorded as open hardware/vehicle dependencies, not guessed. Do not select TXD/RXD GPIOs or active vehicle transmission settings until supported by the exact board and network evidence.

## 5. Proteus installation and Python generator investigation

Proteus is installed under Wine at:

`/home/s752/.wine-proteus/drive_c/Program Files (x86)/Labcenter Electronics/Proteus 8 Professional`

The main executable `BIN/PDS.EXE` and local `HELP/ISIS.chm` exist. The installed user registry path contains `install_8.3.19906.0`, identifying build `8.3.19906.0`. Its user profile path is labelled **Proteus 8 Demonstration**; the live activation/license entitlement was not verified, so this should not be represented as a confirmed fully licensed Professional installation.

The local `SAMPLES/Generator Scripts` directory contains eight `.pdsprj` examples (signal/waveform/stimulus generator simulation projects). These are not a Python utility for generating a native schematic from source. Public Labcenter resources reviewed document schematic capture, samples, downloads, and tutorials, but did not confirm an official Python API/utility that programmatically generates native `.DSN`/`.pdsprj` schematics. No native import/render validation was performed.

**Decision for S09:** preserve the requirement to generate a native Proteus project from Python, but do not invent or falsely label an official API. Before choosing implementation, inspect the installed ISIS help in detail or obtain a direct answer from Labcenter support. Then validate the chosen native-file or automation route using a minimal generated project opened by the installed Proteus build. A static image or simulation stimulus project is not an acceptable substitute.

Official references:
- [Espressif ESP-IDF TWAI documentation for original ESP32](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32/api-reference/peripherals/twai.html)
- [Espressif original ESP32 datasheet](https://documentation.espressif.com/esp32_datasheet_en.pdf)
- [NXP TJA1051 official datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf)
- [Labcenter schematic capture](https://www.labcenter.com/schematic/)
- [Labcenter downloads and utilities](https://www.labcenter.com/downloads/)

## 6. Hardware facts relevant to downstream work

The primary design target remains **original ESP32 + integrated TWAI + NXP TJA1051 SO8 (SOT96-1)**. The original ESP32 has a TWAI controller but no integrated CAN physical-layer transceiver and its TWAI controller is Classical CAN, not CAN FD. The NXP datasheet describes variant-specific electrical details. Because the exact physical item is specified as NXP TJA1051 marked NXP TJA1051 25 06 ND312 without an inferred suffix, pin 5 must not be assigned as VIO until its function is confirmed for that item. No substitute is authorized.

These are component documentation facts only, not proof of a built circuit or vehicle compatibility.

## 7. S00 exit checklist

- [x] Local repository path, branch, remote, HEAD and initial tree inspected.
- [x] Empty local project directory safely populated by cloning the intended remote.
- [x] Host OS/architecture and available core build tools recorded.
- [x] Python and relevant installed/missing packages recorded.
- [x] PlatformIO cache and its actual target-specific compiler packages inspected.
- [x] ESP-IDF/Arduino toolchain readiness assessed without installing packages or changing system configuration.
- [x] Proteus installation, build indicator, help file, and local generator samples inspected.
- [x] Python-to-native-schematic API gap recorded without fabricating support.
- [x] Exact target hardware and no-source-copy constraint retained.
- [x] Open board/network/licensing/API facts assigned to downstream stages.
- [ ] No physical build or vehicle test was attempted; not an S00 acceptance criterion.

## 8. Handoff to S01

S00 is complete. S01 is now the next ready stage: implement the versioned frame/session/analysis/TX/safety schemas and contract tests. The exact board/GPIO and firmware toolchain must be decided before S02 firmware/hardware acceptance; Proteus API validation stays open for S09. No firmware, UI, native schematic, vehicle mapping, or physical test is claimed complete.
