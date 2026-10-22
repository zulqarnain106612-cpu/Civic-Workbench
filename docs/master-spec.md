# Civic-Workbench — Master Engineering Specification

**Status:** requirements baseline. This document is not a claim that firmware, UI, schematic, CAN mappings, or physical tests already exist.

## 1. Product objective

Build a maintainable direct-CAN engineering workbench for the owner's Pakistan-market 2013 Honda Civic, ninth generation, 1.8 L full-option vehicle. The bench must permit evidence-led investigation of CAN traffic, identifier behavior, signal changes, diagnostic capabilities where supported, and controlled raw-frame transmission. The UI must also operate entirely against a deterministic virtual CAN lab.

The primary hardware target is fixed: **original ESP32 with integrated TWAI controller + NXP TJA1051 SO8 transceiver**. A candidate mapping or protocol is not considered a fact merely because its result looks plausible.

## 2. Architectural boundaries

Implement explicit modules and versioned contracts:

1. **Device firmware** — TWAI initialization/state, capture, bounded queues, telemetry, transport, safety gate, controlled TX, watchdog/fault behavior.
2. **Device transport** — connection lifecycle, capability discovery, schema-version handshake, sequence numbers, command IDs, timeouts, deduplication/idempotency where appropriate.
3. **Session store** — immutable raw frames, session metadata, capture configuration, software/firmware versions, source/provenance, annotations, export/import, migrations.
4. **Analysis engine** — identifier frequency/periodicity, payload bit/byte changes, correlation, counter/checksum candidate detection, candidate signal mappings and confidence/evidence.
5. **TX/diagnostic workflow engine** — one policy-enforcing send path, explicit operation capability declarations, user confirmation, rate limits, cancellation, audit records.
6. **Virtual CAN lab** — virtual bus and nodes, scheduled synthetic frames, deterministic replay/mutation, TX policy tests, scenario state and exportable fixtures.
7. **Browser workbench** — live/recorded frame table, filters, details, statistics, timeline/plots, analysis workspace, simulation lab, explicit TX arm/interlock indicator, session browser, logs/errors.
8. **Proteus artifact generator** — Python-driven generation of an importable native schematic/project, with deterministic inputs, versioned outputs, artifact manifest, and available-tool validation.
9. **Verification and traceability** — unit/contract/integration/simulation/performance/fault tests mapped back to REQ and S IDs.

Keep the device, analysis, storage, simulator, and UI interfaces decoupled. The simulator must use the same contracts as real capture to prevent separate behavior implementations drifting.

## 3. Raw CAN frame contract

The frame model must preserve at least:
- Protocol/schema version.
- Monotonic capture timestamp and wall-clock timestamp when available; clock source and synchronization uncertainty.
- CAN identifier and explicit standard (11-bit) versus extended (29-bit) format.
- RTR/remote-frame metadata if supported by the selected controller/API, and frame/error type.
- DLC and original payload bytes without reinterpretation.
- Receive sequence, source/session/device identity, observed bus/controller state, and drop/overflow counters.
- Parse/validation status and provenance.

Validate ranges before use. Never pad, truncate, or normalize raw bytes silently. A decoder consumes the immutable frame and creates a separate annotation.

## 4. Evidence and signal-reverse-engineering model

Each mapping must include a stable ID, source frame references, bus/session and capture conditions, identifier format, bit start/length, byte order, signedness, scale/offset only when substantiated, units only when substantiated, observed range, sampling/period estimate, candidate counter/checksum notes, algorithm/method, confidence rationale, status (observed, candidate, or validated), reviewer/validation method, and schema version.

The analysis must support:
- ID frequency, burstiness, period distribution, missing-frame gaps and co-occurrence.
- Byte and individual-bit change rates, constant bits/bytes, entropy, and state-change intervals.
- Comparing paired capture sessions with controlled user notes about one change at a time.
- Candidate counter/checksum detection without calling a heuristic a confirmed checksum.
- Candidate signal plots and correlation views with reproducible exports.

Do not assume Honda-specific IDs, payload meanings, byte order, scaling, bit rate, or diagnostic services before acquiring evidence.

