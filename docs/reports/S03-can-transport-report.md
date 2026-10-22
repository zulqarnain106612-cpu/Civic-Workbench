# S03 — CAN Receive/Guarded-TX Core and Serial Transport

**Stage status:** complete at the source/build/host-mock verification boundary.
**Date:** 2026-10-22
**Target:** original ESP32 integrated TWAI + NXP TJA1051 SO8 transceiver.
**Baseline commit:** S02 `365cc619cd0daf93fa32af60ad32e414645705ea`.

## 1. Scope and result

S03 turns the S02 firmware skeleton into a bounded CAN receive core with controller/loss telemetry, a versioned serial payload transport, a portable raw-frame JSON serializer, bus-off recovery entry points, and a centrally guarded single-frame C TX API.

The resulting code has been exercised with a native host mock of TWAI, GPIO and FreeRTOS queue/task interfaces and compiled for the original-ESP32 target profile. It has **not** been flashed to a physical board or tested on a real CAN bus or vehicle. The generic PlatformIO `esp32dev` target is a compile profile, not identification of the physical module.

## 2. CAN receive core

Implementation:
- `firmware/esp32/main/civic_can.c`
- `firmware/esp32/main/civic_can.h`

The firmware installs a bounded ESP-IDF TWAI RX queue and a bounded application-ingress queue, then starts a dedicated receive pump. Each dequeued TWAI frame is checked for Classical CAN DLC (0–8) and standard/extended ID width before it is copied into a frame record with monotonic observation time and raw bytes. Timestamp semantics are deliberately explicit: this is the time at which the firmware dequeues/observes the message, **not** a hardware Start-of-Frame timestamp.

The application queue is non-blocking and bounded. When it is full, the dropped-frame counter increments rather than overwriting queued frames or blocking the receive pump. A queue overflow while software TX is armed forces a disarm request. Malformed observations and application-queue drops have separate counters. TWAI status exposes driver queue depth, TX/RX error counters, TX failures, RX missed/overrun counts, arbitration losses, bus errors and controller state.

Controller state distinguishes `running`, `stopped`, `bus_off`, `recovering`, `error`, and `unknown`. Recovery must be explicitly requested from bus-off; restarting after recovery leaves software TX disarmed. This source-level API does not claim that recovery has been verified on a real controller.

## 3. TX authorization boundary

The source has one single-frame request path, `civic_can_transmit_guarded`, with checks for request shape, identifier range, DLC, bounded timeout, compiled TX capability, verified initialization/bitrate gates, software arm, physical-interlock feedback, controller state and a conservative pre-error-passive error-counter threshold.

Safety/configuration controls remain fail-closed:
- `CIVIC_ALLOW_HARDWARE_CAN_INIT` defaults off.
- `CIVIC_BITRATE_EVIDENCE_CONFIRMED` defaults off.
- `CIVIC_ALLOW_HARDWARE_CAN_TX` defaults off and depends on the two preceding options.
- GPIOs remain unassigned by default.
- A reviewed GPIO must be distinct, in range, and not reserved for flash, boot strapping, UART0 console, or another role.
- TWAI TX queue length is zero so frames do not accumulate for later transmission after a disarm/timeout.
- The firmware API does **not** expose a serial command that can arm or transmit; the wire protocol carries diagnostics/capture records only in this stage.

The transceiver's external Silent-mode bias and a physical gate that independently requires the hardware interlock remain the real electrical barrier. Software GPIO readback is not a replacement for that barrier. The mock-enabled compiler test exercises the C transmission path only under test configuration; the production project's default build does not enable hardware TX.

## 4. Serial protocol and versioned JSON

Files:
- `firmware/esp32/main/civic_transport.c/.h`
- `firmware/esp32/main/civic_transport_format.c/.h`
- `docs/protocol/firmware-serial-v1.md`
- `schemas/v1/device-status.schema.json`

Each firmware protocol record is one `CW1 `-prefixed JSON line. The firmware emits:
- `handshake` with firmware role/version and the supported schema/message types.
- `device_status` with controller state, configured bitrate or `null`, TX capability/arm state, software drops, malformed records, driver/application queue depth, TWAI error/failure/missed/overrun/arbitration/bus-error counts, cumulative drop count and structured fault codes.
- `can_frame` with UUID provenance, standard/extended identifier, frame type, DLC, raw bytes, monotonic timestamp, direction/capture source, controller state and adjacent loss-counter snapshots.

