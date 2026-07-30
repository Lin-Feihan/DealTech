from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.deal_analysis_builder import validate_analysis_package
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m6 import M6FailClosed, run_m6_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM6AnalysisPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.certification_result_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "certification_result.json"
        self.claim_evidence_graph_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m4" / "claim_evidence_graph.json"
        self.evidence_repository_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m3" / "evidence_repository.json"
        self.research_gaps_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "research_gaps.json"
        self.repair_plan_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "repair_plan.json"

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
                "transaction_terms_analysis",
                "milestone_economics_analysis",
                "entity_and_asset_lineage_analysis",
                "evidence_gap_and_risk_analysis",
                "decision_readiness_assessment",
            },
        )
        self.assertIn("CL-003", sections_by_id["transaction_terms_analysis"]["included_claim_ids"])
        self.assertIn("CL-007", sections_by_id["transaction_terms_analysis"]["included_claim_ids"])
        self.assertIn("CL-010", sections_by_id["transaction_terms_analysis"]["included_claim_ids"])
        self.assertIn("CL-001", sections_by_id["transaction_terms_analysis"]["included_claim_ids"])
        self.assertIn("CL-011", sections_by_id["milestone_economics_analysis"]["included_claim_ids"])
        self.assertIn("CL-006", sections_by_id["entity_and_asset_lineage_analysis"]["included_claim_ids"])
        self.assertIn("CL-005", sections_by_id["entity_and_asset_lineage_analysis"]["included_claim_ids"])

    def test_unsupported_and_blocked_claims_are_not_used_as_facts(self) -> None:
        analysis_package = self._run_package("m6_no_blocked_facts")
        fact_sections = [
            section
            for section in analysis_package["analysis_sections"]
            if section["section_id"] in {"transaction_terms_analysis", "milestone_economics_analysis", "entity_and_asset_lineage_analysis"}
        ]
        fact_claim_ids = {
            claim_id
            for section in fact_sections
            for finding in section["findings"]
            for claim_id in finding["related_claim_ids"]
        }

        self.assertFalse({"CL-012", "CL-013", "CL-014", "CL-015"} & fact_claim_ids)
        gap_section = self._section(analysis_package, "evidence_gap_and_risk_analysis")
        self.assertEqual(gap_section["section_status"], "gap_tracking_only")
        self.assertTrue({"CL-012", "CL-013", "CL-014", "CL-015"}.issubset(set(gap_section["excluded_claim_ids"])))

    def test_180m_appears_only_with_numeric_caveat(self) -> None:
        analysis_package = self._run_package("m6_180m")
        text = json.dumps(analysis_package)
        milestone_section = self._section(analysis_package, "milestone_economics_analysis")
        derived_findings = [finding for finding in milestone_section["findings"] if "CL-011" in finding["related_claim_ids"]]

        self.assertIn("$180M", text)
        self.assertEqual(len(derived_findings), 1)
        self.assertTrue(derived_findings[0]["caveated"])
        self.assertIn("not a direct-source headline value", derived_findings[0]["finding_text"])
        self.assertTrue(any(caveat["caveat_type"] == "derived_numeric_result" for caveat in analysis_package["caveats"]))

    def test_post_decision_and_retrospective_evidence_remains_caveated(self) -> None:
        analysis_package = self._run_package("m6_temporal")
        caveat_text = json.dumps(analysis_package["caveats"])
        section_caveats = json.dumps([section["caveats"] for section in analysis_package["analysis_sections"]])

        self.assertIn("post_decision_or_retrospective_sources", caveat_text)
        self.assertIn("retrospective validation only", caveat_text)
        self.assertIn("post_decision evidence", section_caveats)

    def test_blocked_analysis_items_are_present(self) -> None:
        analysis_package = self._run_package("m6_blocked_items")
        blocked_by_topic = {item["blocked_topic"]: item for item in analysis_package["blocked_analysis_items"]}

        for topic in (
            "founder ownership economics",
            "Bohan Jin personal realized proceeds",
            "immediate pre-sale cap table",
            "official patent-office confirmation",
            "uncaveated $180M headline value wording",
        ):
            self.assertIn(topic, blocked_by_topic)
            self.assertFalse(blocked_by_topic[topic]["can_appear_in_final_report"])
            self.assertTrue(blocked_by_topic[topic]["required_repair_target"])

    def test_human_review_items_are_carried_forward(self) -> None:
        analysis_package = self._run_package("m6_human_review")
        certification_result = self._load(self.certification_result_path)

        self.assertEqual(analysis_package["human_review_items"], certification_result["human_review_items"])
        self.assertEqual(len(analysis_package["human_review_items"]), 14)

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
