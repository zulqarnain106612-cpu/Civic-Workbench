"""Durable, versioned session storage. Raw frame JSON is immutable after insert."""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .contracts import ContractViolation, validate_record

SOFTWARE_VERSION = "0.4.0"
BUNDLE_FORMAT = "civic-workbench-export-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def uuid_text() -> str:
    return str(uuid4())


class StorageError(RuntimeError):
    pass


class NotFound(StorageError):
    pass


class Conflict(StorageError):
    pass


class SessionStore:
    """Thread-safe SQLite repository with atomic schema-v1 imports and exports."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.raw_dir = self.data_dir / "raw"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "civic-workbench.sqlite3"
        self._lock = threading.RLock()
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @contextmanager
    def _db(self):
        connection = self._connect()
        try:
            # Preserve sqlite3's normal commit/rollback semantics while ensuring
            # the connection is always released after the operation.
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._lock, self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    manifest_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS frames (
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    frame_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(session_id, sequence),
                    UNIQUE(session_id, frame_id)
                );
                CREATE INDEX IF NOT EXISTS frames_identifier_idx
                    ON frames(session_id, json_extract(record_json, '$.arbitration_id'));
                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    record_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tx_audit (
                    audit_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    session_id TEXT,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    level TEXT NOT NULL,
                    code TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS diagnostic_capabilities (
                    capability_id TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS parameter_mappings (
                    mapping_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    record_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    UNIQUE(session_id, name, version)
                );
                CREATE TABLE IF NOT EXISTS scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
            """)

    def log_event(self, level: str, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        with self._lock, self._db() as db:
            db.execute(
                "INSERT INTO events(created_at_utc,level,code,message,details_json) VALUES(?,?,?,?,?)",
                (utc_now(), level.upper(), code, message[:2000], json.dumps(details or {}, sort_keys=True)),
            )

    def list_events(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock, self._db() as db:
            rows = db.execute(
                "SELECT * FROM events ORDER BY event_sequence DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"sequence": r["event_sequence"], "created_at_utc": r["created_at_utc"],
             "level": r["level"], "code": r["code"], "message": r["message"],
             "details": json.loads(r["details_json"])}
            for r in reversed(rows)
        ]

    def create_session(
        self,
        capture_source: str = "simulator",
        bitrate_bps: int | None = None,
        identifier_filter: list[int] | None = None,
        notes: str = "",
        session_id: str | None = None,
        mode: str | None = None,
        started_at_utc: str | None = None,
        firmware_version: str | None = None,
        device_id: str | None = None,
        hardware_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if capture_source not in {"hardware", "simulator", "import"}:
            raise ContractViolation("unsupported capture_source")
        if bitrate_bps is not None and (not isinstance(bitrate_bps, int) or bitrate_bps <= 0):
            raise ContractViolation("bitrate_bps must be a positive integer or null")
        sid = session_id or uuid_text()
        now = utc_now()
        start_time = started_at_utc or now
        manifest = {
            "schema_version": 1,
            "record_type": "capture_session",
            "session_id": sid,
            "created_at_utc": now,
            "started_at_utc": start_time,
            "ended_at_utc": None,
            "capture_source": capture_source,
            "software_version": SOFTWARE_VERSION,
            "firmware_version": firmware_version,
            "device_id": device_id,
            "hardware_profile": hardware_profile,
            "capture_config": {
                "mode": mode or ("simulated" if capture_source == "simulator" else "listen_only" if capture_source == "hardware" else "imported"),
                "bitrate_bps": bitrate_bps,
                "identifier_filter": sorted(set(identifier_filter or [])),
                "notes": notes[:2000],
            },
            "record_count": 0,
            "dropped_frame_count": 0,
            "raw_capture": {
                "relative_path": f"raw/{sid}.jsonl",
                "format": "jsonl",
                "sha256": None,
                "bytes": None,
            },
            "annotation_refs": [],
            "user_notes": notes[:10000],
        }
        validate_record("capture-session", manifest)
        with self._lock, self._db() as db:
            try:
                db.execute(
                    "INSERT INTO sessions(session_id,manifest_json,created_at_utc) VALUES(?,?,?)",
                    (sid, json.dumps(manifest, sort_keys=True), now),
                )
            except sqlite3.IntegrityError as exc:
                raise Conflict(f"session {sid} already exists") from exc
        self.log_event("INFO", "session.created", f"Created {capture_source} session", {"session_id": sid})
        return manifest

    def ensure_external_session(self, session_id: str, capture_source: str, bitrate_bps: int | None = None,
                                firmware_version: str | None = None, device_id: str | None = None,
                                started_at_utc: str | None = None) -> dict[str, Any]:
        try:
            return self.get_session(session_id)
        except NotFound:
            return self.create_session(
                capture_source=capture_source,
                bitrate_bps=bitrate_bps,
                session_id=session_id,
                started_at_utc=started_at_utc,
                firmware_version=firmware_version,
                device_id=device_id,
                notes="Session manifest synthesized from incoming firmware provenance; host did not command ECU behavior.",
            )

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._lock, self._db() as db:
            row = db.execute(
                "SELECT manifest_json FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if row is None:
            raise NotFound(f"session not found: {session_id}")
        return json.loads(row["manifest_json"])

    def _write_raw_jsonl(self, session_id: str) -> tuple[str, int]:
        digest = hashlib.sha256()
        length = 0
        temp_path = self.raw_dir / f".{session_id}.jsonl.tmp"
        target = self.raw_dir / f"{session_id}.jsonl"
        with self._lock, self._connect() as db, temp_path.open("wb") as output:
            rows = db.execute(
                "SELECT record_json FROM frames WHERE session_id=? ORDER BY sequence", (session_id,)
            ).fetchall()
            for row in rows:
                line = row["record_json"].encode("utf-8") + b"\n"
                output.write(line)
                digest.update(line)
                length += len(line)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, target)
        return digest.hexdigest(), length

    def finish_session(self, session_id: str, user_notes: str | None = None) -> dict[str, Any]:
        manifest = self.get_session(session_id)
        if manifest["ended_at_utc"] is None:
            manifest["ended_at_utc"] = utc_now()
        if user_notes is not None:
            manifest["user_notes"] = user_notes[:10000]
        with self._lock, self._db() as db:
            row = db.execute(
                "SELECT COUNT(*) AS n FROM frames WHERE session_id=?", (session_id,)
            ).fetchone()
            manifest["record_count"] = int(row["n"])
            db.execute(
                "UPDATE sessions SET manifest_json=? WHERE session_id=?",
                (json.dumps(manifest, sort_keys=True), session_id),
            )
        digest, byte_count = self._write_raw_jsonl(session_id)
        manifest["raw_capture"]["sha256"] = digest
        manifest["raw_capture"]["bytes"] = byte_count
        with self._lock, self._db() as db:
            db.execute(
                "UPDATE sessions SET manifest_json=? WHERE session_id=?",
                (json.dumps(manifest, sort_keys=True), session_id),
            )
        self.log_event("INFO", "session.finished", "Finalized raw capture", {"session_id": session_id, "records": manifest["record_count"], "sha256": digest})
        return manifest

    def add_frame(self, frame: dict[str, Any]) -> int:
        validate_record("can-frame", frame)
        sid = frame["session_id"]
        with self._lock, self._db() as db:
            session_row = db.execute(
                "SELECT manifest_json FROM sessions WHERE session_id=?", (sid,)
            ).fetchone()
            if session_row is None:
                raise NotFound(f"session not found for frame: {sid}")
            manifest = json.loads(session_row["manifest_json"])
            if manifest["ended_at_utc"] is not None:
                raise Conflict("cannot append frames to a finalized session")
            last = db.execute(
                "SELECT COALESCE(MAX(sequence),-1) AS n FROM frames WHERE session_id=?", (sid,)
            ).fetchone()["n"]
            sequence = int(last) + 1
            try:
                db.execute(
                    "INSERT INTO frames(session_id,sequence,frame_id,record_json) VALUES(?,?,?,?)",
                    (sid, sequence, frame["frame_id"], json.dumps(frame, sort_keys=True, separators=(",", ":"))),
                )
            except sqlite3.IntegrityError as exc:
                raise Conflict(f"frame_id already exists: {frame['frame_id']}") from exc
            manifest["record_count"] = sequence + 1
            manifest["dropped_frame_count"] = max(
                int(manifest.get("dropped_frame_count", 0)),
                int(frame.get("dropped_frames_after", 0)),
            )
            db.execute(
                "UPDATE sessions SET manifest_json=? WHERE session_id=?",
                (json.dumps(manifest, sort_keys=True), sid),
            )
            return sequence

    def add_frames(self, frames: list[dict[str, Any]]) -> list[int]:
        if not frames:
            return []
        for frame in frames:
            validate_record("can-frame", frame)
        session_ids = {frame["session_id"] for frame in frames}
        if len(session_ids) != 1:
            raise ContractViolation("batch append may contain exactly one session_id")
        sid = next(iter(session_ids))
        with self._lock, self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT manifest_json FROM sessions WHERE session_id=?", (sid,)).fetchone()
                if row is None:
                    raise NotFound(f"session not found for batch: {sid}")
                manifest = json.loads(row["manifest_json"])
                if manifest["ended_at_utc"] is not None:
                    raise Conflict("cannot append frames to a finalized session")
                last = db.execute("SELECT COALESCE(MAX(sequence),-1) AS n FROM frames WHERE session_id=?", (sid,)).fetchone()["n"]
                sequences = []
                for offset, frame in enumerate(frames, start=1):
                    sequence = int(last) + offset
                    db.execute(
                        "INSERT INTO frames(session_id,sequence,frame_id,record_json) VALUES(?,?,?,?)",
                        (sid, sequence, frame["frame_id"], json.dumps(frame, sort_keys=True, separators=(",", ":"))),
                    )
                    sequences.append(sequence)
                manifest["record_count"] = int(last) + len(frames) + 1
                manifest["dropped_frame_count"] = max(
                    int(manifest.get("dropped_frame_count", 0)),
                    max(int(frame.get("dropped_frames_after", 0)) for frame in frames),
                )
                db.execute("UPDATE sessions SET manifest_json=? WHERE session_id=?", (json.dumps(manifest, sort_keys=True), sid))
                db.execute("COMMIT")
                return sequences
            except Exception:
                db.execute("ROLLBACK")
                raise

    def list_frames(self, session_id: str, limit: int = 500, after_sequence: int = -1) -> dict[str, Any]:
        if not self.session_exists(session_id):
            raise NotFound(f"session not found: {session_id}")
        limit = max(1, min(int(limit), 5000))
        after_sequence = max(-1, int(after_sequence))
        with self._lock, self._db() as db:
            rows = db.execute(
                "SELECT sequence,record_json FROM frames WHERE session_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (session_id, after_sequence, limit + 1),
            ).fetchall()
        items = [{"sequence": r["sequence"], "frame": json.loads(r["record_json"])} for r in rows[:limit]]
        next_sequence = rows[limit - 1]["sequence"] if len(rows) > limit else None
        return {"schema_version": 1, "items": items, "next_sequence": next_sequence}

    def get_all_frames(self, session_id: str) -> list[dict[str, Any]]:
        if not self.session_exists(session_id):
            raise NotFound(f"session not found: {session_id}")
        with self._lock, self._db() as db:
            rows = db.execute(
                "SELECT record_json FROM frames WHERE session_id=? ORDER BY sequence", (session_id,)
            ).fetchall()
        return [json.loads(r["record_json"]) for r in rows]

    def session_exists(self, session_id: str) -> bool:
        with self._lock, self._db() as db:
            return db.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone() is not None

    def list_sessions(self, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        import base64
        limit = max(1, min(int(limit), 500))
        offset = 0
        if cursor:
            try:
                offset = max(0, int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")))
            except Exception as exc:
                raise ContractViolation("invalid session cursor") from exc
        with self._lock, self._db() as db:
            rows = db.execute(
                "SELECT manifest_json FROM sessions ORDER BY created_at_utc DESC, session_id LIMIT ? OFFSET ?",
                (limit + 1, offset),
            ).fetchall()
        items = [json.loads(r["manifest_json"]) for r in rows[:limit]]
        more = len(rows) > limit
        next_cursor = base64.urlsafe_b64encode(str(offset + limit).encode("ascii")).decode("ascii") if more else None
        return {"schema_version": 1, "items": items, "next_cursor": next_cursor}

    def save_finding(self, session_id: str, finding: dict[str, Any]) -> dict[str, Any]:
        validate_record("analysis-finding", finding)
        with self._lock, self._db() as db:
            row = db.execute(
                "SELECT manifest_json FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"session not found: {session_id}")
            ids = {r["frame_id"] for r in db.execute(
                "SELECT frame_id FROM frames WHERE session_id=?", (session_id,)
            ).fetchall()}
            missing = set(finding["evidence_frame_ids"]) - ids
            if missing:
                raise ContractViolation(f"finding references frames outside this session: {sorted(missing)}")
            db.execute(
                "INSERT OR REPLACE INTO findings(finding_id,session_id,record_json,created_at_utc) VALUES(?,?,?,?)",
                (finding["finding_id"], session_id, json.dumps(finding, sort_keys=True), finding["created_at_utc"]),
            )
            manifest = json.loads(row["manifest_json"])
            refs = set(manifest.get("annotation_refs", []))
            refs.add(finding["finding_id"])
            manifest["annotation_refs"] = sorted(refs)
            db.execute(
                "UPDATE sessions SET manifest_json=? WHERE session_id=?",
                (json.dumps(manifest, sort_keys=True), session_id),
            )
        return finding

    def list_findings(self, session_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT record_json FROM findings"
        conditions: list[str] = []
        values: list[Any] = []
        if session_id:
            conditions.append("session_id=?")
            values.append(session_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at_utc"
        with self._lock, self._db() as db:
            rows = db.execute(query, values).fetchall()
        records = [json.loads(r["record_json"]) for r in rows]
        return [r for r in records if status is None or r["status"] == status]

    def export_bundle(self, session_id: str) -> dict[str, Any]:
        manifest = self.get_session(session_id)
        frames = self.get_all_frames(session_id)
        findings = self.list_findings(session_id=session_id)
        return {"format": BUNDLE_FORMAT, "schema_version": 1, "manifest": manifest, "frames": frames, "findings": findings}

    def import_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Validate a complete export bundle before creating a distinct local import session."""
        if not isinstance(bundle, dict) or bundle.get("format") != "civic-workbench-export-v1" or bundle.get("schema_version") != 1:
            raise ContractViolation("unsupported session export bundle format/version")
        source_manifest = bundle.get("manifest")
        frames = bundle.get("frames")
        findings = bundle.get("findings", [])
        if not isinstance(source_manifest, dict) or not isinstance(frames, list) or not isinstance(findings, list):
            raise ContractViolation("bundle must contain manifest, frames array, and findings array")
        validate_record("capture-session", source_manifest)
        if len(frames) > 2000000:
            raise ContractViolation("bundle exceeds the 2,000,000-frame import limit")
        source_id = source_manifest.get("session_id")
        if not source_id:
            raise ContractViolation("bundle manifest has no session UUID")

        frame_ids: set[str] = set()
        for frame in frames:
            validate_record("can-frame", frame)
            if frame.get("session_id") != source_id:
                raise ContractViolation("all source frames must match the bundle manifest session UUID")
            if frame["frame_id"] in frame_ids:
                raise ContractViolation("bundle contains duplicate raw frame UUIDs")
            frame_ids.add(frame["frame_id"])

        for finding in findings:
            validate_record("analysis-finding", finding)
            if not set(finding.get("evidence_frame_ids", [])) <= frame_ids:
                raise ContractViolation("finding references a frame absent from the exported bundle")

        bitrate = source_manifest.get("capture_config", {}).get("bitrate_bps")
        notes = str(source_manifest.get("user_notes", "Imported version-1 bundle"))[:2000]
        # Do not reuse an external database path or checksum. A new local session and raw
        # JSONL artifact are generated; each frame's raw fields/source label otherwise stays intact.
        self.create_session(
            capture_source="import",
            bitrate_bps=bitrate,
            session_id=source_id,
            mode=None,
            notes=notes,
        )
        try:
            self.add_frames(frames)
            for finding in findings:
                imported_finding = dict(finding)
                source_finding_id = imported_finding["finding_id"]
                # Finding IDs are primary keys in this store. Importing a bundle back
                # beside its source session must not collide with the source annotation.
                imported_finding["finding_id"] = str(uuid4())
                annotations = dict(imported_finding.get("annotations") or {})
                annotations["imported_from_finding_id"] = source_finding_id
                imported_finding["annotations"] = annotations
                self.save_finding(source_id, imported_finding)
            imported = self.finish_session(source_id, notes)
            imported["imported_from"] = {
                "bundle_format": bundle["format"],
                "source_capture_source": source_manifest.get("capture_source"),
                "source_created_at_utc": source_manifest.get("created_at_utc"),
            }
            self.log_event("INFO", "session.bundle_imported", "Imported validated session bundle into local storage",
                           {"session_id": source_id, "raw_frame_count": len(frames), "finding_count": len(findings)})
            return imported
        except Exception:
            # Best-effort cleanup so any post-validation failure does not leave a partial session.
            with self._lock, self._db() as db:
                db.execute("DELETE FROM sessions WHERE session_id=?", (source_id,))
            raw_path = self.data_dir / "raw" / f"{source_id}.jsonl"
            raw_path.unlink(missing_ok=True)
            raise


    def add_tx_audit(self, request_id: str, session_id: str | None, target: str, status: str,
                     event: dict[str, Any]) -> dict[str, Any]:
        audit_id = uuid_text()
        now = utc_now()
        with self._lock, self._db() as db:
            db.execute(
                "INSERT INTO tx_audit(audit_id,request_id,session_id,target,status,event_json,created_at_utc) VALUES(?,?,?,?,?,?,?)",
                (audit_id, request_id, session_id, target, status, json.dumps(event, sort_keys=True), now),
            )
        self.log_event("INFO" if status not in {"rejected", "failed"} else "WARNING",
                       "tx." + status, "TX audit event: " + status,
                       {"audit_id": audit_id, "request_id": request_id, "target": target})
        return {"audit_id": audit_id, "request_id": request_id, "session_id": session_id,
                "target": target, "status": status, "created_at_utc": now, "event": event}

    def list_tx_audit(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock, self._db() as db:
            rows = db.execute("SELECT * FROM tx_audit ORDER BY created_at_utc DESC LIMIT ?", (limit,)).fetchall()
        return [{"audit_id": r["audit_id"], "request_id": r["request_id"], "session_id": r["session_id"],
                 "target": r["target"], "status": r["status"], "created_at_utc": r["created_at_utc"],
                 "event": json.loads(r["event_json"])} for r in rows]

    def save_scenario(self, scenario_id: str, record: dict[str, Any]) -> None:
        with self._lock, self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO scenarios(scenario_id,record_json,created_at_utc) VALUES(?,?,?)",
                (scenario_id, json.dumps(record, sort_keys=True), utc_now()),
            )

    def list_scenarios(self) -> list[dict[str, Any]]:
        with self._lock, self._db() as db:
            rows = db.execute("SELECT record_json FROM scenarios ORDER BY created_at_utc DESC").fetchall()
        return [json.loads(r["record_json"]) for r in rows]

    def save_diagnostic_capability(self, record: dict[str, Any]) -> None:
        validate_record("diagnostic-capability", record)
        if record["status"] != "supported" and record["enabled"]:
            raise ContractViolation("unknown or unsupported diagnostic capabilities must remain disabled")
        with self._lock, self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO diagnostic_capabilities(capability_id,record_json) VALUES(?,?)",
                (record["capability_id"], json.dumps(record, sort_keys=True)),
            )
        self.log_event("INFO", "diagnostic.capability_saved", "Saved capability status/annotation; this does not execute a diagnostic operation",
                       {"capability_id": record["capability_id"], "status": record["status"], "enabled": record["enabled"]})

    def get_diagnostic_capabilities(self) -> list[dict[str, Any]]:
        with self._lock, self._db() as db:
            rows = db.execute("SELECT record_json FROM diagnostic_capabilities ORDER BY capability_id").fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def save_parameter_mapping(
        self,
        session_id: str,
        definition: dict[str, Any],
        evidence_frame_ids: list[str],
        method: str,
    ) -> dict[str, Any]:
        if not self.session_exists(session_id):
            raise NotFound(f"session not found: {session_id}")
        name = str(definition.get("name", "")).strip()
        if not name or not evidence_frame_ids:
            raise ContractViolation("mapping name and evidence frame IDs are required")
        with self._lock, self._db() as db:
            existing_ids = {row["frame_id"] for row in db.execute(
                "SELECT frame_id FROM frames WHERE session_id=?", (session_id,)
            ).fetchall()}
            if not set(evidence_frame_ids).issubset(existing_ids):
                raise ContractViolation("mapping evidence must reference frames in its session")
            row = db.execute(
                "SELECT COALESCE(MAX(version),0) AS version FROM parameter_mappings WHERE session_id=? AND name=?",
                (session_id, name),
            ).fetchone()
            version = int(row["version"]) + 1
            record = {
                "schema_version": 1, "record_type": "parameter_mapping",
                "mapping_id": str(uuid4()), "session_id": session_id,
                "created_at_utc": utc_now(), "name": name, "version": version,
                "definition": {key: value for key, value in definition.items() if key != "name"},
                "status": "candidate", "evidence_frame_ids": list(dict.fromkeys(evidence_frame_ids)),
                "method": method[:1000],
            }
            validate_record("parameter-mapping", record)
            db.execute(
                "INSERT INTO parameter_mappings(mapping_id,session_id,name,version,record_json,created_at_utc) VALUES(?,?,?,?,?,?)",
                (record["mapping_id"], session_id, name, version, json.dumps(record, sort_keys=True), record["created_at_utc"]),
            )
        self.log_event("INFO", "analysis.mapping_version_saved", "Saved new candidate parameter-mapping version",
                       {"session_id": session_id, "name": name, "version": version, "mapping_id": record["mapping_id"]})
        return record

    def list_parameter_mappings(self, session_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock, self._db() as db:
            if session_id:
                rows = db.execute(
                    "SELECT record_json FROM parameter_mappings WHERE session_id=? ORDER BY name,version",
                    (session_id,),
                ).fetchall()
            else:
                rows = db.execute("SELECT record_json FROM parameter_mappings ORDER BY created_at_utc,name,version").fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def validate_parameter_mapping(
        self,
        mapping_id: str,
        validation_method: str,
        evidence_refs: list[str],
        reviewer: str | None = None,
    ) -> dict[str, Any]:
        if not validation_method.strip() or not evidence_refs or any(not str(ref).strip() for ref in evidence_refs):
            raise ContractViolation("independent validation requires a method and evidence references")
        with self._lock, self._db() as db:
            row = db.execute(
                "SELECT record_json,session_id FROM parameter_mappings WHERE mapping_id=?",
                (mapping_id,),
            ).fetchone()
            if row is None:
                raise NotFound("parameter mapping not found")
            record = json.loads(row["record_json"])
            record["status"] = "validated"
            record["validation"] = {
                "validation_method": validation_method.strip()[:1000],
                "validated_at_utc": utc_now(),
                "reviewer": reviewer,
                "evidence_refs": list(dict.fromkeys(str(ref) for ref in evidence_refs)),
            }
            validate_record("parameter-mapping", record)
            db.execute(
                "UPDATE parameter_mappings SET record_json=? WHERE mapping_id=?",
                (json.dumps(record, sort_keys=True), mapping_id),
            )
        self.log_event("WARNING", "analysis.mapping_validated_by_operator",
                       "Mapping promoted only after operator supplied independent evidence",
                       {"mapping_id": mapping_id, "reviewer": reviewer})
        return record
