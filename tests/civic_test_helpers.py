"""Shared deterministic fixtures for product integration tests."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def utc_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_frame(
    session_id: str,
    index: int = 0,
    arbitration_id: int = 0x123,
    id_format: str = "standard",
    payload: list[int] | None = None,
    capture_source: str = "simulator",
    clock_source: str = "monotonic_and_wall_clock",
    controller_state: str = "running",
) -> dict[str, Any]:
    data = list(payload if payload is not None else [
        index & 0xFF, (index * 3) & 0xFF, (index * 7) & 0xFF, 0, 1, 2, 3, 4
    ])
    record: dict[str, Any] = {
        "schema_version": 1,
        "record_type": "can_frame",
        "frame_id": str(uuid4()),
        "session_id": session_id,
        "captured_monotonic_ns": index * 10_000_000,
        "clock_source": clock_source,
        "arbitration_id": arbitration_id,
        "id_format": id_format,
        "frame_type": "data",
        "dlc": len(data),
        "payload": data,
        "direction": "rx",
        "capture_source": capture_source,
        "controller_state": controller_state,
        "dropped_frames_before": 0,
        "dropped_frames_after": 0,
    }
    if clock_source == "monotonic_and_wall_clock":
        record["captured_at_utc"] = utc_text()
    return record


def seed_session(store, count: int = 10, capture_source: str = "simulator",
                 id_format: str = "standard") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = store.create_session(
        capture_source=capture_source,
        bitrate_bps=500000 if capture_source != "import" else None,
        mode="simulated" if capture_source == "simulator" else None,
        notes="Synthetic integration fixture; not physical vehicle evidence.",
    )
    frames = [
        make_frame(
            manifest["session_id"],
            index,
            arbitration_id=0x120 + (index % 3) if id_format == "standard" else 0x123456 + (index % 3),
            id_format=id_format,
            capture_source=capture_source,
        )
        for index in range(count)
    ]
    if frames:
        store.add_frames(frames)
    return manifest, frames


def tx_request(identifier: int = 0x321, repeats: int = 2, period_ms: int = 100,
               timeout_ms: int = 500, frame_type: str = "data", payload: list[int] | None = None) -> dict[str, Any]:
    values = list(payload if payload is not None else [0xAA, 0x55])
    return {
        "schema_version": 1,
        "record_type": "tx_request",
        "request_id": str(uuid4()),
        "created_at_utc": utc_text(),
        "arbitration_id": identifier,
        "id_format": "standard",
        "frame_type": frame_type,
        "dlc": len(values) if frame_type == "data" else 8,
        "payload": values if frame_type == "data" else [],
        "period_ms": period_ms,
        "repeat_count": repeats,
        "timeout_ms": timeout_ms,
        "requested_by": "integration-test",
        "operator_note": "Synthetic virtual-bus request only.",
    }
