#!/usr/bin/env python3
"""Generate deterministic review artifacts from Civic-Workbench's hardware netlist.

Does not fabricate Proteus DSN/PDSPRJ binaries. The inspected Proteus installation uses a
proprietary schematic format, and no official Python native-schematic writer was confirmed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.sax.saxutils as xml
import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hardware/reference/esp32-tja1051-netlist.yaml"
DEFAULT_OUTPUT = ROOT / "hardware/proteus/generated"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def svg_source(design: dict) -> str:
    pins = design["transceiver"]["pins"]
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="830" viewBox="0 0 1240 830">',
        '<rect width="100%" height="100%" fill="#fbfcfe"/>',
        '<text x="40" y="44" font-family="sans-serif" font-size="25" font-weight="bold" fill="#172c40">Civic-Workbench / NodeMCU-32S + TJA1051</text>',
        '<text x="40" y="72" font-family="sans-serif" font-size="13" fill="#5c7185">Review artifact only - physical header checks and unresolved values remain open</text>',
        '<rect x="45" y="135" width="345" height="330" rx="10" fill="#edf4fc" stroke="#486c94" stroke-width="2"/>',
        '<text x="217" y="172" text-anchor="middle" font-family="sans-serif" font-size="19" font-weight="bold" fill="#1d3b5b">ESP32S NodeMCU / NodeMCU-32S</text>',
        '<text x="217" y="196" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#435c76">Classic ESP32 / integrated TWAI</text>',
        '<text x="75" y="245" font-family="monospace" font-size="13" fill="#1d3b5b">TWAI_TX_GPIO = 21</text>',
        '<text x="75" y="276" font-family="monospace" font-size="13" fill="#1d3b5b">TWAI_RX_GPIO = 22</text>',
        '<text x="75" y="315" font-family="sans-serif" font-size="12" fill="#435c76">GPIO21/22 source mapping selected</text>',
        '<text x="75" y="341" font-family="sans-serif" font-size="12" fill="#435c76">Verify physical header continuity/revision</text>',
        '<text x="75" y="392" font-family="sans-serif" font-size="12" fill="#435c76">Hardware initialization and physical TX disabled</text>',
        '<text x="75" y="418" font-family="sans-serif" font-size="12" fill="#435c76">TX_GATE_GPIO = UNASSIGNED; physical TX OFF</text>',
        '<rect x="470" y="155" width="300" height="280" rx="10" fill="#f2f8ed" stroke="#658b4a" stroke-width="2"/>',
        '<text x="620" y="188" text-anchor="middle" font-family="sans-serif" font-size="18" font-weight="bold" fill="#2e5120">U1 / NXP TJA1051 SO8</text>',
    ]
    y = 226
    for pin, info in sorted(pins.items(), key=lambda pair: int(pair[0])):
        label = xml.escape("Pin " + str(pin) + ": " + str(info["name"]))
        net = xml.escape(str(info["net"]))
        x = 490 if int(pin) in {1, 2, 3, 4} else 642
        out.append(f'<text x="{x}" y="{y}" font-family="monospace" font-size="12" fill="#2e5120">{label}</text>')
        out.append(f'<text x="{x}" y="{y+15}" font-family="sans-serif" font-size="10" fill="#4c6840">{net}</text>')
        y += 47
        if int(pin) == 4:
            y = 226
    out += [
        '<path d="M390 285 H445 V285 H470" stroke="#4e789e" stroke-width="3" fill="none"/>',
        '<path d="M390 315 H432 V389 H470" stroke="#4e789e" stroke-width="3" fill="none"/>',
        '<text x="428" y="260" font-family="sans-serif" font-size="10" fill="#385d7e" text-anchor="middle">TWAI TX</text>',
        '<text x="430" y="406" font-family="sans-serif" font-size="10" fill="#385d7e" text-anchor="middle">TWAI RX</text>',
        '<path d="M770 310 H870 V230 H925" stroke="#48783f" stroke-width="3" fill="none"/>',
        '<path d="M770 365 H885 V470 H925" stroke="#48783f" stroke-width="3" fill="none"/>',
        '<rect x="925" y="188" width="260" height="90" rx="8" fill="#fff8e9" stroke="#a9843c" stroke-width="2"/>',
        '<text x="1055" y="220" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#6b4d12">CANH / CANL</text>',
        '<text x="1055" y="244" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#6b4d12">Connector pinout TBD</text>',
        '<rect x="925" y="428" width="260" height="100" rx="8" fill="#fff0ee" stroke="#bf6861" stroke-width="2"/>',
        '<text x="1055" y="459" text-anchor="middle" font-family="sans-serif" font-size="15" font-weight="bold" fill="#7c2923">Silent / TX interlock</text>',
        '<text x="1055" y="482" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#7c2923">Independent hardware gate required</text>',
        '<text x="1055" y="501" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#7c2923">Values/topology review required</text>',
        '<path d="M217 465 V540 H620 V435" stroke="#8f743d" stroke-width="2" stroke-dasharray="7 6" fill="none"/>',
        '<rect x="45" y="565" width="1140" height="180" rx="9" fill="#fff9e9" stroke="#c29a47" stroke-width="1.5"/>',
        '<text x="70" y="600" font-family="sans-serif" font-size="17" font-weight="bold" fill="#765718">Open electrical / CAD decisions</text>',
        '<text x="72" y="630" font-family="sans-serif" font-size="13" fill="#765718">- Confirm the exact marked TJA1051 pin-5 function before assigning its net or power rail.</text>',
        '<text x="72" y="657" font-family="sans-serif" font-size="13" fill="#765718">- Decoupling, transient protection, connector pinout and bus termination remain unassigned.</text>',
        '<text x="72" y="684" font-family="sans-serif" font-size="13" fill="#765718">- TJA1051 S must default HIGH (Silent), including MCU reset/unpowered conditions.</text>',
        '<text x="72" y="711" font-family="sans-serif" font-size="13" fill="#765718">- Native Proteus DSN/PDSPRJ generation/import is blocked pending supported automation.</text>',
        '</svg>',
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    design = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    (output / "reference-design.netlist.json").write_text(
        json.dumps(design, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "reference-design.svg").write_text(svg_source(design), encoding="utf-8")

    with (output / "bill-of-materials.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["Reference", "Manufacturer", "Part", "Package", "Status", "Notes"])
        writer.writerow(["U1", "NXP", "TJA1051", "SO8 / SOT96-1", "required", "Reported marking: NXP TJA1051 25 06 ND312; no substitutions; verify SO8 pin 1 before assembly"])
        writer.writerow(["U_MCU", "Espressif / NodeMCU", "ESP32S NodeMCU / NodeMCU-32S", "board module", "specified", "GPIO21 TWAI TX and GPIO22 TWAI RX source mapping; verify physical board revision and header continuity"])
        writer.writerow(["J1", "TBD", "CAN connector", "TBD", "not-selected", "CANH/CANL/ground pins unverified"])
        writer.writerow(["R-SILENT", "TBD", "Silent-mode pull-up", "TBD", "value-unassigned", "Must hold TJA1051 S HIGH if MCU is reset/unpowered"])
        writer.writerow(["C-VCC", "TBD", "VCC decoupling", "TBD", "value-unassigned", "Determine from final reviewed design"])
        writer.writerow(["C-LOGIC", "TBD", "Variant-dependent pin-5 logic decoupling", "TBD", "value-unassigned", "Only populate if confirmed by the exact marked component datasheet"])

    component_map = {
        "schema_version": 1,
        "design_id": design["design_id"],
        "source_netlist": "hardware/reference/esp32-tja1051-netlist.yaml",
        "symbols": [
            {"ref": "U1", "symbol": "TJA1051", "library_symbol_verified": False, "reason": "Installed Proteus symbol identity not verified."},
            {"ref": "U_MCU", "symbol": "NodeMCU-32S board placeholder", "library_symbol_verified": False, "reason": "Exact board is specified; physical PCB revision and GPIO21/GPIO22 header continuity have not been checked."},
            {"ref": "TX_GATE", "symbol": "Conceptual independent hardware gate", "library_symbol_verified": False, "reason": "Not an electrical implementation; design review required."},
        ],
        "net_names": sorted({str(pin["net"]) for pin in design["transceiver"]["pins"].values()}),
        "native_import_status": "not-performed",
    }
    (output / "component-map.json").write_text(json.dumps(component_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    native_status = {
        "schema_version": 1,
        "status": "blocked",
        "native_artifact_created": False,
        "proteus_version_inspected": "8.3.19906.0 (registry-path inference; entitlement unverified)",
        "official_python_schematic_generation_api_confirmed": False,
        "evidence": [
            "Local .pdsprj samples are ZIP packages containing PROJECT.XML, ROOT.CDB and proprietary binary ROOT.DSN (ISIS SCHEMATIC FILE).",
            "The inspected installation did not contain an identified official Python native-schematic writer.",
            "The official Labcenter schematic/download pages inspected do not document an official Python-native schematic writer.",
        ],
        "completed_artifacts": [
            "reference-design.netlist.json", "reference-design.svg", "component-map.json",
            "bill-of-materials.csv", "artifact-manifest.json",
        ],
        "required_next_action": "Confirm an official Labcenter-supported automation API or utility, then create and import/render a native project using the licensed toolchain.",
        "note": "SVG is only a review companion. It is not a native Proteus schematic.",
    }
    (output / "native-project-status.json").write_text(json.dumps(native_status, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    readme = """# Generated Proteus-design review bundle

