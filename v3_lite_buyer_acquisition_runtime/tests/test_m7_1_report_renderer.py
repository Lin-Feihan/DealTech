from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m7_render import run_m7_render_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM71ReportRendererTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.blocked_report_manifest_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m7" / "report_manifest.json"
        self.blocked_analysis_package_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m6" / "analysis_package.json"
        self.blocked_certification_result_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "certification_result.json"
        self.ready_fixture_dir = RUNTIME_ROOT / "tests" / "fixtures" / "report_ready_case"
        self.ready_report_manifest_path = self.ready_fixture_dir / "report_manifest.json"
        self.ready_analysis_package_path = self.ready_fixture_dir / "analysis_package.json"
        self.ready_certification_result_path = self.ready_fixture_dir / "certification_result.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_blocked_fronthera_manifest_does_not_generate_final_report(self) -> None:
        output_dir = self.root / "blocked_fronthera"

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
        self.assertIn("# Evidence-Bounded Acquisition Analysis Report", report)
        self.assertIn("## Source and Certification Basis", report)
        self.assertIn("## Executive Summary", report)
        self.assertIn("## Transaction Background", report)
        self.assertIn("## Transaction Terms", report)
        self.assertIn("## Milestone Economics", report)
        self.assertIn("## Entity and Asset Lineage", report)
        self.assertIn("## Evidence Gaps and Limitations", report)
        self.assertIn("## Human Review Notes", report)
        self.assertIn("## Certification Caveats", report)
        self.assertIn("## Appendix: Claim-Evidence References", report)

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
        self.assertNotIn("CL-RF-999: Unsupported fixture claim", report)
        self.assertIn("Open source gap: management interview transcript not available", report)

    def test_renderer_includes_caveats_and_source_gaps_when_provided(self) -> None:
        output_dir = self.root / "caveats_and_gaps"

        self._run_ready_fixture(output_dir)
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")

        self.assertIn("Milestone consideration is a cap and remains caveated", report)
        self.assertIn("Caveat preserved", report)
        self.assertIn("Evidence Gaps and Limitations", report)
        self.assertIn("This is a limitation, not a factual finding", report)

    def test_no_recommendation_decision_generated(self) -> None:
        output_dir = self.root / "no_recommendation_decision"

        self._run_ready_fixture(output_dir)

        self.assertTrue((output_dir / "final_report.md").exists())
        self.assertFalse((output_dir / "recommendation_decision.json").exists())
        self.assertFalse((output_dir / "valuation_analysis.json").exists())
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")
        self.assertNotIn("Proceed", report)
        self.assertNotIn("Walk Away", report)

    def _run_ready_fixture(self, output_dir: Path) -> dict:
        return run_m7_render_pipeline(
            self.ready_report_manifest_path,
            self.ready_analysis_package_path,
            self.ready_certification_result_path,
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
