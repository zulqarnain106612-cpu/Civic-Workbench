"""Capability-driven diagnostic and parameter-decoding primitives.

No vehicle addresses, services, scales, or ECU mappings are bundled here. A workflow
can run only against an explicitly evidence-backed capability; physical TX is never
implemented by this module.
"""
from __future__ import annotations

from typing import Any
from .contracts import ContractViolation, validate_record


def decode_explicit_parameter(
    frames: list[dict[str, Any]],
    definition: dict[str, Any],
    evidence_frame_ids: list[str],
) -> dict[str, Any]:
    """Decode a user-reviewed bit/byte hypothesis while retaining candidate status."""
    required = {"name", "start_bit", "bit_length", "byte_order", "signed", "scale", "offset", "unit"}
    if set(definition) != required:
        raise ContractViolation("parameter definition must contain exactly: " + ", ".join(sorted(required)))
    name = str(definition["name"]).strip()
    start = int(definition["start_bit"])
    length = int(definition["bit_length"])
    order = definition["byte_order"]
    if not name or len(name) > 128:
        raise ContractViolation("parameter name is required and must be at most 128 characters")
    if start < 0 or length < 1 or start + length > 64:
        raise ContractViolation("parameter bit range must fit within 64 bits")
    if order not in {"little_endian", "big_endian"}:
        raise ContractViolation("byte_order must be explicitly selected for decoding")
    if not isinstance(definition["scale"], (int, float)) or isinstance(definition["scale"], bool):
        raise ContractViolation("scale must be an explicit numeric value")
    if not isinstance(definition["offset"], (int, float)) or isinstance(definition["offset"], bool):
        raise ContractViolation("offset must be an explicit numeric value")
    if definition["signed"] not in {True, False}:
        raise ContractViolation("signedness must be explicitly selected")
    if not evidence_frame_ids:
        raise ContractViolation("decoding requires at least one evidence frame ID")
    by_id = {frame["frame_id"]: frame for frame in frames}
    missing = sorted(set(evidence_frame_ids) - set(by_id))
    if missing:
        raise ContractViolation("evidence frame IDs are not present in the selected session: " + ", ".join(missing))
    selected = [by_id[frame_id] for frame_id in evidence_frame_ids]
    values = []
    for frame in selected:
        if frame.get("frame_type") != "data" or len(frame.get("payload", [])) * 8 < start + length:
            continue
        payload = list(frame["payload"])
        if order == "little_endian":
            raw = int.from_bytes(bytes(payload), "little")
            raw = (raw >> start) & ((1 << length) - 1)
        else:
            raw = int.from_bytes(bytes(payload), "big")
            shift = len(payload) * 8 - start - length
            raw = (raw >> shift) & ((1 << length) - 1)
        if bool(definition["signed"]) and raw & (1 << (length - 1)):
            raw -= 1 << length
        value = raw * float(definition["scale"]) + float(definition["offset"])
        values.append({"frame_id": frame["frame_id"], "raw": raw, "value": value})
    return {
        "schema_version": 1,
        "definition": dict(definition),
        "status": "candidate",
        "decoded_count": len(values),
        "values": values,
        "evidence_frame_ids": [f["frame_id"] for f in selected],
        "method": "user-specified bit extraction; byte order/scale/offset are inputs, not inferred facts",
        "validated": False,
        "warning": "Candidate decoder only. Independent evidence/review is required before claiming a validated vehicle parameter.",
    }


def workflow_gate(capability: dict[str, Any], target: str) -> dict[str, Any]:
    validate_record("diagnostic-capability", capability)
    if capability["status"] != "supported" or not capability["enabled"] or not capability["supporting_evidence"]:
        raise ContractViolation("workflow denied: capability must be explicitly supported, enabled, and evidence-backed")
    if target != "simulation":
        raise ContractViolation("physical diagnostic workflows are disabled in the host. Only simulation is allowed.")
    return {
        "allowed": True, "target": "simulation", "capability_id": capability["capability_id"],
        "physical_tx_performed": False, "protocol": capability["protocol"],
        "evidence": capability["supporting_evidence"],
    }
