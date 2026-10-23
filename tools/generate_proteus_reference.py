#!/usr/bin/env python3
"""Generate deterministic hardware artifacts from Civic-Workbench's reviewed netlist.

Outputs a canonical netlist, BOM, electrical design checks and a net-label SVG schematic.
It does not fabricate Proteus DSN/PDSPRJ binaries: the native format is proprietary and
no official Python writer is available to this generator. See native-project-status.json.
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
GENERATOR_VERSION = "2.0.0"

ESP32_VDD = 3.3
ESP32_VIH_MIN = 0.75 * ESP32_VDD
ESP32_ABS_MAX = ESP32_VDD + 0.3
TJA_VCC_RANGE = (4.5, 5.5)
TJA_VIH_FRACTION = 0.7
S_IIH_MAX_A = 10e-6


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ohms(value: str) -> float:
    text = value.split()[0].upper().replace("R", "")
    if text.endswith("K"):
        return float(text[:-1]) * 1e3
    return float(text)


def build_nets(design: dict) -> dict[str, list[str]]:
    nets: dict[str, list[str]] = {}
    for comp in design["components"]:
        if not comp["fitted"]:
            continue
        for pin, net in comp["nets"].items():
            nets.setdefault(str(net), []).append(f"{comp['ref']}.{pin}")
    for conn in design["controller"]["connections"]:
        nets.setdefault(conn["net"], []).append(f"{design['controller']['ref']}.{conn['pin']}")
    return {name: sorted(members) for name, members in sorted(nets.items()) if not name.startswith("NC_")}


def no_connects(design: dict) -> list[str]:
    pins = [f"{c['ref']}.{p}" for c in design["components"] if c["fitted"]
            for p, n in c["nets"].items() if str(n).startswith("NC_")]
    pins += [f"{design['controller']['ref']}.{c['pin']}" for c in design["controller"]["connections"]
             if c["net"].startswith("NC_")]
    return sorted(pins)


def design_checks(design: dict) -> dict:
    comps = {c["ref"]: c for c in design["components"]}
    r_top, r_bot = ohms(comps["R3"]["value"]), ohms(comps["R4"]["value"])
    ratio = r_bot / (r_top + r_bot)
    vcc_lo, vcc_hi = TJA_VCC_RANGE
    s_drop = S_IIH_MAX_A * ohms(comps["R1"]["value"])
    checks = [
        {"id": "RXD_DIVIDER_MAX", "value_v": round(vcc_hi * ratio, 3), "limit_v": round(ESP32_ABS_MAX, 3),
         "pass": vcc_hi * ratio <= ESP32_ABS_MAX, "rule": "RXD_3V3 at VCC max must not exceed ESP32 VDD+0.3 V"},
        {"id": "RXD_DIVIDER_MIN", "value_v": round(vcc_lo * ratio, 3), "limit_v": round(ESP32_VIH_MIN, 3),
         "pass": vcc_lo * ratio >= ESP32_VIH_MIN, "rule": "RXD_3V3 HIGH at VCC min must exceed ESP32 VIH (0.75 VDD)"},
        {"id": "S_SILENT_HIGH", "value_v": round(vcc_lo - s_drop, 3), "limit_v": round(TJA_VIH_FRACTION * vcc_lo, 3),
         "pass": vcc_lo - s_drop >= TJA_VIH_FRACTION * vcc_lo, "rule": "S held >= 0.7 VCC (Silent) by R1 to +5V_CAN"},
        {"id": "S_NOT_MCU_DRIVEN", "pass": "S_SILENT" not in {c["net"] for c in design["controller"]["connections"]},
         "rule": "No MCU GPIO is connected to S in the receive-only revision"},
        {"id": "TXD_NOT_MCU_DRIVEN", "pass": "TXD_5V" not in {c["net"] for c in design["controller"]["connections"]},
         "rule": "GPIO21 does not drive TXD (3.3 V is below TXD VIH = 3.5 V)"},
        {"id": "PIN5_OPEN", "pass": design["transceiver"]["pins"][5]["net"].startswith("NC"),
         "rule": "Pin 5 left open: fail-safe for n.c., VIO and EN variants (AH1014 Table 21)"},
        {"id": "TERMINATION_NOT_FITTED", "pass": not any(comps[r]["fitted"] for r in ("R5", "R6", "C5")),
         "rule": "Termination is a bus-topology decision and is not fitted by default"},
    ]
    return {"schema_version": 1, "all_pass": all(c["pass"] for c in checks), "checks": checks,
            "assumptions": {"esp32_vdd_v": ESP32_VDD, "tja1051_vcc_range_v": list(TJA_VCC_RANGE),
                            "tja1051_vih_fraction_of_vio": TJA_VIH_FRACTION, "s_iih_max_a": S_IIH_MAX_A}}


# ---------------------------------------------------------------- SVG schematic
INK, NET, PWR, DNP, BG = "#1b2a3a", "#1f5f99", "#b23a2e", "#8a8f96", "#ffffff"


def _t(x, y, s, size=12, anchor="start", fill=INK, weight="normal", family="sans-serif"):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" text-anchor="{anchor}" '
            f'font-weight="{weight}" fill="{fill}">{xml.escape(str(s))}</text>')


def _line(x1, y1, x2, y2, color=INK, width=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{d}/>'


def _label(x, y, name, side="right"):
    color = PWR if name.startswith("+") or name == "GND" else NET
    anchor = "start" if side == "right" else "end"
    dx = 6 if side == "right" else -6
    return _t(x + dx, y + 4, name, 12, anchor, color, "bold", "monospace") + f'<circle cx="{x}" cy="{y}" r="3" fill="{color}"/>'


def _resistor(x, y, ref, value, net_top, net_bot, fitted=True):
    color = INK if fitted else DNP
    dash = None if fitted else "4 3"
    out = [_line(x, y, x, y + 20, color), _line(x, y + 70, x, y + 90, color),
           f'<rect x="{x-9}" y="{y+20}" width="18" height="50" fill="none" stroke="{color}" stroke-width="2"'
           + (f' stroke-dasharray="{dash}"' if dash else "") + "/>",
           _t(x + 16, y + 42, ref, 12, fill=color, weight="bold"), _t(x + 16, y + 57, value + ("" if fitted else " DNP"), 11, fill=color),
           _label(x, y, net_top, "left"), _label(x, y + 90, net_bot, "left")]
    return out


def _cap(x, y, ref, value, net_top, net_bot, fitted=True):
    color = INK if fitted else DNP
    return [_line(x, y, x, y + 38, color), _line(x - 16, y + 38, x + 16, y + 38, color, 3),
            _line(x - 16, y + 50, x + 16, y + 50, color, 3), _line(x, y + 50, x, y + 90, color),
            _t(x + 22, y + 42, ref, 12, fill=color, weight="bold"), _t(x + 22, y + 57, value + ("" if fitted else " DNP"), 11, fill=color),
            _label(x, y, net_top, "left"), _label(x, y + 90, net_bot, "left")]


def svg_source(design: dict, checks: dict) -> str:
    comps = {c["ref"]: c for c in design["components"]}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="940" viewBox="0 0 1400 940">',
         f'<rect width="100%" height="100%" fill="{BG}"/>',
         f'<rect x="10" y="10" width="1380" height="920" fill="none" stroke="{INK}" stroke-width="2"/>',
         _t(30, 44, "Civic-Workbench - NodeMCU-32S + NXP TJA1051 receive-only CAN interface", 22, weight="bold"),
         _t(30, 68, f"Rev {design['revision']} | {design['design_id']} | net-label schematic generated from hardware/reference/esp32-tja1051-netlist.yaml", 12, fill="#55606b")]

    # J1 NodeMCU-32S
    o += [f'<rect x="60" y="130" width="230" height="250" fill="#f3f7fb" stroke="{INK}" stroke-width="2"/>',
          _t(175, 160, "J1  NodeMCU-32S", 15, "middle", weight="bold"), _t(175, 178, "classic ESP32 / TWAI", 11, "middle", "#55606b")]
    for i, conn in enumerate(design["controller"]["connections"]):
        y = 220 + i * 55
        o.append(_t(280, y + 4, f"{conn['pin']} (hdr {conn['header_pin']})", 12, "end", family="monospace"))
        if conn["net"].startswith("NC"):
            o += [_line(290, y, 330, y), _line(324, y - 6, 336, y + 6, PWR), _line(324, y + 6, 336, y - 6, PWR),
                  _t(345, y + 4, "NC - listen-only, TX not wired", 11, fill=PWR)]
        else:
            o += [_line(290, y, 340, y), _label(340, y, conn["net"])]

    # U1 TJA1051
    ux, uy = 640, 150
    o += [f'<rect x="{ux}" y="{uy}" width="200" height="230" fill="#f4f9f1" stroke="{INK}" stroke-width="2"/>',
          _t(ux + 100, uy - 22, "U1  NXP TJA1051T  SO8", 15, "middle", weight="bold"),
          _t(ux + 100, uy - 6, "marking: NXP TJA1051 25 06 ND312", 10, "middle", "#55606b")]
    pins = design["transceiver"]["pins"]
    for p in range(1, 9):
        left = p <= 4
        y = uy + 35 + ((p - 1) if left else (8 - p)) * 52
        name, net = pins[p]["name"], pins[p]["net"]
        if left:
            o += [_line(ux - 60, y, ux, y), _t(ux + 8, y + 4, name, 12, family="monospace"), _t(ux - 4, y - 5, str(p), 10, "end", "#55606b")]
            o.append(_label(ux - 60, y, net, "left") if not net.startswith("NC") else "")
        else:
            o += [_line(ux + 200, y, ux + 260, y), _t(ux + 192, y + 4, name, 12, "end", family="monospace"), _t(ux + 204, y - 5, str(p), 10, fill="#55606b")]
            if net.startswith("NC"):
                o += [_line(ux + 254, y - 6, ux + 266, y + 6, PWR), _line(ux + 254, y + 6, ux + 266, y - 6, PWR),
                      _t(ux + 272, y + 4, "open", 11, fill=PWR)]
            else:
                o.append(_label(ux + 260, y, net, "right"))

    # passives
    o += _resistor(1000, 130, "R1", comps["R1"]["value"], "+5V_CAN", "S_SILENT")
    o += _resistor(1120, 130, "R2", comps["R2"]["value"], "+5V_CAN", "TXD_5V")
    o += _resistor(1000, 300, "R3", comps["R3"]["value"], "RXD_5V", "RXD_3V3")
    o += _resistor(1120, 300, "R4", comps["R4"]["value"], "RXD_3V3", "GND")
    o += _cap(1240, 130, "C1", "100nF", "+5V_CAN", "GND")
    o += _cap(1240, 300, "C2", "10uF", "+5V_CAN", "GND")

    # connectors
    o += [f'<rect x="60" y="470" width="190" height="150" fill="#fffaf0" stroke="{INK}" stroke-width="2"/>',
          _t(155, 495, "J2  CAN bench", 14, "middle", weight="bold")]
    for i, net in enumerate(["CANH", "CANL", "GND"]):
        y = 530 + i * 32
        o += [_t(235, y + 4, str(i + 1), 12, "end"), _line(250, y, 300, y), _label(300, y, net)]
    o += [f'<rect x="420" y="470" width="190" height="110" fill="#fffaf0" stroke="{INK}" stroke-width="2"/>',
          _t(515, 495, "J3  +5 V bench in", 14, "middle", weight="bold")]
    for i, net in enumerate(["+5V_CAN", "GND"]):
        y = 530 + i * 32
        o += [_t(595, y + 4, str(i + 1), 12, "end"), _line(610, y, 660, y), _label(660, y, net)]

    # optional (DNP) bus parts
    o.append(_t(820, 470, "Optional bus parts - NOT FITTED (fit only per bench topology)", 13, fill=DNP, weight="bold"))
    o += _resistor(830, 500, "R5", comps["R5"]["value"], "CANH", "SPLIT", False)
    o += _resistor(940, 500, "R6", comps["R6"]["value"], "SPLIT", "CANL", False)
    o += _cap(1050, 500, "C5", "4.7nF", "SPLIT", "GND", False)
    o += _cap(1150, 500, "C3", "100pF", "CANH", "GND", False)
    o += _cap(1250, 500, "C4", "100pF", "CANL", "GND", False)

    # notes
    o += [f'<rect x="30" y="660" width="1340" height="255" fill="#fbfbf6" stroke="#c9b98a"/>',
          _t(50, 688, "Design notes", 15, weight="bold")]
    notes = [
        "1. U1 is the plain TJA1051 (pin 5 n.c.): VIO = VCC, so TXD/S need >= 0.7 x VCC = 3.5 V. A 3.3 V ESP32 cannot drive them directly.",
        "2. R1 holds S HIGH from +5V_CAN -> Silent mode whenever U1 is powered, independent of the ESP32. No GPIO touches S.",
        "3. GPIO21 (TWAI TX) is not wired; R2 keeps TXD recessive. Rev B cannot transmit. TX needs a separately reviewed revision.",
        "4. R3/R4 divide RXD (5 V logic) to <= 3.44 V at VCC = 5.5 V for GPIO22. Never connect RXD directly to the ESP32.",
        "5. Power U1 from a current-limited 5.0 V bench supply (J3), not from ESP32 3.3 V. Bench GND, NodeMCU GND and CAN GND are common.",
        "6. Listen-only + Silent never ACKs: a bench capture needs a third CAN node that ACKs. Do not terminate onto a vehicle bus.",
        f"7. Generated design checks: {'ALL PASS' if checks['all_pass'] else 'FAILURES PRESENT'} (design-checks.json). Not bench-validated.",
    ]
    for i, n in enumerate(notes):
        o.append(_t(50, 716 + i * 27, n, 12))
    o.append("</svg>")
    return "\n".join(x for x in o if x) + "\n"


# ---------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    design = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    nets = build_nets(design)
    checks = design_checks(design)

    netlist = {"schema_version": 2, "design_id": design["design_id"], "revision": design["revision"],
               "source": design, "nets": nets, "no_connect": no_connects(design)}
    (output / "reference-design.netlist.json").write_text(
        json.dumps(netlist, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "design-checks.json").write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "reference-design.svg").write_text(svg_source(design, checks), encoding="utf-8")

    with (output / "bill-of-materials.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["Reference", "Value", "Package", "Fitted", "Nets", "Purpose"])
        writer.writerow([design["controller"]["ref"], "ESP32S NodeMCU / NodeMCU-32S", "board", "yes",
                         " ".join(f"{c['pin']}={c['net']}" for c in design["controller"]["connections"]),
                         "Controller board; verify header continuity"])
        for comp in design["components"]:
            value = comp["value"] + (" (marking NXP TJA1051 25 06 ND312; no substitution)" if comp["ref"] == "U1" else "")
            writer.writerow([comp["ref"], value, comp["package"], "yes" if comp["fitted"] else "DNP",
                             " ".join(f"{p}={n}" for p, n in comp["nets"].items()), comp.get("purpose", "")])

    component_map = {
        "schema_version": 2, "design_id": design["design_id"],
        "source_netlist": "hardware/reference/esp32-tja1051-netlist.yaml",
        "symbols": [{"ref": c["ref"], "value": c["value"], "fitted": c["fitted"], "library_symbol_verified": False}
                    for c in design["components"]]
        + [{"ref": "J1", "value": "NodeMCU-32S", "fitted": True, "library_symbol_verified": False}],
        "net_names": sorted(nets), "native_import_status": "not-performed",
    }
    (output / "component-map.json").write_text(json.dumps(component_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    native_status = {
        "schema_version": 2, "status": "blocked", "native_artifact_created": False,
        "proteus_version_inspected": "8.3.19906.0 under Wine (registry label: Proteus 8 Demonstration)",
        "official_python_schematic_generation_api_confirmed": False,
        "blockers": [
            "Native ROOT.DSN inside .pdsprj is a proprietary binary format with no official Python writer.",
            "The installed registry profile is labelled 'Demonstration'; demonstration editions are not expected to save designs - verify on the machine.",
            "The generating session had no shell access to the Proteus host, so no import/render could be attempted.",
        ],
        "completed_artifacts": ["reference-design.netlist.json", "design-checks.json", "reference-design.svg",
                                "component-map.json", "bill-of-materials.csv", "PROTEUS-CAPTURE.md", "artifact-manifest.json"],
        "required_next_action": "In a licensed Proteus 8 install, capture the schematic manually from PROTEUS-CAPTURE.md, save as hardware/proteus/native/civic-workbench-rev-b.pdsprj, and record the import/render evidence.",
        "note": "SVG is a review schematic, not a native Proteus file.",
    }
    (output / "native-project-status.json").write_text(json.dumps(native_status, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    capture = ["# Proteus capture sheet - Rev " + design["revision"], "",
               "Place these parts in Proteus ISIS and connect pins by net name (use terminals/net labels with exactly these names).",
               "Generated from the reviewed netlist; regenerate with `make design-source` after any netlist change.", "",
               "## Parts", "", "| Ref | Value | Package | Fit |", "|---|---|---|---|"]
    for comp in design["components"]:
        capture.append(f"| {comp['ref']} | {comp['value']} | {comp['package']} | {'yes' if comp['fitted'] else 'DNP'} |")
    capture += ["| J1 | NodeMCU-32S (use a header/connector symbol: GPIO22, GPIO21, GND) | board | yes |", "",
                "## Nets", "", "| Net | Members |", "|---|---|"]
    for name, members in nets.items():
        capture.append(f"| {name} | {', '.join(members)} |")
    capture += ["", "No-connect (place no-connect markers): " + ", ".join(no_connects(design)), ""]
    (output / "PROTEUS-CAPTURE.md").write_text("\n".join(capture), encoding="utf-8")

    readme = f"""# Generated hardware design bundle - Rev {design['revision']}

