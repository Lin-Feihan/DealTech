from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.report_rendering_gate import validate_report_manifest
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m7 import M7FailClosed, run_m7_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM7ReportRenderingGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.analysis_package_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m6" / "analysis_package.json"
        self.certification_result_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "certification_result.json"
        self.repair_plan_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "repair_plan.json"

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
        self.assertNotIn("Bohan", blocked)
        self.assertNotIn("$180M", blocked)

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

        self.assertEqual(set(repairs_by_id), {"RP-001", "RP-002", "RP-003", "RP-004", "RP-005"})
        self.assertTrue(all("complete source-bounded repair" in repair["reason"] for repair in repairs_by_id.values()))
        repair_text = json.dumps(manifest["required_repairs_before_report"])
        for marker in ("FronThera", "Bohan", "TYK2", "Alumis", "Esker", "$180M", "11.12"):
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
