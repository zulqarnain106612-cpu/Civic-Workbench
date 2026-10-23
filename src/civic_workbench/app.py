"""Local-only HTTP API and static browser workbench. Default bind is loopback."""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any

from .contracts import ContractViolation, validate_record
from .service import WorkbenchService
from .storage import NotFound, Conflict


MAX_BODY_BYTES = 4 * 1024 * 1024
WEB_ROOT = Path(__file__).resolve().parent / "web"


class WorkbenchHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, service: WorkbenchService):
        super().__init__(address, handler)
        self.service = service


class Handler(BaseHTTPRequestHandler):
    server_version = "CivicWorkbench/0.4"
    protocol_version = "HTTP/1.1"

    @property
    def service(self) -> WorkbenchService:
        return self.server.service  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep default console output concise; structured events belong in the persistent log.
        if os.environ.get("CIVIC_WORKBENCH_HTTP_LOG") == "1":
            super().log_message(fmt, *args)

    def _send_bytes(self, status: int, data: bytes, content_type: str, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Connection", "close")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def _json(self, status: int, value: Any, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", extra_headers)

    def _error(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        self._json(status, {"schema_version": 1, "error": {"code": code, "message": message[:2000], "details": details or {}}})

    def _host_allowed(self) -> bool:
        raw_host = self.headers.get("Host", "")
        try:
            host = urlparse("//" + raw_host).hostname
        except ValueError:
            return False
        return host is not None and host.lower() in {"127.0.0.1", "localhost", "::1"}

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        request_host = self.headers.get("Host", "").lower()
        return parsed.scheme == "http" and parsed.netloc.lower() == request_host and self._host_allowed()

    def _body(self) -> Any:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ContractViolation("invalid Content-Length") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ContractViolation(f"request body exceeds {MAX_BODY_BYTES} bytes")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractViolation("request body must be valid UTF-8 JSON") from exc

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query, keep_blank_values=False)

    def _one(self, query: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
        values = query.get(key)
        return values[0] if values else default

    def _serve_file(self, name: str) -> None:
        allowed = {"index.html", "app.js", "styles.css"}
        if name not in allowed:
            self._error(404, "not_found", "Static asset not found")
            return
        path = WEB_ROOT / name
        try:
            content = path.read_bytes()
        except OSError:
            self._error(503, "ui_not_installed", "Browser assets are not present in this checkout")
            return
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if name.endswith(".js"):
            content_type = "text/javascript"
        self._send_bytes(200, content, content_type + "; charset=utf-8")

    def do_GET(self) -> None:
        if not self._host_allowed():
            self._error(403, "host_rejected", "Only localhost Host headers are accepted.")
            return
        path = unquote(urlparse(self.path).path)
        q = self._query()
        with self.service.lock:
            self._dispatch_get(path, q)

    def _dispatch_get(self, path: str, q: dict[str, list[str]]) -> None:
        try:
            if path in {"/", "/index.html"}:
                return self._serve_file("index.html")
            if path == "/app.js":
                return self._serve_file("app.js")
            if path == "/styles.css":
                return self._serve_file("styles.css")
            if path == "/api/v1/health":
                return self._json(200, self.service.health())
            if path == "/api/v1/capabilities":
                return self._json(200, self.service.capabilities())
            if path == "/api/v1/safety/state":
                return self._json(200, self.service.safety_state())
            if path == "/api/v1/device/status":
                return self._json(200, self.service.serial.status())
            if path == "/api/v1/sessions":
                result = self.service.store.list_sessions(int(self._one(q, "limit", "50") or "50"), self._one(q, "cursor"))
                return self._json(200, result)
            if path == "/api/v1/analysis/findings":
                return self._json(200, {"schema_version": 1, "items": self.service.store.list_findings(
                    self._one(q, "session_id"), self._one(q, "status"))})
            if path == "/api/v1/analysis/mappings":
                return self._json(200, {"schema_version": 1, "items": self.service.store.list_parameter_mappings(
                    self._one(q, "session_id"))})
            if path == "/api/v1/analysis/summary":
                session_id = self._one(q, "session_id", "") or ""
                from .analysis import summarize_frames
                return self._json(200, summarize_frames(self.service.store.get_all_frames(session_id)))
            if path == "/api/v1/serial/status":
                return self._json(200, self.service.serial.status())
            if path == "/api/v1/tx/audit":
                return self._json(200, {"schema_version": 1, "items": self.service.store.list_tx_audit(int(self._one(q, "limit", "200") or "200"))})
            if path == "/api/v1/tx/requests":
                return self._json(200, {"schema_version": 1, "items": self.service.tx.list_requests()})
            if path == "/api/v1/simulator/state":
                return self._json(200, self.service.bus.state())
            if path == "/api/v1/scenarios":
                return self._json(200, {"schema_version": 1, "items": self.service.store.list_scenarios()})
            if path == "/api/v1/diagnostic-capabilities":
                return self._json(200, {"schema_version": 1, "items": self.service.store.get_diagnostic_capabilities()})
            if path == "/api/v1/logs":
                return self._json(200, {"schema_version": 1, "items": self.service.store.list_events(int(self._one(q, "limit", "200") or "200"))})
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:3] == ["api", "v1", "sessions"]:
                return self._json(200, self.service.store.get_session(parts[3]))
            if len(parts) == 5 and parts[:3] == ["api", "v1", "sessions"] and parts[4] == "export":
                bundle = self.service.export_bundle(parts[3])
                name = "civic-workbench-" + parts[3] + ".json"
                return self._json(200, bundle, {"Content-Disposition": f'attachment; filename="{name}"'})
            if len(parts) == 5 and parts[:3] == ["api", "v1", "sessions"] and parts[4] == "frames":
                result = self.service.store.list_frames(parts[3], int(self._one(q, "limit", "500") or "500"),
                                                        int(self._one(q, "after_sequence", "-1") or "-1"))
                return self._json(200, result)
            if len(parts) == 5 and parts[:3] == ["api", "v1", "sessions"] and parts[4] == "summary":
                frames = self.service.store.get_all_frames(parts[3])
                from .analysis import summarize_frames
                return self._json(200, summarize_frames(frames))
            self._error(404, "not_found", "Route not found")
        except NotFound as exc:
            self._error(404, "not_found", str(exc))
        except (ContractViolation, ValueError, TypeError) as exc:
            self._error(422, "invalid_request", str(exc))
        except Exception as exc:
            self.service.store.log_event("ERROR", "api.unhandled_error", "Unhandled GET handler error", {"path": path, "error": str(exc)[:500]})
            self._error(500, "internal_error", "An internal request error occurred.")

    def do_POST(self) -> None:
        if not self._host_allowed():
            self._error(403, "host_rejected", "Only localhost Host headers are accepted.")
            return
        if not self._origin_allowed():
            self._error(403, "origin_rejected", "Cross-origin browser requests are not accepted.")
            return
        path = unquote(urlparse(self.path).path)
        q = self._query()
        try:
            body = self._body()  # read before taking the lock so a slow client cannot stall others
        except ContractViolation as exc:
            self._error(422, "contract_violation", str(exc))
            return
        except OSError:
            self._error(400, "body_read_failed", "The request body could not be read.")
            return
        with self.service.lock:
            self._dispatch_post(path, q, body)

    def _dispatch_post(self, path: str, q: dict[str, list[str]], body: Any) -> None:
        try:
            if path == "/api/v1/capture/start":
                return self._json(202, self.service.start_capture(body))
            if path == "/api/v1/capture/stop":
                return self._json(200, self.service.stop_capture(body))
            if path == "/api/v1/sessions/import":
                return self._json(201, self.service.import_bundle(body))
            if path.startswith("/api/v1/sessions/") and path.endswith("/analysis/run"):
                session_id = path.split("/")[-3]
                return self._json(200, self.service.run_analysis(session_id))
            if path == "/api/v1/simulator/scenarios":
                return self._json(201, self.service.create_scenario(body))
            if path == "/api/v1/simulator/step":
                result = self.service.step_simulation(body)
                return self._json(200, result)
            if path == "/api/v1/simulator/replay":
                return self._json(202, self.service.replay(body))
            if path == "/api/v1/simulator/mutate":
                return self._json(201, self.service.mutate(body))
            if path == "/api/v1/simulator/filter":
                self.service.bus.set_filter(body.get("identifier_filter") or None)
                return self._json(200, {"source": "simulation", "identifier_filter": body.get("identifier_filter", [])})
            if path == "/api/v1/tx/requests":
                target = self._one(q, "target", "") or ""
                session_id = self._one(q, "session_id")
                if target != "simulation":
                    return self._json(409, self._hardware_reject(body))
                result = self.service.tx.submit(body, target, session_id)
                return self._json(202, result)
            if path.startswith("/api/v1/tx/requests/") and path.endswith("/cancel"):
                request_id = path.split("/")[-2]
                record = body
                validate_record("tx-cancel", record)
                if record["request_id"] != request_id:
                    raise ContractViolation("path request_id must match body request_id")
                return self._json(200, self.service.tx.cancel(request_id, record.get("reason", "operator_cancelled")))
            if path == "/api/v1/diagnostic-capabilities":
                return self._json(201, self.service.add_diagnostic_capability(body))
            if path == "/api/v1/analysis/decode-parameter":
                return self._json(200, self.service.decode_parameter(body))
            if path.startswith("/api/v1/analysis/mappings/") and path.endswith("/validate"):
                mapping_id = path.split("/")[-2]
                return self._json(200, self.service.store.validate_parameter_mapping(
                    mapping_id,
                    str(body.get("validation_method", "")),
                    list(body.get("evidence_refs", [])),
                    body.get("reviewer"),
                ))
            if path == "/api/v1/diagnostics/workflow":
                return self._json(200, self.service.diagnostic_workflow(body))
            if path == "/api/v1/serial/connect":
                return self._json(200, self.service.serial.start(str(body.get("port", "")), int(body.get("baudrate", 115200))))
            if path == "/api/v1/serial/disconnect":
                return self._json(200, self.service.serial.stop())
            if path == "/api/v1/import/frame":
                # Ingest one frame only into an already-open session; never re-label its source.
                validate_record("can-frame", body)
                self.service.store.add_frame(body)
                return self._json(201, {"accepted": True, "frame_id": body["frame_id"]})
            self._error(404, "not_found", "Route not found")
        except NotFound as exc:
            self._error(404, "not_found", str(exc))
        except Conflict as exc:
            self._error(409, "state_conflict", str(exc))
        except ContractViolation as exc:
            self._error(422, "contract_violation", str(exc))
        except (ValueError, TypeError) as exc:
            self._error(422, "invalid_request", str(exc))
        except Exception as exc:
            self.service.store.log_event("ERROR", "api.unhandled_error", "Unhandled POST handler error", {"path": path, "error": str(exc)[:500]})
            self._error(500, "internal_error", "An internal request error occurred.")

    def _hardware_reject(self, request: dict[str, Any]) -> dict[str, Any]:
        # Persist a rejection audit before responding; do not echo raw payload to logs.
        try:
            from .contracts import validate_record
            validate_record("tx-request", request)
            audit = self.service.store.add_tx_audit(request["request_id"], None, "hardware", "rejected", {
                "reason": "No hardware TX route is enabled in the host service.",
                "physical_tx_performed": False,
            })
            return {"schema_version": 1, "error": {"code": "hardware_tx_disabled",
                    "message": "Only explicit target=simulation is supported. No physical transmission was attempted.",
                    "details": {"audit_id": audit["audit_id"]}}}
        except ContractViolation as exc:
            return {"schema_version": 1, "error": {"code": "invalid_tx_request", "message": str(exc), "details": {}}}


def serve(data_dir: str | Path | None = None, host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("This unauthenticated workbench server is restricted to loopback. Do not expose it to a network.")
    default_dir = Path.home() / ".local" / "share" / "civic-workbench"
    service = WorkbenchService(data_dir or os.environ.get("CIVIC_WORKBENCH_DATA_DIR") or default_dir)
    httpd = WorkbenchHTTPServer((host, port), Handler, service)
    print(f"Civic-Workbench {service.VERSION} listening at http://{host}:{httpd.server_port}/")
    print(f"Persistent data: {service.store.data_dir}")
    print("Safety: hardware TX is disabled; simulator TX only. Press Ctrl+C to stop.")
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        service.serial.stop()
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Civic-Workbench browser UI/API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be in range 1024..65535")
    serve(args.data_dir, args.host, args.port)


if __name__ == "__main__":
    main()
