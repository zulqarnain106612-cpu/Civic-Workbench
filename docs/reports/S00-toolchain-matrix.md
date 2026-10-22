# S00 — Toolchain and Hardware Matrix

**Inspection date:** 2026-10-22. Evidence was collected directly from `s752-LIFEBOOK-S752` via Desktop Commander. See `project/environment.yaml` for machine-readable details.

| Component | Observed value | State / implication |
|---|---|---|
| OS | Ubuntu 26.04.1 LTS | Verified |
| Kernel / architecture | Linux 7.0.0-38-generic / x86-64 | Verified |
| Python / pip | 3.14.4 / 25.1.1 | Verified |
| Git | 2.53.0 | Verified |
| PyYAML / pyserial | 6.0.3 / 3.5 | Installed in system Python |
| pytest / python-can / system esptool | Not installed | Needed for future tests/CAN tooling as appropriate |
| CMake / Ninja | Not found on PATH | Required by many ESP-IDF builds; select/install in S02 |
| ESP-IDF / `idf.py` | Not found; `IDF_PATH` unset | No standalone ESP-IDF environment verified |
| Arduino CLI | Not found on PATH | Not a blocker if building via ESP-IDF or PlatformIO |
| PlatformIO CLI | Not found on PATH | Cached framework packages exist; shell build is not currently ready |
| PlatformIO espressif32 | 6.9.0 | Cached under `~/.platformio/platforms` |
| Arduino framework package | 3.20017.241212+sha.dcc1105b | Cached under `~/.platformio/packages` |
| PlatformIO esptool package | 1.40501.0 | Cached |
| Xtensa toolchain | ESP32-S3 only, 8.4.0+2021r2-patch5 | Does not satisfy the required original ESP32 target |
| RISC-V toolchain | 8.4.0+2021r2-patch5 | Not the required original ESP32 target |
| Classic ESP32 Xtensa toolchain | Not found in inspected PlatformIO cache | Must be installed/resolved before compiling for original ESP32 |
| ESP32 board / module | Not identified | No board attached at inspection |
| Serial connection | No `/dev/ttyUSB*` or `/dev/ttyACM*`; no Espressif/USB-UART device in `lsusb` | Hardware was not connected/detected at inspection |
| NXP TJA1051 SO8 | Required by project spec | Physical possession not verified |
| Proteus | Installed in Wine, build identifier 8.3.19906.0 | Registry path label is “Proteus 8 Demonstration”; entitlement needs GUI/vendor confirmation |
| Proteus local help | `HELP/ISIS.chm` exists | Present; full CHM content not extracted in this command session |
| Proteus “Generator Scripts” | Eight `.pdsprj` examples | Simulation examples, not Python native-schematic generator |
| Official Python native schematic utility/API | Not confirmed | Must investigate with the installed help/vendor before S09 implementation |

## Decisions

1. Keep **original ESP32 + integrated TWAI + NXP TJA1051 SO8** as the sole hardware baseline.
2. Do not assume that the cached ESP32-S3 compiler or RISC-V compiler can compile for original ESP32.
3. Do not install packages during discovery; record the current environment first. S02 will select and pin a reproducible build route.
4. Keep the default boot/safety state passive, with hardware-enforced TX inhibition.
5. Do not set board GPIOs without exact board/module identification.
6. Proteus is available on the machine but active license features are unverified. S09 must prove native import/render, not only generate a file.
7. Do not call the local waveform/stimulus sample projects a schematic-generation API.
