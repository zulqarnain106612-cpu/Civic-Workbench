# S00 — Toolchain and Hardware Matrix

The machine-specific rows are currently unverified because the linked Desktop Commander device is offline. Do not read "unknown" as "missing" or install a second copy before inspection.

| Component | Required/considered role | Observed status | Verification action |
|---|---|---|---|
| User development OS/architecture | Determines toolchain commands and native Proteus availability | Unknown | Run OS release and architecture commands on the connected device |
| Python 3 | Python analysis, tooling and Proteus generator | Unknown | `python3 --version`, `python3 -m pip --version` |
| Git | Repository and traceability | Unknown on device | `git --version`; `git status --short --branch` in project folder |
| CMake + Ninja | ESP-IDF build | Unknown | `cmake --version`, `ninja --version` |
| ESP-IDF | Recommended firmware framework for native TWAI driver | Unknown | Check `IDF_PATH`, source install/export script only after locating it, then `idf.py --version` |
| Arduino-ESP32 | Alternative framework only if local constraints justify it | Unknown | Check installed core and examples; do not create a duplicate installation without need |
| Original ESP32 board/module | Defines GPIO availability, flash/PSRAM pins and boot strapping | Exact board unknown | Record module marking, chip identification, board model and exposed GPIOs |
| USB serial/flash path | Flashing and device logging | Unknown | Enumerate serial ports and note USB-UART/USB device identification |
| NXP TJA1051T/3 SO8 | Required CAN physical layer | Project requirement; physical possession not verified | Inspect part marking/package and verify pin 1 orientation before schematic review |
| Proteus Design Suite | Native schematic/project generation and validation | Installed/version unknown | Inspect installed app, Help/About, licensed modules, installed docs and examples |
| Official Proteus Python automation | Required by desired delivery, but support path not identified from public pages checked | Unconfirmed | Check installed official help/API and ask Labcenter support if documentation is absent |
| Repository checkout | Actual working tree may differ from GitHub | Desktop offline; local status unknown | Once online, inspect `git remote -v`, `git status`, branch and HEAD; avoid destructive sync |

## Firmware recommendation

Use the official ESP-IDF TWAI driver as the default firmware foundation. The original ESP32 has a TWAI controller but no integrated physical-layer transceiver; the fixed external TJA1051T/3 provides that layer. This ESP32 controller supports Classical CAN frames, not CAN FD. Confirm all assumptions against the selected exact ESP32/module and currently installed ESP-IDF documentation before pinning versions or writing hardware configuration.

Reference: https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32/api-reference/peripherals/twai.html

## First diagnostic session after reconnection

Run read-only inspection first and capture concise output:
1. OS and architecture.
2. Python, Git, CMake, Ninja versions.
3. ESP-IDF path/version and installed toolchains.
4. Existing Arduino-ESP32 versions, if present.
5. Exact board/module markings and serial port.
6. Proteus version, components/libraries, and official automation/help references.
7. Local repository remote, branch, HEAD and dirty status.

Do not flash the ESP32, change installed toolchains, alter repository branches, or connect the CAN wires to the vehicle during S00.
