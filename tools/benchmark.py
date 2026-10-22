#!/usr/bin/env python3
"""Measure SQLite batch-ingest and raw-frame analysis on generated synthetic data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import tempfile
import time
from datetime import datetime, timezone
from uuid import uuid4

from civic_workbench.analysis import analyze_frames, summarize_frames
from civic_workbench.storage import SessionStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_frame(session_id: str, i: int) -> dict:
    identifier_index = (i // 1) % 128
    identifier = 0x100 + identifier_index
    return {
        "schema_version": 1,
        "record_type": "can_frame",
        "frame_id": str(uuid4()),
        "session_id": session_id,
        "captured_monotonic_ns": i * 10_000_000,
        "captured_at_utc": utc_now(),
        "clock_source": "monotonic_and_wall_clock",
        "arbitration_id": identifier,
        "id_format": "standard",
        "frame_type": "data",
        "dlc": 8,
        "payload": [i & 255, (i >> 3) & 255, (identifier_index * 7) & 255,
                    0, 0, 0, (i * 17) & 255, (i >> 7) & 255],
        "direction": "rx",
        "capture_source": "simulator",
        "controller_state": "running",
        "dropped_frames_before": 0,
        "dropped_frames_after": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=20000)
    parser.add_argument("--output", type=Path, default=Path("docs/reports/S11-benchmark-results.json"))
    args = parser.parse_args()
    if not 100 <= args.frames <= 100000:
        parser.error("--frames must be between 100 and 100000")

    with tempfile.TemporaryDirectory(prefix="civic-workbench-benchmark-") as temp:
        store = SessionStore(temp)
        sid = str(uuid4())
        store.create_session(
            capture_source="simulator", bitrate_bps=500000, session_id=sid,
            mode="simulated", notes="Generated load profile; not physical bus traffic.",
        )
        frames = [make_frame(sid, i) for i in range(args.frames)]
        begin = time.perf_counter()
        store.add_frames(frames)
        inserted = time.perf_counter() - begin
        begin = time.perf_counter()
        summary = summarize_frames(frames)
        findings = analyze_frames(frames)
        analysis_seconds = time.perf_counter() - begin
        result = {
            "schema_version": 1,
            "kind": "synthetic_benchmark",
            "created_at_utc": utc_now(),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "cpu_count": os.cpu_count(),
                "storage": "temporary SQLite database using batched transaction",
            },
            "synthetic_input": {"frames": args.frames, "unique_ids": summary["unique_identifiers"],
                                "bitrate_bps": 500000, "period_ns": 10000000},
            "measurements": {
                "batch_insert_seconds": round(inserted, 6),
                "batch_insert_frames_per_second": round(args.frames / max(inserted, 1e-9), 2),
                "analysis_seconds": round(analysis_seconds, 6),
                "analysis_frames_per_second": round(args.frames / max(analysis_seconds, 1e-9), 2),
                "findings_generated": len(findings),
                "unique_identifiers_summarized": summary["unique_identifiers"],
            },
            "limitations": [
                "Synthetic benchmark only; does not measure physical UART/CAN throughput.",
                "This is a single run on the recorded host; it is not a latency guarantee.",
                "Identifiers and byte patterns are deliberately synthetic and imply no Honda mapping.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
