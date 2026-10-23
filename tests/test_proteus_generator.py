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
    "PROTEUS-CAPTURE.md", "README.md", "civic-workbench-rev-b.edf", "civic-workbench-rev-b-sim.edf",
    "artifact-manifest.json",
]
sys.path.insert(0, str(ROOT / "tools"))
import generate_proteus_reference  # noqa: E402
import proteus_edif  # noqa: E402


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

    def _edif(self, simulation: bool):
        name = "civic-workbench-rev-b-sim.edf" if simulation else "civic-workbench-rev-b.edf"
        return proteus_edif.read_edif((self.out / name).read_text())

    def _expected(self, simulation: bool):
        import yaml
        design = yaml.safe_load((ROOT / "hardware/reference/esp32-tja1051-netlist.yaml").read_text())
        return generate_proteus_reference.edif_nets(design, simulation)

    def test_edif_header_matches_proteus_importer_probe(self):
        # IMPORTER.dll probe: first tag EDIF, EDIFVersion '2 0 0', EDIFLevel '0'
        for simulation in (False, True):
            text = (self.out / ("civic-workbench-rev-b-sim.edf" if simulation else "civic-workbench-rev-b.edf")).read_text()
            tree = proteus_edif.parse_sexpr(text)
            self.assertEqual(tree[0], "edif")
            self.assertIn(["edifVersion", "2", "0", "0"], tree)
            self.assertIn(["edifLevel", "0"], tree)
            self.assertIn("(pageSize", text)
            self.assertIn('(program "CAPTURE.EXE"', text)

    def test_edif_stored_and_drawn_netlists_match_reviewed_netlist(self):
        for simulation in (False, True):
            parsed, expected = self._edif(simulation), self._expected(simulation)
            self.assertEqual(parsed["stored"], expected)
            self.assertEqual(parsed["drawn"], sorted(sorted(m) for m in expected.values()))
            self.assertEqual(parsed["interior_hits"], [])
            self.assertEqual(parsed["overlaps"], [])

    def test_edif_hardware_sheet_keeps_receive_only_topology(self):
        nets = self._expected(False)
        self.assertIn("U1.8", nets["S_SILENT"])
        self.assertIn("J1.36", nets["RXD_3V3"])                       # GPIO22 = header pin 36
        self.assertFalse(any("J1.33" in m for m in nets.values()))   # GPIO21 (header 33) unconnected
        self.assertFalse(any("U1.5" in m for m in nets.values()))    # pin 5 open
        self.assertIn("SPLIT", nets)                                  # DNP parts drawn on the hardware sheet
        text = (self.out / "civic-workbench-rev-b.edf").read_text()
        self.assertIn('"DNP"', text)
        self.assertNotIn("CAN_ANALYZER", text)

    def test_edif_simulation_bench_binds_labcenter_models(self):
        text = (self.out / "civic-workbench-rev-b-sim.edf").read_text()
        for token in ('"DIGITAL,CAN_TRANSCEIVER"', '"DIGITAL,CAN_ANALYZER"', '"DIGITAL,ENGINE_ECU"',
                      '"CANBUS.DLL"', '"CANAUTO.DLL"', '"vehicle.dbc"', '"ANALOGUE,CAPACITOR"', '"RESISTOR"'):
            self.assertIn(token, text)
        nets = self._expected(True)
        self.assertTrue({"U1.7", "U2.3", "U3.1"} <= set(nets["CANH"]))
        self.assertTrue({"U1.6", "U2.4", "U3.2"} <= set(nets["CANL"]))
        self.assertNotIn("SPLIT", nets)                               # DNP excluded from the bench
        self.assertIn("TJA1051T", text)                               # no silent part substitution

    def test_native_project_status_is_honest(self):
        status = json.loads((self.out / "native-project-status.json").read_text())
        self.assertEqual(status["status"], "import-pending")
        self.assertFalse(status["native_artifact_created"])
        self.assertEqual(status["import_artifacts"], ["civic-workbench-rev-b.edf", "civic-workbench-rev-b-sim.edf"])
        self.assertFalse(status["official_python_schematic_generation_api_confirmed"])
        self.assertIn("required_next_action", status)
        self.assertFalse(list(self.out.glob("*.pdsprj")))
        self.assertFalse(list(self.out.glob("*.DSN")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
