from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.report_rendering_gate import validate_report_manifest
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m2 import run_m2_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m3 import run_m3_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m4 import run_m4_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m5 import run_m5_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m6 import run_m6_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m7 import M7FailClosed, run_m7_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM7ReportRenderingGateTest(unittest.TestCase):
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
        self.analysis_package_path = m6_artifacts["analysis_package"]
        self.certification_result_path = m5_artifacts["certification_result"]
        self.repair_plan_path = m5_artifacts["repair_plan"]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_m6_and_m5_inputs_produce_report_manifest(self) -> None:
        output_dir = self.root / "m7_valid"

        artifacts = self._run_m7(output_dir)
        report_manifest = self._load(artifacts["report_manifest"])

        validate_report_manifest(report_manifest)
        self.assertTrue(artifacts["report_manifest"].exists())
        self.assertEqual(report_manifest["generated_artifact"], "report_manifest.json")
        self.assertEqual(report_manifest["stage"], "M7_report_rendering_gate")
        self.assertTrue(report_manifest["source_bounded"])

    def test_invalid_input_fails_closed(self) -> None:
        analysis_package = self._load(self.analysis_package_path)
        del analysis_package["final_report_allowed"]
        broken_path = self.root / "broken_analysis_package.json"
        broken_path.write_text(json.dumps(analysis_package, indent=2), encoding="utf-8")

        with self.assertRaises(M7FailClosed):
            run_m7_pipeline(broken_path, self.certification_result_path, self.repair_plan_path, self.root / "m7_invalid")

    def test_final_report_allowed_false_blocks_final_report(self) -> None:
        output_dir = self.root / "m7_final_block"

        manifest = self._run_manifest(output_dir)

        self.assertEqual(manifest["rendering_status"], "blocked_by_repair_required")
        self.assertFalse(manifest["final_report_generated"])
        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertIn("analysis_package final_report_allowed is false", self._blocked_reason_text(manifest))

    def test_recommendation_allowed_false_blocks_recommendation_decision(self) -> None:
        output_dir = self.root / "m7_recommendation_block"

        manifest = self._run_manifest(output_dir)

        self.assertFalse((output_dir / "recommendation_decision.json").exists())
        self.assertIn("analysis_package recommendation_allowed is false", self._blocked_reason_text(manifest))

    def test_repair_required_blocks_rendering(self) -> None:
        manifest = self._run_manifest(self.root / "m7_repair_required")

        self.assertEqual(manifest["rendering_status"], "blocked_by_repair_required")
        self.assertIn("certification_result overall status is repair_required", self._blocked_reason_text(manifest))
        self.assertIn("analysis_readiness_status is limited_by_repair_required", self._blocked_reason_text(manifest))

    def test_unresolved_human_review_items_block_rendering(self) -> None:
        manifest = self._run_manifest(self.root / "m7_human_review")

        self.assertTrue(manifest["human_review_required"])
        self.assertIn("human review items remain unresolved", self._blocked_reason_text(manifest))

    def test_report_manifest_lists_required_blocked_reasons(self) -> None:
        manifest = self._run_manifest(self.root / "m7_blocked_reasons")
        blocked = self._blocked_reason_text(manifest)

        self.assertIn("repair plan has unresolved steps", blocked)
        self.assertIn("one or more claims are failed, unsupported, source-gap-blocked, or require review", blocked)
        self.assertIn("analysis package contains blocked analysis items", blocked)
        self.assertNotIn("ForbiddenTarget", blocked)
        self.assertNotIn("ForbiddenTarget", blocked)

    def test_allowed_and_excluded_sections_are_gate_metadata_only(self) -> None:
        manifest = self._run_manifest(self.root / "m7_sections")
        allowed = {section["section_name"] for section in manifest["allowed_sections"]}
        excluded = {section["section_name"] for section in manifest["excluded_sections"]}

        self.assertEqual(
            allowed,
            {
                "source-bounded analysis package",
                "certification summary",
                "repair plan",
                "source gap summary",
            },
        )
        self.assertIn("investment recommendation", excluded)
        self.assertIn("final proceed or walk-away decision", excluded)
        self.assertIn("uncaveated valuation or deal-value conclusion", excluded)
        self.assertIn("unsupported value-transfer analysis", excluded)
        self.assertIn("unsupported ownership analysis", excluded)
        self.assertIn("unsupported legal or diligence conclusion", excluded)
        self.assertIn("final report narrative", excluded)

    def test_required_repairs_before_report_are_carried_forward(self) -> None:
        manifest = self._run_manifest(self.root / "m7_repairs")
        repairs_by_id = {repair["repair_step_id"]: repair for repair in manifest["required_repairs_before_report"]}

        self.assertEqual(set(repairs_by_id), {"RP-001", "RP-002", "RP-003", "RP-004"})
        self.assertTrue(all("complete source-bounded repair" in repair["reason"] for repair in repairs_by_id.values()))
        repair_text = json.dumps(manifest["required_repairs_before_report"])
        for marker in ("ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget"):
            self.assertNotIn(marker, repair_text)

    def test_no_final_report_or_recommendation_or_valuation_artifacts_are_generated(self) -> None:
        output_dir = self.root / "m7_forbidden_outputs"

        manifest = self._run_manifest(output_dir)

        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertFalse((output_dir / "recommendation_decision.json").exists())
        self.assertFalse((output_dir / "valuation_analysis.json").exists())
        self.assertNotIn("rendered_report_sections", manifest)
        self.assertNotIn("recommendation_decision", manifest)
        self.assertNotIn("valuation_analysis", manifest)
        self.assertEqual([path.name for path in output_dir.iterdir()], ["report_manifest.json"])

    def _run_manifest(self, output_dir: Path) -> dict:
        artifacts = self._run_m7(output_dir)
        return self._load(artifacts["report_manifest"])

    def _run_m7(self, output_dir: Path) -> dict[str, Path]:
        return run_m7_pipeline(
            self.analysis_package_path,
            self.certification_result_path,
            self.repair_plan_path,
            output_dir,
        )

    def _blocked_reason_text(self, manifest: dict) -> str:
        return "\n".join(reason["reason"] for reason in manifest["blocked_reasons"])

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
