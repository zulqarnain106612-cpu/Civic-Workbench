# S09 — Proteus Reference-Design Generation

## Delivered artifacts

The deterministic generator is tools/generate_proteus_reference.py. It consumes hardware/reference/esp32-tja1051-netlist.yaml and writes:
- hardware/proteus/generated/reference-design.netlist.json
- hardware/proteus/generated/component-map.json
- hardware/proteus/generated/reference-design.svg
- hardware/proteus/generated/bill-of-materials.csv
- hardware/proteus/generated/native-project-status.json
- hardware/proteus/generated/artifact-manifest.json
- hardware/proteus/generated/README.md

The source captures the original ESP32 integrated TWAI and required NXP TJA1051 SO8 boundary without fabricating GPIO numbers, resistor/capacitor values, connector pinout, termination, or part-library validation. The SVG is an explicitly labelled vector-review companion, not a screenshot and not a native project.

## Native project status — blocked

Local inspection found Proteus 8.3.19906.0 paths and commercial sample projects packaged as ZIP files with PROJECT.XML, ROOT.CDB and proprietary binary ROOT.DSN content. An official Python utility/API for generating a native schematic was not confirmed in the installed toolset or the official Labcenter schematic/download documentation inspected. The project therefore does not manufacture a plausible-looking invalid DSN or claim a native import/render that was never performed.

Official references:
- https://www.labcenter.com/schematic/
- https://www.labcenter.com/downloads/

To close the remaining native-artifact gap, confirm a Labcenter-supported automation API/utility and licensed module, then generate and import/render the native project in Proteus. S09 has source-generation coverage, but native Proteus generation/import acceptance remains blocked.

## Acceptance evidence

The generator output is deterministic from the tracked netlist; tests compare hashes across independent output directories, validate the BOM/netlist labels, and assert that native-project-status remains accurately blocked.


## 2026-10-23 update (S14)

The generator now emits the Rev B receive-only design: net-label schematic SVG, resolved netlist, BOM with DNP parts, `design-checks.json` and `PROTEUS-CAPTURE.md`. Native project remains blocked; see docs/reports/S14-rev-b-receive-only-and-audit-remediation.md.
