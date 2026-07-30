from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.repair_loop_executor import (
    MUST_NOT_USE_SOURCES,
    validate_repair_attempt_log,
    validate_targeted_source_discovery_plan,
)
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m5_1 import M51FailClosed, run_m5_1_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM51RepairLoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.certification_result_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "certification_result.json"
        self.research_gaps_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "research_gaps.json"
        self.repair_plan_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m5" / "repair_plan.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_repair_plan_produces_dry_run_artifacts(self) -> None:
        output_dir = self.root / "m5_1_valid"

        artifacts = run_m5_1_pipeline(
            self.certification_result_path,
            self.research_gaps_path,
            self.repair_plan_path,
            output_dir,
        )

        targeted_plan = self._load(artifacts["targeted_source_discovery_plan"])
        attempt_log = self._load(artifacts["repair_attempt_log"])
        validate_targeted_source_discovery_plan(targeted_plan)
        validate_repair_attempt_log(attempt_log)
        self.assertEqual(targeted_plan["generated_artifact"], "targeted_source_discovery_plan.json")
        self.assertEqual(targeted_plan["target_state"], "M2_source_retrieval")
        self.assertEqual(attempt_log["generated_artifact"], "repair_attempt_log.json")
        self.assertEqual(len(targeted_plan["targeted_source_needs"]), 5)
        self.assertEqual(len(attempt_log["repair_attempts"]), 5)

    def test_invalid_repair_plan_fails_closed(self) -> None:
        repair_plan = self._load(self.repair_plan_path)
        repair_plan["repair_steps"][0]["target_state"] = "final_report_generation"
        broken_path = self.root / "broken_repair_plan.json"
        broken_path.write_text(json.dumps(repair_plan, indent=2), encoding="utf-8")

        with self.assertRaises(M51FailClosed):
            run_m5_1_pipeline(self.certification_result_path, self.research_gaps_path, broken_path, self.root / "m5_1_invalid")

    def test_repair_targets_point_back_to_m2_source_retrieval(self) -> None:
        targeted_plan = self._run_targeted_plan("m5_1_m2_targets")

        self.assertEqual(targeted_plan["target_state"], "M2_source_retrieval")
        self.assertTrue(targeted_plan["targeted_source_needs"])
        self.assertTrue(all("M2" in need["expected_downstream_update"] or "M5" in need["expected_downstream_update"] for need in targeted_plan["targeted_source_needs"]))
        high_priority_needs = [need for need in targeted_plan["targeted_source_needs"] if need["priority"] == "high"]
        self.assertEqual(len(high_priority_needs), 4)
        self.assertTrue(all(need["source_tier_required"] == "Tier 1" for need in high_priority_needs))

    def test_targeted_source_needs_preserve_claim_and_gap_ids(self) -> None:
        targeted_plan = self._run_targeted_plan("m5_1_ids")
        by_gap = {need["original_research_gap_id"]: need for need in targeted_plan["targeted_source_needs"]}

        self.assertEqual(by_gap["RG-001"]["related_claim_ids"], ["CL-012"])
        self.assertEqual(by_gap["RG-001"]["missing_source_need_ids"], ["SN-005"])
        self.assertEqual(by_gap["RG-002"]["related_claim_ids"], ["CL-013"])
        self.assertEqual(by_gap["RG-003"]["related_claim_ids"], ["CL-014"])
        self.assertEqual(by_gap["RG-004"]["related_claim_ids"], ["CL-015"])
        self.assertEqual(by_gap["RG-005"]["related_claim_ids"], ["CL-011"])

    def test_must_not_use_sources_are_present_on_every_query(self) -> None:
        targeted_plan = self._run_targeted_plan("m5_1_forbidden_sources")

        self.assertTrue(targeted_plan["targeted_search_queries"])
        for query in targeted_plan["targeted_search_queries"]:
            self.assertTrue(set(MUST_NOT_USE_SOURCES).issubset(set(query["must_not_use_sources"])))

    def test_expected_fronthera_query_themes_are_present(self) -> None:
        targeted_plan = self._run_targeted_plan("m5_1_queries")
        query_text = "\n".join(query["query_text"] for query in targeted_plan["targeted_search_queries"])

        self.assertIn("CNINFO SZSE Haisco FronThera Bohan Jin 11.12", query_text)
        self.assertIn("WIPO USPTO PCT/US2019/057485 TYK2 FronThera", query_text)
        self.assertIn("WIPO USPTO PCT/US2020/021850 TYK2 FronThera", query_text)
        self.assertIn("official source FronThera pre-2021 cap table ownership", query_text)
        self.assertIn("official source Bohan Jin personal proceeds", query_text)
        self.assertIn("SEC FronThera acquisition $180 million maximum aggregate value", query_text)

    def test_repair_attempt_log_is_dry_run_only(self) -> None:
        artifacts = run_m5_1_pipeline(
            self.certification_result_path,
            self.research_gaps_path,
            self.repair_plan_path,
            self.root / "m5_1_attempts",
        )
        attempt_log = self._load(artifacts["repair_attempt_log"])

        self.assertEqual(attempt_log["next_action"], "supply_manual_authoritative_sources_or_configure_retrieval_provider_before_running_M2_repair")
        self.assertTrue(all(attempt["status"] in {"planned", "deferred_provider_unavailable"} for attempt in attempt_log["repair_attempts"]))
        self.assertTrue(all(attempt["output_artifact_generated"] is False for attempt in attempt_log["repair_attempts"]))
        self.assertEqual(len(attempt_log["unresolved_repairs"]), 5)

    def test_no_evidence_or_report_artifacts_are_generated(self) -> None:
        output_dir = self.root / "m5_1_forbidden_outputs"

        run_m5_1_pipeline(self.certification_result_path, self.research_gaps_path, self.repair_plan_path, output_dir)

        for filename in (
            "raw_evidence.json",
            "evidence_repository.json",
            "claim_evidence_graph.json",
            "analysis_package.json",
            "final_report.md",
        ):
            self.assertFalse((output_dir / filename).exists())

    def _run_targeted_plan(self, label: str) -> dict:
        artifacts = run_m5_1_pipeline(
            self.certification_result_path,
            self.research_gaps_path,
            self.repair_plan_path,
            self.root / label,
        )
        return self._load(artifacts["targeted_source_discovery_plan"])

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
