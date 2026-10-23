"""Conservative host TX scheduler. Only simulation targets are executable in this build."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .contracts import ContractViolation, validate_record
from .storage import SessionStore
from .simulator import VirtualCanBus


class TxScheduler:
    def __init__(self, store: SessionStore, bus: VirtualCanBus):
        self.store = store
        self.bus = bus
        self._requests: dict[str, dict[str, Any]] = {}
        self.hardware_tx_enabled = False

    def _utc(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def safety_snapshot(self, live_firmware_status: dict[str, Any] | None = None) -> dict[str, Any]:
        status = live_firmware_status or {}
        controller = status.get("controller_state", "unknown")
        fault_codes = list(status.get("faults", []))
        reasons = ["host TX scheduler is simulation-only", "no independently verified physical interlock state"]
        if not status or status.get("connected") is not True:
            reasons.append("no live firmware status")
        return {
            "schema_version": 1, "record_type": "safety_state", "observed_at_utc": self._utc(),
            "mode": "normal" if self.bus.session_id else "listen_only",
            "software_armed": False, "hardware_interlock_active": False, "tx_permitted": False,
            "controller_state": controller if controller in {"running", "stopped", "bus_off", "error", "unknown"} else "unknown",
            "faults": sorted(set(fault_codes + ["host_hardware_tx_disabled"])),
            "state_age_ms": 0, "source": "firmware" if status else "simulator",
            "inhibit_reasons": reasons, "arm_expires_at_utc": None,
        }

    def submit(self, request: dict[str, Any], target: str, session_id: str | None) -> dict[str, Any]:
        try:
            validate_record("tx-request", request)
        except ContractViolation:
            raise
        if target != "simulation":
            self.store.add_tx_audit(request["request_id"], session_id, target, "rejected", {
                "reason": "hardware transmission is disabled; this host API never calls a physical TX endpoint",
                "request": request,
                "physical_tx_performed": False,
            })
            raise ContractViolation("hardware transmission is disabled; set target=simulation for virtual-bus testing")
        if session_id is None or not self.store.session_exists(session_id):
            raise ContractViolation("simulation TX requires an existing session_id")
        manifest = self.store.get_session(session_id)
        if manifest["capture_source"] != "simulator":
            raise ContractViolation("simulation TX cannot target a hardware or imported session")
        if request["repeat_count"] > 100:
            raise ContractViolation("simulation TX repeat_count is capped at 100 per request")
        if request["timeout_ms"] < (request["repeat_count"]-1)*request["period_ms"]:
            raise ContractViolation("repeat schedule exceeds timeout")
        if request["request_id"] in self._requests:
            raise ContractViolation("request_id already exists")
        record = {"request": request, "target": target, "session_id": session_id,
                  "status": "queued", "sent_count": 0, "cancelled": False}
        self._requests[request["request_id"]] = record
        now_ns = self.bus.now_ns
        for repeat in range(request["repeat_count"]):
            due_ns = now_ns + repeat*request["period_ms"]*1_000_000
            payload = list(request["payload"])
            if request["frame_type"] == "remote":
                payload = []
            frame = self.bus._frame(request["arbitration_id"], request["id_format"], payload, "tx",
                                    request_id=request["request_id"], source_ref=request["request_id"])
            frame["frame_type"] = request["frame_type"]
            frame["dlc"] = request["dlc"]
            frame["payload"] = payload
            # Raw-frame schema handles remote-frame empty payload with preserved DLC.
            validate_record("can-frame", frame)
            self.bus.schedule(frame, due_ns, request["request_id"])
        audit = self.store.add_tx_audit(request["request_id"], session_id, target, "queued", {
            "repeat_count": request["repeat_count"], "period_ms": request["period_ms"],
            "timeout_ms": request["timeout_ms"], "execution": "virtual_bus_only",
        })
        return {"schema_version": 1, "record_type": "tx_result", "request_id": request["request_id"],
                "completed_at_utc": self._utc(), "status": "queued", "frames_sent": 0,
                "error_code": None, "details": "Scheduled on simulation bus only; no physical CAN API is called.",
                "audit": audit}

    def cancel(self, request_id: str, reason: str = "operator_cancelled") -> dict[str, Any]:
        request = self._requests.get(request_id)
        if request is None:
            raise ContractViolation("unknown TX request")
        if request["status"] in {"sent", "cancelled", "failed", "rejected"}:
            status = request["status"]
            count = 0
        else:
            count = self.bus.cancel_request(request_id)
            request["cancelled"] = True
            request["status"] = "cancelled"
            status = "cancelled"
        audit = self.store.add_tx_audit(request_id, request["session_id"], "simulation", status, {
            "cancelled_events": count, "reason": reason[:1000], "physical_tx_performed": False,
        })
        return {"schema_version": 1, "record_type": "tx_result", "request_id": request_id,
                "completed_at_utc": self._utc(), "status": status, "frames_sent": request["sent_count"],
                "error_code": None, "details": "Cancellation only affects pending virtual-bus events.", "audit": audit}

    def after_step(self, request_id: str) -> None:
        request = self._requests.get(request_id)
        if not request or request["cancelled"]:
            return
        record = request["request"]
        request["sent_count"] += 1
        if request["sent_count"] >= record["repeat_count"]:
            request["status"] = "sent"
        self.store.add_tx_audit(request_id, request["session_id"], "simulation",
                                "sent" if request["status"] == "sent" else "partial", {
            "frames_sent": request["sent_count"], "repeat_count": record["repeat_count"],
            "physical_tx_performed": False, "execution": "virtual_bus_only",
        })

    def after_bus_step(self, emitted: list[dict[str, Any]]) -> None:
        for frame in emitted:
            ref = frame.get("source_record_ref")
            if ref in self._requests:
                self.after_step(ref)

    def list_requests(self) -> list[dict[str, Any]]:
        return [{"request": r["request"], "target": r["target"], "session_id": r["session_id"],
                 "status": r["status"], "sent_count": r["sent_count"], "cancelled": r["cancelled"]}
                for r in self._requests.values()]
