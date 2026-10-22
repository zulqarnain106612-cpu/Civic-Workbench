# Setup, Build and Run

## Requirements

- Python 3.10 or newer; the current verified host used Python 3.14.
- A local operating system that supports SQLite and the standard library HTTP server.
- For CW1 firmware ingestion, pySerial and a serial device/driver. A serial port is optional for simulation.
- For ESP32 compile verification, the pinned PlatformIO environment described in firmware/esp32/README.md.
- Proteus is optional for host application tests. Native Proteus generation is an explicitly documented open item.

## Install and launch

From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
civic-workbench --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765/ in the same machine/browser. The unauthenticated server refuses non-loopback binding. Do not reverse-proxy it to a network or expose the port.

If running directly from a source checkout without installing the package:

```sh
PYTHONPATH=src python3 -m civic_workbench --host 127.0.0.1 --port 8765
```

Persistent data defaults to ~/.local/share/civic-workbench. Set CIVIC_WORKBENCH_DATA_DIR to choose a different local directory. Never place the SQLite database on a concurrently shared network filesystem without separately validating SQLite locking semantics.

## Use the synthetic workbench

1. Select Start simulated capture.
2. Advance virtual time to emit tagged synthetic frames.
3. Filter the frame table, inspect raw records, and run analysis.
4. Save explicit parameter definitions with frame UUID evidence; they begin as candidate.
5. Supply independent method/evidence references only after real independent review to change a mapping’s status.
6. Exercise simulation TX scheduling, repeat limits, cancellation and the TX audit.
7. Export a portable JSON bundle and test import into a different data directory.

All simulator nodes/frames are synthetic. Their identifier numbers do not imply Civic or Honda ECU identifiers.

## Firmware serial ingestion

The firmware stream is CW1-prefixed JSON. Use Device / Firmware to open an existing port. This path reads only; it does not command the firmware. Port access may require OS serial-group permissions. Hardware status is not live unless valid firmware records arrive.

## Verification commands

```sh
make test
python3 -m compileall -q src tests
git diff --check
python3 tools/generate_proteus_reference.py
python3 tools/benchmark.py --frames 20000
```

ESP32 compile-only build with the pinned environment:

```sh
cd firmware/esp32
~/.venvs/civic-workbench-pio/bin/pio run
```

The exact source target is ESP32S NodeMCU / NodeMCU-32S with the fixed NXP TJA1051T/3 SO8 transceiver; PlatformIO uses the nodemcu-32s board profile, GPIO21/TWAI_TX and GPIO22/TWAI_RX. Do not flash or attach to a vehicle until physical board revision/header continuity, IC pin-1 orientation, supply/decoupling, Silent-mode bias, controlled bench setup, and independent bitrate evidence are reviewed. Runtime initialization and physical TX remain disabled. Build success is not hardware validation.
