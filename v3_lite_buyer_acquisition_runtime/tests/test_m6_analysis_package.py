from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.deal_analysis_builder import validate_analysis_package
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m2 import run_m2_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m3 import run_m3_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m4 import run_m4_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m5 import run_m5_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m6 import M6FailClosed, run_m6_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


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

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_m5_artifacts_produce_analysis_package(self) -> None:
        output_dir = self.root / "m6_valid"

        artifacts = self._run_m6(output_dir)
        analysis_package = self._load(artifacts["analysis_package"])
        certification_result = self._load(self.certification_result_path)

        validate_analysis_package(analysis_package, certification_result)
        self.assertTrue(artifacts["analysis_package"].exists())
        self.assertEqual(analysis_package["generated_artifact"], "analysis_package.json")
        self.assertEqual(analysis_package["stage"], "M6_evidence_bounded_deal_analysis")
        self.assertTrue(analysis_package["source_bounded"])

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

    def test_repair_required_disallows_recommendation_and_final_report(self) -> None:
        analysis_package = self._run_package("m6_gate")

        self.assertEqual(analysis_package["analysis_readiness_status"], "limited_by_repair_required")
        self.assertFalse(analysis_package["recommendation_allowed"])
        self.assertFalse(analysis_package["final_report_allowed"])
        self.assertEqual(analysis_package["next_action"], "run_targeted_source_repair_or_human_review_before_recommendation_or_final_report")

    def test_analysis_sections_are_present(self) -> None:
        analysis_package = self._run_package("m6_sections")
        sections_by_id = {section["section_id"]: section for section in analysis_package["analysis_sections"]}

        self.assertEqual(
            set(sections_by_id),
            {
                "transaction_background_and_terms",
                "strategic_rationale_and_alternatives",
                "target_business_quality",
                "market_and_competitive_position",
                "valuation_deal_structure_and_returns",
                "synergy_and_value_creation",
                "financing_payment_mechanics_and_value_transfer",
                "legal_regulatory_and_diligence_risks",
                "integration_and_operational_risks",
                "source_gaps_and_human_review",
                "decision_readiness",
            },
        )
        self.assertTrue(any(section["included_claim_ids"] for section in sections_by_id.values()))
        self.assertEqual(sections_by_id["source_gaps_and_human_review"]["section_status"], "gap_tracking_only")
        self.assertEqual(sections_by_id["decision_readiness"]["section_status"], "limited_by_repair_required")

    def test_unsupported_and_blocked_claims_are_not_used_as_facts(self) -> None:
        analysis_package = self._run_package("m6_no_blocked_facts")
        fact_sections = [
            section
            for section in analysis_package["analysis_sections"]
            if section["section_id"] not in {"source_gaps_and_human_review", "decision_readiness"}
        ]
        fact_claim_ids = {
            claim_id
            for section in fact_sections
            for finding in section["findings"]
            for claim_id in finding["related_claim_ids"]
        }

        self.assertFalse({"CL-005", "CL-006", "CL-007", "CL-008"} & fact_claim_ids)
        gap_section = self._section(analysis_package, "source_gaps_and_human_review")
        self.assertEqual(gap_section["section_status"], "gap_tracking_only")
        self.assertTrue({"CL-005", "CL-006", "CL-007", "CL-008"}.issubset(set(gap_section["excluded_claim_ids"])))

    def test_numeric_claims_are_blocked_without_explicit_verified_support(self) -> None:
        analysis_package = self._run_package("m6_numeric_generic")
        text = json.dumps(analysis_package)

        self.assertIn("numeric_or_transaction_terms_source_gap unresolved", text)
        self.assertNotIn("ForbiddenTarget", text)
        self.assertFalse(any("ForbiddenTarget" in finding["finding_text"] for section in analysis_package["analysis_sections"] for finding in section["findings"]))
        self.assertFalse(any(caveat["caveat_type"] == "derived_numeric_result" for caveat in analysis_package["caveats"]))

    def test_post_decision_and_retrospective_evidence_remains_caveated(self) -> None:
        analysis_package = self._run_package("m6_temporal")
        caveat_text = json.dumps(analysis_package["caveats"])
        section_caveats = json.dumps([section["caveats"] for section in analysis_package["analysis_sections"]])

        self.assertIn("post_decision_or_retrospective_sources", caveat_text)
        self.assertIn("retrospective validation only", caveat_text)
        self.assertIn("retrospective/source-limit caveat", section_caveats)

    def test_blocked_analysis_items_are_present(self) -> None:
        analysis_package = self._run_package("m6_blocked_items")
        blocked_topics = {item["blocked_topic"] for item in analysis_package["blocked_analysis_items"]}

        self.assertTrue(blocked_topics)
        self.assertTrue(any("source_gap" in topic or "claim not certified" in topic for topic in blocked_topics))
        for item in analysis_package["blocked_analysis_items"]:
            self.assertFalse(item["can_appear_in_final_report"])
            self.assertTrue(item["required_repair_target"])

    def test_human_review_items_are_carried_forward(self) -> None:
        analysis_package = self._run_package("m6_human_review")
        certification_result = self._load(self.certification_result_path)

        self.assertEqual(analysis_package["human_review_items"], certification_result["human_review_items"])
        self.assertEqual(len(analysis_package["human_review_items"]), 6)

    def test_no_recommendation_decision_or_final_report_generated(self) -> None:
        output_dir = self.root / "m6_forbidden_outputs"

        self._run_m6(output_dir)

        self.assertFalse((output_dir / "recommendation_decision.json").exists())
        self.assertFalse((output_dir / "final_report.md").exists())

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
