# S10 — Integration and End-to-End Path

## Integrated path

A locally served browser client calls the loopback HTTP API. The API uses shared contract validation, SQLite persistence and event/audit logging. A simulation scenario emits raw records into the same session/frame store consumed by analysis, exports and evidence-linked annotations. The read-only CW1 bridge turns actual firmware serial records into hardware-labelled sessions without providing a TX-control route. Capability/mapping versions reference source frame UUIDs and cannot mutate those raw records.

Integration targets are:
1. Start a synthetic scenario.
2. Advance virtual time and persist records.
3. Inspect/filter frames and run analysis.
4. Save a parameter candidate referencing existing raw frames.
5. Export and import a versioned bundle.
6. Submit/cancel a simulation TX request and inspect durable audit.
7. Inspect the safety state, which remains tx_permitted=false.
8. Attempt a non-loopback/cross-origin request and confirm rejection.

## Boundaries

This end-to-end path is host/simulation integration. It does not prove a real serial device is present, a real CAN frame has been acquired, a vehicle mapping is accurate, or a native Proteus project imports.

## Acceptance evidence

Tests exercise these flows through HTTP and service boundaries with temporary data stores, including fail-closed TX and raw-frame provenance.
