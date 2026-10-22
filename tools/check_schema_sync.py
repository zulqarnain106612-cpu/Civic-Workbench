#!/usr/bin/env python3
"""Verify that canonical repository schemas and wheel-packaged schemas are identical."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "schemas" / "v1"
PACKAGED = ROOT / "src" / "civic_workbench" / "schemas" / "v1"


def main() -> int:
    source_files = {path.name: path for path in SOURCE.glob("*.schema.json")}
    packaged_files = {path.name: path for path in PACKAGED.glob("*.schema.json")}
    if set(source_files) != set(packaged_files):
        missing = sorted(set(source_files) - set(packaged_files))
        extra = sorted(set(packaged_files) - set(source_files))
        raise SystemExit(f"packaged schema manifest mismatch; missing={missing}, extra={extra}")
    differences = [
        name for name, source in source_files.items()
        if hashlib.sha256(source.read_bytes()).digest()
        != hashlib.sha256(packaged_files[name].read_bytes()).digest()
    ]
    if differences:
        raise SystemExit("schema copies are out of sync: " + ", ".join(sorted(differences)))
    print(f"SCHEMA_PACKAGE_SYNC=PASS ({len(source_files)} identical versioned schemas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
