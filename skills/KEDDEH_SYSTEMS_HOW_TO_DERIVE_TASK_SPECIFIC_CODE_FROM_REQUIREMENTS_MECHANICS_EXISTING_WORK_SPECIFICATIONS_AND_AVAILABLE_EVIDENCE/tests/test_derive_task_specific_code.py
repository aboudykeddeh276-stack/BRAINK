#!/usr/bin/env python3
"""
Tests for the task-specific code derivation engine.

Runnable with either:
    python3 -m pytest tests/
    python3 tests/test_derive_task_specific_code.py   (built-in runner, no deps)
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import derive_task_specific_code as engine  # noqa: E402


def _mechanic(mech_id: str, pathways: list[dict]) -> dict:
    return {
        "id": mech_id,
        "name": f"Mechanic {mech_id}",
        "functions": [],
        "required_knowledge": [],
        "derivation_pathways": pathways,
    }


def _spec(mechanics: list[dict]) -> dict:
    return {"capability": "test capability", "mechanics": mechanics}


class ValidationTests(unittest.TestCase):
    def test_rejects_non_object_spec(self) -> None:
        with self.assertRaises(engine.SpecError):
            engine.validate_spec([])

    def test_rejects_empty_capability(self) -> None:
        with self.assertRaises(engine.SpecError):
            engine.validate_spec({"capability": "   ", "mechanics": [_mechanic("A", [])]})

    def test_rejects_empty_mechanics(self) -> None:
        with self.assertRaises(engine.SpecError):
            engine.validate_spec({"capability": "c", "mechanics": []})

    def test_rejects_duplicate_mechanic_ids(self) -> None:
        m = _mechanic("DUP", [{"kind": "download", "status": "available"}])
        with self.assertRaises(engine.SpecError):
            engine.validate_spec(_spec([m, copy.deepcopy(m)]))

    def test_rejects_invalid_pathway_status(self) -> None:
        m = _mechanic("A", [{"kind": "download", "status": "maybe"}])
        with self.assertRaises(engine.SpecError):
            engine.validate_spec(_spec([m]))

    def test_rejects_empty_pathways(self) -> None:
        with self.assertRaises(engine.SpecError):
            engine.validate_spec(_spec([_mechanic("A", [])]))


class MechanicVerdictTests(unittest.TestCase):
    def test_available_pathway_is_derivable(self) -> None:
        m = _mechanic("A", [{"kind": "protocol_specification", "status": "available"}])
        result = engine.evaluate_mechanic(m)
        self.assertEqual(result["verdict"], engine.MECHANIC_DERIVABLE)
        self.assertEqual(result["selected_pathway"], "protocol_specification")

    def test_untested_only_is_status_unknown(self) -> None:
        m = _mechanic("A", [{"kind": "download", "status": "untested"}])
        result = engine.evaluate_mechanic(m)
        self.assertEqual(result["verdict"], engine.MECHANIC_STATUS_UNKNOWN)
        self.assertIsNone(result["selected_pathway"])

    def test_all_exhausted_is_limitation(self) -> None:
        m = _mechanic(
            "A",
            [
                {"kind": "download", "status": "tested_and_failed", "evidence": "x"},
                {"kind": "protocol_specification", "status": "ruled_out_with_evidence", "evidence": "y"},
            ],
        )
        result = engine.evaluate_mechanic(m)
        self.assertEqual(result["verdict"], engine.MECHANIC_LIMITATION)

    def test_prefers_higher_priority_available_pathway(self) -> None:
        m = _mechanic(
            "A",
            [
                {"kind": "download", "status": "available"},
                {"kind": "protocol_specification", "status": "available"},
            ],
        )
        result = engine.evaluate_mechanic(m)
        # protocol_specification outranks download in PATHWAY_PRIORITY.
        self.assertEqual(result["selected_pathway"], "protocol_specification")


class GoverningRuleTests(unittest.TestCase):
    """The central rule: a failed acquisition route is not a capability limit
    while other pathways remain available or untested."""

    def test_failed_download_with_available_spec_is_derivable(self) -> None:
        m = _mechanic(
            "SUBMITBLOCK",
            [
                {"kind": "download", "status": "tested_and_failed", "evidence": "no network"},
                {"kind": "protocol_specification", "status": "available"},
            ],
        )
        result = engine.evaluate_mechanic(m)
        self.assertEqual(result["verdict"], engine.MECHANIC_DERIVABLE)

    def test_failed_download_with_untested_source_is_not_limitation(self) -> None:
        m = _mechanic(
            "SUBMITBLOCK",
            [
                {"kind": "download", "status": "tested_and_failed", "evidence": "no network"},
                {"kind": "existing_source", "status": "untested"},
            ],
        )
        result = engine.evaluate_mechanic(m)
        self.assertEqual(result["verdict"], engine.MECHANIC_STATUS_UNKNOWN)
        self.assertNotEqual(result["verdict"], engine.MECHANIC_LIMITATION)

    def test_failure_is_acquisition_only_flag(self) -> None:
        m = _mechanic(
            "A",
            [
                {"kind": "download", "status": "tested_and_failed", "evidence": "x"},
                {"kind": "git_clone", "status": "tested_and_failed", "evidence": "y"},
                {"kind": "protocol_specification", "status": "available"},
            ],
        )
        result = engine.evaluate_mechanic(m)
        self.assertTrue(result["failure_is_acquisition_only"])

    def test_non_acquisition_failure_not_flagged_as_acquisition_only(self) -> None:
        m = _mechanic(
            "A",
            [
                {"kind": "protocol_specification", "status": "ruled_out_with_evidence", "evidence": "spec ambiguous"},
                {"kind": "existing_source", "status": "available"},
            ],
        )
        result = engine.evaluate_mechanic(m)
        self.assertFalse(result["failure_is_acquisition_only"])


class CapabilityReportTests(unittest.TestCase):
    def test_fully_derivable_capability(self) -> None:
        spec = _spec([_mechanic("A", [{"kind": "protocol_specification", "status": "available"}])])
        report = engine.derive(spec)
        self.assertEqual(report["capability_verdict"], "CAPABILITY_IS_FULLY_DERIVABLE")
        self.assertEqual(engine.report_exit_code(report), 0)

    def test_status_unknown_capability(self) -> None:
        spec = _spec([_mechanic("A", [{"kind": "download", "status": "untested"}])])
        report = engine.derive(spec)
        self.assertEqual(
            report["capability_verdict"],
            "CAPABILITY_DERIVATION_STATUS_UNKNOWN_EVIDENCE_INSUFFICIENT",
        )
        self.assertEqual(engine.report_exit_code(report), 2)

    def test_proven_limitation_capability(self) -> None:
        spec = _spec(
            [
                _mechanic(
                    "A",
                    [{"kind": "download", "status": "tested_and_failed", "evidence": "x"}],
                )
            ]
        )
        report = engine.derive(spec)
        self.assertEqual(report["capability_verdict"], "CAPABILITY_HAS_PROVEN_LIMITATION")
        self.assertEqual(engine.report_exit_code(report), 1)


class BtcCaseStudyTests(unittest.TestCase):
    def test_btc_case_study_is_listed(self) -> None:
        self.assertIn("btc", engine.list_case_studies())

    def test_btc_case_study_loads_and_validates(self) -> None:
        spec = engine.load_case_study("btc")
        engine.validate_spec(spec)  # must not raise

    def test_btc_case_study_is_fully_derivable(self) -> None:
        """Every BTC mechanic must have a live derivation pathway even though the
        download acquisition route for submitblock is recorded as failed."""
        spec = engine.load_case_study("btc")
        report = engine.derive(spec)
        self.assertEqual(report["capability_verdict"], "CAPABILITY_IS_FULLY_DERIVABLE")

    def test_submitblock_failed_download_does_not_block_derivation(self) -> None:
        spec = engine.load_case_study("btc")
        report = engine.derive(spec)
        submit = next(m for m in report["mechanics"] if m["id"] == "SUBMITBLOCK_INTERACTION")
        self.assertEqual(submit["verdict"], engine.MECHANIC_DERIVABLE)
        exhausted_kinds = {p["kind"] for p in submit["exhausted_pathways"]}
        self.assertIn("download", exhausted_kinds)
        self.assertNotEqual(submit["selected_pathway"], "download")

    def test_unknown_case_study_raises(self) -> None:
        with self.assertRaises(engine.SpecError):
            engine.load_case_study("does_not_exist")


class CliTests(unittest.TestCase):
    def test_cli_list_case_studies(self) -> None:
        rc = engine.main(["--list-case-studies"])
        self.assertEqual(rc, 0)

    def test_cli_case_study_btc_exit_zero(self) -> None:
        rc = engine.main(["--case-study", "btc"])
        self.assertEqual(rc, 0)

    def test_cli_missing_file_returns_one(self) -> None:
        rc = engine.main(["/nonexistent/spec.json"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
