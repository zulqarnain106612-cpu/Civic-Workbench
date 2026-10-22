"""Evidence-linked identifier and signal discovery from raw observations."""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .contracts import ContractViolation, validate_record


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _finding(kind: str, status: str, summary: str, evidence: list[dict[str, Any]], method: str,
             confidence: float, identifier: int | None = None, id_format: str | None = None,
             candidate_signal: dict[str, Any] | None = None,
             annotations: dict[str, Any] | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": 1, "record_type": "analysis_finding",
        "finding_id": str(uuid4()), "created_at_utc": _utc(),
        "finding_kind": kind, "status": status, "summary": summary[:2000],
        "evidence_frame_ids": list(dict.fromkeys(f["frame_id"] for f in evidence)),
        "method": method, "confidence": max(0.0, min(1.0, float(confidence))),
    }
    if identifier is not None:
        record["arbitration_id"] = identifier
        record["id_format"] = id_format
    if candidate_signal is not None:
        record["candidate_signal"] = candidate_signal
    if annotations:
        record["annotations"] = annotations
    validate_record("analysis-finding", record)
    return record


def summarize_frames(frames: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for frame in frames:
        by_id[(frame["id_format"], frame["arbitration_id"])].append(frame)
    ids = []
    total_intervals = []
    for (id_format, arbitration_id), records in sorted(by_id.items(), key=lambda item: (item[0][0], item[0][1])):
        stamps = sorted(int(r["captured_monotonic_ns"]) for r in records)
        deltas = [b - a for a, b in zip(stamps, stamps[1:]) if b >= a]
        median_ns = int(statistics.median(deltas)) if deltas else None
        jitter_ns = int(max(deltas) - min(deltas)) if len(deltas) > 1 else 0 if deltas else None
        if median_ns is not None:
            total_intervals.append(median_ns)
        variability = []
        for offset in range(8):
            values = {r["payload"][offset] for r in records if r["frame_type"] == "data" and len(r["payload"]) > offset}
            if len(values) > 1:
                variability.append({"byte_offset": offset, "unique_values": len(values), "sample_count": len(records)})
        ids.append({
            "id_format": id_format, "arbitration_id": arbitration_id, "count": len(records),
            "median_period_ns": median_ns, "jitter_range_ns": jitter_ns,
            "variable_bytes": variability,
            "last_seen_monotonic_ns": max(stamps) if stamps else None,
        })
    return {
        "schema_version": 1, "total_frames": len(frames), "unique_identifiers": len(by_id),
        "frames_per_second_estimate": round(1e9 * len(frames) / max(1, max((f["captured_monotonic_ns"] for f in frames), default=0) - min((f["captured_monotonic_ns"] for f in frames), default=0)), 3) if len(frames) > 1 else 0.0,
        "identifiers": ids,
        "simulation_or_hardware_mixed": len({f["capture_source"] for f in frames}) > 1,
    }


def analyze_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return schema-valid observations/candidates; never auto-promote a mapping to validated."""
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for frame in frames:
        validate_record("can-frame", frame)
        groups[(frame["id_format"], frame["arbitration_id"])].append(frame)
    findings: list[dict[str, Any]] = []
    for (id_format, identifier), original in sorted(groups.items()):
        records = sorted(original, key=lambda r: (r["captured_monotonic_ns"], r["frame_id"]))
        if len(records) >= 3:
            stamps = [int(r["captured_monotonic_ns"]) for r in records]
            deltas = [b-a for a,b in zip(stamps, stamps[1:]) if b > a]
            if deltas:
                median = statistics.median(deltas)
                jitter = (max(deltas)-min(deltas))/median if median else 1.0
                findings.append(_finding(
                    "identifier_periodicity", "observed",
                    f"{id_format} ID 0x{identifier:X}: {len(records)} observed frames; median observed interval {median/1e6:.3f} ms; relative interval range {jitter:.3f}.",
                    records[: min(12, len(records))], "median consecutive monotonic timestamp deltas; duplicate/zero deltas excluded",
                    1.0 if len(deltas) >= 3 else 0.6, identifier, id_format,
                    annotations={"median_period_ns": int(median), "min_interval_ns": min(deltas), "max_interval_ns": max(deltas), "sample_count": len(records)}
                ))
        data_records = [r for r in records if r["frame_type"] == "data"]
        if len(data_records) < 2:
            continue
        max_payload = max((len(r["payload"]) for r in data_records), default=0)
        for offset in range(max_payload):
            indexed = [(r, r["payload"][offset]) for r in data_records if len(r["payload"]) > offset]
            values = [v for _, v in indexed]
            unique = sorted(set(values))
            if len(unique) < 2:
                continue
            evidence = [indexed[0][0], indexed[-1][0]]
            ratio = len(unique)/max(2, len(values))
            findings.append(_finding(
                "payload_change", "observed",
                f"{id_format} ID 0x{identifier:X}, byte {offset}: {len(unique)} distinct values across {len(values)} samples.",
                evidence, "per-byte distinct-value count across raw payload samples", min(0.95, 0.45 + ratio*0.25),
                identifier, id_format,
                candidate_signal={"start_bit": offset*8, "bit_length": 8, "byte_order": "unknown", "signed": None, "scale": None, "offset": None, "unit": None},
                annotations={"byte_offset": offset, "unique_values": len(unique), "sample_count": len(values), "values_preview": unique[:32]}
            ))
            if len(values) >= 4:
                deltas = [b-a for a,b in zip(values, values[1:])]
                increasing = sum(1 for d in deltas if d > 0)
                nondecreasing_wrap = sum(1 for d in deltas if d == 1 or d < -200)
                if len(deltas) >= 3 and (increasing + nondecreasing_wrap) / len(deltas) >= 0.75:
                    findings.append(_finding(
                        "counter_candidate", "candidate",
                        f"Candidate counter: ID 0x{identifier:X}, payload byte {offset}; values are mostly incrementing or byte-wrapping in capture order.",
                        [r for r,_ in indexed[: min(12, len(indexed))]], "adjacent-byte sequence inspection (little-endian 8-bit view only)", 0.35,
                        identifier, id_format,
                        candidate_signal={"start_bit": offset*8, "bit_length": 8, "byte_order": "unknown", "signed": False, "scale": None, "offset": None, "unit": None},
                        annotations={"candidate_pattern": "mostly_incrementing_byte", "increasing_transitions": increasing, "transitions": len(deltas)}
                    ))
        # High-variation bytes are hypotheses, not checksum identifications.
        if len(data_records) >= 8 and max_payload >= 2:
            variability = []
            for offset in range(max_payload):
                vals = {r["payload"][offset] for r in data_records if len(r["payload"]) > offset}
                if len(vals) >= min(8, len(data_records) // 2):
                    variability.append(offset)
            if variability:
                findings.append(_finding(
                    "checksum_candidate", "candidate",
                    f"High-variation byte positions {variability} on ID 0x{identifier:X} merit checksum/counter investigation; no algorithm is asserted.",
                    records[: min(16, len(records))], "byte entropy proxy and coverage threshold; not a checksum detector", 0.2,
                    identifier, id_format, annotations={"high_variation_byte_offsets": variability}
                ))
    return findings


def independent_validation(finding: dict[str, Any], validation_method: str, evidence_refs: list[str],
                            reviewer: str | None = None) -> dict[str, Any]:
    """Explicit operator step; requires non-empty independent evidence before status=validated."""
    if finding.get("status") != "candidate":
        raise ContractViolation("only a candidate finding may be moved to validated")
    if not validation_method.strip() or not evidence_refs or any(not str(ref).strip() for ref in evidence_refs):
        raise ContractViolation("independent validation method and evidence references are required")
    validated = dict(finding)
    validated["status"] = "validated"
    validated["validation"] = {
        "validation_method": validation_method.strip()[:1000],
        "validated_at_utc": _utc(),
        "reviewer": reviewer,
        "evidence_refs": list(dict.fromkeys(str(ref) for ref in evidence_refs)),
    }
    validate_record("analysis-finding", validated)
    return validated
