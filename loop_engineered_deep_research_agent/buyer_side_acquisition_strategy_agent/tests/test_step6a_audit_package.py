from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.audit_package_builder import validate_audit_package
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.mandate_intake import load_mandate
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.research_planning import build_research_plan
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m2 import run_m2_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m3 import run_m3_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m4 import run_m4_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m5 import run_m5_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m6 import run_m6_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m7 import run_m7_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_step6a_audit_package import run_step6a_audit_package_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class BuyerSideAcquisitionStrategyAgentStep6AAuditPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        mandate_path = RUNTIME_ROOT / "examples" / "synthetic_acquisition_mandate.json"
        case_seed_path = RUNTIME_ROOT / "case_seeds" / "synthetic_acquisition_case_seed.json"
        research_plan_path = self.root / "research_plan.json"
        research_plan = build_research_plan(load_mandate(mandate_path))
        research_plan_path.write_text(json.dumps(research_plan, indent=2), encoding="utf-8")
        self.m2_artifacts = run_m2_pipeline(
            mandate_path=mandate_path,
            research_plan_path=research_plan_path,
            case_seed_path=case_seed_path,
            output_dir=self.root / "m2",
            retrieval_mode="manual_retrieved_sources",
            retrieved_sources_manifest_path=RUNTIME_ROOT / "retrieved_sources" / "synthetic_acquisition" / "retrieved_sources_manifest.json",
        )
        self.m3_artifacts = run_m3_pipeline(
            raw_evidence_path=self.m2_artifacts["raw_evidence"],
            retrieved_sources_manifest_path=self.m2_artifacts["retrieved_sources_manifest"],
            output_dir=self.root / "m3",
        )
        self.m4_artifacts = run_m4_pipeline(self.m3_artifacts["evidence_repository"], self.root / "m4")
        self.m5_artifacts = run_m5_pipeline(self.m4_artifacts["claim_evidence_graph"], self.m3_artifacts["evidence_repository"], self.root / "m5")
        self.m6_artifacts = run_m6_pipeline(
            certification_result_path=self.m5_artifacts["certification_result"],
            claim_evidence_graph_path=self.m4_artifacts["claim_evidence_graph"],
            evidence_repository_path=self.m3_artifacts["evidence_repository"],
            research_gaps_path=self.m5_artifacts["research_gaps"],
            repair_plan_path=self.m5_artifacts["repair_plan"],
            output_dir=self.root / "m6",
        )
        self.m7_artifacts = run_m7_pipeline(
            analysis_package_path=self.m6_artifacts["analysis_package"],
            certification_result_path=self.m5_artifacts["certification_result"],
            repair_plan_path=self.m5_artifacts["repair_plan"],
            output_dir=self.root / "m7",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_m3_to_m7_artifacts_generate_audit_package(self) -> None:
        output_dir = self.root / "step6a_valid"

        artifacts = self._run_step6a(output_dir)
        audit_package = self._load(artifacts["audit_package"])

        validate_audit_package(audit_package)
        self.assertTrue(artifacts["audit_package"].exists())
        self.assertEqual(audit_package["generated_artifact"], "audit_package.json")
        self.assertEqual(audit_package["stage"], "Step6A_professional_report_audit_package")
        self.assertTrue(audit_package["source_bounded"])

    def test_audit_package_contains_report_section_trace(self) -> None:
        audit_package = self._run_package("step6a_trace")
        trace_ids = [trace["report_section_id"] for trace in audit_package["report_section_trace"]]

        self.assertIn("executive_summary", trace_ids)
        self.assertIn("transaction_snapshot", trace_ids)
        self.assertIn("appendix_source_list", trace_ids)
        for trace in audit_package["report_section_trace"]:
            for field in (
                "report_section_id",
                "report_section_title",
                "source_analysis_section_ids",
                "used_claim_ids",
                "used_evidence_record_ids",
                "used_source_ids",
                "required_caveats",
                "excluded_claim_ids",
                "trace_notes",
            ):
                self.assertIn(field, trace)

    def test_report_section_traces_map_to_claims_evidence_and_sources_where_available(self) -> None:
        audit_package = self._run_package("step6a_mapping")
        mapped = [trace for trace in audit_package["report_section_trace"] if trace["used_claim_ids"]]

        self.assertTrue(mapped)
        self.assertTrue(any(trace["used_evidence_record_ids"] for trace in mapped))
        self.assertTrue(any(trace["used_source_ids"] for trace in mapped))
        self.assertTrue(audit_package["source_citation_table"])
        for row in audit_package["source_citation_table"]:
            self.assertTrue(row["evidence_record_ids"])
            self.assertTrue(row["claim_ids"])
            self.assertTrue(row["report_section_ids"])

    def test_excluded_claims_remain_excluded(self) -> None:
        audit_package = self._run_package("step6a_exclusions")
        analysis_package = self._load(self.m6_artifacts["analysis_package"])
        excluded_ids = {row["claim_id"] for row in audit_package["excluded_claims"]}

        self.assertTrue(excluded_ids)
        self.assertTrue(set(analysis_package["excluded_claim_ids"]).issubset(excluded_ids))
        used_ids = {claim_id for trace in audit_package["report_section_trace"] for claim_id in trace["used_claim_ids"]}
        self.assertFalse(used_ids.intersection(set(analysis_package["excluded_claim_ids"])))

    def test_caveats_are_preserved(self) -> None:
        audit_package = self._run_package("step6a_caveats")
        analysis_package = self._load(self.m6_artifacts["analysis_package"])

        self.assertGreaterEqual(len(audit_package["caveat_map"]), len(analysis_package["preserved_caveats"]))
        caveat_text = json.dumps(audit_package["caveat_map"])
        self.assertIn("retrospective", caveat_text)

    def test_recommendation_gate_status_is_preserved(self) -> None:
        audit_package = self._run_package("step6a_recommendation_gate")
        analysis_package = self._load(self.m6_artifacts["analysis_package"])

        self.assertEqual(audit_package["recommendation_allowed"], analysis_package["recommendation_allowed"])
        self.assertEqual(audit_package["recommendation_gate_record"]["recommendation_allowed"], analysis_package["recommendation_allowed"])
        self.assertTrue(audit_package["recommendation_gate_record"]["decision_artifact_required_for_recommendation"])

    def test_no_final_report_or_recommendation_decision_generated_by_step6a(self) -> None:
        output_dir = self.root / "step6a_forbidden_outputs"

        self._run_step6a(output_dir)

        self.assertEqual([path.name for path in output_dir.iterdir()], ["audit_package.json"])
        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertFalse((output_dir / "recommendation_decision.json").exists())

    def _run_package(self, label: str) -> dict:
        artifacts = self._run_step6a(self.root / label)
        return self._load(artifacts["audit_package"])

    def _run_step6a(self, output_dir: Path) -> dict[str, Path]:
        return run_step6a_audit_package_pipeline(
            report_manifest_path=self.m7_artifacts["report_manifest"],
            analysis_package_path=self.m6_artifacts["analysis_package"],
            certification_result_path=self.m5_artifacts["certification_result"],
            claim_evidence_graph_path=self.m4_artifacts["claim_evidence_graph"],
            evidence_repository_path=self.m3_artifacts["evidence_repository"],
            output_dir=output_dir,
        )

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
