#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
exec env PYTHONPATH=src python3 -m civic_workbench --host 127.0.0.1 --port 8765 "$@"
