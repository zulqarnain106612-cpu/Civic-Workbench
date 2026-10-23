"""EAGLE schematic export: structure, connectivity equals the reviewed netlist, deterministic."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools/generate_eagle_schematic.py"
COMMITTED = ROOT / "hardware/proteus/generated/civic-workbench-rev-b.sch"
NETLIST = ROOT / "hardware/proteus/generated/reference-design.netlist.json"


def generate(path: Path) -> bytes:
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(path)], cwd=ROOT, check=True,
                   capture_output=True, text=True, timeout=20)
    return path.read_bytes()


class EagleSchematicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls._tmp.name) / "out.sch"
        cls.data = generate(cls.path)
        cls.root = ET.fromstring(cls.data)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_deterministic_and_committed_copy_current(self):
        self.assertEqual(generate(Path(self._tmp.name) / "again.sch"), self.data)
        self.assertEqual(COMMITTED.read_bytes(), self.data, "run make design-source")

    def test_eagle_document_shape(self):
        self.assertTrue(self.data.startswith(b'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE eagle'))
        self.assertEqual(self.root.tag, "eagle")
        for path in ("drawing/layers", "drawing/schematic/libraries/library", "drawing/schematic/parts",
                     "drawing/schematic/sheets/sheet/instances", "drawing/schematic/sheets/sheet/nets"):
            self.assertIsNotNone(self.root.find(path), path)

    def test_every_reference_resolves(self):
        lib = self.root.find("drawing/schematic/libraries/library")
        symbols = {s.get("name"): {p.get("name") for p in s.iter("pin")} for s in lib.iter("symbol")}
        packages = {p.get("name"): {x.get("name") for x in p if x.tag in ("pad", "smd")} for p in lib.iter("package")}
        devicesets = {}
        for ds in lib.iter("deviceset"):
            dev = ds.find("devices/device")
            sym = ds.find("gates/gate").get("symbol")
            for c in dev.iter("connect"):
                self.assertIn(c.get("pin"), symbols[sym])
                self.assertIn(c.get("pad"), packages[dev.get("package")])
            self.assertEqual({c.get("pin") for c in dev.iter("connect")}, symbols[sym])
            devicesets[ds.get("name")] = symbols[sym]
        parts = {p.get("name"): p.get("deviceset") for p in self.root.iter("part")}
        instances = {i.get("part") for i in self.root.iter("instance")}
        self.assertEqual(set(parts), instances)
        for ref in self.root.iter("pinref"):
            self.assertIn(ref.get("pin"), devicesets[parts[ref.get("part")]])

    def test_connectivity_matches_reviewed_netlist(self):
        lib = self.root.find("drawing/schematic/libraries/library")
        pad_of = {}
        for ds in lib.iter("deviceset"):
            pad_of[ds.get("name")] = {c.get("pin"): c.get("pad") for c in ds.iter("connect")}
        parts = {p.get("name"): p.get("deviceset") for p in self.root.iter("part")}
        got = {}
        for net in self.root.iter("net"):
            members = set()
            for ref in net.iter("pinref"):
                part, pin = ref.get("part"), ref.get("pin")
                members.add(f"{part}.{pin}" if part == "J1" else f"{part}.{pad_of[parts[part]][pin]}")
            got[net.get("name")] = members
        expected = {k: set(v) for k, v in json.loads(NETLIST.read_text())["nets"].items()}
        for name, members in expected.items():
            self.assertTrue(members <= got[name], name)
        self.assertEqual(got["SPLIT"], {"R5.2", "R6.1", "C5.1"})          # DNP parts carried as DNP
        self.assertNotIn("J1.GPIO21", set().union(*got.values()))        # TX not wired
        self.assertNotIn("U1.5", set().union(*got.values()))             # pin 5 open
        values = {p.get("name"): p.get("value") for p in self.root.iter("part")}
        self.assertEqual(values["R1"], "10k")
        self.assertTrue(values["R5"].startswith("DNP"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