Receive-only NodeMCU-32S + NXP TJA1051T (SO8) CAN interface. Generated by `tools/generate_proteus_reference.py`
from `hardware/reference/esp32-tja1051-netlist.yaml`. Do not edit these files by hand.

- reference-design.svg: net-label schematic for review (not a native Proteus file).
- reference-design.netlist.json: canonical netlist with resolved nets.
- design-checks.json: computed electrical checks (logic levels, Silent bias, pin 5, termination).
- bill-of-materials.csv: fitted and DNP parts.
- PROTEUS-CAPTURE.md: part and net list for capturing the native schematic in Proteus.
- native-project-status.json: why no native .pdsprj exists yet.

Status: design checks pass on paper; nothing here is bench-validated.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    names = ["reference-design.netlist.json", "design-checks.json", "reference-design.svg", "component-map.json",
             "bill-of-materials.csv", "native-project-status.json", "PROTEUS-CAPTURE.md", "README.md"]
    manifest = {
        "schema_version": 2, "design_id": design["design_id"], "revision": design["revision"],
        "generator": "tools/generate_proteus_reference.py", "generator_version": GENERATOR_VERSION,
        "input": {"path": "hardware/reference/esp32-tja1051-netlist.yaml", "sha256": sha256(SOURCE)},
        "deterministic_outputs": {name: sha256(output / name) for name in names},
        "native_project": {"status": "blocked", "import_render_validation": "not-performed"},
    }
    (output / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "files": names + ["artifact-manifest.json"],
                      "design_checks_pass": checks["all_pass"], "native_project": "BLOCKED"}, indent=2))
    return 0 if checks["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
