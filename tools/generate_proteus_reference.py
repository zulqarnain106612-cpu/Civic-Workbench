#!/usr/bin/env python3
"""Generate deterministic hardware artifacts from Civic-Workbench's reviewed netlist.

Outputs a canonical netlist, BOM, electrical design checks, a net-label SVG review schematic and two
OrCAD-dialect EDIF 2 0 0 schematics for Proteus 9.2 SP1 "File > Import ECAD Files" (the only schematic
import route documented in the installed IMPORTER.chm): the Rev B hardware sheet and a simulation bench that
adds Labcenter's CAN Bus Analyser and a behavioural Engine ECU. Proteus' own DSN/PDSPRJ binaries are not
fabricated: that format is proprietary and Labcenter publishes no Python writer for it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.sax.saxutils as xml
import yaml

import proteus_edif

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hardware/reference/esp32-tja1051-netlist.yaml"
DEFAULT_OUTPUT = ROOT / "hardware/proteus/generated"
GENERATOR_VERSION = "3.0.0"

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
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="940" viewBox="0 0 1400 940">',
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
    o += ['<rect x="30" y="660" width="1340" height="255" fill="#fbfbf6" stroke="#c9b98a"/>',
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


# ---------------------------------------------------------------- EDIF (Proteus ECAD import)
EDIF_TIMESTAMP = (2026, 10, 23, 0, 0, 0)   # fixed so output stays byte-deterministic
TJA1051_LEFT = ("1", "2", "3", "4")
TJA1051_RIGHT = ("8", "7", "6", "5")

# Labcenter library facts read from the installed Proteus 9.2 SP1 CANBUS.LIB / DEVICE.LIB / CAPACITORS.LIB.
# There is no TJA1051 model in the library; Labcenter's own transceivers (TJA1050, MCP2551, SN65HVD23x)
# all bind the same behavioural primitive, so the TJA1051 symbol is bound to it for simulation only.
SIM_TRANSCEIVER_PROPS = {"PRIMITIVE": "DIGITAL,CAN_TRANSCEIVER", "MODDLL": "CANBUS.DLL", "ITFMOD": "AVR",
                         "FD_CAPABLE": "FALSE", "MAX_BAUD": "1000000",
                         "SIM_NOTE": "Behavioural CAN_TRANSCEIVER model; Silent pin S not modelled"}
SIM_RES_PROPS = {"PRIMITIVE": "ANALOG", "PRIMTYPE": "RESISTOR"}
SIM_CAP_PROPS = {"PRIMITIVE": "ANALOGUE,CAPACITOR"}


def _edif_parts(design: dict, simulation: bool) -> list[proteus_edif.Part]:
    P = proteus_edif.Pin
    pins = design["transceiver"]["pins"]
    parts = []
    for comp in design["components"]:
        if simulation and not comp["fitted"]:
            continue
        props = {"PACKAGE": comp["package"], "FITTED": "yes" if comp["fitted"] else "DNP"}
        ref = comp["ref"]
        if ref == "U1":
            pin_list = [P(n, pins[int(n)]["name"], "L") for n in TJA1051_LEFT] + \
                       [P(n, pins[int(n)]["name"], "R") for n in TJA1051_RIGHT]
            props["MARKING"] = design["transceiver"]["reported_top_marking"]
            if simulation:
                props.update(SIM_TRANSCEIVER_PROPS)
            parts.append(proteus_edif.Part(ref, "TJA1051T_SO8", comp["value"], pin_list, props))
        elif ref.startswith(("R", "C")):
            if simulation:
                props.update(SIM_RES_PROPS if ref.startswith("R") else SIM_CAP_PROPS)
            cell = "RES_2P" if ref.startswith("R") else "CAP_2P"
            parts.append(proteus_edif.Part(ref, cell, comp["value"], [P("1", "1", "L"), P("2", "2", "R")], props))
        elif ref == "J2":
            parts.append(proteus_edif.Part(ref, "CONN_CAN_3P", comp["value"],
                                           [P("1", "CANH", "L"), P("2", "CANL", "L"), P("3", "GND", "L")], props))
        elif ref == "J3":
            parts.append(proteus_edif.Part(ref, "CONN_PWR_2P", comp["value"],
                                           [P("1", "+5V", "L"), P("2", "GND", "L")], props))
        else:
            raise ValueError(f"no EDIF symbol for {ref}")
    ctrl = design["controller"]
    parts.insert(0, proteus_edif.Part(ctrl["ref"], "NODEMCU32S_HDR", "NodeMCU-32S",
                                      [P(str(c["header_pin"]), c["pin"], "R") for c in ctrl["connections"]],
                                      {"BOARD": ctrl["board_id"], "SIM_NOTE": "Header only; ESP32 is not simulated"}))
    if simulation:
        parts += [
            proteus_edif.Part("BAT1", "DC_SOURCE_2P", "5V", [P("1", "+", "L"), P("2", "-", "R")],
                              {"PRIMITIVE": "ANALOGUE", "SIM_NOTE": "Stands in for the J3 bench supply"}),
            proteus_edif.Part("U2", "CAN_ANALYZER", "CAN_ANALYZER",
                              [P("1", "GND", "L"), P("2", "VCC", "L"), P("3", "CANH", "R"), P("4", "CANL", "R")],
                              {"PRIMITIVE": "DIGITAL,CAN_ANALYZER", "MODDLL": "CANBUS.DLL", "ITFMOD": "AVR",
                               "DATABASE": "vehicle.dbc"}),
            proteus_edif.Part("U3", "ENGINE_ECU", "ENGINE_ECU", [P("1", "CANH", "L"), P("2", "CANL", "L")],
                              {"PRIMITIVE": "DIGITAL,ENGINE_ECU", "MODDLL": "CANAUTO.DLL", "SHOW_POPUP": "1",
                               "SIM_NOTE": "Labcenter behavioural ECU: synthetic traffic source, not vehicle data"}),
        ]
    return parts


def edif_nets(design: dict, simulation: bool) -> dict[str, list[str]]:
    header = {c["pin"]: str(c["header_pin"]) for c in design["controller"]["connections"]}
    nets: dict[str, list[str]] = {}
    for comp in design["components"]:
        if simulation and not comp["fitted"]:
            continue
        for pin, net in comp["nets"].items():
            if not str(net).startswith("NC_"):
                nets.setdefault(str(net), []).append(f"{comp['ref']}.{pin}")
    for conn in design["controller"]["connections"]:
        if not conn["net"].startswith("NC_"):
            nets.setdefault(conn["net"], []).append(f"{design['controller']['ref']}.{header[conn['pin']]}")
    if simulation:
        nets["+5V_CAN"] += ["BAT1.1", "U2.2"]
        nets["GND"] += ["BAT1.2", "U2.1"]
        nets["CANH"] += ["U2.3", "U3.1"]
        nets["CANL"] += ["U2.4", "U3.2"]
    return {name: sorted(members) for name, members in sorted(nets.items())}


def edif_source(design: dict, simulation: bool) -> str:
    title = ("Rev %s simulation bench (CAN analyser + behavioural ECU)" if simulation
             else "Rev %s hardware schematic") % design["revision"]
    name = "CIVIC_WORKBENCH_REV_" + design["revision"] + ("_SIM" if simulation else "")
    return proteus_edif.write_edif(name, _edif_parts(design, simulation), edif_nets(design, simulation),
                                   title, EDIF_TIMESTAMP)


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
        "net_names": sorted(nets), "native_import_status": "edif-generated-import-not-performed",
    }
    (output / "component-map.json").write_text(json.dumps(component_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    (output / "civic-workbench-rev-b.edf").write_text(edif_source(design, simulation=False), encoding="utf-8")
    (output / "civic-workbench-rev-b-sim.edf").write_text(edif_source(design, simulation=True), encoding="utf-8")

    native_status = {
        "schema_version": 3, "status": "import-pending",
        "native_artifact_created": False,
        "import_artifacts": ["civic-workbench-rev-b.edf", "civic-workbench-rev-b-sim.edf"],
        "import_route": "Proteus 9.2 SP1: File > Import ECAD Files > ORCAD EDIF 2 (*.edf) - documented in Help/IMPORTER.chm",
        "proteus_version_inspected": "Proteus 9 Professional 9.2 SP1 build 45801 under Wine 10.0",
        "official_python_schematic_generation_api_confirmed": False,
        "blockers": [
            "The installed Proteus reports 'Licensing error. Bad or missing Customer Key' (Unlicensed Version); in that state the Schematic Editor does not open and File > Import ECAD Files produced no project, so import, save and simulation could not be executed.",
            "Native ROOT.DSN inside .pdsprj is a proprietary binary format with no published writer; it is produced by Proteus itself when the imported design is saved.",
            "The simulation bench binds the TJA1051 symbol to Labcenter's generic CAN_TRANSCEIVER behavioural model (CANBUS.LIB has no TJA1051 model); the Silent pin S is not modelled.",
        ],
        "completed_artifacts": ["reference-design.netlist.json", "design-checks.json", "reference-design.svg",
                                "component-map.json", "bill-of-materials.csv", "PROTEUS-CAPTURE.md",
                                "civic-workbench-rev-b.edf", "civic-workbench-rev-b-sim.edf", "artifact-manifest.json"],
        "verified_offline": "EDIF stored netlists and drawn wire connectivity are reproduced by an independent reader in tests/test_proteus_generator.py",
        "required_next_action": "With a working licence: File > Import ECAD Files, select civic-workbench-rev-b-sim.edf, confirm the importer log reports no netlist differences, save as hardware/proteus/native/civic-workbench-rev-b-sim.pdsprj, press Run and record the CAN Bus Analyser capture as evidence; repeat import for civic-workbench-rev-b.edf.",
        "note": "SVG is a review drawing. The .edf files are the Proteus import sources; no .pdsprj is claimed.",
    }
    (output / "native-project-status.json").write_text(json.dumps(native_status, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    capture = ["# Proteus capture sheet - Rev " + design["revision"], "",
               "Import `civic-workbench-rev-b.edf` (hardware) or `civic-workbench-rev-b-sim.edf` (simulation bench) with "
               "Proteus File > Import ECAD Files. Use this sheet to check the imported connectivity, or to capture by hand "
               "(terminals/net labels with exactly these names).",
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
- civic-workbench-rev-b.edf: Rev B hardware schematic, OrCAD EDIF2 for Proteus File > Import ECAD Files.
- civic-workbench-rev-b-sim.edf: Rev B fitted parts plus Proteus CAN Bus Analyser (U2) and behavioural Engine ECU (U3)
  on CANH/CANL, with Labcenter simulation primitives on each part. Import, save as .pdsprj, then Run.
- PROTEUS-CAPTURE.md: part and net list for checking the imported schematic.
- native-project-status.json: import status and what still blocks a saved native project.

Status: design checks pass on paper; nothing here is bench-validated.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    names = ["reference-design.netlist.json", "design-checks.json", "reference-design.svg", "component-map.json",
             "bill-of-materials.csv", "native-project-status.json", "PROTEUS-CAPTURE.md", "README.md",
             "civic-workbench-rev-b.edf", "civic-workbench-rev-b-sim.edf"]
    manifest = {
        "schema_version": 2, "design_id": design["design_id"], "revision": design["revision"],
        "generator": "tools/generate_proteus_reference.py", "generator_version": GENERATOR_VERSION,
        "input": {"path": "hardware/reference/esp32-tja1051-netlist.yaml", "sha256": sha256(SOURCE)},
        "deterministic_outputs": {name: sha256(output / name) for name in names},
        "native_project": {"status": "import-pending", "import_render_validation": "not-performed",
                           "import_sources": ["civic-workbench-rev-b.edf", "civic-workbench-rev-b-sim.edf"]},
    }
    (output / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "files": names + ["artifact-manifest.json"],
                      "design_checks_pass": checks["all_pass"], "native_project": "IMPORT-PENDING"}, indent=2))
    return 0 if checks["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
