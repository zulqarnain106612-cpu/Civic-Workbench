# S05 — Persistent Sessions and Portable Evidence

## Delivered

- SQLite-backed storage persists session manifests, raw CAN frame objects, analysis findings, versioned parameter mappings, diagnostic-capability annotations, scenarios, event logs and TX audit events.
- A frame is validated before persistence, raw source/payload/timestamp fields are retained, duplicate frame IDs are rejected, and finalized sessions reject further appends.
- Batch append is a single immediate SQLite transaction, preserving order while avoiding one connection/transaction per synthetic frame.
- Finalization writes ordered JSONL raw data atomically, computes SHA-256 and byte count, and records record/drop counts in the session manifest.
- Export produces the versioned civic-workbench-export-v1 bundle with manifest, frames and findings.
- Import validates the complete payload and all evidence references before a transaction, rejects duplicate session/frame IDs, preserves individual raw frame provenance, assigns a safe local raw path, and materializes a new local JSONL file.
- Pagination is bounded; JSON input has a 4 MiB request cap and imported bundle frame count has a hard limit.

## Boundaries

The export bundle transports records and annotations. It does not embed private SQLite journals or assume that imported frame timestamps share a wall clock with the current host. The raw JSONL digest proves file contents, not the authenticity of a sender.

## Acceptance evidence

Storage integration tests cover restart durability, order/pagination, finalization, checksum consistency, transactional import/export and hostile/malformed input. Measurements are recorded separately in the S11 benchmark output.
