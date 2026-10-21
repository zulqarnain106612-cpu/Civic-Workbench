# S02 — Hardware Design and Firmware Foundation

**Status: COMPLETE for the source/build foundation.**  
**Date:** 2026-10-22  
**Repository baseline:** S01 commit `007e5bfed74d5832a91b3ea0154139e6ddc4744d`

## 1. Result

The project now has a reproducible PlatformIO/ESP-IDF target for the **original ESP32** (not ESP32-S2/S3/C3), a compiling TWAI receive-only firmware skeleton, a fail-closed firmware safety-policy module, a machine-readable TJA1051T/3 pin-to-net contract, and a hardware interlock design note. S02 provides no physical CAN transmit API.

The local build profile is the generic PlatformIO `esp32dev` profile, set to a 4 MB flash configuration for compile reproducibility. This is **not** identification of the physical board and must not be flashed onto an unidentified module. At S00 the actual board was not connected/detected. No firmware was flashed, no physical transceiver was electrically tested, and no vehicle CAN wires were connected.

## 2. Pinned build path

The firmware build runs in an isolated Python virtual environment at `~/.venvs/civic-workbench-pio`; it does not require changing system Python. Source-controlled pins/configuration:

- PlatformIO Core: **6.2.0** (`tools/requirements-platformio.txt`)
- PlatformIO ESP32 platform: **6.9.0** (`platformio.ini`)
- ESP-IDF resolved through PlatformIO: **5.3.1** (package `framework-espidf 3.50301.0`)
- Original ESP32 Xtensa compiler: **13.2.0+20240530**
- CMake: **3.16.4**
- Ninja: **1.7.1**
- esptool: **4.5.1** (PlatformIO package `tool-esptoolpy 1.40501.0`)

Build command:

```sh
cd firmware/esp32
~/.venvs/civic-workbench-pio/bin/pio run
```

The final clean-configuration build completed with **SUCCESS, exit code 0** after generating both `firmware.elf` and `firmware.bin`. The invocation identified `PLATFORM: Espressif 32 (6.9.0)`, `HARDWARE: ESP32 240MHz, 320KB RAM, 4MB Flash`, and used `--chip esp32`. The final build emitted no flash-size mismatch or unassigned-GPIO shift warnings.

Final reported sizes:
- RAM: **10,788 / 327,680 bytes (3.3%)**.
- Application flash: **161,588 / 1,048,576 bytes (15.4%)** of the configured application region.
- These are build-profile numbers, not measurement from the physical board.

## 3. Firmware foundation

Files under `firmware/esp32/main/`:
- `app_main.c` — safe boot/status loop; if hardware capture is unavailable it remains alive and inhibited; received frames log ID format, type, DLC, dequeue-observation timestamp and raw payload bytes.
- `civic_can.c/.h` — ESP-IDF 5.3.1 TWAI initialization/receive/status interface; data frame records preserve ID, standard/extended flag, DLC, bytes, remote-frame flag and monotonic application dequeue time.
- `civic_safety.c/.h` — default-inactive TX request output initializer.
- `civic_safety_policy.c/.h` — pure fail-closed policy calculation isolated for native host testing.
- `Kconfig.projbuild` — explicit configuration gates.

The timestamp is intentionally called an **observation/dequeue timestamp**. It is not a hardware start-of-frame timestamp. ESP-IDF 5.3.1's `twai_message_t` does not expose the per-message overrun field used by earlier design drafts; controller/queue loss statistics are exposed through `twai_get_status_info` instead.

## 4. Fail-closed startup and pin configuration