## 5. Direct-CAN transmission and diagnostics

Raw TX is part of scope and must not be dropped from the product. Its path must nevertheless be safety-constrained:
- TX disabled on startup/reset/reconnect/error; transceiver silent mode is the hardware default.
- Physical hardware interlock and explicit UI/software arming are both required to enable normal transceiver mode.
- The firmware owns final authorization; UI visibility or a UI checkbox alone is not authorization.
- Validate ID width/format, DLC, payload, period, repeat count, queue bounds, expiry, and rate before queuing.
- Support cancel/stop, a global abort, timeout, visible state, and immutable audit history.
- Simulation and isolated-bench validation precede any active in-vehicle experiment.

Diagnostic workflows must be capability-driven. The project may implement generic request/response/transport abstractions, but a target-specific operation is enabled only when the protocol, ECU, request, expected response, safety implications, and support evidence are recorded. A raw CAN interface is not to be replaced with an OBD-II/ELM/PID adapter abstraction.

## 6. Storage, replay, and export

Raw session records are append-only/immutable after ingestion. Metadata and interpretations may evolve under version control without changing source frames. A session includes hardware/firmware/software versions, capture setup, timing basis, known bus conditions, user annotations, and data-quality counters.

Provide machine-readable export suitable for analysis and test fixtures. Import must validate schema version, bytes/DLC, identifiers, record ordering, checksums where defined by the export format, and size limits. Store migration tests alongside each schema evolution.

## 7. UI requirements

The browser UI is an instrument panel, not a decorative mockup. It must distinguish live connection state from recorded/replayed data, simulated bus state from a physical interface, and armed from disarmed TX. Provide useful empty/error/loading states, searchable tables, filters, row details, timelines/plots, configurable columns, session metadata, analysis findings with provenance, simulation controls, TX audit and cancellation. Do not hide connection or data-loss faults.

## 8. Virtual CAN and Proteus

The virtual lab must support deterministic scenarios with virtual nodes, frame schedules, replay, controlled mutations, TX request testing, capture loss/error injection and repeatable test assertions. Virtual data must be explicitly labelled synthetic/simulated.

Use Python source to generate native Proteus schematic/project artifacts. Keep the generator deterministic and emit an artifact manifest (generator version, input configuration hash, output paths, tool/library versions, validation state). Use official Proteus Python automation/generation functionality if available in the installed version; first discover and document the actual supported API instead of inventing commands. If an official automation utility is not available, implement a tested Python generator around a supported native file/API path and report tool-import validation separately. A picture or netlist alone does not satisfy the native-project requirement.

## 9. Hardware grounding

The exact physical transceiver specified for this project is NXP TJA1051 marked NXP TJA1051 25 06 ND312; no substitute is permitted. Do not infer an orderable suffix from that marking. TJA1051 orderable variants can differ at pin 5, so the pin-5 function must be confirmed for the exact installed item before wiring or applying power. Use the matching official datasheet once that identity is established.

The original ESP32 TWAI controller is not itself a CAN transceiver and requires an external physical-layer device. See:
- [Espressif TWAI — ESP32](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/twai.html)
- [NXP TJA1051 datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf)

## 10. Quality attributes

- Reproducible toolchain and build steps.
- Explicit state machines and error contracts.
- Bounded queues, memory, CPU use and event rates; measurable performance.
- Security and safety fail closed; validate every input crossing a trust boundary.
- Tests at unit, contract, integration and deterministic simulation levels.
- Evidence-linked completion; distinguish tests, simulation, CAD import/render, and physical validation.

## 11. Definition of done

The project is complete only when all MUST requirements have implementation and traceable verification, or are precisely identified as blocked with evidence and an accountable follow-up. The handoff includes setup/build/test/run instructions, source, generated firmware and Proteus artifacts, test summaries, performance numbers, safety/fault matrix, known limitations, and explicit statement of whether physical vehicle validation was performed.

See project/requirements.yaml, project/stages.yaml, project/dependencies.yaml, project/constraints.yaml, and tests/requirements-traceability.yaml for machine-readable controls.
