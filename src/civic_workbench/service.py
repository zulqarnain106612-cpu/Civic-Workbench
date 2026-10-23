"""Application service coordinating persistence, analysis, simulator and safety boundaries."""
from __future__ import annotations

from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from .analysis import analyze_frames, summarize_frames
from .diagnostics import decode_explicit_parameter, workflow_gate
from .contracts import ContractViolation, validate_record
from .serial_bridge import SerialBridge
from .simulator import VirtualCanBus
from .storage import SessionStore, NotFound, Conflict, utc_now
from .tx import TxScheduler


class WorkbenchService:
    VERSION = "0.4.0"

    def __init__(self, data_dir: str | Path):
        self.store = SessionStore(data_dir)
        self.bus = VirtualCanBus()
        self.tx = TxScheduler(self.store, self.bus)
        self.serial = SerialBridge(self.store)
        self.last_device_status: dict[str, Any] | None = None
        # The HTTP server is threaded; the virtual bus and TX scheduler are not thread-safe on their
        # own, so every request that reads or changes simulator/TX state holds this lock.
        self.lock = threading.RLock()
        self.bus.subscribe(self._on_simulated_frame)

    def _on_simulated_frame(self, frame: dict[str, Any]) -> None:
        # Storage is the authoritative record; callbacks intentionally do not mutate raw records.
        pass

    def health(self) -> dict[str, Any]:
        serial = self.serial.status()
        details = ["sqlite_store_ready", "simulation_ready", "hardware_tx_disabled"]
        status = "ok"
        if not serial["connected"]:
            details.append("firmware_serial_not_connected")
            status = "degraded"
        return {"schema_version": 1, "status": status, "details": details}

    def capabilities(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "features": [
                "schema-v1-contract-validation", "sqlite-session-persistence", "json-bundle-import-export",
                "raw-can-frame-filtering", "identifier-periodicity-analysis", "payload-change-analysis",
                "candidate-counter-checks", "evidence-linked-findings", "deterministic-virtual-can",
                "trace-replay-and-mutation", "simulation-only-tx-scheduling-and-cancellation",
                "tx-audit-log", "read-only-cw1-serial-ingest", "browser-engineering-workbench",
                "deterministic-proteus-design-source-generator",
            ],
            "diagnostic_capabilities": self.store.get_diagnostic_capabilities(),
        }

    def safety_state(self) -> dict[str, Any]:
        live = self.serial.status()
        has_device_status = isinstance(live.get("last_device_status"), dict)
        status = live.get("last_device_status", {}) if has_device_status else {}
        state = self.tx.safety_snapshot(status if has_device_status else None)
        # The host cannot independently measure the physical interlock, and it never authorizes hardware TX.
        state["source"] = "firmware" if has_device_status else "simulator"
        if state["controller_state"] not in {"running", "stopped", "bus_off", "error", "unknown"}:
            state["controller_state"] = "error"
        state["hardware_interlock_active"] = False
        state["software_armed"] = False
        state["tx_permitted"] = False
        state["faults"] = sorted(set(state["faults"] + ["host_hardware_tx_disabled", "physical_interlock_not_verified"]))
        state["inhibit_reasons"] = sorted(set(state["inhibit_reasons"] + ["no host-to-firmware TX control channel is defined in protocol v1"]))
        validate_record("safety-state", state)
        return state

    def start_capture(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_record("capture-start", request)
        if request["mode"] == "listen_only":
            self.store.log_event("WARNING", "capture.hardware_control_unavailable",
                                 "Host capture-start does not command firmware; S03 defines a read-only CW1 stream.",
                                 {"request_id": request["request_id"]})
            raise Conflict("hardware capture cannot be remotely started by this firmware protocol revision; connect its CW1 serial stream and use firmware-side configuration. No start command was sent.")
        if self.bus.session_id:
            try:
                existing = self.store.get_session(self.bus.session_id)
                if existing["ended_at_utc"] is None:
                    raise Conflict("a simulation session is already active")
            except NotFound:
                pass
        manifest = self.bus.create_session(
            self.store, request["bitrate_bps"], request["identifier_filter"], request.get("notes", "")
        )
        self.store.log_event("INFO", "capture.simulation_started", "Started deterministic simulated capture",
                             {"session_id": manifest["session_id"], "request_id": request["request_id"]})
        return manifest

    def stop_capture(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_record("capture-stop", request)
        manifest = self.store.get_session(request["session_id"])
        if manifest["ended_at_utc"] is not None:
            return manifest
        finished = self.store.finish_session(request["session_id"], manifest.get("user_notes", ""))
        if self.bus.session_id == request["session_id"]:
            self.bus._session_id = None
            self.bus._scenario = None
            self.bus._scheduled_nodes.clear()
            self.bus._events.clear()
        return finished

    def create_scenario(self, body: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise ContractViolation("scenario must be an object")
        allowed = {"name", "bitrate_bps", "identifier_filter", "notes", "nodes"}
        unknown = set(body) - allowed
        if unknown:
            raise ContractViolation("unknown scenario fields: " + ", ".join(sorted(unknown)))
        nodes = body.get("nodes", [])
        if not isinstance(nodes, list) or len(nodes) > 32:
            raise ContractViolation("nodes must be an array with no more than 32 nodes")
        req = {
            "schema_version": 1, "record_type": "capture_start", "request_id": str(uuid4()),
            "requested_at_utc": utc_now(), "mode": "simulated",
            "bitrate_bps": body.get("bitrate_bps", 500000),
            "identifier_filter": body.get("identifier_filter", []),
            "notes": str(body.get("notes", ""))[:2000],
        }
        manifest = self.start_capture(req)
        try:
            for node in nodes:
                self.bus.add_node(node)
            self.bus.start_nodes()
        except Exception:
            self.store.finish_session(manifest["session_id"], "Scenario creation failed; session retained for evidence.")
            self.bus._session_id = None
            raise
        scenario = {
            "schema_version": 1, "scenario_id": str(uuid4()), "name": str(body.get("name", "Untitled scenario"))[:128],
            "source": "simulation", "session_id": manifest["session_id"], "created_at_utc": utc_now(),
            "nodes": [self.bus.node_record(n) for n in self.bus._nodes.values()],
            "policy": {"hardware_transmission": False, "vehicle_mappings_assumed": False},
        }
        self.store.save_scenario(scenario["scenario_id"], scenario)
        return {"scenario": scenario, "session": manifest, "simulator": self.bus.state()}

    def step_simulation(self, body: dict[str, Any]) -> dict[str, Any]:
        if not self.bus.session_id:
            raise Conflict("create a simulation scenario or start simulated capture first")
        result = self.bus.advance(self.store, int(body.get("delta_ms", 100)))
        self.tx.after_bus_step(result["frames"])
        result["summary"] = summarize_frames(self.store.get_all_frames(self.bus.session_id))
        return result

    def replay(self, body: dict[str, Any]) -> dict[str, Any]:
        if not self.bus.session_id:
            raise Conflict("start a target simulated session before trace replay")
        source_id = str(body.get("source_session_id", ""))
        speed = float(body.get("speed", 1.0))
        source_frames = self.store.get_all_frames(source_id)
        return self.bus.replay(self.store, source_frames, speed)

    def mutate(self, body: dict[str, Any]) -> dict[str, Any]:
        if not self.bus.session_id:
            raise Conflict("start a target simulated session before mutation")
        source_id = str(body.get("source_session_id", self.bus.session_id))
        source_frames = self.store.get_all_frames(source_id)
        operations = body.get("operations", [])
        if not isinstance(operations, list) or len(operations) > 16:
            raise ContractViolation("operations must be an array with no more than 16 entries")
        records = self.bus.mutate(self.store, source_frames, operations)
        return {"created_count": len(records), "frames": records, "session_id": self.bus.session_id}

    def run_analysis(self, session_id: str) -> dict[str, Any]:
        frames = self.store.get_all_frames(session_id)
        summary = summarize_frames(frames)
        findings = analyze_frames(frames)
        stored = [self.store.save_finding(session_id, item) for item in findings]
        return {"schema_version": 1, "session_id": session_id, "summary": summary,
                "findings": stored, "finding_count": len(stored),
                "raw_frames_mutated": False,
                "limitations": ["findings are observed/candidate hypotheses", "no vehicle-specific mapping is validated automatically"]}

    def import_bundle(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.store.import_bundle(body)

    def export_bundle(self, session_id: str) -> dict[str, Any]:
        return self.store.export_bundle(session_id)

    def add_diagnostic_capability(self, record: dict[str, Any]) -> dict[str, Any]:
        validate_record("diagnostic-capability", record)
        if record["status"] != "supported" and record["enabled"]:
            raise ContractViolation("unknown/unsupported capabilities must remain disabled")
        self.store.save_diagnostic_capability(record)
        return record

    def decode_parameter(self, body: dict[str, Any]) -> dict[str, Any]:
        session_id = str(body.get("session_id", ""))
        try:
            self.store.get_session(session_id)
        except NotFound:
            raise NotFound(f"session not found: {session_id}") from None
        frames = self.store.get_all_frames(session_id)
        definition = body.get("definition", {})
        evidence_frame_ids = body.get("evidence_frame_ids", [])
        result = decode_explicit_parameter(frames, definition, evidence_frame_ids)
        mapping = self.store.save_parameter_mapping(
            session_id, definition, evidence_frame_ids, result["method"]
        )
        result["mapping"] = mapping
        self.store.log_event(
            "INFO", "analysis.parameter_candidate",
            "Ran explicit parameter extraction; result remains a candidate",
            {"session_id": session_id, "decoded_count": result["decoded_count"],
             "mapping_id": mapping["mapping_id"], "mapping_version": mapping["version"]},
        )
        return result

    def diagnostic_workflow(self, body: dict[str, Any]) -> dict[str, Any]:
        capability_id = str(body.get("capability_id", ""))
        target = str(body.get("target", "simulation"))
        capabilities = self.store.get_diagnostic_capabilities()
        capability = next((c for c in capabilities if c["capability_id"] == capability_id), None)
        if capability is None:
            raise NotFound("diagnostic capability not found")
        gate = workflow_gate(capability, target)
        result = {
            **gate,
            "executed": False,
            "reason": "Gate evaluation only; this release does not execute vehicle-specific diagnostic protocol operations.",
            "physical_tx_performed": False,
        }
        self.store.log_event(
            "INFO", "diagnostic.workflow_gated",
            "Evaluated evidence-backed simulation gate without protocol execution",
            {"capability_id": capability_id, "target": target, "executed": False},
        )
        return result
