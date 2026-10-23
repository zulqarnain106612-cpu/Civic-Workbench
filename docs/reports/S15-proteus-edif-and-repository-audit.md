# S15 — Proteus EDIF import sources, CAN simulation bench and repository audit

**Date:** 2026-10-23. **Status:** generator, EDIF sources and audit fixes implemented and verified on the host. Proteus import, save and simulation run are **not** performed: the installed Proteus reports a licence error.

## What the installed Proteus offers (inspected on the host)

| Fact | Evidence |
|---|---|
| Proteus 9 Professional 9.2 SP1, build 45801, under Wine 10.0 | Home page About panel; `regid...Proteus 9 Professional_9.2.45801.1.swidtag` |
| Licence state: "Unlicensed Version", "Licensing error. Bad or missing Customer Key"; the Schematic Editor does not open; File > Import ECAD Files returns without creating a project | Observed in a private X display on 2026-10-23 |
| Documented schematic import: File > Import ECAD Files, OrCAD v9.2 / 17.2 EDIF2; after import Proteus compares its netlist with the EDIF netlist | `Help/IMPORTER.chm`, topics "Importing EDIF Files" and "Limitations" |
| Importer probe: first tag `EDIF`, `EDIFVersion 2 0 0`, `EDIFLevel 0`; needs page size, instance designator/value/origin, pin line figure and dot connect location | `Bin/IMPORTER.dll` diagnostic strings |
| CAN simulation: CAN Bus Analyser (`CAN_ANALYZER`, pins CANH/CANL, DBC decoding, trace logging), behavioural ECU nodes, transceivers MCP2551 / TJA1050 / SN65HVD23x all bound to one `DIGITAL,CAN_TRANSCEIVER` primitive in `CANBUS.DLL`; **no TJA1051 model** | `Help/Instruments.chm` (CAN Bus Analyser, CAN Models, CAN Examples); `Library/CANBUS.LIB` |
| Python in Proteus is MicroPython VSM targets and Python VSM device models, not a schematic-authoring API | `Help/MicroPython.chm`, `Tools/VSMPY`; Labcenter "What's new in 9.0" |

The native `ROOT.DSN` inside a `.pdsprj` is a proprietary binary (`ISIS SCHEMATIC FILE` header) with no published writer, so it is not fabricated. Python generates the documented import source; Proteus writes the native project when the import is saved.

## Delivered

- `tools/proteus_edif.py`: OrCAD-dialect EDIF 2 0 0 writer (cells with pin line figures and PINDOT connect locations, instances with designator/value/properties, nets with `joined` records and wire figures) and an independent S-expression reader.
- Router: every pin escapes to a private column, drops to its net's trunk row, and trunks are split at each drop, so every connection is endpoint-to-endpoint (Proteus does not join a wire end to another wire's interior).
- `hardware/proteus/generated/civic-workbench-rev-b.edf`: Rev B hardware sheet, all parts including DNP termination (FITTED property), J1 pins by NodeMCU header number (36 GPIO22, 33 GPIO21, 38 GND), U1 pin 5 and GPIO21 unconnected.
- `hardware/proteus/generated/civic-workbench-rev-b-sim.edf`: fitted Rev B parts plus `BAT1` 5 V, `U2` CAN Bus Analyser (`DATABASE=vehicle.dbc`) and `U3` behavioural Engine ECU on CANH/CANL. Each part carries the Labcenter primitive read from the installed libraries (`RES`: `ANALOG`/`RESISTOR`; capacitors: `ANALOGUE,CAPACITOR`; transceiver: `DIGITAL,CAN_TRANSCEIVER` + `CANBUS.DLL`).
- Model boundary: the TJA1051 symbol keeps its own name, pinout and marking; only its simulation primitive is Labcenter's generic transceiver, which does not model the Silent pin. The ESP32 is a header symbol and is not simulated. The ECU traffic is Labcenter's synthetic protocol, not Honda data.

## Repository audit #1 — findings and fixes

| # | Finding | Fix |
|---|---|---|
| A1 | Committed `reference-design.svg` no longer matched the generator (a C2PA manifest had been injected), failing `test_committed_bundle_matches_generator` | Regenerated with `make design-source` |
| A2 | Proteus facts stale (8.3 "Demonstration") in environment, progress, limitations, S09/S14 reports, netlist and checklist | Updated to the inspected 9.2 SP1 state and the EDIF route |
| A3 | Receive-only firmware: disarm/abort returned `ESP_ERR_INVALID_STATE` because no TX gate GPIO exists | Disarm returns `ESP_OK` in `CIVIC_RECEIVE_ONLY_BENCH`; assertion added to `test_can_rx_only_mock.c` |
| A4 | Unused imports/variables in `app.py`, `service.py`, `serial_bridge.py`, `storage.py`, `tx.py`, `simulator.py`, a test, and f-strings without placeholders in the generator | Removed; `make lint` (pyflakes) added locally and in CI |
| A5 | `.claude/` agent worktrees (a full repo copy) and `.vscode/` were untracked but not ignored; `make yaml-check` parsed the worktree copy | Both ignored; yaml-check skips dot-directories |
| A6 | `docs/reference/README.md` called the owner-merged third-party images "internal only" while the repository is public | Wording corrected and public source links added; the owner's decision to publish them is kept |
| A7 | README delivery summary was stale (95 tests, S04–S12 only) | Rewritten for S00–S15 |

## Repository audit #2 — findings and fixes

| # | Finding | Fix |
|---|---|---|
| B1 | Serial bridge `readline()` had no size bound; the 4096-byte check ran only after the whole line was in memory | `readline(MAX_LINE_BYTES + 1)` |
| B2 | After a stale-stream fault, CAN frame records cleared the fault but `connected` stayed false until a device-status record | Any valid CW1 record restores `connected` |
| B3 | A serial frame could carry `capture_source` other than hardware, or reuse the UUID of a simulator/import session and be appended to it | Serial frames must be hardware `rx`; a session-ID collision with a non-hardware session is rejected (tests added) |
| B4 | The threaded HTTP server let concurrent requests mutate the virtual bus and TX scheduler, which have no locking | `WorkbenchService.lock` serialises request dispatch; the body is read before the lock; concurrency test added |
| B5 | `WorkbenchService.hardware_tx_request` was unused dead code duplicating the API rejection path | Removed |

## Verification

- `make lint`, `make verify` (unit/integration tests, firmware safety C test, compile, schema, YAML, diff, wheel, design-source) and `pio run` for the NodeMCU-32S profile; results in the commit that adds this report and in `project/progress.json`.
- EDIF tests (`tests/test_proteus_generator.py`): importer probe header; stored netlist == reviewed netlist; drawn-geometry netlist == reviewed netlist; zero wire-on-interior hits; zero cross-net collinear overlaps; simulation primitives present; DNP excluded from the bench.

## Next action (needs a working licence)

1. Proteus: File > Import ECAD Files > ORCAD EDIF 2 > `hardware/proteus/generated/civic-workbench-rev-b-sim.edf`.
2. Confirm the importer log reports no netlist differences; fix and regenerate if it does.
3. Save as `hardware/proteus/native/civic-workbench-rev-b-sim.pdsprj`, press Run, and keep the CAN Bus Analyser capture (Save Trace, `.asc`) as evidence.
4. Repeat the import for `civic-workbench-rev-b.edf`.
