"""Runtime validation for Civic-Workbench v1 contracts.

This module validates data shapes using JSON Schema and checks cross-field safety
invariants that JSON Schema cannot reliably express. It does not transmit CAN
frames; firmware remains the final authority for transmission authorization.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "v1"
MAX_SAFETY_STATE_AGE_MS = 500
SCHEMA_FILES = {
    "can-frame": "can-frame.schema.json",
    "capture-session": "capture-session.schema.json",
    "analysis-finding": "analysis-finding.schema.json",
    "diagnostic-capability": "diagnostic-capability.schema.json",
    "tx-request": "tx-request.schema.json",
    "safety-state": "safety-state.schema.json",
    "transport-envelope": "transport-envelope.schema.json",
    "handshake": "handshake.schema.json",
    "device-status": "device-status.schema.json",
    "capture-start": "capture-start.schema.json",
    "capture-stop": "capture-stop.schema.json",
    "tx-cancel": "tx-cancel.schema.json",
    "tx-result": "tx-result.schema.json",
    "error-event": "error-event.schema.json",
}
ENVELOPE_PAYLOAD_SCHEMAS = {
    "hello": "handshake",
    "hello_ack": "handshake",
    "device_status": "device-status",
    "can_frame": "can-frame",
    "capture_start": "capture-start",
    "capture_started": "capture-session",
    "capture_stop": "capture-stop",
    "capture_stopped": "capture-session",
    "analysis_finding": "analysis-finding",
    "tx_request": "tx-request",
    "tx_cancel": "tx-cancel",
    "tx_result": "tx-result",
    "safety_state": "safety-state",
    "error": "error-event",
}


class ContractViolation(ValueError):
    """A contract failed schema or cross-field validation."""


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ContractViolation(f"{field} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ContractViolation(f"{field} must include a timezone")
    return parsed


@lru_cache(maxsize=len(SCHEMA_FILES))
def _load_schema(schema_name: str) -> dict[str, Any]:
    if schema_name not in SCHEMA_FILES:
        raise ContractViolation(f"unknown schema name: {schema_name}")
    path = SCHEMA_DIR / SCHEMA_FILES[schema_name]
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractViolation(f"cannot load schema {path}: {exc}") from exc
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ContractViolation(f"invalid JSON Schema {path}: {exc}") from exc
    return schema


def _validate_schema(schema_name: str, instance: Any) -> None:
    validator = Draft202012Validator(
        _load_schema(schema_name), format_checker=FormatChecker()
    )
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: (list(map(str, error.absolute_path)), error.message),
    )
    if errors:
        error = errors[0]
        location = "/" + "/".join(map(str, error.absolute_path))
        if location == "/":
            location = "(root)"
        raise ContractViolation(
            f"{schema_name} invalid at {location}: {error.message}"
        )


def _validate_semantics(schema_name: str, record: dict[str, Any]) -> None:
    if schema_name in {"can-frame", "tx-request"}:
        identifier = record["arbitration_id"]
        if record["id_format"] == "standard" and identifier > 0x7FF:
            raise ContractViolation("standard CAN identifier exceeds 11 bits")
        if record["id_format"] == "extended" and identifier > 0x1FFFFFFF:
            raise ContractViolation("extended CAN identifier exceeds 29 bits")
        if record["frame_type"] == "data" and len(record["payload"]) != record["dlc"]:
            raise ContractViolation("data-frame payload length must equal DLC")
        if record["frame_type"] == "remote" and record["payload"]:
            raise ContractViolation("remote frame must not contain payload bytes")
        if schema_name == "tx-request" and record["repeat_count"] < 1:
            raise ContractViolation("TX requests must be bounded to at least one send")
        if schema_name == "tx-request":
            minimum_duration_ms = (record["repeat_count"] - 1) * record["period_ms"]
            if minimum_duration_ms > record["timeout_ms"]:
                raise ContractViolation(
                    "TX repeat schedule exceeds the request timeout budget"
                )

    elif schema_name == "capture-session":
        started = _parse_datetime(record["started_at_utc"], "started_at_utc")
        if record["ended_at_utc"] is not None:
            ended = _parse_datetime(record["ended_at_utc"], "ended_at_utc")
            if ended < started:
                raise ContractViolation("ended_at_utc cannot precede started_at_utc")
        raw_path = record["raw_capture"]["relative_path"]
        path_parts = PurePosixPath(raw_path).parts
        if (
            PurePosixPath(raw_path).is_absolute()
            or "\\" in raw_path
            or ".." in path_parts
            or (len(raw_path) > 1 and raw_path[1] == ":")
            or "\x00" in raw_path
        ):
            raise ContractViolation(
                "raw_capture.relative_path must be a safe POSIX relative path"
            )

    elif schema_name == "analysis-finding":
        candidate = record.get("candidate_signal")
        if candidate and candidate["start_bit"] + candidate["bit_length"] > 64:
            raise ContractViolation("candidate signal bit range exceeds 64 bits")
        if record["status"] == "validated" and not record.get("validation"):
            raise ContractViolation(
                "validated findings require independent validation evidence"
            )

    elif schema_name == "diagnostic-capability":
        status = record["status"]
        enabled = record["enabled"]
        evidence = record["supporting_evidence"]
        if status == "supported" and (not enabled or not evidence):
            raise ContractViolation(
                "supported diagnostic capability must be enabled and evidence-backed"
            )
        if status != "supported" and enabled:
            raise ContractViolation(
                "unknown/unsupported diagnostic capabilities cannot be enabled"
            )

    elif schema_name == "safety-state":
        if record["tx_permitted"]:
            required = (
                record["mode"] == "normal"
                and record["software_armed"]
                and record["hardware_interlock_active"]
                and record["controller_state"] == "running"
                and not record["faults"]
                and record["state_age_ms"] <= MAX_SAFETY_STATE_AGE_MS
            )
            if not required:
                raise ContractViolation(
                    "TX permission requires normal mode, software arm, hardware "
                    "interlock, running controller, no faults, and a fresh state"
                )
            expiry = record.get("arm_expires_at_utc")
            if expiry is not None:
                expires_at = _parse_datetime(expiry, "arm_expires_at_utc")
                observed_at = _parse_datetime(
                    record["observed_at_utc"], "observed_at_utc"
                )
                if expires_at <= observed_at:
                    raise ContractViolation("TX arm lease is expired")

    elif schema_name == "transport-envelope":
        payload_schema = ENVELOPE_PAYLOAD_SCHEMAS.get(record["message_type"])
        if payload_schema is not None:
            _validate_schema(payload_schema, record["payload"])
            _validate_semantics(payload_schema, record["payload"])


def validate_record(schema_name: str, record: Any) -> dict[str, Any]:
    """Validate a v1 contract record and return the same object unchanged."""
    _validate_schema(schema_name, record)
    if not isinstance(record, dict):
        raise ContractViolation("contract records must be JSON objects")
    _validate_semantics(schema_name, record)
    return record


def authorize_transmission(
    tx_request: dict[str, Any], safety_state: dict[str, Any]
) -> None:
    """Validate a TX request and a fresh, fully permissive safety snapshot.

    This is a host-side contract guard only, not physical authorization. The
    firmware must independently check interlock state and revalidate every send.
    """
    validate_record("tx-request", tx_request)
    validate_record("safety-state", safety_state)
    if safety_state["source"] != "firmware":
        raise ContractViolation(
            "transmission denied: only a live firmware safety state can authorize hardware TX"
        )
    if not safety_state["tx_permitted"]:
        reasons = safety_state.get("inhibit_reasons", [])
        joined = "; ".join(reasons) if reasons else "TX is inhibited"
        raise ContractViolation(f"transmission denied: {joined}")
    if safety_state["state_age_ms"] > MAX_SAFETY_STATE_AGE_MS:
        raise ContractViolation("transmission denied: safety state is stale")
