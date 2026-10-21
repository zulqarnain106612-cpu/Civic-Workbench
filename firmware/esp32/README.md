# ESP32 Firmware Foundation

## Target and scope

This project targets the **original Espressif ESP32** with its integrated TWAI controller and the required external NXP TJA1051T/3 SO8 transceiver. The generic PlatformIO board target is used only to prove code compiles for the classic ESP32 family; it is not a verified physical-board definition.

S02 provides the build skeleton, passive TWAI receive loop, controller status API, frame representation and safety-policy foundation. **There is no hardware transmit API in S02.** Active TX is a later stage and must pass the physical interlock and firmware-side guards.

## Build

The root Linux environment was inspected on 2026-10-22. It does not have standalone ESP-IDF or the PlatformIO CLI on PATH. A separate isolated PlatformIO venv is used on that host:

```sh
python3 -m venv ~/.venvs/civic-workbench-pio
~/.venvs/civic-workbench-pio/bin/python -m pip install -r tools/requirements-platformio.txt
cd firmware/esp32
~/.venvs/civic-workbench-pio/bin/pio run
```

The project pins PlatformIO's ESP32 platform to 6.9.0. Actual resolved toolchain/framework package versions and build output must be recorded in the S02 stage report. Avoid silently updating the platform or framework.

## Why the safe defaults do not start CAN

The exact ESP32 module is not yet identified and no board was detected during S00. Therefore all GPIO selectors default to -1, CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT defaults disabled, and CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED defaults disabled. The numeric bitrate default exists only so the generic compile-time timing selection can be type-checked; it is **not** a measured or recommended vehicle bitrate. Firmware must refuse controller initialization unless the evidence-confirmation and explicit enable flags are set and real TX/RX/interlock GPIOs have been reviewed.

Do not flash this generic build to a board or connect it to the vehicle. A board-specific config must be produced only after reading the exact module/board marking and reviewing GPIO strapping, flash/PSRAM use, and the hardware gate circuit.

## References

- [Espressif ESP-IDF TWAI guide for ESP32](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/twai.html)
- [NXP TJA1051 datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf)
- Hardware inhibit rationale: [hardware/reference/safety-interlock.md](../../hardware/reference/safety-interlock.md)
