"""OrCAD-dialect EDIF 2 0 0 writer and reader for Proteus ECAD import.

Proteus 9.2 SP1 documents exactly one schematic import route (IMPORTER.chm, "Importing EDIF Files"):
File > Import ECAD Files, OrCAD v9.2 / 17.2 EDIF2. Proteus parses the file, draws the schematic and then
compares its own netlist with the netlist stored in the EDIF ``joined`` records. This module therefore
emits both: explicit ``joined`` netlists and wire figures whose every connection is endpoint-to-endpoint
(no T-junction on a wire interior, no wire passing over a pin), so drawn connectivity equals stored
connectivity.

``read_edif`` is an independent S-expression reader used by the tests to prove that (a) the stored
netlist equals the reviewed netlist and (b) the drawn wire geometry reproduces exactly the same nets.
Units: 1 EDIF distance unit = 0.01 inch (``scale 1 (e 254 -6)`` metres), pins on a 0.1 inch grid.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

PIN_PITCH = 20          # 0.2 inch between pins on one side
PIN_LEN = 30            # pin stub drawn inside the symbol
BODY_W = 140
PART_GAP = 420          # horizontal spacing between part origins (leaves room for escape columns)
CHANNEL = 10            # spacing of escape columns and trunk rows


@dataclass
class Pin:
    number: str
    name: str
    side: str            # "L" or "R"


@dataclass
class Part:
    ref: str
    cell: str
    value: str
    pins: list[Pin]
    properties: dict[str, str] = field(default_factory=dict)


def ident(text: str) -> str:
    """EDIF identifier: letters, digits and '_' only, must start with a letter or '&'."""
    body = re.sub(r"[^A-Za-z0-9_]", "_", text)
    return body if body[:1].isalpha() else "&" + body


def named(text: str) -> str:
    token = ident(text)
    return token if token.lstrip("&") == text else f'(rename {token} "{text}")'


def q(text: str) -> str:
    return '"' + str(text).replace('"', "'") + '"'


def _rows(part: Part, side: str) -> list[Pin]:
    return [p for p in part.pins if p.side == side]


def _height(part: Part) -> int:
    return PIN_PITCH * (max(len(_rows(part, "L")), len(_rows(part, "R")), 1) + 1)


def pin_points(part: Part) -> dict[str, tuple[int, int]]:
    """Connection points relative to the symbol origin (top-left of body, y grows upward in EDIF)."""
    pts: dict[str, tuple[int, int]] = {}
    for side, x in (("L", -PIN_LEN), ("R", BODY_W + PIN_LEN)):
        for i, pin in enumerate(_rows(part, side)):
            pts[pin.number] = (x, -PIN_PITCH * (i + 1))
    return pts


def _cell(part: Part) -> str:
    h = _height(part)
    ports, impls = [], []
    for pin in part.pins:
        pid = ident("P" + pin.number)
        x, y = pin_points(part)[pin.number]
        inner = 0 if pin.side == "L" else BODY_W
        ports.append(f'          (port (rename {pid} {q(pin.name)}) (designator {q(pin.number)}) (direction INOUT))')
        impls.append(
            f"            (portImplementation {pid}\n"
            f"              (figure PIN (path (pointList (pt {x} {y}) (pt {inner} {y}))))\n"
            f"              (connectLocation (figure PINDOT (dot (pt {x} {y})))))")
    labels = [f'            (commentGraphics (annotate (stringDisplay {q(p.name)} (display PINNAME '
              f'(origin (pt {6 if p.side == "L" else BODY_W - 6} {pin_points(part)[p.number][1]}))))))'
              for p in part.pins]
    return "\n".join([
        f"    (cell {ident(part.cell)}",
        "      (cellType GENERIC)",
        "      (view Normal",
        "        (viewType SCHEMATIC)",  # Proteus IMPORTER makes a component only from SCHEMATIC + GENERIC
        "        (interface",
        *ports,
        "          (symbol",
        f"            (boundingBox (rectangle (pt {-PIN_LEN} 0) (pt {BODY_W + PIN_LEN} {-h})))",
        *impls,
        f"            (figure BODYFIGURE (rectangle (pt 0 0) (pt {BODY_W} {-h})))",
        *labels,
        "            (keywordDisplay designator (display PARTREFERENCE (origin (pt 0 12))))",
        "            (propertyDisplay VALUE (display PARTVALUE (origin (pt 0 " + str(-h - 12) + "))))))))",
    ])


@dataclass
class Layout:
    origins: dict[str, tuple[int, int]]
    wires: dict[str, list[tuple[tuple[int, int], tuple[int, int]]]]


def layout(parts: list[Part], nets: dict[str, list[str]]) -> Layout:
    """Place parts in one row and route every net on its own trunk below the row.

    Each connected pin escapes horizontally to a private column, drops vertically to its net's trunk row,
    and the trunk is split into segments between consecutive drops so every join is endpoint-to-endpoint.
    """
    origins = {p.ref: (100 + PIN_LEN + 40 + i * PART_GAP, 800) for i, p in enumerate(parts)}
    by_ref = {p.ref: p for p in parts}
    lowest = min(origins[p.ref][1] - _height(p) for p in parts)
    wires: dict[str, list] = {}
    column_used: set[int] = set()
    for k, (net, members) in enumerate(sorted(nets.items())):
        trunk_y = lowest - 40 - CHANNEL * 2 * k
        drops = []
        segs = []
        for member in members:
            ref, num = member.split(".", 1)
            part = by_ref[ref]
            pin = next(p for p in part.pins if p.number == num)
            ox, oy = origins[ref]
            px, py = pin_points(part)[num]
            ax, ay = ox + px, oy + py
            step = -CHANNEL if pin.side == "L" else CHANNEL
            cx = ax + step
            while cx in column_used:
                cx += step
            column_used.add(cx)
            segs.append(((ax, ay), (cx, ay)))
            segs.append(((cx, ay), (cx, trunk_y)))
            drops.append(cx)
        drops.sort()
        for a, b in zip(drops, drops[1:]):
            segs.append(((a, trunk_y), (b, trunk_y)))
        wires[net] = segs
    return Layout(origins, wires)


def write_edif(design_name: str, parts: list[Part], nets: dict[str, list[str]], title: str,
               timestamp: tuple[int, int, int, int, int, int] = (2026, 1, 1, 0, 0, 0)) -> str:
    lay = layout(parts, nets)
    cells, seen = [], set()
    for part in parts:
        if part.cell not in seen:
            seen.add(part.cell)
            cells.append(_cell(part))
    insts = []
    for part in parts:
        x, y = lay.origins[part.ref]
        props = "".join(f"\n          (property {ident(k)} (string {q(v)}))" for k, v in part.properties.items())
        insts.append(
            f"        (instance {ident(part.ref)}\n"
            f"          (viewRef Normal (cellRef {ident(part.cell)} (libraryRef CIVIC_LIB)))\n"
            f"          (transform (orientation R0) (origin (pt {x} {y})))\n"
            f"          (designator {q(part.ref)})\n"
            f"          (property VALUE (string {q(part.value)})){props})")
    net_txt = []
    for net, members in sorted(nets.items()):
        refs = " ".join(f"(portRef {ident('P' + m.split('.', 1)[1])} (instanceRef {ident(m.split('.', 1)[0])}))"
                        for m in members)
        figs = "".join(f"\n          (figure WIRE (path (pointList (pt {a[0]} {a[1]}) (pt {b[0]} {b[1]}))))"
                       for a, b in lay.wires[net])
        net_txt.append(f"        (net {named(net)}\n          (joined {refs}){figs})")
    ts = " ".join(str(v) for v in timestamp)
    return "\n".join([
        f"(edif {ident(design_name)}",
        "  (edifVersion 2 0 0)",
        "  (edifLevel 0)",
        "  (keywordMap (keywordLevel 0))",
        "  (status",
        "    (written",
        f"      (timeStamp {ts})",
        '      (program "CAPTURE.EXE" (version "17.2.0"))',
        f"      (comment {q('Generated by Civic-Workbench tools/generate_proteus_reference.py - ' + title)})))",
        "  (library CIVIC_LIB",
        "    (edifLevel 0)",
        "    (technology",
        "      (numberDefinition (scale 1 (e 254 -6) (unit DISTANCE)))",
        "      (figureGroup PIN (pathWidth 0) (borderWidth 0))",
        "      (figureGroup PINDOT (pathWidth 0) (borderWidth 0))",
        "      (figureGroup BODYFIGURE (pathWidth 0) (borderWidth 0)))",
        *cells,
        "  )",
        "  (library DESIGNS",
        "    (edifLevel 0)",
        "    (technology",
        "      (numberDefinition (scale 1 (e 254 -6) (unit DISTANCE)))",
        "      (figureGroup WIRE (pathWidth 0) (borderWidth 0)))",
        f"    (cell {ident(design_name)}",
        "      (cellType GENERIC)",
        "      (view Schematic",
        "        (viewType SCHEMATIC)",
        "        (interface)",
        "        (contents",
        '        (page (rename &PAGE1 "PAGE1")',
        "          (pageSize (rectangle (pt 0 0) (pt 6000 1200)))",
        *insts,
        *net_txt,
        "        )))))",
        f"  (design {ident(design_name)} (cellRef {ident(design_name)} (libraryRef DESIGNS))))",
        "",
    ])


# ------------------------------------------------------------------ independent reader
def parse_sexpr(text: str):
    tokens = re.findall(r'"[^"]*"|\(|\)|[^\s()]+', text)
    stack: list[list] = [[]]
    for tok in tokens:
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError("unbalanced EDIF")
    return stack[0][0]


def _find(node, key):
    if isinstance(node, list):
        if node and node[0] == key:
            yield node
        for child in node:
            yield from _find(child, key)


def _name(token) -> str:
    if isinstance(token, list) and token[0] == "rename":
        return token[2].strip('"')
    return str(token).lstrip("&")


def read_edif(text: str) -> dict:
    """Return {'stored': nets from joined, 'drawn': nets reconstructed from wire geometry, 'pins': ...}."""
    tree = parse_sexpr(text)
    assert tree[0] == "edif" and ["edifVersion", "2", "0", "0"] in tree and ["edifLevel", "0"] in tree
    cells: dict[str, dict[str, tuple[int, int]]] = {}
    port_names: dict[str, dict[str, str]] = {}
    for lib in _find(tree, "library"):
        if lib[1] != "CIVIC_LIB":
            continue
        for cell in [c for c in lib if isinstance(c, list) and c[0] == "cell"]:
            pts, names = {}, {}
            for port in _find(cell, "port"):
                key = port[1][1] if isinstance(port[1], list) else port[1]
                names[key.lstrip("&")] = port[2][1].strip('"')
            for impl in _find(cell, "portImplementation"):
                dot = next(_find(impl, "dot"))
                pts[impl[1].lstrip("&")] = (int(dot[1][1]), int(dot[1][2]))
            cells[cell[1].lstrip("&")] = pts
            port_names[cell[1].lstrip("&")] = names
    inst_pins: dict[tuple[int, int], str] = {}
    designators: dict[str, str] = {}
    for inst in _find(tree, "instance"):
        iid = inst[1].lstrip("&")
        cell = next(_find(inst, "cellRef"))[1].lstrip("&")
        origin = next(_find(inst, "origin"))[1]
        ox, oy = int(origin[1]), int(origin[2])
        designator = next(_find(inst, "designator"))[1].strip('"')
        designators[iid] = designator
        for port, (x, y) in cells[cell].items():
            pin_number = port_names[cell][port]
            inst_pins[(ox + x, oy + y)] = f"{designator}.{pin_number}"
    stored: dict[str, list[str]] = {}
    segments = []
    for net in _find(tree, "net"):
        name = _name(net[1])
        members = []
        for ref in _find(net, "portRef"):
            port = ref[1].lstrip("&")
            inst = ref[2][1].lstrip("&")
            members.append(f"{designators[inst]}.{port[1:]}")
        stored[name] = sorted(members)
        for path in _find(net, "pointList"):
            pts = [(int(p[1]), int(p[2])) for p in path[1:]]
            segments += [(a, b, name) for a, b in zip(pts, pts[1:])]
    # union-find over segment endpoints only (endpoint-to-endpoint connectivity, as the writer guarantees)
    parent: dict[tuple[int, int], tuple[int, int]] = {}

    def root(p):
        parent.setdefault(p, p)
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    for a, b, _ in segments:
        parent[root(a)] = root(b)
    groups: dict[tuple[int, int], list[str]] = {}
    for point, pin in inst_pins.items():
        if point in parent:
            groups.setdefault(root(point), []).append(pin)
    drawn = sorted(sorted(g) for g in groups.values())
    ends = set(inst_pins) | {p for s in segments for p in s[:2]}
    interior_hits = [(pt, a, b) for a, b, _ in segments for pt in ends if pt not in (a, b) and _on_segment(pt, a, b)]
    overlaps = [(s1, s2) for i, s1 in enumerate(segments) for s2 in segments[i + 1:]
                if s1[2] != s2[2] and _overlap(s1[:2], s2[:2])]
    return {"stored": stored, "drawn": drawn, "interior_hits": interior_hits, "overlaps": overlaps,
            "designators": designators}


def _overlap(s1, s2) -> bool:
    """True when two axis-parallel segments are collinear and share more than a single point."""
    (a, b), (c, d) = s1, s2
    if a[0] == b[0] == c[0] == d[0]:
        lo, hi = max(min(a[1], b[1]), min(c[1], d[1])), min(max(a[1], b[1]), max(c[1], d[1]))
        return hi > lo
    if a[1] == b[1] == c[1] == d[1]:
        lo, hi = max(min(a[0], b[0]), min(c[0], d[0])), min(max(a[0], b[0]), max(c[0], d[0]))
        return hi > lo
    return False


def _on_segment(p, a, b) -> bool:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if x1 == x2 == x:
        return min(y1, y2) < y < max(y1, y2)
    if y1 == y2 == y:
        return min(x1, x2) < x < max(x1, x2)
    return False
