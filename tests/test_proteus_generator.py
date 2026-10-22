"""Deterministic generated CAD-source and native-format honesty tests."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools/generate_proteus_reference.py"


class ProteusGeneratorTests(unittest.TestCase):
    def generate(self, output: Path):
        completed = subprocess.run(
            [sys.executable, str(GENERATOR), "--output", str(output)],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        )
        return json.loads(completed.stdout)

    def test_generator_outputs_deterministic_source_bom_and_vector_review(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            self.generate(first)
            self.generate(second)
            names = [
                "reference-design.netlist.json", "reference-design.svg",
                "component-map.json", "bill-of-materials.csv",
                "native-project-status.json", "README.md", "artifact-manifest.json",
            ]
            for name in names:
                self.assertEqual(
                    hashlib.sha256((first / name).read_bytes()).hexdigest(),
                    hashlib.sha256((second / name).read_bytes()).hexdigest(),
                    name,
                )
            svg = (first / "reference-design.svg").read_text()
            netlist = json.loads((first / "reference-design.netlist.json").read_text())
            bom = (first / "bill-of-materials.csv").read_text()
            mapping = json.loads((first / "component-map.json").read_text())
            self.assertIn("NodeMCU-32S", svg)
            self.assertIn("TWAI_TX_GPIO = 21", svg)
            self.assertIn("TWAI_RX_GPIO = 22", svg)
            self.assertIn("UNASSIGNED", svg)  # TX gate/interlock mapping remains intentionally unspecified.
            self.assertIn("NXP TJA1051 25 06 ND312", (first / "reference-design.netlist.json").read_text())
            self.assertEqual(netlist["transceiver"]["pins"]["5"]["net"], "UNRESOLVED_PIN5_DO_NOT_CONNECT")
            self.assertEqual(netlist["controller"]["tx_gpio"], 21)
            self.assertEqual(netlist["controller"]["rx_gpio"], 22)
            self.assertEqual(netlist["transceiver"]["reported_top_marking"], "NXP TJA1051 25 06 ND312")
            self.assertFalse(netlist["transceiver"]["substitutions_allowed"])
            self.assertIn("NodeMCU-32S", bom)
            self.assertIn("value-unassigned", bom)
            self.assertIn("GPIO21/GPIO22 header continuity", mapping["symbols"][1]["reason"])

    def test_native_project_is_explicitly_blocked_not_fabricated(self):
        with tempfile.TemporaryDirectory() as temp:
            self.generate(Path(temp))
            status = json.loads((Path(temp) / "native-project-status.json").read_text())
            self.assertEqual(status["status"], "blocked")
            self.assertFalse(status["native_artifact_created"])
            self.assertFalse(status["official_python_schematic_generation_api_confirmed"])
            self.assertIn("required_next_action", status)
            self.assertIn("SVG is only a review companion", status["note"])
            self.assertFalse((Path(temp) / "reference-design.pdsprj").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
