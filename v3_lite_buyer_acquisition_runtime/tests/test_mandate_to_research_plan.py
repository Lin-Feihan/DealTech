from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import MandateValidationError, validate_mandate
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import validate_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite import run_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteMandateToResearchPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.mandate = self._valid_mandate()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_mandate_generates_valid_research_plan(self) -> None:
        mandate_path = self._write_mandate(self.mandate)
        output_dir = self.root / "outputs" / "valid_run"

        artifacts = run_pipeline(mandate_path, output_dir)

        self.assertEqual(artifacts["mandate"], output_dir / "mandate.json")
        self.assertEqual(artifacts["research_plan"], output_dir / "research_plan.json")
        self.assertTrue((output_dir / "mandate.json").exists())
        self.assertTrue((output_dir / "research_plan.json").exists())

        research_plan = self._read_json(output_dir / "research_plan.json")
        validate_research_plan(research_plan)
        self.assertEqual(research_plan["case_id"], self.mandate["case_id"])
        self.assertEqual(research_plan["expected_artifacts"], ["mandate.json", "research_plan.json"])
        verification_text = json.dumps(research_plan["verification_targets"])
        self.assertIn("web search", verification_text)

    def test_named_case_mandate_generates_generic_research_plan(self) -> None:
        mandate_path = RUNTIME_ROOT / "examples" / "fronthera_esker_alumis_mandate.json"
        output_dir = self.root / "outputs" / "named_case_run"

        run_pipeline(mandate_path, output_dir)

        research_plan = self._read_json(output_dir / "research_plan.json")
        validate_research_plan(research_plan)
        plan_text = json.dumps(research_plan)

        self.assertEqual(research_plan["case_id"], "fronthera_esker_alumis_2021_acquisition_m1")
        self.assertEqual(len(research_plan["workstreams"]), 9)
        self.assertIn("Transaction Background and Mandate Clarification", plan_text)
        self.assertIn("Buyer Strategic Rationale and Acquisition Alternatives", plan_text)
        self.assertIn("Target Business Quality and Competitive Position", plan_text)
        self.assertIn("Valuation, Deal Structure, Synergy, and Returns", plan_text)
        self.assertIn("Diligence Priorities and Risk Review", plan_text)
        self.assertIn("IC Decision Framework and Red-Line Conditions", plan_text)
        for term in ("TYK2", "Bohan Jin", "ESK-001", "envudeucitinib", "$60M", "$120M", "$180M", "11.12%"):
            self.assertNotIn(term, plan_text)

    def test_required_mandate_fields_fail_closed(self) -> None:
        required_fields = (
            "buyer",
            "target",
            "transaction_context",
            "decision_date",
            "requested_scope",
            "source_pack_reference",
        )
        for field in required_fields:
            with self.subTest(field=field):
                invalid = copy.deepcopy(self.mandate)
                invalid.pop(field)
                with self.assertRaises(MandateValidationError):
                    validate_mandate(invalid)

    def test_invalid_mandate_does_not_generate_downstream_artifact(self) -> None:
        invalid = copy.deepcopy(self.mandate)
        invalid.pop("buyer")
        mandate_path = self._write_mandate(invalid)
        output_dir = self.root / "outputs" / "invalid_run"

        with self.assertRaises(MandateValidationError):
            run_pipeline(mandate_path, output_dir)

        self.assertFalse((output_dir / "research_plan.json").exists())
        self.assertFalse((output_dir / "mandate.json").exists())

    def _write_mandate(self, mandate: dict) -> Path:
        path = self.root / "mandate.json"
        path.write_text(json.dumps(mandate, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _valid_mandate() -> dict:
        return {
            "case_id": "unit_test_buyer_acquisition_milestone_1",
            "buyer": {"name": "Northstar Therapeutics"},
            "target": {"name": "Meridian BioAssets"},
            "transaction_context": {
                "transaction_type": "buyer-side acquisition evaluation",
                "stage": "pre-diligence planning",
                "decision_need": "Define a research plan before downstream work.",
            },
            "decision_date": "2026-07-28",
            "requested_scope": [
                "buyer strategic objectives",
                "target business quality",
                "valuation and acceptable purchase price",
            ],
            "source_pack_reference": {
                "reference_id": "SOURCE-PACK-UNIT-001",
                "description": "Unit-test source pack placeholder.",
            },
            "constraints": {
                "no_web_search": True,
                "no_evidence_generation": True,
                "no_report_generation": True,
            },
            "output_requirements": {
                "expected_artifacts": ["mandate.json", "research_plan.json"],
                "language": "English",
            },
        }


if __name__ == "__main__":
    unittest.main()
