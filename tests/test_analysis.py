"""Signal-analysis heuristics, explicit decoder and validation-separation tests."""
from __future__ import annotations

import unittest
import uuid

from civic_workbench.analysis import analyze_frames, independent_validation, summarize_frames
from civic_workbench.contracts import ContractViolation
from civic_workbench.diagnostics import decode_explicit_parameter
from civic_test_helpers import make_frame


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.session_id = str(uuid.uuid4())
        self.frames = [
            make_frame(self.session_id, i, arbitration_id=0x120, payload=[i, 0, i * 2 & 255, 0, 0, 0, 0, 0])
            for i in range(12)
        ]

    def test_summary_and_observed_findings_include_exact_frame_provenance(self):
        summary = summarize_frames(self.frames)
        self.assertEqual(summary["total_frames"], 12)
        self.assertEqual(summary["unique_identifiers"], 1)
        self.assertGreater(summary["identifiers"][0]["median_period_ns"], 0)
        findings = analyze_frames(self.frames)
        self.assertTrue(findings)
        self.assertTrue(all(f["status"] in {"observed", "candidate"} for f in findings))
        frame_ids = {f["frame_id"] for f in self.frames}
        self.assertTrue(all(set(f["evidence_frame_ids"]).issubset(frame_ids) for f in findings))
        self.assertTrue(any(f["finding_kind"] == "identifier_periodicity" for f in findings))
        self.assertTrue(any(f["finding_kind"] == "payload_change" for f in findings))

    def test_counter_hypothesis_is_candidate_and_validation_requires_independent_evidence(self):
        findings = analyze_frames(self.frames)
        candidates = [f for f in findings if f["status"] == "candidate"]
        self.assertTrue(candidates)
        candidate = candidates[0]
        with self.assertRaises(ContractViolation):
            independent_validation(candidate, "", [])
        validated = independent_validation(
            candidate, "compared against independent test equipment", ["bench-report-2"], "reviewer"
        )
        self.assertEqual(validated["status"], "validated")
        self.assertNotEqual(candidate["status"], "validated")

    def test_explicit_parameter_decoder_extracts_user_selected_value_without_auto_validation(self):
        definition = {
            "name": "byte-zero",
            "start_bit": 0,
            "bit_length": 8,
            "byte_order": "little_endian",
            "signed": False,
            "scale": 0.5,
            "offset": 1.0,
            "unit": "candidate-unit",
        }
        result = decode_explicit_parameter(self.frames, definition, [self.frames[0]["frame_id"], self.frames[5]["frame_id"]])
        self.assertEqual(result["status"], "candidate")
        self.assertFalse(result["validated"])
        self.assertEqual([item["value"] for item in result["values"]], [1.0, 3.5])
        self.assertEqual(len(result["evidence_frame_ids"]), 2)

    def test_decoder_rejects_missing_or_out_of_range_evidence_and_unknown_endianness(self):
        definition = {"name":"x","start_bit":0,"bit_length":8,"byte_order":"unknown","signed":False,"scale":1,"offset":0,"unit":None}
        with self.assertRaises(ContractViolation):
            decode_explicit_parameter(self.frames, definition, [self.frames[0]["frame_id"]])
        definition["byte_order"] = "little_endian"
        definition["start_bit"] = 63
        with self.assertRaises(ContractViolation):
            decode_explicit_parameter(self.frames, definition, [self.frames[0]["frame_id"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
