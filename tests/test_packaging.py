"""Package metadata, install assets and stage handoff contracts."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class PackagingAndHandoffTests(unittest.TestCase):
    def test_installable_package_declares_cli_web_and_bundled_schema_assets(self):
        project_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "civic-workbench"', project_text)
        self.assertIn('civic-workbench = "civic_workbench.app:main"', project_text)
        self.assertIn('"web/*.html"', project_text)
        self.assertIn('"schemas/v1/*.schema.json"', project_text)

        canonical = ROOT / "schemas/v1"
        packaged = ROOT / "src/civic_workbench/schemas/v1"
        self.assertEqual(
            {path.name for path in canonical.glob("*.schema.json")},
            {path.name for path in packaged.glob("*.schema.json")},
        )
        for schema in canonical.glob("*.schema.json"):
            self.assertEqual(schema.read_bytes(), (packaged / schema.name).read_bytes(), schema.name)

        for name in ("index.html", "app.js", "styles.css"):
            self.assertTrue((ROOT / "src/civic_workbench/web" / name).is_file(), name)

    def test_stage_reports_and_final_handoff_documents_exist(self):
        for stage in (
            "S04-browser-ui-report.md", "S05-storage-report.md", "S06-analysis-report.md",
            "S07-tx-diagnostics-report.md", "S08-simulator-report.md",
            "S09-proteus-generator-report.md", "S10-integration-report.md",
            "S11-hardening-performance-report.md", "S12-final-handoff-report.md",
        ):
            self.assertTrue((ROOT / "docs/reports" / stage).is_file(), stage)
        for name in (
            "setup-and-run.md", "fault-matrix.md", "security-review.md",
            "known-limitations.md", "evidence-index.md",
        ):
            self.assertTrue((ROOT / "docs" / name).is_file(), name)
        self.assertTrue((ROOT / ".github/workflows/ci.yml").is_file())

    def test_openapi_routes_and_parameter_mapping_schema_are_declared(self):
        spec = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
        for route in (
            "/api/v1/analysis/mappings",
            "/api/v1/analysis/decode-parameter",
            "/api/v1/analysis/mappings/{mapping_id}/validate",
            "/api/v1/diagnostics/workflow",
            "/api/v1/simulator/scenarios",
            "/api/v1/simulator/step",
            "/api/v1/sessions/import",
            "/api/v1/sessions/{session_id}/export",
        ):
            self.assertIn(route, spec["paths"], route)
        schema = json.loads((ROOT / "schemas/v1/parameter-mapping.schema.json").read_text())
        self.assertIn("validation", schema["properties"])
        self.assertEqual(schema["properties"]["status"]["enum"], ["candidate", "validated"])

    def test_every_served_api_route_is_declared_in_openapi(self):
        import re
        spec = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
        declared = {(method.upper(), path) for path, ops in spec["paths"].items() for method in ops
                    if method in {"get", "post", "put", "delete"}}
        source = (ROOT / "src/civic_workbench/app.py").read_text(encoding="utf-8")
        get_part = source[source.index("def _dispatch_get"):source.index("def do_POST")]
        post_part = source[source.index("def _dispatch_post"):source.index("def _hardware_reject")]
        served = {("GET", p) for p in re.findall(r'path == "(/api/v1/[^"]+)"', get_part)}
        served |= {("POST", p) for p in re.findall(r'path == "(/api/v1/[^"]+)"', post_part)}
        served |= {("GET", "/api/v1/sessions/{session_id}"), ("GET", "/api/v1/sessions/{session_id}/export"),
                   ("GET", "/api/v1/sessions/{session_id}/frames"), ("GET", "/api/v1/sessions/{session_id}/summary"),
                   ("POST", "/api/v1/sessions/{session_id}/analysis/run"),
                   ("POST", "/api/v1/tx/requests/{request_id}/cancel"),
                   ("POST", "/api/v1/analysis/mappings/{mapping_id}/validate")}
        self.assertEqual(sorted(served - declared), [])
        self.assertEqual(sorted(declared - served), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
