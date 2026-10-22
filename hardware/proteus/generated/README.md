# Generated Proteus-design review bundle

This folder contains deterministic source-derived review artifacts; it does not contain a native Proteus project.

- reference-design.netlist.json: canonical machine-readable netlist.
- component-map.json: symbol-map review status, with unverified items flagged.
- reference-design.svg: editable vector companion; not a native Proteus schematic.
- bill-of-materials.csv: BOM with unresolved design values explicitly unassigned.
- native-project-status.json: current native-generation/import validation blocker.

The physical design must retain the original ESP32 TWAI baseline and NXP TJA1051T/3 SO8 part. Module pins, power sequencing, protection, termination, Silent-mode bias and independent hardware TX gate must be reviewed before fabrication or vehicle attachment.
