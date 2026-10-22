# S07 — Guarded TX Scheduling and Capability-Driven Diagnostics

## Delivered

- Host TX requests are validated against the existing versioned Classical-CAN request contract: identifier format, frame type, DLC/payload shape, bounded repeat count, cadence and timeout budget.
- The simulator scheduler supports repeat scheduling, cancel, progress/results and durable audit records. Every simulation TX frame is marked simulator and is persisted alongside a separate TX audit entry.
- Any host TX target other than simulation is rejected and audited before returning a conflict. No host code calls a physical CAN API.
- Firmware S03 exposes one guarded C-level frame-send entry point; build flags default off for hardware initialization, bitrate evidence and TX capability. The API checks the software arm, controller status/error counters and physical-interlock input; the transceiver’s independent hardware gate remains necessary.
- Diagnostic capabilities are saved only as explicit evidence-backed annotations. Unknown/unsupported capabilities must remain disabled. A workflow-gate endpoint evaluates a supported capability for simulation only and does not execute vehicle-specific protocol traffic.
- Parameter candidates are not promoted automatically. Diagnostics do not guess an ECU address, service ID or expected response.

## Important remaining restriction

The S03 CW1 serial protocol is read-only and does not expose hardware TX/arm commands. Consequently, this release does not offer an end-to-end host-to-firmware vehicle-transmission control channel, repeating hardware transmission, or executable vehicle-specific diagnostic services. This is an intentional safety boundary while board identity, bitrate, transceiver wiring and the independent interlock remain unverified. S07 is complete for simulation scheduling and gating infrastructure, but physical operation remains explicitly incomplete.

## Acceptance evidence

Tests cover invalid requests, disarmed/simulator safety boundaries, repeat limits, cancellation, durable audit, unsupported capability denial and simulation-only gates. No physical transmission was attempted.
