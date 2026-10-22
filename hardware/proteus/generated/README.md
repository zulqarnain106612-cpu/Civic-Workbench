# Generated Proteus-design review bundle

This folder contains deterministic source-derived review artifacts; it does not contain a native Proteus project.

- reference-design.netlist.json: canonical machine-readable netlist.
- component-map.json: symbol-map review status, with unverified items flagged.
- reference-design.svg: editable vector companion; not a native Proteus schematic.
- bill-of-materials.csv: BOM with unresolved design values explicitly unassigned.
- native-project-status.json: current native-generation/import validation blocker.

The exact hardware baseline is ESP32S NodeMCU / NodeMCU-32S (classic ESP32 with TWAI) and the NXP TJA1051 bearing the full visible marking NXP TJA1051 25 06 ND312; substitutions are not authorized. No orderable suffix is inferred. GPIO21 maps to TWAI TX and GPIO22 to TWAI RX in source. NXP must confirm the exact variant before pin 5 is wired; leave it unconnected and do not power the circuit until confirmed. Physical board/header checks, power sequencing, protection, termination and Silent-mode circuit review remain pending.
