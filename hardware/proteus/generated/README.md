# Generated Proteus-design review bundle

This folder contains deterministic source-derived review artifacts; it does not contain a native Proteus project.

- reference-design.netlist.json: canonical machine-readable netlist.
- component-map.json: symbol-map review status, with unverified items flagged.
- reference-design.svg: editable vector companion; not a native Proteus schematic.
- bill-of-materials.csv: BOM with unresolved design values explicitly unassigned.
- native-project-status.json: current native-generation/import validation blocker.

The exact hardware baseline is ESP32S NodeMCU / NodeMCU-32S (classic ESP32 with TWAI) and NXP TJA1051 SO8 (SOT96-1); substitutions are not authorized. Owner-reported visible marking is preserved verbatim: NXP TJA1051 25 06 ND312. GPIO21 maps to TWAI TX and GPIO22 to TWAI RX in source. Physical board revision/header continuity, power sequencing, protection, termination and Silent-mode bias must be reviewed before assembly or vehicle connection.
