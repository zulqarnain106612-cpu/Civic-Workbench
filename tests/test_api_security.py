"""Loopback, Host/Origin, body-size and API boundary tests."""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest

from civic_workbench.app import Handler, WorkbenchHTTPServer
from civic_workbench.service import WorkbenchService


class ApiSecurityTests(unittest.TestCase):
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

    def request(self, method, path, raw_body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        actual = dict(headers or {})
        if raw_body is not None:
            actual.setdefault("Content-Type", "application/json")
            actual.setdefault("Origin", self.origin)
        conn.request(method, path, body=raw_body, headers=actual)
        response = conn.getresponse()
        status, headers_out, raw = response.status, dict(response.getheaders()), response.read()
        conn.close()
        body = json.loads(raw) if raw and "application/json" in headers_out.get("Content-Type", "") else raw
        return status, headers_out, body

    def test_external_host_header_is_rejected_before_route(self):
        status, _, body = self.request("GET", "/api/v1/health", headers={"Host":"evil.example"})
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "host_rejected")

    def test_cross_origin_post_is_rejected_before_mutation(self):
        status, _, body = self.request(
            "POST", "/api/v1/simulator/scenarios", json.dumps({"nodes":[]}).encode(),
            {"Origin":"http://attacker.example"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "origin_rejected")
        self.assertEqual(self.service.store.list_sessions()["items"], [])

    def test_body_size_limit_rejects_before_reading_large_body(self):
        status, _, body = self.request(
            "POST", "/api/v1/simulator/scenarios", None,
            {"Content-Length":"4194305","Origin":self.origin},
        )
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "contract_violation")
        self.assertEqual(self.service.store.list_sessions()["items"], [])

    def test_unexpected_static_path_is_not_served_from_disk(self):
        status, _, body = self.request("GET", "/../../project/progress.json")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_hardware_configuration_is_always_inhibited_in_host_safety_snapshot(self):
        state = self.service.safety_state()
        self.assertFalse(state["tx_permitted"])
        self.assertFalse(state["hardware_interlock_active"])
        self.assertIn("host_hardware_tx_disabled", state["faults"])
        self.assertIn("physical_interlock_not_verified", state["faults"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
