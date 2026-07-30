from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.case_seed_loader import load_case_seed
from v3_lite_buyer_acquisition_runtime.runtime.evidence_repository_builder import validate_evidence_repository
from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m2 import run_m2_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m3 import M3FailClosed, run_m3_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM3EvidenceRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.mandate_path = RUNTIME_ROOT / "examples" / "fronthera_esker_alumis_mandate.json"
        self.case_seed_path = RUNTIME_ROOT / "case_seeds" / "fronthera_esker_alumis_case_seed.json"
        self.real_manifest_path = RUNTIME_ROOT / "retrieved_sources" / "fronthera" / "retrieved_sources_manifest.json"
        self.mandate = load_mandate(self.mandate_path)
        self.case_seed = load_case_seed(self.case_seed_path)
        self.research_plan = build_research_plan(self.mandate)
        self.research_plan_path = self.root / "research_plan.json"
        self.research_plan_path.write_text(json.dumps(self.research_plan, indent=2), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_raw_evidence_produces_evidence_repository(self) -> None:
        m2_artifacts = self._run_real_source_m2("m2_for_m3_valid")
        output_dir = self.root / "m3_valid"

        artifacts = run_m3_pipeline(
            raw_evidence_path=m2_artifacts["raw_evidence"],
            retrieved_sources_manifest_path=m2_artifacts["retrieved_sources_manifest"],
            output_dir=output_dir,
        )

        self.assertTrue(artifacts["evidence_repository"].exists())
        repository = json.loads(artifacts["evidence_repository"].read_text(encoding="utf-8"))
        validate_evidence_repository(repository)
        self.assertEqual(repository["generated_artifact"], "evidence_repository.json")
        self.assertEqual(repository["stage"], "M3_evidence_repository")
        self.assertTrue(repository["source_bounded"])
        self.assertFalse((output_dir / "claim_evidence_graph.json").exists())
        self.assertFalse((output_dir / "certification_result.json").exists())
        self.assertFalse((output_dir / "final_report.md").exists())

    def test_invalid_raw_evidence_fails_closed(self) -> None:
        m2_artifacts = self._run_real_source_m2("m2_for_m3_invalid")
        raw_evidence = json.loads(m2_artifacts["raw_evidence"].read_text(encoding="utf-8"))
        del raw_evidence["raw_evidence_items"][0]["evidence_time_relation_to_decision_date"]
        broken_raw_evidence_path = self.root / "broken_raw_evidence.json"
        broken_raw_evidence_path.write_text(json.dumps(raw_evidence, indent=2), encoding="utf-8")

        with self.assertRaises(M3FailClosed):
            run_m3_pipeline(
                raw_evidence_path=broken_raw_evidence_path,
                retrieved_sources_manifest_path=m2_artifacts["retrieved_sources_manifest"],
                output_dir=self.root / "m3_invalid",
            )

    def test_duplicate_raw_items_group_into_canonical_records(self) -> None:
        repository = self._run_real_source_repository("m3_dedup")
        records_by_key = {record["canonical_fact_key"]: record for record in repository["evidence_records"]}

        self.assertLess(repository["repository_quality_summary"]["evidence_record_count"], repository["repository_quality_summary"]["raw_evidence_item_count"])
        self.assertGreater(repository["repository_quality_summary"]["duplicate_groups_count"], 0)
        self.assertIn("milestone_consideration_cap_120m", records_by_key)
        self.assertEqual(records_by_key["milestone_consideration_cap_120m"]["source_count"], 4)
        self.assertIn("base_initial_consideration_60m", records_by_key)
        self.assertIn("fl2021_001_to_esker_to_alumis_entity_lineage", records_by_key)

    def test_failed_source_needs_become_source_gaps_and_not_evidence_records(self) -> None:
        repository = self._run_real_source_repository("m3_source_gaps")
        descriptions = {gap["missing_source_description"] for gap in repository["source_gaps"]}
        record_keys = {record["canonical_fact_key"] for record in repository["evidence_records"]}

        self.assertEqual(len(repository["source_gaps"]), 4)
        self.assertIn("Haisco / CNINFO / SZSE disclosure for Bohan Jin role and 2017 11.12% shareholding", descriptions)
        self.assertIn("Official patent-office records for TYK2 inhibitor chemistry", descriptions)
        self.assertIn("Direct source on Bohan Jin personal realized proceeds", descriptions)
        self.assertIn("Immediately pre-2021 FronThera cap table source", descriptions)
        self.assertNotIn("personal_proceeds_not_verified", record_keys)
        self.assertNotIn("pre_sale_cap_table_gap", record_keys)
        self.assertTrue(all(record["support_status"] != "source_gap" for record in repository["evidence_records"]))

    def test_temporal_classifications_are_preserved(self) -> None:
        repository = self._run_real_source_repository("m3_temporal")
        records_by_key = {record["canonical_fact_key"]: record for record in repository["evidence_records"]}

        self.assertEqual(records_by_key["milestone_consideration_cap_120m"]["evidence_time_relation_to_decision_date"], "at_decision")
        self.assertEqual(records_by_key["milestone_consideration_cap_120m"]["permitted_use"], "transaction_terms_verification")
        self.assertEqual(records_by_key["alumis_pipeline_current_envudeucitinib"]["evidence_time_relation_to_decision_date"], "retrospective")
        self.assertEqual(records_by_key["alumis_pipeline_current_envudeucitinib"]["permitted_use"], "retrospective_outcome_validation")
        for record in repository["evidence_records"]:
            if record["evidence_time_relation_to_decision_date"] in {"post_decision", "retrospective"}:
                self.assertNotEqual(record["permitted_use"], "ex_ante_deal_evaluation")

    def test_no_180m_fact_is_inferred_without_direct_raw_evidence(self) -> None:
        m2_artifacts = self._run_real_source_m2("m2_for_m3_no_180")
        raw_evidence = json.loads(m2_artifacts["raw_evidence"].read_text(encoding="utf-8"))
        repository = self._run_m3_from_artifacts(m2_artifacts, "m3_no_180")
        record_keys = {record["canonical_fact_key"] for record in repository["evidence_records"]}

        self.assertFalse(any(item["raw_fact_type"] == "headline_maximum_value" for item in raw_evidence["raw_evidence_items"]))
        self.assertFalse(any("180m" in key or "headline_maximum_value" in key for key in record_keys))

    def _run_real_source_m2(self, label: str) -> dict[str, Path]:
        return run_m2_pipeline(
            mandate_path=self.mandate_path,
            research_plan_path=self.research_plan_path,
            case_seed_path=self.case_seed_path,
            output_dir=self.root / label,
            retrieval_mode="manual_retrieved_sources",
            retrieved_sources_manifest_path=self.real_manifest_path,
        )

    def _run_real_source_repository(self, label: str) -> dict:
        m2_artifacts = self._run_real_source_m2(f"{label}_m2")
        return self._run_m3_from_artifacts(m2_artifacts, label)

    def _run_m3_from_artifacts(self, m2_artifacts: dict[str, Path], label: str) -> dict:
        artifacts = run_m3_pipeline(
            raw_evidence_path=m2_artifacts["raw_evidence"],
            retrieved_sources_manifest_path=m2_artifacts["retrieved_sources_manifest"],
            output_dir=self.root / label,
        )
        return json.loads(artifacts["evidence_repository"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