`device-status.schema.json` accepts either a trustworthy UTC timestamp or a monotonic-only timestamp with `clock_source: monotonic_only`. The device does not fabricate UTC. The transport preserves a frame's drop-counter snapshots; it does not substitute the latest total for the per-frame snapshot. Non-`CW1 ` ESP-IDF log lines are diagnostics, not protocol records.

The serial output tests compile and execute the actual firmware serializer on the host and validate every emitted record against the corresponding existing schema, including recovery state on both status and per-frame records, plus the explicit high-error-counter inhibit status.

## 5. Toolchain/build evidence

Pinned versions:
- PlatformIO Core **6.2.0**
- Espressif32 platform **6.9.0**
- ESP-IDF **5.3.1** (`framework-espidf 3.50301.0`)
- Xtensa ESP-ELF toolchain **13.2.0+20240530**
- CMake **3.16.4**, Ninja **1.7.1**, esptool **4.5.1**

Command:
```sh
cd firmware/esp32
~/.venvs/civic-workbench-pio/bin/pio run
```

The PlatformIO profile selects classic ESP32 (`--chip esp32`), generic `esp32dev`, and 4 MB flash for compile reproducibility. It is **not** permission to flash an unidentified physical board.

## 6. Automated validation

The complete command `make test` completed with **64 Python tests passed**, plus the standalone C safety-policy executable passed **7 assertions** with `gcc -std=c11 -Wall -Wextra -Werror -pedantic`.

More specific host integration evidence:
- The production CAN core (`civic_can.c`) plus safety modules compiled with strict warnings against mock TWAI/GPIO/FreeRTOS interfaces; **71 assertions passed** covering standard/extended frame ingress, invalid DLC/IDs, bounded-queue overflow/loss, blocked disarmed TX, guarded single-frame TX, interlock-open disarm, queue-overflow disarm and bus-off recovery/restart.
- The portable frame formatter passed **7 C assertions**; standard, extended, remote and recovering-state vectors were parsed and validated against the versioned raw-frame schema.
- Six serial integration tests passed; actual firmware handshake, disabled/running/recovering status and frame records were checked against the versioned schemas, including monotonic time, bitrate nullability, loss counters and fault codes.
- `python3 -m compileall -q src tests` passed.
- All **14** JSON Schemas passed Draft 2020-12 schema validation.
- All **9** project YAML files parsed, including requirement traceability.
- `git diff --check` passed.

Host-mock and schema evidence proves only the source contract/integration behavior exercised by those tests. It is not evidence that UART throughput/reconnect behavior, physical GPIO timing, real-controller bus-off, transceiver Silent-mode bias, or vehicle CAN acquisition works.

## 7. Exit criteria and explicit limitations

- [x] Original-ESP32 build target and S03 sources compile.
- [x] Bounded TWAI/application ingress and explicit drop/error counters.
- [x] Raw-frame records keep ID format, DLC, raw payload and monotonic observation provenance.
- [x] Schema-v1 handshake, status and CAN-frame serial payloads compile and validate.
- [x] Centralized guarded single-frame C TX API; production default remains TX-disabled/listen-only.
- [x] Host-mock tests exercise queue saturation, interlock-open disarm, TX gate request, and bus-off recovery/restart.
- [x] Progress and requirement traceability updated with scope/limitations.
- [ ] Actual board identity/pins/flash size confirmed — not available in the S00 inspection.
- [ ] Serial link tested on real hardware — not performed.
- [ ] Physical interlock and transceiver Silent mode bench-verified — not performed.
- [ ] Real bus/vehicle CAN capture/transmission tested — not performed.
- [ ] Serial TX command, TX repeat scheduling, UI controls and persistent TX audit — explicitly not in S03.
- [ ] Native Proteus schematic generation/import — remains S09.

## 8. Handoff

**S03 is complete at source/build/host-mock verification.** S04 (browser engineering UI) and S05 (session persistence/export) are ready as independent consumers of the versioned frame/status contracts. They must continue to label all mock/simulator data separately from physical captures. Any work that enables actual vehicle transmission still requires independently reviewed hardware and physical-interlock validation.
