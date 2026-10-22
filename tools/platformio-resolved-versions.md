# Firmware Toolchain Lock and Resolution

## Requested project pins

- PlatformIO Core: 6.2.0 (`tools/requirements-platformio.txt`)
- PlatformIO Espressif32 platform: 6.9.0 (`firmware/esp32/platformio.ini`)
- PlatformIO board target: nodemcu-32s (the specified NodeMCU-32S / classic ESP32 board; 4 MB board profile). Physical PCB revision and flash contents have not been independently inspected.
- Framework: ESP-IDF via PlatformIO package `framework-espidf)

## Resolved package versions observed in the successful build

| Component | Resolved version |
|---|---|
| PlatformIO Core | 6.2.0 |
| Platform | espressif32 6.9.0 |
| ESP-IDF | 5.3.1 (`framework-espidf` 3.50301.0) |
| Xtensa ESP-ELF GCC toolchain | 13.2.0+20240530 |
| CMake | 3.16.4 |
| Ninja | 1.7.1 |
| esptool | 4.5.1 (`tool-esptoolpy` 1.40501.0) |
| ESP32 ULP toolchain | 2.38.0 (`toolchain-esp32ulp` 1.23800.240113) |

Build evidence: `docs/reports/S02-firmware-report.md`.

Keep generated sdkconfig.esp32dev and PlatformIO .pio/ files out of Git; the reproducible project defaults are firmware/esp32/sdkconfig.defaults, platformio.ini, and main/Kconfig.projbuild. The environment name remains esp32dev for compatibility, while its selected board definition is nodemcu-32s. If the pinned platform resolves different package versions in a future clean environment, capture and review those changes explicitly instead of silently upgrading.

**Flash warning:** the 4 MB setting is for the generic compile profile, not evidence about the physical board's flash size. Do not flash this profile until the exact module/board is identified and its flash layout is confirmed.
