# Final completion-claim audit (S16)

**Date:** 2026-10-25. **Verdict:** software complete with physical validation pending. The project is **not** fully complete: hardware raw-frame transmission (REQ-CAN-003) is BLOCKED, and the native Proteus import/save/simulation (REQ-PROT-001), board/transceiver bench work (REQ-HW-001, REQ-SAFE-001) and all vehicle work are NOT_PERFORMED.

## 1. Repository state

| Item | Value |
|---|---|
| Repository | https://github.com/zulqarnain106612-cpu/Civic-Workbench |
| Branch / upstream | `main` tracking `origin/main` |
| Audit baseline HEAD | `e8cc776f1248e77bf6df5a1a8d6a63f078767379` (local and remote agreed, clean tree) |
| Other refs | `s14-rev-b-receive-only` = PR #1 head `b4d64ee`, already merged; no open PR covers this work |
| Audit workspace | fresh clone in the audit sandbox. The Linux checkout `/home/s752/Civic-Workbench` was not reachable during the audit (computer not linked); the owner's Windows copy is a ZIP download, not a git checkout |
| Result | changes committed on `main` in the commit that adds this report; see `git log` |

## 2. Scope inspected

Contracts: `CLAUDE.md`, `docs/master-spec.md`, `project/requirements.yaml`, `stages.yaml`, `dependencies.yaml`, `constraints.yaml`, `hardware.yaml`, `environment.yaml`, `progress.json`, `tests/requirements-traceability.yaml`.
Implementation read in full along the control paths: `firmware/esp32/main/civic_can.c`, `civic_safety.c`, `civic_transport_format.c`, `app_main.c`, `Kconfig.projbuild`; `src/civic_workbench/app.py`, `service.py`, `serial_bridge.py`, `storage.py`, `tx.py`, `simulator.py`, `contracts.py`, `web/index.html`, `web/app.js`; `tools/generate_proteus_reference.py`, `tools/proteus_edif.py`, `tools/generate_eagle_schematic.py`; mocks `tests/firmware/mock_esp/*`; `contracts/openapi.yaml`; `.github/workflows/ci.yml`; `Makefile`.
External references checked: Espressif TWAI API (return codes of `twai_receive`), Proteus 9.2 SP1 `IMPORTER.dll` (disassembled cell-classification branch), Proteus help `IMPORTER.chm` and `Instruments.chm`.

## 3. Findings and repairs

| # | Severity | Finding | Root cause | Fix | Regression test |
|---|---|---|---|---|---|
| F1 | High (safety) | Bus-off while armed never disarmed TX in the RX pump | Pump only checked bus-off when `twai_receive()` failed, but ESP-IDF documents `INVALID_STATE` only for an uninstalled driver, so bus-off just times out. The mock returned `INVALID_STATE` on bus-off and hid the defect | Pump polls controller state and error counters every cycle while armed and disarms on not-running or error-passive; mock follows the documented API | `tests/firmware/test_can_core_mock.c` bus-off-while-armed block (fails on the old code, passes now) |
| F2 | High (deliverable) | Proteus import of the EDIF produced 0 components and then 26 missing connections | (a) extra bracket closed the page before instances and nets; (b) symbol cells used `viewType NETLIST`, but `IMPORTER.dll` creates a component only for `viewType SCHEMATIC` + `cellType GENERIC` | Bracket removed; symbol views are `SCHEMATIC` | `tests/test_proteus_generator.py::test_edif_header_matches_proteus_importer_probe` (page children, viewType/cellType per cell) |
| F3 | Medium (requirement) | No global TX abort; stopping a capture left simulation TX requests "queued" forever with no audit | Missing feature | `TxScheduler.abort_all`, `POST /api/v1/tx/abort`, UI "Abort all pending TX", abort on capture stop; request status becomes `partial` after the first frame | `tests/test_simulator_tx.py` (global abort, abort on stop); OpenAPI parity test |
| F4 | Medium (hardware identity) | U1 value and docs said `TJA1051T` / "plain TJA1051T (pin 5 n.c.)" as fact | Orderable suffix and pin-5 variant inferred, contrary to REQ-HW-001 | Value is `NXP TJA1051 (marking 25 06 ND312)`; variant recorded NOT CONFIRMED; new open item: Rev B receives only if pin 5 is n.c. | `test_edif_simulation_bench_binds_labcenter_models` asserts no `TJA1051T` |
| F5 | Medium (data integrity) | SQLite store had no layout version; a newer or foreign DB would be opened silently | Missing schema stamp | `PRAGMA user_version` = `STORAGE_SCHEMA_VERSION`; newer versions are refused | `StorageSchemaVersionTests` |
| F6 | Low (accessibility) | Frame rows were mouse-only | Click handler without focus/keyboard | `tabindex="0"` plus Enter/Space handler | `tests/test_ui_accessibility.py` (labels, lang, button names, tab order, keyboard rows) |

