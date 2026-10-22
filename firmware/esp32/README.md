# Original ESP32 Firmware

## Scope

S03 extends the S02 original-ESP32 foundation into a bounded TWAI receive core, controller diagnostics/recovery surface, schema-v1 JSON record formatting, prefixed serial telemetry and a centrally guarded single-frame TX API.

Fixed hardware baseline: **ESP32S NodeMCU / NodeMCU-32S (classic ESP32 with integrated TWAI) + NXP TJA1051T/3 SO8 (SOT96-1)**. The PlatformIO board target is nodemcu-32s (4 MB profile). TWAI source mapping: GPIO21 TX, GPIO22 RX. The reported transceiver top marking is recorded verbatim as NXP TJA1051 25 06 ND312; no successor, predecessor or substitute part is permitted. Runtime hardware initialization, bitrate authorization, and physical TX remain disabled until the actual board revision/header continuity, exact IC orientation, circuit and bitrate are checked.

## Build

Use the pinned isolated PlatformIO environment:

```sh
~/.venvs/civic-workbench-pio/bin/pio --version
cd firmware/esp32
~/.venvs/civic-workbench-pio/bin/pio run
```

Pins: PlatformIO Core 6.2.0, Espressif32 platform 6.9.0, ESP-IDF 5.3.1, Xtensa toolchain 13.2.0+20240530. Do not silently upgrade platform/framework dependencies.

## Receive path and telemetry

The TWAI driver uses a bounded driver-owned RX queue plus a bounded FreeRTOS application-ingress queue. A dedicated receive-pump validates identifier width and DLC, stamps the dequeue observation time, copies raw bytes, and increments explicit software drops when the application queue is full. Diagnostics report driver RX queue depth, app queue depth, malformed observations, TWAI missed/overrun counts, controller state, error counters and loss categories.

The serial wire format is defined in [firmware-serial-v1.md](../../docs/protocol/firmware-serial-v1.md). Each protocol record is prefixed with `CW1 `; non-prefixed ESP-IDF log lines are diagnostic output. Time is monotonic observation time, not a hardware wire timestamp or fabricated UTC wall-clock time.

## TX safety boundary

- `CIVIC_ALLOW_HARDWARE_CAN_INIT` defaults off.
- `CIVIC_BITRATE_EVIDENCE_CONFIRMED` defaults off.
- `CIVIC_ALLOW_HARDWARE_CAN_TX` defaults off and depends on the other two gates.
- GPIO21/TWAI_TX and GPIO22/TWAI_RX are mapped for the specified NodeMCU-32S; the physical header continuity/revision still requires bench confirmation.
- The transceiver S pin must remain externally biased HIGH for this receive-only baseline; do not drive it directly from the MCU.
- When TX capability is not explicitly built in, TWAI remains `TWAI_MODE_LISTEN_ONLY`.
- TX queue length is configured as zero; the one-frame guarded API validates the request and requires software arm, an active interlock sense, a healthy running controller and reviewed configuration.
- Software disarm requests the inactive level on the TX-gate request GPIO. The external hardware interlock and external default-inactive transceiver Silent bias remain essential; software is not the independent safety barrier.
- This stage does not provide periodic/repeated TX scheduling, diagnostic workflows, a browser/serial command to arm TX, or persistent TX audit storage. Those remain downstream work.

## Test scope

`make test` runs repository contracts, firmware source guards, a native C safety policy test, and a native host-compiled JSON formatter validated against the JSON Schemas. `make firmware-build` calls the pinned PlatformIO executable if it is on PATH; otherwise run the explicit command above.

Host checks and compilation do not substitute for serial-link, isolated-bench, physical interlock, or vehicle tests. No physical board or vehicle was exercised for S03.