- TWAI mode is explicitly `TWAI_MODE_LISTEN_ONLY`.
- No `twai_transmit` or equivalent transmit call exists in the S02 driver.
- TWAI initialization defaults disabled (`CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT=n)).
- Bitrate evidence confirmation defaults disabled (`CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED=n)).
- TWAI TX/RX GPIOs, gate-request GPIO and interlock-feedback GPIO default to **-1 (unassigned)**.
- The numeric bitrate default in Kconfig is a compile-time placeholder only. The firmware refuses initialization unless bitrate evidence is explicitly confirmed, initialization is enabled, all GPIOs are valid and distinct, and the GPIO checks reject original-ESP32 flash-connected and boot-strapping pins.
- Before configuring the hardware-gate output, the safety initializer rejects an unassigned/unsafe GPIO, keeps an external pull-down on the MCU gate request, then drives the gate request LOW (inactive).
- The external hardware remains the actual safety barrier: the transceiver S pin must be biased HIGH independently so a reset, unpowered MCU, or inactive/failed gate request leaves the transceiver in Silent mode.

No physical gate was built or measured during S02. Software checks are not proof of electrical interlock performance.

## 5. Hardware source baseline

- `hardware/reference/esp32-tja1051t3-netlist.yaml` defines the required pin-to-net relationship for **NXP TJA1051T/3 SO8 (SOT96-1)**. MCU GPIO assignments remain null until the board is identified.
- `hardware/reference/safety-interlock.md` describes power ranges, pin 5 VIO, pin 8 S mode, external Silent-mode bias, interlock topology requirements, termination caveats and evidence that must precede vehicle attachment.
- Source reference: [NXP TJA1051 official datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf).
- TWAI implementation reference: [Espressif ESP-IDF TWAI documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/twai.html).

S02 delivered the source-level hardware connection contract and review note, **not** a generated/validated native Proteus schematic. Native Proteus generation/import validation remains assigned to S09; no unsupported Python API was fabricated.

## 6. Verification evidence

The final verification command set:

```sh
make test
python3 -m compileall -q src tests
# JSON Schema, YAML, progress ledger validation
git diff --check
cd firmware/esp32
~/.venvs/civic-workbench-pio/bin/pio run
```

Results:
- **51 Python unit/contract/source-guard tests passed**.
- The host-compiled C safety policy passed **7 assertions** with `gcc -std=c11 -Wall -Wextra -Werror -pedantic`.
- All 14 S01 JSON Schemas passed Draft 2020-12 meta-schema validation.
- Project YAML documents (including the hardware netlist contract) and the progress JSON parsed successfully.
- Python compilation passed.
- `git diff --check` passed.
- Clean original-ESP32 PlatformIO build completed successfully as described above.

These results establish source-contract and build-profile correctness. They do not establish physical CAN operation, a working vehicle connection, pin compatibility with the as-yet unidentified board, or electrical safety of an assembled interlock.

## 7. S02 exit checklist

- [x] Original ESP32 target selected; incompatible S3/C3/RISC-V target not substituted.
- [x] Pinned build environment installed in isolated Python venv.
- [x] Clean PlatformIO build for original ESP32 passed.
- [x] TWAI receive/status skeleton implemented in Listen Only.
- [x] No S02 CAN transmit path.
- [x] TX request, bitrate evidence and hardware-init switches fail closed by default.
- [x] Unassigned/reused/flash/strapping GPIO guard and tests added.
- [x] NXP TJA1051T/3 pin-to-net/source contract recorded.
- [x] Unit, contract, source-guard and native C safety-policy tests passed.
- [ ] Exact physical ESP32 board/module and actual GPIOs identified — no board was detected during S00.
- [ ] Physical transceiver/assembled hardware and hardware-only interlock bench-verified — not performed.
- [ ] Native Proteus project generated/imported — downstream S09.

## 8. Handoff

**S02 is complete at the firmware/source/build-foundation boundary.** S03 can now define and implement the capture/transport protocol, bounded buffering/queues, loss/error telemetry, and centrally guarded TX APIs using the compiled foundation. Its active transmission work must remain disabled until the firmware authorization and independent physical inhibit are implemented/tested. Exact board pins, actual vehicle bitrate/topology, physical electrical validation and the native Proteus artifact remain explicitly unverified.
