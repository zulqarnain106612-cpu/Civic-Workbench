# Civic-Workbench Contract Set — Version 1

**Status:** S01 interface baseline; these contracts define data boundaries, not completed drivers or services.

## Contract files

| Contract | JSON Schema |
|---|---|
| Raw Classical CAN frame | `schemas/v1/can-frame.schema.json` |
| Capture session manifest and storage references | `schemas/v1/capture-session.schema.json` |
| Analysis finding / inferred mapping annotation | `schemas/v1/analysis-finding.schema.json` |
| Evidence-backed diagnostic capability | `schemas/v1/diagnostic-capability.schema.json` |
| Bounded raw-CAN TX request | `schemas/v1/tx-request.schema.json` |
| Safety-state snapshot | `schemas/v1/safety-state.schema.json` |
| Versioned request/event envelope | `schemas/v1/transport-envelope.schema.json` |
| Handshake, device status, capture start/stop | `schemas/v1/handshake.schema.json`, `device-status.schema.json`, `capture-start.schema.json`, `capture-stop.schema.json` |
| TX cancellation/result and structured errors | `schemas/v1/tx-cancel.schema.json`, `tx-result.schema.json`, `error-event.schema.json` |
| Logical host API | `contracts/openapi.yaml` |
| Reference semantic validator | `src/civic_workbench/contracts.py` |

All JSON Schemas use Draft 2020-12 and reject unknown properties unless an explicitly extensible map is defined. Schema version 1 fields must not be silently reinterpreted. Breaking changes require a new version and migration strategy.

## Raw frame and session rules

- CAN identifiers are integers. Standard identifiers are limited to 11 bits (0x000–0x7FF); extended identifiers are limited to 29 bits (0x00000000–0x1FFFFFFF).
- This baseline describes Classical CAN: DLC is 0–8. CAN-FD is not represented as supported by this contract.
- A data frame payload contains exactly DLC bytes; each byte is 0–255. A remote frame has an empty payload, with DLC retained as the requested length.
- The original raw frame is immutable after ingestion. Decode results, candidate mappings, user interpretations and analysis results are separate records referring to source frame IDs.
- Monotonic nanoseconds are the ordering/timing basis for a capture process. UTC timestamps may be absent for frames captured without a reliable wall clock.
- A session manifest describes capture configuration, source/provenance, software/firmware versions, record/drop counts and the relative raw-capture location. A raw-capture location must be a safe POSIX relative path: absolute paths, drive-prefixed paths, backslashes and parent traversal are rejected. A null bitrate means it is not yet established; do not fill it by guessing. A hardware capture-start request must be rejected until a valid bitrate is explicitly selected from trustworthy evidence or otherwise established.

## Firmware clock and status semantics

- Version-1 device status accepts a trustworthy `observed_at_utc` or a monotonic-only `observed_monotonic_ns` with `clock_source: monotonic_only`. Firmware must not invent UTC values when no reliable wall clock has been established.
- The original-ESP32 S03 serial wire transport emits `CW1 ` followed by a schema-v1 JSON payload and newline. Only this prefix identifies a protocol record; other UART console lines are diagnostics.
- The firmware `device_status` record provides controller state (including `recovering`), bitrate or `null`, TX-capability/arm state, driver and app queue depth, TWAI error counters, missed/overrun/failed-frame counters, arbitration loss, bus errors, malformed observations, software drops, a cumulative drop total, and structured fault codes. Queue depth is not a loss count.
- `captured_monotonic_ns` is the device's frame observation/dequeue time. It is not a hardware start-of-frame timestamp. The host may attach its own UTC envelope timestamp but must preserve the original monotonic value and source provenance.
- Firmware frame and status telemetry are diagnostic data. They do not authorize transmission. In S03, the single-frame C TX API is gated and not exposed as a serial command; browser TX controls, repeat scheduling and persistent TX audit records remain downstream work.

## Analysis and capability rules

- Findings always reference one or more existing frame UUIDs and state the method and confidence.
- `observed`, `candidate`, and `validated` are distinct claims. A `validated` finding requires a validation method, timestamp and evidence references.
- A candidate signal bit range must fit within the 64-bit Classical CAN data field. Endianness, signedness, scale, offset and units remain unknown unless supported.
- A diagnostic capability is usable only when `status=supported`, `enabled=true`, and evidence is supplied. Both `unknown` and `unsupported` must be disabled. The schema does not encode or assume any Honda-specific ECU address or service.

## Transmission request and safety rules

A `tx-request` is a **request**, never a permission grant. Its bounded repeat count, cadence, timeout, identifier format, frame type, DLC and payload must be validated. The planned repeat schedule must fit within the request timeout. The later TX scheduler/firmware must additionally enforce configured rate, repeat and bus-policy limits.

A safety snapshot may set `tx_permitted=true` only if all the following are true simultaneously:
1. Mode is `normal`.
2. Software is explicitly armed.
3. The hardware interlock is active/closed.
4. Controller state is `running`.
5. No faults are present.
6. State age is at most 500 ms.
7. Any arm lease has not expired.

The 500 ms freshness threshold is a v1 control-plane fail-closed threshold, not a measured vehicle timing property. The firmware and physical interlock remain authoritative and must independently deny transmission at send time. Missing/stale/unknown status, disconnect, controller error/bus-off, reset, disarm or a fault must inhibit pending TX. Browser state alone cannot authorize it.

## Envelope and API behavior

The envelope provides a UUID message ID, schema version, message type, UTC issue time, sequence number, optional correlation/session IDs, optional sender identity and a JSON-object payload. Sequences are monotonic per sender/connection. Receivers reject unknown message types and invalid known payloads; reconnects require a new hello/capabilities handshake.

The REST surface is defined by `contracts/openapi.yaml`. Streaming may use WebSocket under the same event-envelope contract, but transport details must be selected before implementation. Responses distinguish request acceptance from completed transmission. TX queue/cancel operations must be auditable and idempotent by request UUID; retries must not accidentally enqueue duplicate physical sends.

## Verification and implementation boundary

Run:

```sh
python3 -m unittest discover -s tests -v
```

The tests validate the schema documents, representative accepted/rejected data, cross-field constraints, schema versioning, TX safety gates, recursive known-event validation, YAML configuration and the dependency DAG. Passing tests prove contract correctness only; they do not prove live CAN, hardware, UI, persistence service, or vehicle compatibility.
