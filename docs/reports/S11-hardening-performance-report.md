# S11 — Hardening, Fault Model and Performance

## Hardening delivered

- The unauthenticated service only binds to loopback, validates the Host header and rejects cross-origin POST requests. It emits CSP, nosniff, no-referrer and no-store headers.
- JSON bodies are limited to 4 MiB; identifier/DLC/bit-range shapes, import counts, replay counts, virtual pending-event counts and per-step emitted events are bounded.
- Raw frames are append-only until a session is finalized; frame records cannot be appended to closed sessions and are immutable relative to analysis annotations.
- Serial input is read-only, accepts only CW1-prefixed records, rejects malformed/schema-invalid/oversized lines, and does not issue firmware commands.
- The simulator and TX scheduler never route to the physical TWAI send function. The host safety state always reports tx_permitted=false and a not-verified physical interlock.
- Firmware remains Listen Only / TX-inhibited by default and the exact GPIO map and bitrate evidence remain unconfigured until reviewed.

## Performance method

tools/benchmark.py measures batch SQLite ingest and heuristic analysis against bounded, generated synthetic traces. It writes the run’s environment and measured rates to docs/reports/S11-benchmark-results.json. The report is host-specific descriptive evidence, not a throughput or latency guarantee for a UART or real CAN bus.

## Fault matrix

See docs/fault-matrix.md for malformed/oversized input, storage failure, serial loss, queue overflow, bus-off, import collision, no-device status and native CAD availability conditions.

## Final verified run (2026-10-22)

- Integrated verification: **95 Python tests passed**; `make verify` exit code 0.
- Native C safety policy: **7 assertions passed**.
- JSON Schema files checked: **15**; YAML files parsed: **9**; wheel content/schema-sync checks: PASS.
- Synthetic batch insert: **4136.54 frames/s** (4.834956 s for 20000 frames).
- Synthetic analysis: **3330.75 frames/s** (6.004661 s; 1024 findings and 128 IDs).
- Host: Python 3.14.4; Linux-7.0.0-38-generic-x86_64-with-glibc2.43; 4 logical CPUs.
- Original-ESP32 compile: **SUCCESS**, RAM 10828/327680 bytes (3.3%), application flash 179252/1048576 bytes (17.1%).

Benchmark measurements are a single synthetic host run, not physical UART/CAN throughput or a worst-case latency guarantee. No board flash, physical interlock test, live vehicle capture or physical transmission was performed.
