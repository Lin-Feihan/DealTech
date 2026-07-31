from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.deal_analysis_builder import validate_analysis_package
from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m2 import run_m2_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m3 import run_m3_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m4 import run_m4_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m5 import run_m5_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m6 import M6FailClosed, run_m6_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_PATH = RUNTIME_ROOT / "config" / "buyer_acquisition_analysis_framework.json"
SCHEMA_PATH = RUNTIME_ROOT / "schemas" / "analysis_package.schema.json"
FORBIDDEN_DECISION_TERMS = ("Proceed", "Proceed with Conditions", "Renegotiate", "Defer", "Walk Away")
FORBIDDEN_RETURN_METRICS = ("DCF", "IRR", "MOIC", "NPV", "ROIC")


class V3LiteM6AnalysisPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        mandate_path = RUNTIME_ROOT / "examples" / "synthetic_acquisition_mandate.json"
        case_seed_path = RUNTIME_ROOT / "case_seeds" / "synthetic_acquisition_case_seed.json"
        research_plan_path = self.root / "research_plan.json"
        research_plan = build_research_plan(load_mandate(mandate_path))
        research_plan_path.write_text(json.dumps(research_plan, indent=2), encoding="utf-8")
        m2_artifacts = run_m2_pipeline(
            mandate_path=mandate_path,
            research_plan_path=research_plan_path,
            case_seed_path=case_seed_path,
            output_dir=self.root / "m2",
            retrieval_mode="manual_retrieved_sources",
            retrieved_sources_manifest_path=RUNTIME_ROOT / "retrieved_sources" / "synthetic_acquisition" / "retrieved_sources_manifest.json",
        )
        m3_artifacts = run_m3_pipeline(
            raw_evidence_path=m2_artifacts["raw_evidence"],
            retrieved_sources_manifest_path=m2_artifacts["retrieved_sources_manifest"],
            output_dir=self.root / "m3",
        )
        m4_artifacts = run_m4_pipeline(evidence_repository_path=m3_artifacts["evidence_repository"], output_dir=self.root / "m4")
        m5_artifacts = run_m5_pipeline(m4_artifacts["claim_evidence_graph"], m3_artifacts["evidence_repository"], self.root / "m5")
        self.certification_result_path = m5_artifacts["certification_result"]
        self.claim_evidence_graph_path = m4_artifacts["claim_evidence_graph"]
        self.evidence_repository_path = m3_artifacts["evidence_repository"]
        self.research_gaps_path = m5_artifacts["research_gaps"]
        self.repair_plan_path = m5_artifacts["repair_plan"]
        self.framework = self._load(FRAMEWORK_PATH)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_m5_artifacts_produce_analysis_package(self) -> None:
        output_dir = self.root / "m6_valid"

        artifacts = self._run_m6(output_dir)
        analysis_package = self._load(artifacts["analysis_package"])
        certification_result = self._load(self.certification_result_path)

        validate_analysis_package(analysis_package, certification_result)
        self._assert_schema_accepts(analysis_package)
        self.assertTrue(artifacts["analysis_package"].exists())
        self.assertEqual(analysis_package["generated_artifact"], "analysis_package.json")
        self.assertEqual(analysis_package["stage"], "M6_evidence_bounded_deal_analysis")
        self.assertTrue(analysis_package["source_bounded"])
        self.assertIn("recommendation_gate_status", analysis_package)
        self.assertIn("report_gate_status", analysis_package)

    def test_invalid_input_fails_closed(self) -> None:
        certification_result = self._load(self.certification_result_path)
        certification_result["stage"] = "M6_report_generation"
        broken_path = self.root / "broken_certification_result.json"
        broken_path.write_text(json.dumps(certification_result, indent=2), encoding="utf-8")

        with self.assertRaises(M6FailClosed):
            run_m6_pipeline(
                broken_path,
                self.claim_evidence_graph_path,
                self.evidence_repository_path,
                self.research_gaps_path,
                self.repair_plan_path,
                self.root / "m6_invalid",
            )

    def test_output_contains_exactly_14_framework_sections(self) -> None:
        analysis_package = self._run_package("m6_sections")
        framework_ids = [section["section_id"] for section in self.framework["sections"]]
        actual_ids = [section["section_id"] for section in analysis_package["analysis_sections"]]

        self.assertEqual(len(actual_ids), 14)
        self.assertEqual(actual_ids, framework_ids)

    def test_framework_contains_explicit_buyer_side_analyst_playbook(self) -> None:
        required = {
            "section_id",
            "section_title",
            "business_question",
            "analyst_lens",
            "interpretation_rules",
            "buyer_implication_rules",
            "decision_impact_rules",
            "analysis_boundary_rules",
            "relevant_claim_types",
            "optional_exhibits",
        }

        self.assertEqual([section["section_id"] for section in self.framework["sections"]], [
            "transaction_logic",
            "buyer_strategic_objectives",
            "target_business_quality",
            "industry_and_competitive_position",
            "strategic_fit",
            "standalone_financial_analysis",
            "valuation_and_acceptable_price",
            "synergy_and_value_creation",
            "deal_structure",
            "financing_and_capital_structure",
            "return_analysis",
            "due_diligence_priorities",
            "regulatory_integration_and_downside_risks",
            "decision_recommendation_readiness",
        ])
        for section in self.framework["sections"]:
            self.assertTrue(required.issubset(section))
            for field in ("analyst_lens", "interpretation_rules", "buyer_implication_rules", "decision_impact_rules", "analysis_boundary_rules"):
                self.assertTrue(section[field])

    def test_every_section_has_professional_m6b_fields(self) -> None:
        analysis_package = self._run_package("m6_section_fields")
        required = {
            "analyst_interpretation",
            "buyer_implication",
            "key_takeaway",
            "decision_impact",
            "analysis_boundary",
            "imported_limitations_from_m5",
            "missing_inputs",
            "pending_diligence_items",
            "caveats",
            "confidence",
            "optional_exhibits",
        }

        for section in analysis_package["analysis_sections"]:
            self.assertTrue(required.issubset(section))
            self.assertIn(section["analysis_status"], self._schema_section_statuses())
            self.assertIn(section["confidence"], self._schema_confidence_values())
            self.assertIsInstance(section["optional_exhibits"], list)
            for field in ("analyst_interpretation", "buyer_implication", "decision_impact", "analysis_boundary"):
                self.assertIsInstance(section[field], str)
                self.assertGreater(len(section[field]), 40)
                self.assertNotIn("Certified claim", section[field])
                self.assertNotIn("supports limited analysis", section[field])
            self.assertNotIn("Certified source-bounded", section["key_takeaway"])

    def test_supporting_claim_sections_are_limited_not_certification_failures(self) -> None:
        analysis_package = self._run_package("m6_limited_sections")
        with_support = [section for section in analysis_package["analysis_sections"] if section["supporting_claim_ids"]]

        self.assertTrue(with_support)
        for section in with_support:
            self.assertEqual(section["analysis_status"], "limited")

    def test_sections_without_usable_claims_are_not_assessable_not_certification_failures(self) -> None:
        analysis_package = self._run_package("m6_no_usable_claim_sections")
        without_support = [section for section in analysis_package["analysis_sections"] if not section["supporting_claim_ids"]]

        self.assertTrue(without_support)
        for section in without_support:
            self.assertIn(section["analysis_status"], {"limited", "not_assessable_due_to_missing_evidence", "blocked_by_missing_evidence"})
            self.assertNotEqual(section["analysis_status"], "blocked_by_certification_failure")

    def test_unsupported_and_blocked_claims_are_not_supporting_claims(self) -> None:
        analysis_package = self._run_package("m6_no_blocked_support")
        certification_result = self._load(self.certification_result_path)
        blocked_claim_ids = set(certification_result["analysis_gate_summary"]["analysis_blocked_claim_ids"])

        self.assertFalse(set(analysis_package["supporting_claim_ids"]).intersection(blocked_claim_ids))
        for section in analysis_package["analysis_sections"]:
            self.assertFalse(set(section["supporting_claim_ids"]).intersection(blocked_claim_ids))
        self.assertTrue(blocked_claim_ids.issubset(set(analysis_package["excluded_claim_ids"])))

    def test_caveated_claims_and_temporal_limits_are_preserved(self) -> None:
        analysis_package = self._run_package("m6_preserved_caveats")
        certification_result = self._load(self.certification_result_path)
        claim_certs = {claim["claim_id"]: claim for claim in certification_result["claim_certifications"]}

        self.assertTrue(analysis_package["consumed_caveated_claim_ids"])
        preserved_by_claim = {item["claim_id"]: item["caveats"] for item in analysis_package["preserved_caveats"]}
        for claim_id in analysis_package["consumed_caveated_claim_ids"]:
            expected = []
            for field in ("required_caveats", "caveats"):
                expected.extend(claim_certs[claim_id].get(field, []))
            self.assertTrue(expected)
            self.assertEqual(preserved_by_claim[claim_id], list(dict.fromkeys(expected)))
        text = json.dumps(analysis_package)
        self.assertIn("retrospective validation only", text)
        self.assertIn("retrospective/source-limit caveat", text)

    def test_valuation_section_does_not_fabricate_return_metrics_when_inputs_missing(self) -> None:
        section = self._section(self._run_package("m6_valuation_limits"), "valuation_and_acceptable_price")
        text = json.dumps(section)

        self.assertIn("consideration or price mechanics", section["analyst_interpretation"])
        self.assertIn("does not by itself support a full valuation conclusion", section["analyst_interpretation"])
        self.assertIn("contingent consideration can reduce upfront capital at risk", section["buyer_implication"])
        for metric in FORBIDDEN_RETURN_METRICS:
            self.assertIn(metric, text)
        self.assertFalse(any("calculated" in item.lower() for item in section["missing_inputs"]))

    def test_synergy_section_does_not_quantify_synergy_when_evidence_missing(self) -> None:
        section = self._section(self._run_package("m6_synergy_limits"), "synergy_and_value_creation")
        text = json.dumps(section)

        self.assertIn("Synergy remains a diligence hypothesis", section["analyst_interpretation"])
        self.assertIn("control premium", section["analyst_interpretation"])
        self.assertIn("not a valuation input", section["decision_impact"])
        self.assertNotRegex(text, r"\$\d|\d+%|\d+x")

    def test_financing_section_does_not_generate_sources_and_uses_values_when_missing(self) -> None:
        section = self._section(self._run_package("m6_financing_limits"), "financing_and_capital_structure")
        text = json.dumps(section)

        self.assertIn("does not establish a complete Sources and Uses", section["analyst_interpretation"])
        self.assertNotRegex(text, r"sources_total|uses_total|debt_amount|equity_amount|leverage_ratio")

    def test_optional_exhibits_are_statused_not_forced_tables(self) -> None:
        analysis_package = self._run_package("m6_optional_exhibits")
        allowed_statuses = {"ready", "skeleton_only", "blocked_by_missing_inputs", "not_applicable"}
        statuses = set()

        for section in analysis_package["analysis_sections"]:
            for exhibit in section["optional_exhibits"]:
                statuses.add(exhibit["status"])
                self.assertIn(exhibit["status"], allowed_statuses)
                self.assertIn("required_inputs", exhibit)
                self.assertIn("available_inputs", exhibit)
                self.assertNotIn("rows", exhibit)
                self.assertNotIn("table", exhibit)
        self.assertIn("blocked_by_missing_inputs", statuses)
        self.assertTrue(statuses.intersection({"skeleton_only", "ready", "not_applicable"}))

    def test_decision_recommendation_readiness_does_not_generate_final_recommendation(self) -> None:
        analysis_package = self._run_package("m6_decision_readiness")
        section = self._section(analysis_package, "decision_recommendation_readiness")
        text = json.dumps(section)

        self.assertFalse(analysis_package["recommendation_allowed"])
        self.assertIn(section["analysis_status"], {"limited", "not_assessable_due_to_missing_evidence", "blocked_by_missing_evidence"})
        self.assertIn("cannot create a final buyer recommendation", section["buyer_implication"])
        self.assertIn("M6 records readiness only", section["decision_impact"])
        for forbidden in FORBIDDEN_DECISION_TERMS:
            self.assertNotIn(forbidden, text)

    def test_due_diligence_priorities_convert_m5_gaps_into_actions(self) -> None:
        analysis_package = self._run_package("m6_diligence_actions")
        section = self._section(analysis_package, "due_diligence_priorities")

        self.assertEqual(section["analysis_status"], "limited")
        self.assertTrue(section["pending_diligence_items"])
        self.assertTrue(section["imported_limitations_from_m5"])
        self.assertIn("converts M5 gaps", section["analyst_interpretation"])
        self.assertTrue(all(item["diligence_item_id"].startswith("DI-due_diligence_priorities-RG-") for item in section["pending_diligence_items"]))

    def test_repair_required_disallows_recommendation_and_final_report(self) -> None:
        analysis_package = self._run_package("m6_gate")
        certification_result = self._load(self.certification_result_path)

        self.assertEqual(analysis_package["analysis_readiness_status"], "limited_by_repair_required")
        self.assertFalse(analysis_package["recommendation_allowed"])
        self.assertFalse(analysis_package["final_report_allowed"])
        self.assertEqual(analysis_package["recommendation_allowed"], certification_result["recommendation_gate_summary"]["recommendation_allowed"])
        self.assertEqual(analysis_package["final_report_allowed"], not bool(certification_result["report_gate_summary"]["report_blocked_claim_ids"]))
        self.assertEqual(analysis_package["next_action"], "run_targeted_source_repair_or_human_review_before_recommendation_or_final_report")

    def test_human_review_items_are_carried_forward(self) -> None:
        analysis_package = self._run_package("m6_human_review")
        certification_result = self._load(self.certification_result_path)

        self.assertEqual(analysis_package["human_review_items"], certification_result["human_review_items"])
        self.assertEqual(len(analysis_package["human_review_items"]), 6)

    def test_no_recommendation_decision_or_final_report_generated(self) -> None:
        output_dir = self.root / "m6_forbidden_outputs"

        self._run_m6(output_dir)

        self.assertEqual([path.name for path in output_dir.iterdir()], ["analysis_package.json"])
        self.assertFalse((output_dir / "recommendation_decision.json").exists())
        self.assertFalse((output_dir / "final_report.md").exists())

    def _assert_schema_accepts(self, analysis_package: dict) -> None:
        schema = self._load(SCHEMA_PATH)
        for field in schema["required"]:
            self.assertIn(field, analysis_package)
        self.assertTrue(analysis_package["source_bounded"])
        self.assertEqual(analysis_package["generated_artifact"], "analysis_package.json")
        self.assertEqual(analysis_package["stage"], "M6_evidence_bounded_deal_analysis")
        schema_section_ids = [rule["contains"]["properties"]["section_id"]["const"] for rule in schema["properties"]["analysis_sections"]["allOf"]]
        self.assertEqual([section["section_id"] for section in analysis_package["analysis_sections"]], schema_section_ids)
        section_required = set(schema["$defs"]["analysis_section"]["required"])
        for section in analysis_package["analysis_sections"]:
            self.assertTrue(section_required.issubset(section))

    def _schema_section_statuses(self) -> set[str]:
        schema = self._load(SCHEMA_PATH)
        return set(schema["$defs"]["analysis_section"]["properties"]["analysis_status"]["enum"])

    def _schema_confidence_values(self) -> set[str]:
        schema = self._load(SCHEMA_PATH)
        return set(schema["$defs"]["analysis_section"]["properties"]["confidence"]["enum"])

    def _run_package(self, label: str) -> dict:
        artifacts = self._run_m6(self.root / label)
        return self._load(artifacts["analysis_package"])

    def _run_m6(self, output_dir: Path) -> dict[str, Path]:
        return run_m6_pipeline(
            self.certification_result_path,
            self.claim_evidence_graph_path,
            self.evidence_repository_path,
            self.research_gaps_path,
            self.repair_plan_path,
            output_dir,
        )

    def _section(self, analysis_package: dict, section_id: str) -> dict:
        return next(section for section in analysis_package["analysis_sections"] if section["section_id"] == section_id)

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
