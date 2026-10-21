"""Schema and semantic contract tests for S01; runs with Python unittest."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from civic_workbench.contracts import (  # noqa: E402
    ContractViolation,
    ENVELOPE_PAYLOAD_SCHEMAS,
    SCHEMA_DIR,
    SCHEMA_FILES,
    authorize_transmission,
    validate_record,
)


SESSION_ID = "11111111-1111-4111-8111-111111111111"
FRAME_ID = "22222222-2222-4222-8222-222222222222"
FINDING_ID = "33333333-3333-4333-8333-333333333333"
CAPABILITY_ID = "44444444-4444-4444-8444-444444444444"
REQUEST_ID = "55555555-5555-4555-8555-555555555555"
MESSAGE_ID = "66666666-6666-4666-8666-666666666666"
NOW = "2026-10-22T00:00:00Z"


def frame(**changes):
    record = {
        "schema_version": 1,
        "record_type": "can_frame",
        "frame_id": FRAME_ID,
        "session_id": SESSION_ID,
        "captured_monotonic_ns": 123456,
        "captured_at_utc": NOW,
        "clock_source": "monotonic_and_wall_clock",
        "arbitration_id": 291,
        "id_format": "standard",
        "frame_type": "data",
        "dlc": 2,
        "payload": [18, 52],
        "direction": "rx",
        "capture_source": "simulator",
        "controller_state": "running",
    }
    record.update(changes)
    return record


def session(**changes):
    record = {
        "schema_version": 1,
        "record_type": "capture_session",
        "session_id": SESSION_ID,
        "created_at_utc": NOW,
        "started_at_utc": NOW,
        "ended_at_utc": None,
        "capture_source": "simulator",
        "software_version": "0.1.0",
        "firmware_version": None,
        "device_id": None,
        "hardware_profile": None,
        "capture_config": {
            "mode": "simulated",
            "bitrate_bps": None,
            "identifier_filter": [],
            "notes": "Deterministic contract fixture; not a vehicle capture.",
        },
        "record_count": 1,
        "dropped_frame_count": 0,
        "raw_capture": {
            "relative_path": "sessions/example/frames.jsonl",
            "format": "jsonl",
            "sha256": None,
            "bytes": None,
        },
        "annotation_refs": [],
        "user_notes": "Synthetic test data.",
    }
    record.update(changes)
    return record


def finding(**changes):
    record = {
        "schema_version": 1,
        "record_type": "analysis_finding",
        "finding_id": FINDING_ID,
        "created_at_utc": NOW,
        "finding_kind": "signal_candidate",
        "status": "candidate",
        "summary": "Payload bits changed in the supplied synthetic trace.",
        "evidence_frame_ids": [FRAME_ID],
        "method": "bit-change frequency",
        "confidence": 0.65,
        "arbitration_id": 291,
        "id_format": "standard",
        "candidate_signal": {
            "start_bit": 0,
            "bit_length": 8,
            "byte_order": "unknown",
            "signed": None,
            "scale": None,
            "offset": None,
            "unit": None,
        },
    }
    record.update(changes)
    return record


def diagnostic(**changes):
    record = {
        "schema_version": 1,
        "record_type": "diagnostic_capability",
        "capability_id": CAPABILITY_ID,
        "status": "unknown",
        "enabled": False,
        "protocol": "unknown",
        "operation": "not established",
        "ecu_label": None,
        "addressing": None,
        "supporting_evidence": [],
        "reviewed_at_utc": None,
    }
    record.update(changes)
    return record


def tx_request(**changes):
    record = {
        "schema_version": 1,
        "record_type": "tx_request",
        "request_id": REQUEST_ID,
        "created_at_utc": NOW,
        "arbitration_id": 291,
        "id_format": "standard",
        "frame_type": "data",
        "dlc": 2,
        "payload": [18, 52],
        "period_ms": 100,
        "repeat_count": 1,
        "timeout_ms": 1000,
        "requested_by": "contract-test",
        "operator_note": "Synthetic request only; not transmitted.",
    }
    record.update(changes)
    return record


def safety_state(**changes):
    record = {
        "schema_version": 1,
        "record_type": "safety_state",
        "observed_at_utc": NOW,
        "mode": "listen_only",
        "software_armed": False,
        "hardware_interlock_active": False,
        "tx_permitted": False,
        "controller_state": "running",
        "faults": [],
        "state_age_ms": 0,
        "source": "firmware",
        "inhibit_reasons": ["default passive state"],
        "arm_expires_at_utc": None,
    }
    record.update(changes)
    return record


class JsonSchemaTests(unittest.TestCase):
    def test_every_schema_is_draft_2020_12_and_valid(self):
        self.assertGreaterEqual(len(SCHEMA_FILES), 14)
        for schema_name, filename in SCHEMA_FILES.items():
            with self.subTest(schema=schema_name):
                schema = json.loads((SCHEMA_DIR / filename).read_text())
                self.assertEqual(
                    schema["$schema"],
                    "https://json-schema.org/draft/2020-12/schema",
                )
                Draft202012Validator.check_schema(schema)

    def test_all_yaml_project_contracts_parse(self):
        for path in [ROOT / "project" / "requirements.yaml",
                     ROOT / "project" / "dependencies.yaml",
                     ROOT / "project" / "stages.yaml",
                     ROOT / "project" / "hardware.yaml",
                     ROOT / "project" / "constraints.yaml",
                     ROOT / "project" / "environment.yaml",
                     ROOT / "tests" / "requirements-traceability.yaml",
                     ROOT / "hardware" / "reference" / "esp32-tja1051t3-netlist.yaml"]:
            with self.subTest(path=path.relative_to(ROOT)):
                yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_json_schemas_accept_valid_samples(self):
        samples = {
            "can-frame": frame(),
            "capture-session": session(),
            "analysis-finding": finding(),
            "diagnostic-capability": diagnostic(),
            "tx-request": tx_request(),
            "safety-state": safety_state(),
            "handshake": {
                "schema_version": 1,
                "record_type": "handshake",
                "agent_role": "simulator",
                "agent_id": "test-simulator",
                "software_version": "0.1.0",
                "supported_schema_versions": {"can_frame": [1], "tx_request": [1]},
                "supported_message_types": ["hello", "hello_ack", "can_frame"],
            },
            "device-status": {
                "schema_version": 1,
                "record_type": "device_status",
                "observed_at_utc": NOW,
                "connected": False,
                "controller_state": "stopped",
                "firmware_version": None,
                "bitrate_bps": None,
                "dropped_frames_total": 0,
                "faults": [],
            },
            "capture-start": {
                "schema_version": 1,
                "record_type": "capture_start",
                "request_id": REQUEST_ID,
                "requested_at_utc": NOW,
                "mode": "simulated",
                "bitrate_bps": None,
                "identifier_filter": [],
                "notes": "Synthetic contract fixture.",
            },
            "capture-stop": {
                "schema_version": 1,
                "record_type": "capture_stop",
                "request_id": REQUEST_ID,
                "session_id": SESSION_ID,
                "requested_at_utc": NOW,
                "requested_by": "contract-test",
            },
            "tx-cancel": {
                "schema_version": 1,
                "record_type": "tx_cancel",
                "request_id": REQUEST_ID,
                "requested_at_utc": NOW,
                "requested_by": "contract-test",
            },
            "tx-result": {
                "schema_version": 1,
                "record_type": "tx_result",
                "request_id": REQUEST_ID,
                "completed_at_utc": NOW,
                "status": "queued",
                "frames_sent": 0,
                "error_code": None,
                "details": None,
            },
            "error-event": {
                "schema_version": 1,
                "record_type": "error",
                "code": "SYNTHETIC_TEST_ERROR",
                "message": "Synthetic contract fixture error.",
                "retryable": False,
                "correlation_id": MESSAGE_ID,
                "details": {},
            },
        }
        for schema_name, sample in samples.items():
            with self.subTest(schema=schema_name):
                validate_record(schema_name, sample)


class CanFrameContractTests(unittest.TestCase):
    def test_rejects_standard_identifier_outside_11_bits(self):
        with self.assertRaises(ContractViolation):
            validate_record("can-frame", frame(arbitration_id=0x800))

    def test_rejects_data_payload_length_that_disagrees_with_dlc(self):
        with self.assertRaisesRegex(ContractViolation, "payload length"):
            validate_record("can-frame", frame(dlc=3))

    def test_accepts_extended_29_bit_identifier(self):
        validate_record("can-frame", frame(
            arbitration_id=0x1ABCDEFF, id_format="extended"
        ))

    def test_rejects_identifier_outside_29_bits(self):
        with self.assertRaises(ContractViolation):
            validate_record("can-frame", frame(
                arbitration_id=0x20000000, id_format="extended"
            ))

    def test_remote_frame_has_dlc_but_no_payload_bytes(self):
        validate_record("can-frame", frame(frame_type="remote", dlc=8, payload=[]))
        with self.assertRaises(ContractViolation):
            validate_record("can-frame", frame(
                frame_type="remote", dlc=1, payload=[0]
            ))

    def test_raw_record_is_not_mutated(self):
        raw = frame()
        original = deepcopy(raw)
        result = validate_record("can-frame", raw)
        self.assertIs(result, raw)
        self.assertEqual(raw, original)


class TxRequestContractTests(unittest.TestCase):
    def test_rejects_tx_payload_length_that_disagrees_with_dlc(self):
        with self.assertRaisesRegex(ContractViolation, "payload length"):
            validate_record("tx-request", tx_request(dlc=3))

    def test_rejects_standard_tx_identifier_outside_11_bits(self):
        with self.assertRaises(ContractViolation):
            validate_record("tx-request", tx_request(arbitration_id=0x800))

    def test_tx_request_must_have_bounded_repeat_count(self):
        with self.assertRaises(ContractViolation):
            validate_record("tx-request", tx_request(repeat_count=1001))

    def test_tx_repeat_schedule_must_fit_timeout_budget(self):
        with self.assertRaisesRegex(ContractViolation, "exceeds the request timeout"):
            validate_record(
                "tx-request",
                tx_request(repeat_count=10, period_ms=100, timeout_ms=100),
            )


class SessionAndFindingContractTests(unittest.TestCase):
    def test_rejects_raw_capture_path_traversal(self):
        unsafe_capture = {
            "relative_path": "../../private/frames.jsonl",
            "format": "jsonl",
            "sha256": None,
            "bytes": None,
        }
        with self.assertRaisesRegex(ContractViolation, "safe POSIX relative path"):
            validate_record("capture-session", session(raw_capture=unsafe_capture))

    def test_rejects_session_end_before_start(self):
        with self.assertRaisesRegex(ContractViolation, "cannot precede"):
            validate_record("capture-session", session(
                ended_at_utc="2026-10-21T23:59:59Z"
            ))

    def test_rejects_unknown_extra_raw_frame_property(self):
        sample = frame()
        sample["decoded_speed_kph"] = 42
        with self.assertRaises(ContractViolation):
            validate_record("can-frame", sample)

    def test_candidate_finding_does_not_need_validation_claim(self):
        validate_record("analysis-finding", finding())

    def test_validated_finding_requires_independent_validation_evidence(self):
        with self.assertRaises(ContractViolation):
            validate_record("analysis-finding", finding(status="validated"))

    def test_validated_finding_with_evidence_passes(self):
        sample = finding(
            status="validated",
            validation={
                "validation_method": "independent reproducible check",
                "validated_at_utc": NOW,
                "reviewer": "test reviewer",
                "evidence_refs": ["tests/fixtures/independent-validation.json"],
            },
        )
        validate_record("analysis-finding", sample)

    def test_candidate_signal_must_fit_within_classical_can_payload(self):
        bad = finding(candidate_signal={
            "start_bit": 63,
            "bit_length": 8,
            "byte_order": "unknown",
            "signed": None,
            "scale": None,
            "offset": None,
            "unit": None,
        })
        with self.assertRaisesRegex(ContractViolation, "exceeds 64 bits"):
            validate_record("analysis-finding", bad)


class DiagnosticAndSafetyContractTests(unittest.TestCase):
    def test_unknown_diagnostic_capability_must_remain_disabled(self):
        validate_record("diagnostic-capability", diagnostic())
        with self.assertRaises(ContractViolation):
            validate_record("diagnostic-capability", diagnostic(enabled=True))

    def test_supported_diagnostic_requires_evidence(self):
        with self.assertRaises(ContractViolation):
            validate_record("diagnostic-capability", diagnostic(
                status="supported", enabled=True
            ))

    def test_evidence_backed_supported_diagnostic_is_valid_shape(self):
        validate_record("diagnostic-capability", diagnostic(
            status="supported",
            enabled=True,
            protocol="custom",
            operation="example operation documented by primary source",
            supporting_evidence=[{
                "kind": "official_document",
                "reference": "https://example.invalid/primary-source",
                "notes": "Synthetic contract fixture, not a Honda capability claim.",
            }],
        ))

    def test_default_safety_state_is_disarmed_and_denies_transmission(self):
        state = safety_state()
        validate_record("safety-state", state)
        with self.assertRaisesRegex(ContractViolation, "transmission denied"):
            authorize_transmission(tx_request(), state)

    def test_tx_permitted_requires_all_hardware_and_software_gates(self):
        unsafe = safety_state(
            mode="normal",
            software_armed=True,
            hardware_interlock_active=False,
            tx_permitted=True,
            inhibit_reasons=[],
        )
        with self.assertRaises(ContractViolation):
            validate_record("safety-state", unsafe)

    def test_tx_permitted_requires_no_faults(self):
        unsafe = safety_state(
            mode="normal",
            software_armed=True,
            hardware_interlock_active=True,
            tx_permitted=True,
            faults=["bus-off"],
            inhibit_reasons=[],
        )
        with self.assertRaises(ContractViolation):
            validate_record("safety-state", unsafe)

    def test_tx_permitted_requires_fresh_state(self):
        unsafe = safety_state(
            mode="normal",
            software_armed=True,
            hardware_interlock_active=True,
            tx_permitted=True,
            state_age_ms=501,
            inhibit_reasons=[],
        )
        with self.assertRaises(ContractViolation):
            validate_record("safety-state", unsafe)

    def test_fully_permissive_synthetic_state_passes_contract_gate(self):
        state = safety_state(
            mode="normal",
            software_armed=True,
            hardware_interlock_active=True,
            tx_permitted=True,
            faults=[],
            state_age_ms=10,
            inhibit_reasons=[],
            arm_expires_at_utc="2026-10-22T00:01:00Z",
        )
        validate_record("safety-state", state)
        authorize_transmission(tx_request(), state)

    def test_simulator_state_cannot_authorize_hardware_transmission(self):
        state = safety_state(
            mode="normal",
            software_armed=True,
            hardware_interlock_active=True,
            tx_permitted=True,
            faults=[],
            state_age_ms=10,
            source="simulator",
            inhibit_reasons=[],
        )
        with self.assertRaises(ContractViolation):
            validate_record("safety-state", state)
        with self.assertRaises(ContractViolation):
            authorize_transmission(tx_request(), state)

    def test_expired_arm_lease_is_rejected(self):
        state = safety_state(
            mode="normal",
            software_armed=True,
            hardware_interlock_active=True,
            tx_permitted=True,
            faults=[],
            state_age_ms=10,
            inhibit_reasons=[],
            arm_expires_at_utc="2026-10-21T23:59:00Z",
        )
        with self.assertRaisesRegex(ContractViolation, "expired"):
            validate_record("safety-state", state)


class TransportEnvelopeTests(unittest.TestCase):
    def envelope(self, message_type, payload):
        return {
            "schema_version": 1,
            "message_id": MESSAGE_ID,
            "message_type": message_type,
            "issued_at_utc": NOW,
            "sequence": 0,
            "sender": {"role": "simulator", "id": "contract-fixture"},
            "payload": payload,
        }

    def test_can_frame_event_payload_is_validated_recursively(self):
        validate_record(
            "transport-envelope",
            self.envelope("can_frame", frame()),
        )

    def test_can_frame_event_rejects_invalid_nested_payload(self):
        with self.assertRaises(ContractViolation):
            validate_record(
                "transport-envelope",
                self.envelope("can_frame", frame(dlc=7)),
            )

    def test_unknown_event_types_are_rejected(self):
        with self.assertRaises(ContractViolation):
            validate_record(
                "transport-envelope",
                self.envelope("surprise", {}),
            )


class ApiAndTraceabilityTests(unittest.TestCase):
    def test_openapi_contract_declares_required_api_boundaries(self):
        spec = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text())
        self.assertEqual(spec["openapi"], "3.1.0")
        required_paths = {
            "/api/v1/health",
            "/api/v1/capabilities",
            "/api/v1/safety/state",
            "/api/v1/capture/start",
            "/api/v1/capture/stop",
            "/api/v1/sessions",
            "/api/v1/sessions/{session_id}",
            "/api/v1/sessions/{session_id}/frames",
            "/api/v1/analysis/findings",
            "/api/v1/tx/requests",
            "/api/v1/tx/requests/{request_id}/cancel",
        }
        self.assertTrue(required_paths.issubset(set(spec["paths"])))

    def test_every_envelope_message_has_a_versioned_payload_contract(self):
        envelope = json.loads(
            (SCHEMA_DIR / SCHEMA_FILES["transport-envelope"]).read_text(encoding="utf-8")
        )
        declared_types = set(envelope["properties"]["message_type"]["enum"])
        self.assertEqual(declared_types, set(ENVELOPE_PAYLOAD_SCHEMAS))
        self.assertTrue(
            set(ENVELOPE_PAYLOAD_SCHEMAS.values()).issubset(set(SCHEMA_FILES))
        )

    def test_every_openapi_relative_schema_reference_exists(self):
        spec_path = ROOT / "contracts" / "openapi.yaml"
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        references = []

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "$ref" and isinstance(child, str):
                        references.append(child)
                    else:
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(spec)
        for ref in references:
            if ref.startswith("#/"):
                continue
            with self.subTest(ref=ref):
                self.assertTrue((spec_path.parent / ref).resolve().is_file())

    def test_requirement_traceability_covers_all_declared_requirements(self):
        requirements = yaml.safe_load(
            (ROOT / "project" / "requirements.yaml").read_text(encoding="utf-8")
        )["requirements"]
        trace = yaml.safe_load(
            (ROOT / "tests" / "requirements-traceability.yaml").read_text(encoding="utf-8")
        )["requirements"]
        expected = {entry["id"] for entry in requirements}
        self.assertEqual(expected, set(trace))

    def test_hardware_capture_requires_explicit_bitrate(self):
        capture_start = {
            "schema_version": 1,
            "record_type": "capture_start",
            "request_id": REQUEST_ID,
            "requested_at_utc": NOW,
            "mode": "listen_only",
            "bitrate_bps": None,
            "identifier_filter": [],
        }
        with self.assertRaises(ContractViolation):
            validate_record("capture-start", capture_start)

    def test_progress_ledger_records_verified_stage_state(self):
        progress = json.loads(
            (ROOT / "project" / "progress.json").read_text(encoding="utf-8")
        )
        self.assertEqual(progress["stage_status"]["S00"], "complete")
        self.assertEqual(progress["stage_status"]["S01"], "complete")
        self.assertEqual(progress["stage_status"]["S02"], "complete-source-and-build-foundation")
        self.assertEqual(progress["stage_status"]["S03"], "ready")
        self.assertEqual(progress["current_focus"], "S03")
        self.assertEqual(progress["s02_evidence"]["build_result"], "SUCCESS; exit code 0")
        self.assertEqual(progress["s01_evidence"]["test_result"], "42 tests passed")

    def test_stage_dependency_graph_is_complete_and_acyclic(self):
        dependencies = yaml.safe_load(
            (ROOT / "project" / "dependencies.yaml").read_text(encoding="utf-8")
        )["nodes"]
        stages = yaml.safe_load(
            (ROOT / "project" / "stages.yaml").read_text(encoding="utf-8")
        )["stages"]
        stage_ids = {item["id"] for item in stages}
        self.assertEqual(set(dependencies), stage_ids)
        for stage_id, node in dependencies.items():
            with self.subTest(stage=stage_id):
                self.assertTrue(set(node["depends_on"]).issubset(stage_ids))

        complete = set()
        visiting = set()

        def visit(stage_id):
            self.assertNotIn(stage_id, visiting, f"dependency cycle at {stage_id}")
            if stage_id in complete:
                return
            visiting.add(stage_id)
            for prerequisite in dependencies[stage_id]["depends_on"]:
                visit(prerequisite)
            visiting.remove(stage_id)
            complete.add(stage_id)

        for stage_id in dependencies:
            visit(stage_id)
        self.assertEqual(complete, stage_ids)

    def test_each_requirement_has_a_unique_id_and_acceptance_criterion(self):
        requirements = yaml.safe_load(
            (ROOT / "project" / "requirements.yaml").read_text(encoding="utf-8")
        )["requirements"]
        ids = [item["id"] for item in requirements]
        self.assertEqual(len(ids), len(set(ids)))
        for item in requirements:
            with self.subTest(requirement=item.get("id")):
                self.assertIn(item["priority"], {"MUST", "SHOULD"})
                self.assertTrue(item.get("acceptance", "").strip())

    def test_v1_control_envelope_schema_rejects_unknown_message_type(self):
        event = {
            "schema_version": 1,
            "message_id": MESSAGE_ID,
            "message_type": "not_a_real_event",
            "issued_at_utc": NOW,
            "sequence": 0,
            "payload": {},
        }
        with self.assertRaises(ContractViolation):
            validate_record("transport-envelope", event)


if __name__ == "__main__":
    unittest.main(verbosity=2)
