"""Read-only CW1 firmware serial bridge. It never sends bytes to firmware."""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from .contracts import ContractViolation, validate_record
from .storage import SessionStore, NotFound, Conflict, utc_now


class SerialBridge:
    def __init__(self, store: SessionStore):
        self.store = store
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._serial = None
        self._lock = threading.RLock()
        self._port: str | None = None
        self._baudrate: int | None = None
        self._opened_monotonic: float | None = None
        self._last_record_monotonic: float | None = None
        self._status: dict[str, Any] = {
            "connected": False, "port": None, "baudrate": None, "last_record_at_utc": None,
            "firmware_version": None, "controller_state": "unknown", "bitrate_bps": None,
            "session_id": None, "faults": ["serial_bridge_not_connected"], "frames_received": 0,
            "bytes_received": 0, "malformed_records": 0,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._status))

    def start(self, port: str, baudrate: int = 115200) -> dict[str, Any]:
        if not port or len(port) > 256:
            raise ContractViolation("serial port is required")
        if not 1200 <= int(baudrate) <= 2_000_000:
            raise ContractViolation("baudrate must be between 1200 and 2000000")
        if self._thread and self._thread.is_alive():
            raise Conflict("serial bridge is already running")
        try:
            import serial
            connection = serial.Serial(port=port, baudrate=int(baudrate), timeout=0.5, write_timeout=0.5)
        except ImportError as exc:
            raise ContractViolation("pyserial is not installed in the host service environment") from exc
        except Exception as exc:
            raise ContractViolation(f"could not open serial port: {exc}") from exc
        self._serial = connection
        self._port = port
        self._baudrate = int(baudrate)
        self._stop.clear()
        self._opened_monotonic = time.monotonic()
        self._last_record_monotonic = None
        with self._lock:
            self._status.update({"connected": True, "port": port, "baudrate": int(baudrate),
                                 "last_record_at_utc": None, "faults": []})
        self._thread = threading.Thread(target=self._read_loop, name="civic-serial-rx", daemon=True)
        self._thread.start()
        self.store.log_event("INFO", "serial.connected", "Opened read-only CW1 serial stream",
                             {"port": port, "baudrate": int(baudrate)})
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        try:
            if self._serial is not None:
                self._serial.close()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=2)
        with self._lock:
            self._status["connected"] = False
            self._status["faults"] = sorted(set(self._status.get("faults", []) + ["serial_bridge_stopped"]))
        self.store.log_event("INFO", "serial.disconnected", "Stopped read-only serial bridge", {})
        return self.status()

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                line = self._serial.readline()
                if not line:
                    reference = self._last_record_monotonic or self._opened_monotonic
                    if reference is not None and time.monotonic() - reference > 5.0:
                        with self._lock:
                            self._status["connected"] = False
                            self._status["faults"] = sorted(set(self._status.get("faults", []) + ["serial_stream_stale"]))
                    continue
                with self._lock:
                    self._status["bytes_received"] += len(line)
                if len(line) > 4096:
                    with self._lock:
                        self._status["malformed_records"] += 1
                        self._status["faults"] = sorted(set(self._status.get("faults", []) + ["oversized_serial_line"]))
                    continue
                text = line.decode("utf-8", "replace").strip()
                if not text.startswith("CW1 "):
                    continue
                try:
                    record = json.loads(text[4:])
                    self.consume(record)
                except Exception as exc:
                    with self._lock:
                        self._status["malformed_records"] += 1
                        self._status["faults"] = sorted(set(self._status.get("faults", []) + ["malformed_cw1_record"]))
                    self.store.log_event("WARNING", "serial.record_invalid", "Rejected invalid CW1 record",
                                         {"error": str(exc)[:500]})
            except Exception as exc:
                if not self._stop.is_set():
                    with self._lock:
                        self._status["connected"] = False
                        self._status["faults"] = sorted(set(self._status.get("faults", []) + ["serial_read_error"]))
                    self.store.log_event("ERROR", "serial.read_error", "Serial read failed", {"error": str(exc)[:500]})
                break

    def consume(self, record: dict[str, Any]) -> None:
        kind = record.get("record_type")
        if kind == "handshake":
            validate_record("handshake", record)
            with self._lock:
                self._status["firmware_version"] = record["software_version"]
        elif kind == "device_status":
            validate_record("device-status", record)
            with self._lock:
                self._status["controller_state"] = record["controller_state"]
                self._status["bitrate_bps"] = record["bitrate_bps"]
                self._status["faults"] = list(record["faults"])
                self._status["last_device_status"] = record
                self._status["connected"] = True
        elif kind == "can_frame":
            validate_record("can-frame", record)
            sid = record["session_id"]
            self.store.ensure_external_session(
                sid, "hardware", bitrate_bps=self._status.get("bitrate_bps"),
                firmware_version=self._status.get("firmware_version"),
                device_id=record.get("device_id"), started_at_utc=record.get("captured_at_utc"),
            )
            # The firmware frame object is stored byte-for-byte as a JSON object: provenance remains intact.
            self.store.add_frame(record)
            with self._lock:
                self._status["session_id"] = sid
                self._status["frames_received"] += 1
        else:
            raise ContractViolation("unsupported CW1 record type")
        with self._lock:
            self._last_record_monotonic = time.monotonic()
            self._status["last_record_at_utc"] = utc_now()
            self._status["faults"] = [code for code in self._status.get("faults", []) if code != "serial_stream_stale"]
