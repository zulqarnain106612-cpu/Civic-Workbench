# S08 — Deterministic Virtual CAN Lab

## Delivered

- A virtual-time event queue can run multiple synthetic nodes with configurable standard/extended IDs, bounded periods and fixed/toggle/counter byte patterns.
- Scenarios create ordinary persisted capture sessions; all generated records use capture_source=simulator and do not imply known vehicle IDs.
- Filtering, source-trace replay, controlled payload mutations (bit flip, byte XOR/set and monotonic delay), step-by-step time advancement and event cancellation are implemented.
- Replay and per-step generation have explicit queue/frame bounds. Emitted frames are validated and batch-written to SQLite without rewriting source frames.
- Virtual TX requests use the same scheduler and audit model as the host APIs, but execute only as scheduled simulator events.

## Boundaries

This is deterministic simulation, not a model of the Civic ECU/network or of CAN electrical arbitration, transceiver timing, ACK/error confinement, bus load, or ISO-TP ECU behavior. Simulator output remains separately labeled.

## Acceptance evidence

Simulation tests verify repeatable time steps, queued node emissions, filters, replay/mutation provenance, resource caps and the fact that hardware transmission remains disabled.
