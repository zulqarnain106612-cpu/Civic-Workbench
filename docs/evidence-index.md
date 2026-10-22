# Evidence Index

| Scope | Artifact / command | Evidence boundary |
|---|---|---|
| Stage plan / DAG | project/stages.yaml, project/dependencies.yaml | Delivery requirements and dependency graph |
| Versioned contracts | schemas/v1/, contracts/openapi.yaml, src/civic_workbench/contracts.py | JSON shape + semantic constraints |
| S02/S03/S13 firmware/hardware | firmware/esp32/, hardware/reference/, docs/reports/S13-hardware-baseline-and-pin-map.md | NodeMCU-32S build + GPIO21/22 source map; physical header and bench tests still pending |
| Browser UI | src/civic_workbench/web/, tests/test_api_integration.py | Local HTTP/static/API behavior; not all-browser visual certification |
| Durable sessions | src/civic_workbench/storage.py, tests/test_storage_and_import_export.py | SQLite/raw JSONL semantics and bundle portability |
| Analysis | src/civic_workbench/analysis.py, src/civic_workbench/diagnostics.py, tests/test_analysis.py | Deterministic heuristics; candidate mapping not vehicle truth |
| Simulation TX | src/civic_workbench/simulator.py, src/civic_workbench/tx.py, tests/test_simulator_tx.py | Synthetic event scheduling only |
| Serial ingest | src/civic_workbench/serial_bridge.py, tests/test_product_integration.py | Mocked CW1 ingestion plus schema validation; no real serial port proof |
| Proteus sources | tools/generate_proteus_reference.py, hardware/proteus/generated/ | Deterministic source-side artifacts; native import/render remains blocked |
| Security/faults | docs/security-review.md, docs/fault-matrix.md, tests/test_api_security.py | Unit/HTTP tests, not a penetration test or external deployment approval |
| Performance | tools/benchmark.py, docs/reports/S11-benchmark-results.json | Single synthetic workload and host measurement only |
| Stage handoff | docs/reports/S04-browser-ui-report.md through S13-hardware-baseline-and-pin-map.md, project/progress.json | Current implementation, verification and open gaps |
