#!/usr/bin/env python3
"""Check that a built wheel contains the browser and contract schema assets."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def main() -> int:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/civic-workbench-wheels")
    wheels = sorted(directory.glob("civic_workbench-*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise SystemExit(f"no civic-workbench wheel found in {directory}")
    wheel = wheels[-1]
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required = {
            "civic_workbench/app.py",
            "civic_workbench/contracts.py",
            "civic_workbench/web/index.html",
            "civic_workbench/web/app.js",
            "civic_workbench/web/styles.css",
            "civic_workbench/schemas/v1/can-frame.schema.json",
            "civic_workbench/schemas/v1/parameter-mapping.schema.json",
        }
        missing = sorted(required - names)
        if missing:
            raise SystemExit(f"wheel {wheel.name} is missing required package data: {missing}")
    print(f"WHEEL_ASSETS=PASS ({wheel.name}; {len(required)} required assets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
