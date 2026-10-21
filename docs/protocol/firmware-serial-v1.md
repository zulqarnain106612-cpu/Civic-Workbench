# Firmware Serial Protocol v1

**Status:** source-level protocol contract; no physical serial-link or host integration test has been performed.

## Framing

Each firmware-to-host protocol record is one UTF-8 line:

```text
CW1 <JSON-object>\n
```

The host should discard or route to a diagnostic view any line that does not start with the exact `CW1 ` prefix. ESP-IDF log output is not a protocol record. The JSON object is a direct versioned payload record, not yet the outer `transport-envelope.schema.json` envelope. A host bridge can validate the payload using its `record_type` schema and wrap it in an envelope with host-observed UTC time, sequence, sender and correlation metadata.

## Record types emitted

- `handshake`: protocol/schema versions, firmware role/id/version, and supported record/message types.
- `device_status`: connected state, controller state, configured bitrate (or `null` if the driver is not installed), cumulative observed loss count and structured fault codes.
- `can_frame`: immutable raw observation record with session/frame UUIDs, arbitration ID, standard/extended flag, frame type, DLC, raw payload, monotonic timestamp, direction, capture source, controller state and adjacent loss counters.

## Time semantics

Firmware reports `observed_monotonic_ns` for status and `captured_monotonic_ns` for frames. These are derived from the ESP-IDF monotonic timer at observation/dequeue time; they are **not** hardware start-of-frame timestamps and are not Unix time. The device does not invent a UTC timestamp without an established wall-clock source. The `clock_source` is `monotonic_only`.

## RX loss semantics

The frame record's `dropped_frames_before` and `dropped_frames_after` preserve the software application-ingress drop-counter snapshots captured with the queued frame and when the host-facing receive API dequeues it. Device status combines the software-ingress drop count with ESP-IDF TWAI driver's `rx_missed_count` and `rx_overrun_count`; individual categories are preserved in the `faults` list. Queue depth and error/arbitration counters are also visible in the firmware diagnostic log. The host must not interpret queue depth as a loss count.

The device-status payload exposes cumulative `dropped_frames_total`, `software_dropped_frames`, `malformed_frames`, driver/application queue depths, TWAI error counters, TX failures, missed/overrun counts, arbitration losses, bus errors, and the capability/armed booleans. Counts can be correlated to raw frame/session provenance; raw payload bytes are never replaced by decoded signals.

## TX boundary

S03 exposes a single-frame C API named `civic_can_transmit_guarded`; it is not exposed as a serial command in this protocol revision. Its build capability is disabled by default. TX queueing is disabled so an accepted/disarmed request cannot linger in the driver TX queue. Repeat scheduling, audit persistence, diagnostics, browser controls and a serial command endpoint remain later-stage work. No record or request itself authorizes TX; the firmware checks software arm, configured capability, controller health, fault counters and physical interlock, while the independent hardware gate remains the final electrical barrier.

## Verification limits

Host tests compile the JSON frame formatter natively and validate standard, extended and remote test vectors against the repository's schema. This is deterministic host evidence only. It does not prove UART framing, throughput, reconnect behavior, ESP32 timing, physical CAN reception, or vehicle compatibility.
