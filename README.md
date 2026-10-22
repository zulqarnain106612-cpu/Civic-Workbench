# Civic-Workbench

A local-first direct-CAN engineering workbench for researching a Pakistan-market 2013 Honda Civic (9th generation, 1.8 L), based on the **original ESP32 integrated TWAI controller and NXP TJA1051T/3 SO8 transceiver**.

This repository is independent of the earlier build-a-web-page-for-ios repository. No source or project structure was copied from that project.

## Current delivery state

S00–S03 are the prior committed baseline. The remaining S04–S12 host/software delivery is now implemented and verified together: 95 Python tests passed, `make verify` exited 0, the 20,000-frame synthetic benchmark completed, and the generic original-ESP32 firmware profile compiled successfully. S07 deliberately remains simulation-only at the host boundary: hardware TX/arm commands are not carried over the read-only CW1 protocol. S09 produces deterministic reference-design source artifacts, but a native Proteus DSN/PDSPRJ has not been generated/imported because an official supported writer/API was not confirmed. The exact physical ESP32 module, GPIO map, transceiver installation, vehicle bitrate and safe capture point remain unverified. No firmware was flashed and no Civic bus operation was performed.

The complete test/build evidence and open issues are tracked in project/progress.json and docs/reports/S12-final-handoff-report.md.

## What is delivered

- Responsive local browser UI for raw frames, status, sessions, filters, charts, findings, simulator, TX audit and read-only serial ingestion.
- Loopback-only local HTTP API with Origin/Host checks and response security headers.
- SQLite session/store service, atomic batched frame writes, content-hashed ordered JSONL finalization, portable bundle export/import and audit/event records.
- Deterministic identifier/timing/byte-variability analysis with evidence-linked findings; explicit decoder definitions are versioned and start as candidate.
- Evidence-gated diagnostic capability metadata and a simulation-only workflow gate. No Honda ECU services or IDs are assumed.
- Virtual CAN nodes, virtual time, trace replay/mutation, resource-bounded events and simulator-only TX repeats/cancellation/audit.
- CW1-prefixed firmware serial frame/status protocol; host bridge ingests serial only and does not send bytes to firmware.
- Deterministic hardware netlist/component map/BOM/SVG source generator, with native Proteus generation status explicitly recorded.
- Fault matrix, threat/safety notes, stage reports, requirement traceability and a performance benchmark tool.

## Install and run

Python 3.10+, SQLite and the standard library are required. From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
civic-workbench --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765/. Or run directly from source with:

```sh
make run
```

Persistent data is stored under ~/.local/share/civic-workbench by default. Use CIVIC_WORKBENCH_DATA_DIR to choose another private local directory. Do not expose this unauthenticated service to a network.

## Development and verification

```sh
make test
make verify
make firmware-build PIO="$HOME/.venvs/civic-workbench-pio/bin/pio"
python3 tools/generate_proteus_reference.py
make benchmark BENCH_FRAMES=20000
```

The synthetic benchmark writes measured single-host results to docs/reports/S11-benchmark-results.json. It does not characterize real UART/CAN throughput or guarantee real-time latency.

## Firmware and safety boundary

- Target MCU: original Espressif ESP32 with integrated TWAI; no ESP32-S2/S3 substitution.
- CAN physical layer: NXP TJA1051T/3 in SO8/SOT96-1 package.
- Firmware hardware-init, verified-bitrate and hardware-TX build flags remain off by default; GPIOs remain unassigned until the actual board is identified.
- The host TX scheduler accepts only target=simulation. It never forwards TX requests to a physical adapter.
- The firmware C API can issue one guarded frame only when built/configured and armed, but CW1 v1 has no host command channel for arming or transmission.
- The transceiver must default Silent and the independent physical interlock must be a verified electrical barrier; software checks do not substitute for hardware.
- No vehicle identifier, bit layout, scale, unit, ECU address, diagnostic service or behavior is a fact until supported by traceable independent evidence.
- Hardware flash, physical interlock, live UART/CAN, bench and vehicle tests have not been performed.

## Main project map

| Area | Entry point |
|---|---|
| Agent/stage contract | CLAUDE.md, project/stages.yaml, project/dependencies.yaml |
| Requirements and traceability | project/requirements.yaml, tests/requirements-traceability.yaml |
| JSON Schemas and semantic checks | schemas/v1/, src/civic_workbench/contracts.py |
| Local service / API | src/civic_workbench/app.py, src/civic_workbench/service.py |
| Browser assets | src/civic_workbench/web/ |
| Persistence | src/civic_workbench/storage.py |
| Analysis / parameter versions | src/civic_workbench/analysis.py, src/civic_workbench/diagnostics.py |
| Virtual bus / TX audit | src/civic_workbench/simulator.py, src/civic_workbench/tx.py |
| Read-only serial ingestion | src/civic_workbench/serial_bridge.py |
| Proteus reference artifact generation | tools/generate_proteus_reference.py, hardware/proteus/generated/ |
| Reports / evidence status | docs/reports/, docs/evidence-index.md, project/progress.json |

## Official hardware references

- [Espressif ESP32 TWAI documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/twai.html)
- [NXP TJA1051 product datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf)
- [Labcenter Proteus schematic capture](https://www.labcenter.com/schematic/)
- [Labcenter downloads](https://www.labcenter.com/downloads/)
