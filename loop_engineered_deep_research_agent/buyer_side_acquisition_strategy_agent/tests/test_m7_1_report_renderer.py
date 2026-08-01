from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.mandate_intake import load_mandate
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.research_planning import build_research_plan
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m2 import run_m2_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m3 import run_m3_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m4 import run_m4_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m5 import run_m5_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m6 import run_m6_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m7 import run_m7_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m7_render import main as render_main
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m7_render import run_m7_render_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class BuyerSideAcquisitionStrategyAgentM71ReportRendererTest(unittest.TestCase):
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
        m6_artifacts = run_m6_pipeline(
            m5_artifacts["certification_result"],
            m4_artifacts["claim_evidence_graph"],
            m3_artifacts["evidence_repository"],
            m5_artifacts["research_gaps"],
            m5_artifacts["repair_plan"],
            self.root / "m6",
        )
        m7_artifacts = run_m7_pipeline(
            m6_artifacts["analysis_package"],
            m5_artifacts["certification_result"],
            m5_artifacts["repair_plan"],
            self.root / "m7",
        )
        self.blocked_report_manifest_path = m7_artifacts["report_manifest"]
        self.blocked_analysis_package_path = m6_artifacts["analysis_package"]
        self.blocked_certification_result_path = m5_artifacts["certification_result"]
        self.ready_fixture_dir = RUNTIME_ROOT / "tests" / "fixtures" / "report_ready_case"
        self.ready_report_manifest_path = self.ready_fixture_dir / "report_manifest.json"
        self.ready_analysis_package_path = self.ready_fixture_dir / "analysis_package.json"
        self.ready_certification_result_path = self.ready_fixture_dir / "certification_result.json"
        self.ready_m6b_fixture_dir = RUNTIME_ROOT / "tests" / "fixtures" / "report_ready_m6b_case"
        self.ready_m6b_report_manifest_path = self.ready_m6b_fixture_dir / "report_manifest.json"
        self.ready_m6b_analysis_package_path = self.ready_m6b_fixture_dir / "analysis_package.json"
        self.ready_m6b_certification_result_path = self.ready_m6b_fixture_dir / "certification_result.json"
        self.ready_m6b_audit_package_path = self.ready_m6b_fixture_dir / "audit_package.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_blocked_synthetic_manifest_does_not_generate_final_report(self) -> None:
        output_dir = self.root / "blocked_synthetic"

        result = run_m7_render_pipeline(
            self.blocked_report_manifest_path,
            self.blocked_analysis_package_path,
            self.blocked_certification_result_path,
            output_dir,
        )

        self.assertEqual(result["rendering_status"], "blocked")
        self.assertFalse(result["final_report_generated"])
        self.assertIsNone(result["final_report_path"])
        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertIn("report_manifest.rendering_status is blocked_by_repair_required", self._blocked_reason_text(result))

    def test_ready_to_render_fixture_generates_final_report(self) -> None:
        output_dir = self.root / "ready_fixture"

        result = self._run_ready_fixture(output_dir)

        self.assertEqual(result["rendering_status"], "rendered")
        self.assertTrue(result["final_report_generated"])
        self.assertTrue((output_dir / "final_report.md").exists())
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")
        self.assertIn("# Buyer-Side Acquisition Analysis Report", report)
        self.assertIn("## Executive Summary", report)
        self.assertIn("## Transaction Snapshot", report)
        self.assertIn("## Buyer Mandate And Decision Context", report)
        self.assertIn("## Target Overview", report)
        self.assertIn("## Strategic Rationale", report)
        self.assertIn("## Market And Competitive Context", report)
        self.assertIn("## Deal Structure And Transaction Economics", report)
        self.assertIn("## Valuation And Price Reasonableness", report)
        self.assertIn("## Synergy And Value Creation", report)
        self.assertIn("## Key Risks And Red Flags", report)
        self.assertIn("## Due Diligence Priorities", report)
        self.assertIn("## Decision Readiness Or Recommendation", report)
        self.assertIn("## Limitations", report)
        self.assertIn("## Appendix: Source List", report)

    def test_renderer_refuses_when_final_report_allowed_is_false(self) -> None:
        analysis_package = self._load(self.ready_analysis_package_path)
        analysis_package["final_report_allowed"] = False
        analysis_path = self._write_json("analysis_package_final_blocked.json", analysis_package)
        output_dir = self.root / "final_report_false"

        result = run_m7_render_pipeline(
            self.ready_report_manifest_path,
            analysis_path,
            self.ready_certification_result_path,
            output_dir,
        )

        self.assertEqual(result["rendering_status"], "blocked")
        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertIn("analysis_package.final_report_allowed is not true", self._blocked_reason_text(result))

    def test_renderer_refuses_when_certification_is_repair_required(self) -> None:
        certification_result = self._load(self.ready_certification_result_path)
        certification_result["overall_certification_status"] = "repair_required"
        cert_path = self._write_json("certification_result_repair_required.json", certification_result)
        output_dir = self.root / "cert_repair_required"

        result = run_m7_render_pipeline(
            self.ready_report_manifest_path,
            self.ready_analysis_package_path,
            cert_path,
            output_dir,
        )

        self.assertEqual(result["rendering_status"], "blocked")
        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertIn("certification_result.overall_certification_status is repair_required", self._blocked_reason_text(result))

    def test_renderer_does_not_include_unsupported_claim_as_fact(self) -> None:
        output_dir = self.root / "unsupported_exclusion"

        self._run_ready_fixture(output_dir)
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")

        self.assertNotIn("Unsupported fixture claim should never appear as a factual report finding", report)
        self.assertNotIn("CL-RF-999", report)

    def test_renderer_includes_caveats_and_source_gaps_when_provided(self) -> None:
        output_dir = self.root / "m6b_caveats_and_gaps"

        self._run_ready_m6b_fixture(output_dir)
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")

        self.assertIn("Return threshold remains unavailable", report)
        self.assertIn("Confirm buyer-specific return threshold before recommendation use", report)
        self.assertIn("Limitations", report)

    def test_main_body_hides_internal_engineering_markers(self) -> None:
        output_dir = self.root / "clean_main_body"

        self._run_ready_fixture(output_dir)
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")
        main_body = report.split("## Appendix: Source List", maxsplit=1)[0]

        for marker in ("CL-RF-001", "ER-RF-001", "certification_status", "raw_evidence_id", "claim_node", "evidence_record"):
            self.assertNotIn(marker, main_body)

    def test_m6b_fixture_renders_from_professional_structure_mapping(self) -> None:
        output_dir = self.root / "ready_m6b_fixture"

        result = self._run_ready_m6b_fixture(output_dir)

        self.assertEqual(result["rendering_status"], "rendered")
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")
        self.assertIn("Analyst interpretation: the transaction perimeter is sufficiently defined for a limited buyer-side review", report)
        self.assertIn("Buyer implication: price reasonableness should be treated as a diligence question", report)
        self.assertIn("Decision impact: unresolved gates prevent final recommendation language", report)
        self.assertNotIn("transaction_terms_analysis", report)
        self.assertNotIn("milestone_economics_analysis", report)
        self.assertNotIn("entity_and_asset_lineage_analysis", report)

    def test_m6b_main_body_hides_internal_ids_and_unauthorized_recommendations(self) -> None:
        output_dir = self.root / "ready_m6b_clean"

        self._run_ready_m6b_fixture(output_dir)
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")
        main_body = report.split("## Appendix: Source List", maxsplit=1)[0]

        for marker in ("CL-", "ER-", "claim_id", "raw_evidence_id", "certification_status", "claim_node", "evidence_record", "support_level"):
            self.assertNotIn(marker, main_body)
        for term in ("Proceed", "Proceed with Conditions", "Renegotiate", "Defer", "Walk Away", "proceed", "renegotiate", "defer", "walk-away"):
            self.assertNotIn(term, report)
        self.assertIn("A final acquisition recommendation is not authorized by the upstream gates. This report should be used only for decision-readiness review.", report)

    def test_m6b_optional_audit_package_populates_source_appendix(self) -> None:
        output_dir = self.root / "ready_m6b_audit_package"

        result = run_m7_render_pipeline(
            self.ready_m6b_report_manifest_path,
            self.ready_m6b_analysis_package_path,
            self.ready_m6b_certification_result_path,
            output_dir,
            audit_package_path=self.ready_m6b_audit_package_path,
        )

        self.assertEqual(result["rendering_status"], "rendered")
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")
        self.assertIn("M6B fixture source memorandum", report)
        self.assertIn("Detailed claim, evidence, and source mapping remains in audit_package.json", report)

    def test_m6b_optional_audit_package_cli_argument(self) -> None:
        output_dir = self.root / "ready_m6b_cli_audit_package"

        exit_code = render_main(
            [
                "--report-manifest",
                str(self.ready_m6b_report_manifest_path),
                "--analysis-package",
                str(self.ready_m6b_analysis_package_path),
                "--certification-result",
                str(self.ready_m6b_certification_result_path),
                "--audit-package",
                str(self.ready_m6b_audit_package_path),
                "--output-dir",
                str(output_dir),
            ]
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue((output_dir / "final_report.md").exists())

    def test_no_recommendation_decision_generated(self) -> None:
        output_dir = self.root / "no_recommendation_decision"

        self._run_ready_fixture(output_dir)

        self.assertTrue((output_dir / "final_report.md").exists())
        self.assertFalse((output_dir / "recommendation_decision.json").exists())
        self.assertFalse((output_dir / "valuation_analysis.json").exists())
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")
        self.assertNotIn("Proceed", report)
        self.assertNotIn("Renegotiate", report)
        self.assertNotIn("Defer", report)
        self.assertNotIn("Walk Away", report)
        self.assertIn("A final acquisition recommendation is not authorized by the upstream gates", report)

    def _run_ready_fixture(self, output_dir: Path) -> dict:
        return run_m7_render_pipeline(
            self.ready_report_manifest_path,
            self.ready_analysis_package_path,
            self.ready_certification_result_path,
            output_dir,
        )

    def _run_ready_m6b_fixture(self, output_dir: Path) -> dict:
        return run_m7_render_pipeline(
            self.ready_m6b_report_manifest_path,
            self.ready_m6b_analysis_package_path,
            self.ready_m6b_certification_result_path,
            output_dir,
        )

    def _blocked_reason_text(self, result: dict) -> str:
        return "\n".join(reason["reason"] for reason in result["blocked_reasons"])

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, filename: str, payload: dict) -> Path:
        path = self.root / filename
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
