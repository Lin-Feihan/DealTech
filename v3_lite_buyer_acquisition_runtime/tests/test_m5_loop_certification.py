from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.claim_certifier import validate_certification_result
from v3_lite_buyer_acquisition_runtime.runtime.repair_plan_builder import validate_repair_plan, validate_research_gaps
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m5 import M5FailClosed, run_m5_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM5LoopCertificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.graph_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m4" / "claim_evidence_graph.json"
        self.repository_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m3" / "evidence_repository.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_graph_produces_m5_artifacts(self) -> None:
        output_dir = self.root / "m5_valid"

        artifacts = run_m5_pipeline(self.graph_path, self.repository_path, output_dir)

        self.assertTrue(artifacts["certification_result"].exists())
        self.assertTrue(artifacts["research_gaps"].exists())
        self.assertTrue(artifacts["repair_plan"].exists())
        certification = self._load(artifacts["certification_result"])
        research_gaps = self._load(artifacts["research_gaps"])
        repair_plan = self._load(artifacts["repair_plan"])
        validate_certification_result(certification)
        validate_research_gaps(research_gaps)
        validate_repair_plan(repair_plan)
        self.assertEqual(certification["generated_artifact"], "certification_result.json")
        self.assertEqual(certification["overall_certification_status"], "repair_required")
        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertFalse((output_dir / "analysis_package.json").exists())

    def test_invalid_graph_fails_closed(self) -> None:
        graph = self._load(self.graph_path)
        graph["evidence_edges"][0]["claim_id"] = "CL-DOES-NOT-EXIST"
        broken_graph_path = self.root / "broken_claim_evidence_graph.json"
        broken_graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

        with self.assertRaises(M5FailClosed):
            run_m5_pipeline(broken_graph_path, self.repository_path, self.root / "m5_invalid")

    def test_certified_claims_have_supporting_evidence(self) -> None:
        certification = self._run_certification("m5_support")

        for claim_cert in certification["claim_certifications"]:
            if claim_cert["certification_status"] in {"certified", "certified_with_caveat"}:
                self.assertTrue(claim_cert["supporting_evidence_record_ids"])
                self.assertEqual(claim_cert["citation_check_status"], "passed")

    def test_gap_only_claims_cannot_be_certified(self) -> None:
        certification = self._run_certification("m5_gap_claims")
        blocked = {claim["claim_id"]: claim for claim in certification["claim_certifications"] if claim["related_source_gap_ids"]}

        self.assertEqual(blocked["CL-012"]["certification_status"], "blocked_by_source_gap")
        self.assertEqual(blocked["CL-013"]["certification_status"], "blocked_by_source_gap")
        self.assertEqual(blocked["CL-015"]["certification_status"], "blocked_by_source_gap")
        self.assertNotIn(blocked["CL-012"]["certification_status"], {"certified", "certified_with_caveat"})

    def test_bohan_jin_personal_proceeds_remains_unsupported_or_blocked(self) -> None:
        certification = self._run_certification("m5_personal_proceeds")
        personal = self._claim_certification(certification, "CL-014")

        self.assertIn(personal["certification_status"], {"unsupported", "blocked_by_source_gap"})
        self.assertFalse(personal["supporting_evidence_record_ids"])
        self.assertTrue(personal["requires_human_review"])

    def test_numeric_verification_is_not_inferred_without_explicit_formula(self) -> None:
        certification = self._run_certification("m5_numeric")
        numeric_results = certification["numeric_verification_results"]

        self.assertEqual(numeric_results, [])
        self.assertTrue(all(cert["numeric_check_status"] == "not_applicable" for cert in certification["claim_certifications"]))

    def test_post_decision_evidence_does_not_support_ex_ante_claims(self) -> None:
        certification = self._run_certification("m5_temporal")

        temporal_by_claim = {result["claim_id"]: result for result in certification["temporal_verification_results"]}
        self.assertEqual(temporal_by_claim["CL-008"]["verification_status"], "passed_with_caveat")
        self.assertEqual(temporal_by_claim["CL-009"]["verification_status"], "passed_with_caveat")
        self.assertIn("retrospective validation only", temporal_by_claim["CL-008"]["caveat"])

    def test_source_gaps_become_research_gaps(self) -> None:
        artifacts = run_m5_pipeline(self.graph_path, self.repository_path, self.root / "m5_gaps")
        research_gaps = self._load(artifacts["research_gaps"])
        descriptions = {gap["gap_description"] for gap in research_gaps["research_gaps"]}

        self.assertIn("Haisco / CNINFO / SZSE disclosure for Bohan Jin role and 2017 11.12% shareholding", descriptions)
        self.assertIn("Official patent-office records for TYK2 inhibitor chemistry", descriptions)
        self.assertIn("Direct source on Bohan Jin personal realized proceeds", descriptions)
        self.assertIn("Immediately pre-2021 FronThera cap table source", descriptions)
        self.assertIn("Optional direct source for headline $180M maximum value if final report wording needs a direct quoted deal value.", descriptions)

    def test_repair_plan_points_source_gaps_to_m2_source_retrieval(self) -> None:
        artifacts = run_m5_pipeline(self.graph_path, self.repository_path, self.root / "m5_repair")
        repair_plan = self._load(artifacts["repair_plan"])
        source_gap_steps = [step for step in repair_plan["repair_steps"] if step["priority"] == "high"]

        self.assertTrue(source_gap_steps)
        self.assertTrue(all(step["target_state"] == "M2_source_retrieval" for step in source_gap_steps))
        self.assertTrue(any(step["target_state"] == "M2_source_retrieval_or_M5_numeric_verification" for step in repair_plan["repair_steps"]))

    def test_no_final_report_or_analysis_package_generated(self) -> None:
        output_dir = self.root / "m5_forbidden_outputs"

        run_m5_pipeline(self.graph_path, self.repository_path, output_dir)

        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertFalse((output_dir / "analysis_package.json").exists())

    def _run_certification(self, label: str) -> dict:
        artifacts = run_m5_pipeline(self.graph_path, self.repository_path, self.root / label)
        return self._load(artifacts["certification_result"])

    def _claim_certification(self, certification: dict, claim_id: str) -> dict:
        return next(claim for claim in certification["claim_certifications"] if claim["claim_id"] == claim_id)

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