Earlier audit rounds on 2026-10-23 (S15 report) fixed serial provenance, bounded serial reads, request serialisation, the unvalidated frame-import route and OpenAPI parity; they were re-verified here.

## 4. Contradictions resolved

**A. Receive-only hardware vs REQ-CAN-003.** Not satisfied for hardware. Simulation TX meets the request contract (format, payload, DLC, cadence, repeats, cancel, global abort, audit). The firmware has a guarded single-frame API with arm, interlock, rate and per-arm budget (mock-tested, compiled out by default). Two independent blockers remain: CW1 v1 has no host-to-firmware TX command, and Rev B cannot transmit (S tied HIGH by R1, TXD not wired). Closing it needs a reviewed Rev C circuit (3.3 V to 5 V TXD buffer, interlock-gated S pull-down), a host-to-firmware TX protocol, and bench evidence. The safe default is kept; the scheduler is not presented as physical TX. Status: **BLOCKED**.

**B. Hardware identity.** NodeMCU-32S, GPIO21/GPIO22 and the literal marking `NXP TJA1051 25 06 ND312` now agree across netlist, BOM, EDIF, EAGLE, SVG, `hardware.yaml` and firmware Kconfig. GPIO mapping stays provisional until continuity is measured. Pin 5 is left open (fail-safe for n.c./VIO/EN types), and its function must be confirmed before relying on reception.

**C. Proteus.** Generator, EDIF structure, netlists, pin maps and wire endpoints are verified offline. A real import on the owner's Proteus 9.2 SP1 (Windows, 2026-10-25) found F2. After the fixes, re-import, `.pdsprj` save and simulation have **not** been performed; doing them needs the Proteus GUI, which the owner did not authorise for automation in this session. No `.DSN`/`.pdsprj` is fabricated. Status: **NOT_PERFORMED**.

**D. Test/build claims.** Re-run independently (section 5).

## 5. Verification commands (audit sandbox, Python 3.13.17, gcc 13.3)

| Command | Exit | Observed |
|---|---|---|
| `make test` (baseline) | 0 | 115 tests OK; firmware safety 7 assertions |
| `make lint` | 0 | pyflakes clean on `src tests tools` |
| `make verify` (final) | 0 | 124 tests OK, safety C test, schema sync PASS (15), YAML parse, `git diff --check`, wheel assets PASS, design-source regenerated with no drift |
| `make benchmark BENCH_FRAMES=20000` | 0 | insert 32,085 frames/s, analysis 30,017 frames/s, 1,024 findings (synthetic, this host; `docs/reports/S11-benchmark-results.json`) |
| `pio run` (firmware-build) | 1 | `HTTPClientError` installing `espressif32@6.9.0`: the sandbox blocks the PlatformIO registry. Firmware build evidence is the CI job `original-esp32-compile` on the pushed commit |
| `python3 tools/generate_proteus_reference.py` | 0 | design checks all pass; outputs byte-identical to the committed bundle |

## 6. Requirement dispositions

Status keys: Impl = implemented, Unit, Integ = integration, Build = build/package, Sim = simulator, CAD-gen = CAD generator, CAD-native = native tool, Bench, Vehicle. "-" = not applicable; NP = NOT_PERFORMED.

