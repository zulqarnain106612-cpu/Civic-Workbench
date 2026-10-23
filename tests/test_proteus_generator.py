"""Deterministic hardware-design generation, electrical checks and native-format honesty tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools/generate_proteus_reference.py"
NAMES = [
    "reference-design.netlist.json", "design-checks.json", "reference-design.svg",
    "component-map.json", "bill-of-materials.csv", "native-project-status.json",
    "PROTEUS-CAPTURE.md", "README.md", "artifact-manifest.json",
]


class ProteusGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name)
        cls.result = cls.generate(cls.out)
        cls.netlist = json.loads((cls.out / "reference-design.netlist.json").read_text())
        cls.checks = json.loads((cls.out / "design-checks.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @staticmethod
    def generate(output: Path):
        completed = subprocess.run([sys.executable, str(GENERATOR), "--output", str(output)], cwd=ROOT,
                                   check=True, text=True, capture_output=True, timeout=20)
        return json.loads(completed.stdout)

    def test_outputs_are_deterministic(self):
        with tempfile.TemporaryDirectory() as other:
            self.generate(Path(other))
            for name in NAMES:
                self.assertEqual(hashlib.sha256((self.out / name).read_bytes()).hexdigest(),
                                 hashlib.sha256((Path(other) / name).read_bytes()).hexdigest(), name)

    def test_committed_bundle_matches_generator(self):
        committed = ROOT / "hardware/proteus/generated"
        for name in NAMES:
            self.assertEqual((committed / name).read_bytes(), (self.out / name).read_bytes(),
                             f"{name} is stale; run make design-source")

    def test_all_electrical_design_checks_pass(self):
        self.assertTrue(self.result["design_checks_pass"])
        failing = [c["id"] for c in self.checks["checks"] if not c["pass"]]
        self.assertEqual(failing, [])
        ids = {c["id"] for c in self.checks["checks"]}
        self.assertTrue({"RXD_DIVIDER_MAX", "RXD_DIVIDER_MIN", "S_SILENT_HIGH", "PIN5_OPEN",
                         "S_NOT_MCU_DRIVEN", "TXD_NOT_MCU_DRIVEN", "TERMINATION_NOT_FITTED"} <= ids)

    def test_receive_only_topology(self):
        nets = self.netlist["nets"]
        self.assertIn("R1.2", nets["+5V_CAN"])          # Silent pull-up from transceiver rail
        self.assertIn("U1.8", nets["S_SILENT"])
        self.assertNotIn("J1.GPIO21", nets.get("TXD_5V", []))
        self.assertIn("J1.GPIO22", nets["RXD_3V3"])
        self.assertNotIn("J1.GPIO22", nets["RXD_5V"])    # RXD never direct to ESP32
        self.assertNotIn("NC_PIN5", nets)                 # pin 5 left open, no net
        self.assertNotIn("SPLIT", nets)                   # DNP termination excluded from fitted nets
        source = self.netlist["source"]
        self.assertEqual(source["transceiver"]["reported_top_marking"], "NXP TJA1051 25 06 ND312")
        self.assertFalse(source["transceiver"]["substitutions_allowed"])
        self.assertEqual(source["controller"]["tx_gpio"], 21)
        self.assertEqual(source["controller"]["rx_gpio"], 22)

    def test_bom_and_svg_content(self):
        rows = list(csv.DictReader((self.out / "bill-of-materials.csv").open()))
        fitted = {r["Reference"]: r["Fitted"] for r in rows}
        self.assertEqual(fitted["U1"], "yes")
        for ref in ("R5", "R6", "C5", "C3", "C4"):
            self.assertEqual(fitted[ref], "DNP")
        svg = (self.out / "reference-design.svg").read_text()
        for token in ("NodeMCU-32S", "TJA1051T", "S_SILENT", "RXD_3V3", "ALL PASS"):
            self.assertIn(token, svg)

    def test_native_project_is_explicitly_blocked_not_fabricated(self):
        status = json.loads((self.out / "native-project-status.json").read_text())
        self.assertEqual(status["status"], "blocked")
        self.assertFalse(status["native_artifact_created"])
        self.assertFalse(status["official_python_schematic_generation_api_confirmed"])
        self.assertIn("required_next_action", status)
        self.assertFalse(list(self.out.glob("*.pdsprj")))
        self.assertFalse(list(self.out.glob("*.DSN")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
