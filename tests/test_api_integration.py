"""End-to-end local HTTP flows across simulator, storage, analysis and safety gates."""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from uuid import uuid4

from civic_workbench.app import Handler, WorkbenchHTTPServer
from civic_workbench.service import WorkbenchService
from civic_test_helpers import utc_text, tx_request


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = WorkbenchService(self.temp.name)
        self.server = WorkbenchHTTPServer(("127.0.0.1", 0), Handler, self.service)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.service.serial.stop()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        actual_headers = {}
        if body is not None:
            actual_headers["Content-Type"] = "application/json"
            actual_headers["Origin"] = self.origin
        actual_headers.update(headers or {})
        raw = None if body is None else json.dumps(body).encode("utf-8")
        conn.request(method, path, body=raw, headers=actual_headers)
        response = conn.getresponse()
        status = response.status
        content = response.read()
        response_headers = dict(response.getheaders())
        conn.close()
        parsed = json.loads(content) if content and "application/json" in response_headers.get("Content-Type", "") else content
        return status, response_headers, parsed

    def test_concurrent_simulation_steps_are_serialized(self):
        scenario = {"name": "concurrency", "bitrate_bps": 500000, "identifier_filter": [], "notes": "synthetic",
                    "nodes": [{"node_id": "node-a", "arbitration_id": 0x100, "id_format": "standard",
                               "period_ms": 10, "payload_mode": "counter"}]}
        status, _, created = self.request("POST", "/api/v1/simulator/scenarios", scenario)
        self.assertEqual(status, 201)
        statuses: list[int] = []

        def step():
            statuses.append(self.request("POST", "/api/v1/simulator/step", {"delta_ms": 50})[0])

        threads = [threading.Thread(target=step) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(statuses, [200] * 8)
        status, _, state = self.request("GET", "/api/v1/simulator/state")
        self.assertEqual(state["virtual_time_ms"], 400)
        frames = self.service.store.get_all_frames(created["session"]["session_id"])
        stamps = [f["captured_monotonic_ns"] for f in frames]
        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual(len({f["frame_id"] for f in frames}), len(frames))

    def test_simulate_analyze_version_mapping_tx_export_and_import(self):
        status, _, health = self.request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertIn(health["status"], {"ok", "degraded"})

        scenario = {
            "name": "integration synthetic nodes",
            "bitrate_bps": 500000,
            "identifier_filter": [],
            "notes": "synthetic fixture",
            "nodes": [
                {"node_id":"node-a","arbitration_id":0x100,"id_format":"standard","period_ms":100,"payload_mode":"counter"},
                {"node_id":"node-b","arbitration_id":0x200,"id_format":"standard","period_ms":250,"payload_mode":"toggle"},
            ],
        }
        status, _, created = self.request("POST", "/api/v1/simulator/scenarios", scenario)
        self.assertEqual(status, 201)
        sid = created["session"]["session_id"]
        status, _, step = self.request("POST", "/api/v1/simulator/step", {"delta_ms":300})
        self.assertEqual(status, 200)
        self.assertEqual(step["emitted_count"], 4)

        status, _, page = self.request("GET", "/api/v1/sessions/" + sid + "/frames?limit=20&after_sequence=-1")
        self.assertEqual(status, 200)
        self.assertEqual(len(page["items"]), 4)
        records = [entry["frame"] for entry in page["items"]]
        self.assertTrue(all(frame["capture_source"] == "simulator" for frame in records))

        status, _, analysis = self.request("POST", "/api/v1/sessions/" + sid + "/analysis/run", {})
        self.assertEqual(status, 200)
        self.assertEqual(analysis["summary"]["total_frames"], 4)
        self.assertFalse(analysis["raw_frames_mutated"])
        self.assertTrue(all(f["evidence_frame_ids"] for f in analysis["findings"]))

        definition = {
            "name":"integration-byte",
            "start_bit":0,
            "bit_length":8,
            "byte_order":"little_endian",
            "signed":False,
            "scale":1,
            "offset":0,
            "unit":None,
        }
        status, _, decoded = self.request("POST", "/api/v1/analysis/decode-parameter", {
            "session_id":sid,
            "definition":definition,
            "evidence_frame_ids":[records[0]["frame_id"],records[1]["frame_id"]],
        })
        self.assertEqual(status, 200)
        self.assertEqual(decoded["mapping"]["status"], "candidate")
        self.assertEqual(decoded["mapping"]["version"], 1)
        status, _, maps = self.request("GET", "/api/v1/analysis/mappings?session_id=" + sid)
        self.assertEqual(status, 200)
        self.assertEqual(len(maps["items"]), 1)
        mapping_id = decoded["mapping"]["mapping_id"]
        status, _, promoted = self.request("POST", "/api/v1/analysis/mappings/" + mapping_id + "/validate", {
            "validation_method": "integration-fixture independent comparison",
            "evidence_refs": ["fixture-reference-01", "fixture-bench-report-02"],
            "reviewer": "integration-test",
        })
        self.assertEqual(status, 200)
        self.assertEqual(promoted["status"], "validated")
        self.assertEqual(len(promoted["validation"]["evidence_refs"]), 2)

        capability = {
            "schema_version":1,
            "record_type":"diagnostic_capability",
            "capability_id":str(uuid4()),
            "status":"supported",
            "enabled":True,
            "protocol":"unknown",
            "operation":"synthetic demonstration capability",
            "ecu_label":None,
            "addressing":None,
            "supporting_evidence":[{"kind":"official_document","reference":"https://example.invalid/test-evidence","notes":"Fixture for gate behavior only."}],
        }
        status, _, saved_capability = self.request("POST", "/api/v1/diagnostic-capabilities", capability)
        self.assertEqual(status, 201)
        status, _, gate = self.request("POST", "/api/v1/diagnostics/workflow", {"capability_id":capability["capability_id"],"target":"simulation"})
        self.assertEqual(status, 200)
        self.assertTrue(gate["allowed"])
        self.assertFalse(gate["executed"])
        self.assertFalse(gate["physical_tx_performed"])

        tx = tx_request(repeats=2, period_ms=100, timeout_ms=250)
        status, _, queued = self.request("POST", "/api/v1/tx/requests?target=simulation&session_id=" + sid, tx)
        self.assertEqual(status, 202)
        self.assertEqual(queued["status"], "queued")
        status, _, step = self.request("POST", "/api/v1/simulator/step", {"delta_ms":200})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(step["emitted_count"], 2)
        self.assertEqual(sum(frame["direction"] == "tx" for frame in step["frames"]), 2)
        status, _, audits = self.request("GET", "/api/v1/tx/audit")
        self.assertEqual(status, 200)
        self.assertTrue(any(item["request_id"] == tx["request_id"] for item in audits["items"]))
        safety_status, _, safety = self.request("GET", "/api/v1/safety/state")
        self.assertEqual(safety_status, 200)
        self.assertFalse(safety["tx_permitted"])

        stop = {
            "schema_version":1,"record_type":"capture_stop","request_id":str(uuid4()),
            "session_id":sid,"requested_at_utc":utc_text(),"requested_by":"integration-test",
            "reason":"close synthetic fixture",
        }
        status, _, closed = self.request("POST", "/api/v1/capture/stop", stop)
        self.assertEqual(status, 200)
        self.assertIsNotNone(closed["ended_at_utc"])
        status, headers, bundle = self.request("GET", "/api/v1/sessions/" + sid + "/export")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(len(bundle["frames"]), closed["record_count"])
        imported_id = str(uuid4())
        bundle["manifest"]["session_id"] = imported_id
        for frame in bundle["frames"]:
            frame["session_id"] = imported_id
        status, _, imported = self.request("POST", "/api/v1/sessions/import", bundle)
        self.assertEqual(status, 201, imported)
        self.assertEqual(imported["session_id"], imported_id)
        self.assertEqual(imported["capture_source"], "import")

    def test_non_simulation_tx_is_rejected_and_persistently_audited(self):
        request = tx_request(repeats=1)
        status, _, body = self.request("POST", "/api/v1/tx/requests?target=hardware", request)
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "hardware_tx_disabled")
        status, _, audits = self.request("GET", "/api/v1/tx/audit")
        self.assertEqual(status, 200)
        event = next(item for item in audits["items"] if item["request_id"] == request["request_id"])
        self.assertEqual(event["status"], "rejected")
        self.assertFalse(event["event"]["physical_tx_performed"])

    def test_static_ui_and_response_security_headers(self):
        status, headers, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Civic-Workbench", html)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main(verbosity=2)