| ID | Impl | Unit | Integ | Build | Sim | CAD-gen | CAD-native | Bench | Vehicle | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| ARCH-001 | yes | yes | yes | yes | yes | - | - | NP | NP | `tests/test_contracts.py`, `test_packaging.py` |
| HW-001 | source | yes | - | CI | - | yes | NP | NP | NP | netlist, `hardware.yaml`, F4 |
| CAN-001 | yes | yes (mock) | yes | CI | - | - | - | NP | NP | `test_firmware_can_core.py` |
| CAN-002 | yes | yes | yes | yes | yes | - | - | NP | NP | `test_storage_and_import_export.py` |
| CAN-003 | partial | yes | yes | CI | yes | - | - | BLOCKED | BLOCKED | section 4A |
| REV-001 | yes | yes | yes | yes | yes | - | - | - | NP | `test_analysis.py` |
| DATA-001 | yes | yes | yes | yes | - | - | - | - | - | F5 tests |
| UI-001 | yes | static | yes | yes | yes | - | - | NP (hardware UI) | NP | F6, `test_api_integration.py` |
| SIM-001 | yes | yes | yes | yes | yes | - | - | - | - | `test_simulator_tx.py` |
| DIAG-001 | gating only | yes | yes | yes | yes | - | - | - | NP | `test_api_integration.py` |
| PROT-001 | yes | yes | - | - | - | yes | NP | - | - | F2, section 4C |
| SAFE-001 | yes | yes | yes | CI | yes | - | - | NP | NP | F1, `test_safety_policy.c` |
| EVID-001 | yes | yes | - | - | - | - | - | - | - | this report, traceability |
| QUAL-001 | yes | yes | yes | partial | - | - | - | - | - | section 5 |

## 7. Safety status

Physical TX remains disabled: Rev B hardware cannot transmit, firmware TX is compiled out by default, and the host rejects and audits hardware-target requests. No firmware was flashed. No board, transceiver, bench, live-bus or Honda Civic measurement happened. No diagnostic service was executed.

## 8. Remaining gates and acceptance criteria

1. **Native Proteus (PROT-001):** import `hardware/proteus/generated/civic-workbench-rev-b-sim.edf`, confirm the importer log reports 0 missing and 0 extra connections, save `hardware/proteus/native/civic-workbench-rev-b-sim.pdsprj`, run, and save the CAN Bus Analyser trace (`.asc`). Repeat for `civic-workbench-rev-b.edf`.
2. **Board/transceiver (HW-001):** header continuity 33/36/38, SO8 pin-1 orientation, pin-5 function of the installed IC, +5V_CAN 4.5 to 5.5 V, S at least 3.5 V, RXD_3V3 at most 3.6 V.
3. **Bench RX (CAN-001/SAFE-001):** receive-only build on an isolated bench bus with a third ACKing node; capture evidence.
4. **Hardware TX (CAN-003):** Rev C circuit review, host-to-firmware TX protocol, bench interlock tests. Never on the vehicle before an explicitly reviewed safe test.
5. **Vehicle:** bitrate, topology and safe tap point from independent evidence.

## 9. Changed files in this audit

Firmware: `firmware/esp32/main/civic_can.c`. Mocks/tests: `tests/firmware/mock_esp/mock_esp.c`, `tests/firmware/test_can_core_mock.c`, `tests/test_simulator_tx.py`, `tests/test_storage_and_import_export.py`, `tests/test_proteus_generator.py`, `tests/test_ui_accessibility.py`. Host: `src/civic_workbench/tx.py`, `service.py`, `app.py`, `storage.py`, `web/index.html`, `web/app.js`, `contracts/openapi.yaml`. Generators and outputs: `tools/proteus_edif.py`, `tools/generate_proteus_reference.py`, `tools/generate_eagle_schematic.py`, `hardware/proteus/generated/*`. Docs/ledgers: `hardware/reference/*`, `project/*`, `tests/requirements-traceability.yaml`, `docs/known-limitations.md`, `docs/evidence-index.md`, `docs/reports/S11-benchmark-results.json`.
