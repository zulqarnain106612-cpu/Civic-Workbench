# Evidence Index

| Scope | Artifact / command | Evidence boundary |
|---|---|---|
| Stage plan / DAG | project/stages.yaml, project/dependencies.yaml | Delivery requirements and dependency graph |
| Versioned contracts | schemas/v1/, contracts/openapi.yaml, src/civic_workbench/contracts.py | JSON shape + semantic constraints |
| S02/S03 firmware | firmware/esp32/, docs/reports/S03-can-transport-report.md | Classic ESP32 compile plus host mocks; not flash/bench/vehicle proof |
| Browser UI | src/civic_workbench/web/, tests/test_api_integration.py | Local HTTP/static/API behavior; not all-browser visual certification |
| Durable sessions | src/civic_workbench/storage.py, tests/test_storage_and_import_export.py | SQLite/raw JSONL semantics and bundle portability |
| Analysis | src/civic_workbench/analysis.py, src/civic_workbench/diagnostics.py, tests/test_analysis.py | Deterministic heuristics; candidate mapping not vehicle truth |
| Simulation TX | src/civic_workbench/simulator.py, src/civic_workbench/tx.py, tests/test_simulator_tx.py | Synthetic event scheduling only |
| Serial ingest | src/civic_workbench/serial_bridge.py, tests/test_product_integration.py | Mocked CW1 ingestion plus schema validation; no real serial port proof |
| Proteus sources | tools/generate_proteus_reference.py, hardware/proteus/generated/ | Deterministic source-side artifacts; native import/render remains blocked |
| Security/faults | docs/security-review.md, docs/fault-matrix.md, tests/test_api_security.py | Unit/HTTP tests, not a penetration test or external deployment approval |
| Performance | tools/benchmark.py, docs/reports/S11-benchmark-results.json | Single synthetic workload and host measurement only |
| Stage handoff | docs/reports/S04-browser-ui-report.md through S12-final-handoff-report.md, project/progress.json | Current implementation, verification and open gaps |
