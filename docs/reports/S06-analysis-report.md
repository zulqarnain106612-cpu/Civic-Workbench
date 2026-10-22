# S06 — Identifier and Signal Analysis

## Delivered

- Per-identifier summaries include observed frame count, median observed interval, interval-jitter range, variable byte positions and last-observed monotonic timestamp.
- Analysis emits evidence-linked findings for periodicity and payload changes, plus low-confidence counter-like and high-variation/checksum-investigation candidates.
- Findings reference UUIDs from the same session and keep method, confidence, status and annotations separate from the original raw frame records.
- Explicit parameter decoding supports a user-selected bit range, endianness, signedness, scale, offset and unit. A decoder never infers these properties from Honda model/year.
- Parameter definitions are persisted as per-session, per-name versions with source evidence IDs. Every newly saved definition starts as candidate.
- Promotion to validated requires a non-empty independent validation method, reviewer/evidence references and a timestamp. The UI identifies this as an operator-supplied validation claim.

## Boundaries

The algorithms are exploratory heuristics rather than reverse-engineering or signal-meaning guarantees. Counter, checksum, rolling-counter and physical-unit interpretations remain hypotheses until independently validated. CAN timing is based on timestamps in the capture record; for S03 firmware those are observation/dequeue times.

## Acceptance evidence

Analysis tests use deterministic synthetic traces to exercise periodicity, changing bytes, candidate labeling, evidence-reference constraints, range validation, version increments and independent promotion gates.
