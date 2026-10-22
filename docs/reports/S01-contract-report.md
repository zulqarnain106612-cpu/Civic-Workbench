# S01 — Requirements, Schemas, Interfaces, and Contracts

**Status: COMPLETE**  
**Date:** 2026-10-22  
**Base commit:** `8aef9546927e0cb0737113ce10bdf2e8d91500db`

## 1. Result

S01 establishes the first executable contract layer for Civic-Workbench. Versioned data shapes, a logical REST API contract, a transport/event envelope, cross-field semantic checks, and automated contract tests are now present. The work is deliberately interface-first: it does not pretend the UI, persistence service, simulator, firmware or CAN transmit driver exists.

## 2. Deliverables

- **14 JSON Schemas (Draft 2020-12)** under `schemas/v1/`:
  - raw CAN frame and capture-session manifest;
  - analysis finding/evidence annotation;
  - evidence-backed diagnostic capability;
  - bounded TX request and explicit safety-state snapshot;
  - transport envelope;
  - handshake, device status, capture start/stop, TX cancel/result and structured error payloads.
- **OpenAPI 3.1** host API contract at `contracts/openapi.yaml` for health/capabilities, safety state, passive/simulated capture control, session/frame retrieval, analysis findings, and guarded TX request/cancellation.
- **Reference semantic validator** at `src/civic_workbench/contracts.py`, which validates schemas plus cross-field rules that JSON Schema alone does not conveniently express.
- **Test command and dependencies** in `Makefile`, `requirements.txt`, and `requirements-dev.txt`.
- **Contract documentation** in `docs/contracts-v1.md`.
- **Requirement traceability** updated in `tests/requirements-traceability.yaml`; each project requirement remains individually identified and its incomplete downstream work is explicitly listed.

## 3. Important contract decisions

### Immutable observations

Raw frames preserve bytes, DLC, ID format, timestamp basis, source and controller-state information. A data frame's payload length must equal DLC; a remote frame has no payload bytes. Standard IDs are restricted to 11 bits, extended IDs to 29 bits, and the schema is explicitly Classical CAN (DLC 0–8). Decoded signals and interpretations are separate evidence-linked findings rather than fields added to a raw observation.

### Evidence before claims

An analysis finding has evidence-frame references, method, confidence, and a state (`observed`, `candidate`, or `validated`). A `validated` status requires an explicit validation method, timestamp and evidence references. Diagnostic capabilities in `unknown` or `unsupported` state cannot be enabled; a `supported` capability must contain supporting evidence. No Honda-specific identifier, ECU address, diagnostic service or signal is asserted by these schemas.

### TX request is not TX authorization

A TX request is bounded by cadence, repeat count and timeout and validated independently from a safety state. A safety snapshot can claim `tx_permitted=true` only if mode is normal, software is armed, hardware interlock is active, the controller is running, there are no faults, state age is at most 500 ms, the arm lease has not expired, and the state source is firmware. The semantic validator rejects simulator/import-originated snapshots as hardware authorization.

The reference `authorize_transmission` function is a host-side contract guard only; it sends no frames. Firmware must re-check state at send time and the physical hardware interlock must independently inhibit the transceiver. The 500 ms threshold is a v1 fail-closed control-plane choice, not a measured vehicle timing fact.

### Versioned boundaries

The transport envelope has a schema version, message UUID, typed message name, UTC issue time, monotonic per-sender sequence, optional correlation/session identifiers and a payload. Each declared envelope message maps to a versioned payload schema and known payloads are recursively validated. The REST contract is logical; the backend framework and streaming transport implementation are not selected by S01.

## 4. Verification evidence

Command executed on the local Linux development machine:

```sh
make test-contracts
python3 -m compileall -q src tests
git diff --check
```

Results:
- **42/42 unit/contract tests passed** with Python 3.14.4 and jsonschema 4.19.2.
- All 14 JSON Schema documents pass Draft 2020-12 meta-schema checking; representative valid payload/record samples pass and the transport envelope's nested payload validation is exercised.
- Positive and negative tests cover 11-bit/29-bit identifier boundaries, DLC/payload mismatch, remote-frame shape, immutable raw records, raw-capture path traversal rejection, session time ordering, candidate/validated finding evidence, diagnostic capability enablement, bounded TX input, repeat schedule versus timeout, required TX interlocks, no faults, freshness/lease expiry, simulator-source rejection, explicit bitrate for hardware capture start, envelope payload validation, API paths/relative references, progress-ledger consistency, unique requirement IDs and acyclic stage dependencies.
- All project YAML files parsed and `project/progress.json` parsed successfully.
- `python3 -m compileall -q src tests` passed.
- `git diff --check` passed after cleanup.

OpenAPI verification in this stage checks YAML parsing, required operations and that all relative schema references resolve to existing files. It does not claim a full external OpenAPI conformance run.

## 5. Remaining scope boundaries

S01 does not implement physical CAN capture or transmission, session persistence, analysis algorithms, the browser UI, virtual bus behavior, firmware interlock, or Proteus generation. Traceability statuses remain `partial` for requirements where only their contract/interface layer exists and `open` for features not started. No physical or vehicle tests were performed.

## 6. Handoff

S01 acceptance criteria are met. **S02 is next**: confirm the exact original ESP32 module when available, choose/pin a working classic-ESP32 firmware toolchain, and implement the firmware/hardware foundation around TWAI plus the exact TJA1051 SO8. S02 must keep hardware TX inhibited by default. S09 retains the documented open question about a supported native Proteus schematic-generation route.
