"""Deterministic virtual CAN bus. All generated traffic is tagged capture_source=simulator."""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .contracts import ContractViolation, validate_record
from .analysis import summarize_frames


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(order=True)
class ScheduledFrame:
    due_ns: int
    sequence: int
    record: dict[str, Any] = field(compare=False)
    request_id: str | None = field(default=None, compare=False)


@dataclass
class VirtualNode:
    node_id: str
    arbitration_id: int
    id_format: str = "standard"
    period_ms: int = 100
    payload_mode: str = "counter"
    payload: list[int] = field(default_factory=lambda: [0] * 8)
    enabled: bool = True
    _counter: int = 0

    def frame_payload(self) -> list[int]:
        out = list(self.payload[:8])
        out += [0] * (8-len(out))
        if self.payload_mode == "counter":
            out[0] = self._counter & 0xFF
            self._counter += 1
        elif self.payload_mode == "toggle":
            out[0] = 0xFF if self._counter % 2 else 0
            self._counter += 1
        elif self.payload_mode == "fixed":
            pass
        else:
            raise ContractViolation("payload_mode must be counter, toggle or fixed")
        return out


class VirtualCanBus:
    def __init__(self):
        self.now_ns = 0
        self._sequence = 0
        self._events: list[ScheduledFrame] = []
        self._nodes: dict[str, VirtualNode] = {}
        self._listeners: list[Any] = []
        self._filters: set[int] | None = None
        self._history: list[dict[str, Any]] = []
        self._scenario: dict[str, Any] | None = None
        self._session_id: str | None = None
        self._scheduled_nodes: list[tuple[int, str]] = []

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def now_ms(self) -> float:
        return self.now_ns / 1_000_000

    @property
    def queue_depth(self) -> int:
        return len(self._events)

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def set_filter(self, identifiers: list[int] | None) -> None:
        self._filters = set(identifiers) if identifiers else None

    def create_session(self, store, bitrate_bps: int | None, filters: list[int] | None, notes: str = "") -> dict[str, Any]:
        self._session_id = str(uuid4())
        self.now_ns = 0
        self._sequence = 0
        self._events.clear()
        self._history.clear()
        self._nodes.clear()
        self._scheduled_nodes.clear()
        self._filters = set(filters) if filters else None
        self._scenario = {"nodes": [], "started_at_utc": _utc()}
        return store.create_session("simulator", bitrate_bps, filters, notes, session_id=self._session_id, mode="simulated")

    def add_node(self, config: dict[str, Any]) -> VirtualNode:
        allowed = {"node_id", "arbitration_id", "id_format", "period_ms", "payload_mode", "payload", "enabled"}
        if set(config) - allowed:
            raise ContractViolation("unknown virtual node fields: " + ", ".join(sorted(set(config)-allowed)))
        node_id = str(config.get("node_id") or ("node-" + str(len(self._nodes)+1)))
        identifier = int(config.get("arbitration_id", 0x100))
        id_format = str(config.get("id_format", "standard"))
        period = int(config.get("period_ms", 100))
        mode = str(config.get("payload_mode", "counter"))
        payload = list(config.get("payload", [0]*8))
        if id_format not in {"standard", "extended"}:
            raise ContractViolation("id_format must be standard or extended")
        if not 1 <= period <= 60000:
            raise ContractViolation("period_ms must be between 1 and 60000")
        if not 0 <= identifier <= (0x7FF if id_format == "standard" else 0x1FFFFFFF):
            raise ContractViolation("identifier is outside the selected CAN format")
        if mode not in {"counter", "toggle", "fixed"}:
            raise ContractViolation("payload_mode must be counter, toggle or fixed")
        if len(payload) > 8 or any(not isinstance(x, int) or not 0 <= x <= 255 for x in payload):
            raise ContractViolation("payload must contain at most 8 bytes, each 0..255")
        node = VirtualNode(node_id, identifier, id_format, period, mode, payload, bool(config.get("enabled", True)))
        self._nodes[node_id] = node
        if self._scenario is not None:
            self._scenario["nodes"] = [self.node_record(n) for n in self._nodes.values()]
        return node

    @staticmethod
    def node_record(node: VirtualNode) -> dict[str, Any]:
        return {"node_id": node.node_id, "arbitration_id": node.arbitration_id, "id_format": node.id_format,
                "period_ms": node.period_ms, "payload_mode": node.payload_mode, "payload": node.payload,
                "enabled": node.enabled}

    def start_nodes(self) -> None:
        for node in self._nodes.values():
            if node.enabled:
                self._scheduled_nodes.append((self.now_ns + node.period_ms * 1_000_000, node.node_id))
        self._scheduled_nodes.sort()

    def _frame(self, identifier: int, id_format: str, payload: list[int], direction: str = "rx",
               request_id: str | None = None, source_ref: str | None = None) -> dict[str, Any]:
        if not self._session_id:
            raise ContractViolation("start a simulated capture session first")
        now = self.now_ns
        frame = {
            "schema_version": 1, "record_type": "can_frame",
            "frame_id": str(uuid4()), "session_id": self._session_id,
            "captured_monotonic_ns": now,
            "clock_source": "monotonic_only",
            "arbitration_id": identifier, "id_format": id_format, "frame_type": "data",
            "dlc": len(payload), "payload": list(payload), "direction": direction,
            "capture_source": "simulator",
            "controller_state": "running", "dropped_frames_before": 0, "dropped_frames_after": 0,
        }
        if source_ref:
            frame["source_record_ref"] = source_ref
        validate_record("can-frame", frame)
        return frame

    def send(self, store, identifier: int, id_format: str, payload: list[int], direction: str = "rx",
             request_id: str | None = None, source_ref: str | None = None) -> dict[str, Any] | None:
        if self._filters is not None and identifier not in self._filters:
            return None
        frame = self._frame(identifier, id_format, payload, direction, request_id, source_ref)
        store.add_frame(frame)
        self._history.append(frame)
        for callback in list(self._listeners):
            callback(frame)
        return frame

    def inject_raw(self, store, frame: dict[str, Any], at_ms: int = 0) -> dict[str, Any] | None:
        if not 0 <= int(at_ms) <= 3_600_000:
            raise ContractViolation("scheduled time must be within one hour")
        record = self._frame(frame["arbitration_id"], frame["id_format"], list(frame["payload"]))
        record["captured_monotonic_ns"] = self.now_ns + int(at_ms)*1_000_000
        record["source_record_ref"] = frame["frame_id"]
        record["direction"] = "rx"
        heapq.heappush(self._events, ScheduledFrame(record["captured_monotonic_ns"], self._sequence, record))
        self._sequence += 1
        return record

    def schedule(self, record: dict[str, Any], at_ns: int, request_id: str | None = None) -> None:
        if not self._session_id:
            raise ContractViolation("start a simulated capture session first")
        if at_ns < self.now_ns:
            raise ContractViolation("cannot schedule an event in the past")
        heapq.heappush(self._events, ScheduledFrame(int(at_ns), self._sequence, record, request_id))
        self._sequence += 1

    def cancel_request(self, request_id: str) -> int:
        before = len(self._events)
        self._events = [event for event in self._events if event.request_id != request_id]
        heapq.heapify(self._events)
        return before - len(self._events)

    def advance(self, store, delta_ms: int) -> dict[str, Any]:
        if not isinstance(delta_ms, int) or delta_ms < 0 or delta_ms > 3_600_000:
            raise ContractViolation("delta_ms must be 0..3600000")
        end_ns = self.now_ns + delta_ms*1_000_000
        scheduled_count = 0
        for due_ns, node_id in self._scheduled_nodes:
            node = self._nodes.get(node_id)
            if node and node.enabled and due_ns <= end_ns:
                scheduled_count += (end_ns - due_ns) // (node.period_ms * 1_000_000) + 1
        if scheduled_count + len(self._events) > 50000:
            raise ContractViolation("one simulation step is capped at 50000 pending/generated events; use smaller time increments")
        emitted: list[dict[str, Any]] = []
        while self._scheduled_nodes and self._scheduled_nodes[0][0] <= end_ns:
            due_ns, node_id = self._scheduled_nodes.pop(0)
            node = self._nodes[node_id]
            self.now_ns = due_ns
            record = self._frame(node.arbitration_id, node.id_format, node.frame_payload())
            event = ScheduledFrame(due_ns, self._sequence, record)
            heapq.heappush(self._events, event)
            self._sequence += 1
            self._scheduled_nodes.append((due_ns + node.period_ms*1_000_000, node_id))
            self._scheduled_nodes.sort()
        while self._events and self._events[0].due_ns <= end_ns:
            event = heapq.heappop(self._events)
            self.now_ns = event.due_ns
            record = event.record
            record["captured_monotonic_ns"] = self.now_ns
            if event.request_id:
                record["direction"] = "tx"
                # Request correlation remains in source_record_ref and the separate TX audit table.
            validate_record("can-frame", record)
            if self._filters is None or record["arbitration_id"] in self._filters:
                emitted.append(record)
        self.now_ns = end_ns
        # Batch writes in one SQLite transaction so long deterministic scenarios do not open a
        # connection per frame. Sequence and raw record ordering remain stable.
        if emitted:
            store.add_frames(emitted)
            self._history.extend(emitted)
            for record in emitted:
                for callback in list(self._listeners):
                    callback(record)
        summary = summarize_frames(self._history)
        return {"now_ms": self.now_ms, "emitted_count": len(emitted), "frames": emitted,
                "queue_depth": len(self._events), "session_id": self._session_id,
                "summary": summary}

    def replay(self, store, source_frames: list[dict[str, Any]], speed: float = 1.0) -> dict[str, Any]:
        if not 0.01 <= speed <= 100:
            raise ContractViolation("replay speed must be 0.01..100")
        if len(source_frames) > 100000:
            raise ContractViolation("replay is capped at 100000 frames per request")
        if len(self._events) + len(source_frames) > 100000:
            raise ContractViolation("virtual pending event queue is capped at 100000 records")
        if not source_frames:
            return {"scheduled_count": 0, "session_id": self._session_id}
        origin = min(f["captured_monotonic_ns"] for f in source_frames)
        for frame in source_frames:
            due_ms = int((frame["captured_monotonic_ns"] - origin) / 1_000_000 / speed)
            self.inject_raw(store, frame, due_ms)
        return {"scheduled_count": len(source_frames), "session_id": self._session_id, "speed": speed}

    def mutate(self, store, frames: list[dict[str, Any]], operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        allowed_ops = {"flip_bit", "xor_byte", "set_byte", "delay_ms"}
        mutated = []
        for source in frames:
            payload = list(source["payload"])
            for op in operations:
                kind = op.get("kind")
                if kind not in allowed_ops:
                    raise ContractViolation("mutation kind must be flip_bit, xor_byte, set_byte, or delay_ms")
                if kind == "flip_bit":
                    bit = int(op.get("bit", 0))
                    if 0 <= bit < len(payload)*8:
                        payload[bit//8] ^= 1 << (bit % 8)
                elif kind in {"xor_byte", "set_byte"}:
                    offset = int(op.get("byte_offset", 0))
                    value = int(op.get("value", 0))
                    if not 0 <= offset < len(payload) or not 0 <= value <= 255:
                        raise ContractViolation("mutation byte_offset/value outside range")
                    payload[offset] = payload[offset] ^ value if kind == "xor_byte" else value
            new_frame = self._frame(source["arbitration_id"], source["id_format"], payload, "rx", source_ref=source["frame_id"])
            if any(op.get("kind") == "delay_ms" for op in operations):
                delay = sum(max(0, int(op.get("value", 0))) for op in operations if op.get("kind") == "delay_ms")
                new_frame["captured_monotonic_ns"] += delay*1_000_000
            store.add_frame(new_frame)
            mutated.append(new_frame)
        return mutated

    def state(self) -> dict[str, Any]:
        return {"session_id": self._session_id, "virtual_time_ms": self.now_ms, "queue_depth": len(self._events),
                "nodes": [self.node_record(n) for n in self._nodes.values()],
                "scheduled_nodes": len(self._scheduled_nodes), "history_count": len(self._history),
                "source": "simulation"}