This folder contains deterministic source-derived review artifacts; it does not contain a native Proteus project.

- reference-design.netlist.json: canonical machine-readable netlist.
- component-map.json: symbol-map review status, with unverified items flagged.
- reference-design.svg: editable vector companion; not a native Proteus schematic.
- bill-of-materials.csv: BOM with unresolved design values explicitly unassigned.
- native-project-status.json: current native-generation/import validation blocker.

The exact hardware baseline is ESP32S NodeMCU / NodeMCU-32S (classic ESP32 with TWAI) and NXP TJA1051 SO8 (SOT96-1); substitutions are not authorized. Owner-reported visible marking is preserved verbatim: NXP TJA1051 25 06 ND312. GPIO21 maps to TWAI TX and GPIO22 to TWAI RX in source. Physical board revision/header continuity, power sequencing, protection, termination and Silent-mode bias must be reviewed before assembly or vehicle connection.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    names = [
        "reference-design.netlist.json", "reference-design.svg", "component-map.json",
        "bill-of-materials.csv", "native-project-status.json", "README.md",
    ]
    manifest = {
        "schema_version": 1,
        "design_id": design["design_id"],
        "generator": "tools/generate_proteus_reference.py",
        "generator_version": "1.0.0",
        "input": {"path": "hardware/reference/esp32-tja1051-netlist.yaml", "sha256": sha256(SOURCE)},
        "deterministic_outputs": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in names},
        "native_project": {"status": "blocked", "import_render_validation": "not-performed"},
    }
    (output / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "files": names + ["artifact-manifest.json"],
                      "native_project": "BLOCKED - official writer/API not confirmed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
