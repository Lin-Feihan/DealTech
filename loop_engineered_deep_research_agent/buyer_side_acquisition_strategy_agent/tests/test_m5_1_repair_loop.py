from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.mandate_intake import load_mandate
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.research_planning import build_research_plan
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.repair_loop_executor import (
    MUST_NOT_USE_SOURCES,
    validate_repair_attempt_log,
    validate_targeted_source_discovery_plan,
)
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m2 import run_m2_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m3 import run_m3_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m4 import run_m4_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m5 import run_m5_pipeline
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m5_1 import M51FailClosed, run_m5_1_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class BuyerSideAcquisitionStrategyAgentM51RepairLoopTest(unittest.TestCase):
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
        self.research_gaps_path = m5_artifacts["research_gaps"]
        self.repair_plan_path = m5_artifacts["repair_plan"]

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
        self.assertEqual(len(targeted_plan["targeted_source_needs"]), 4)
        self.assertEqual(len(attempt_log["repair_attempts"]), 4)

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

        self.assertEqual(by_gap["RG-001"]["related_claim_ids"], ["CL-005"])
        self.assertEqual(by_gap["RG-001"]["missing_source_need_ids"], ["SN-005"])
        self.assertEqual(by_gap["RG-002"]["related_claim_ids"], ["CL-006"])
        self.assertEqual(by_gap["RG-003"]["related_claim_ids"], ["CL-007"])
        self.assertEqual(by_gap["RG-004"]["related_claim_ids"], ["CL-008"])

    def test_must_not_use_sources_are_present_on_every_query(self) -> None:
        targeted_plan = self._run_targeted_plan("m5_1_forbidden_sources")

        self.assertTrue(targeted_plan["targeted_search_queries"])
        for query in targeted_plan["targeted_search_queries"]:
            self.assertTrue(set(MUST_NOT_USE_SOURCES).issubset(set(query["must_not_use_sources"])))

    def test_generic_query_themes_are_present_without_real_case_markers(self) -> None:
        targeted_plan = self._run_targeted_plan("m5_1_queries")
        query_text = "\n".join(query["query_text"] for query in targeted_plan["targeted_search_queries"])

        self.assertIn("buyer target acquisition", query_text)
        self.assertIn("authoritative", query_text)
        self.assertIn("official filing source", query_text)
        for marker in ("ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget"):
            self.assertNotIn(marker, query_text)
        self.assertTrue(all(need["target_fact_or_question"] for need in targeted_plan["targeted_source_needs"]))

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
        self.assertEqual(len(attempt_log["unresolved_repairs"]), 4)

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
