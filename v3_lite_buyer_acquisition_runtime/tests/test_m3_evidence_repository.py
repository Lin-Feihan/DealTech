from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.case_seed_loader import load_case_seed
from v3_lite_buyer_acquisition_runtime.runtime.evidence_repository_builder import canonicalize_raw_evidence_item, validate_evidence_repository
from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m2 import run_m2_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m3 import M3FailClosed, run_m3_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM3EvidenceRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.mandate_path = RUNTIME_ROOT / "examples" / "synthetic_acquisition_mandate.json"
        self.case_seed_path = RUNTIME_ROOT / "case_seeds" / "synthetic_acquisition_case_seed.json"
        self.real_manifest_path = RUNTIME_ROOT / "retrieved_sources" / "synthetic_acquisition" / "retrieved_sources_manifest.json"
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
        forbidden_key_markers = ("base_initial", "milestone_consideration_cap", "headline_maximum", "180m")
        self.assertFalse(any(any(marker in key for marker in forbidden_key_markers) for key in records_by_key))
        self.assertTrue(any(record["source_count"] > 1 for record in repository["evidence_records"]))
        self.assertTrue(all("structured_attributes" in record for record in repository["evidence_records"]))
        self.assertTrue(any(record["canonical_fact_type"] in {"transaction_timing", "transaction_parties", "financing_or_payment_mechanics"} for record in repository["evidence_records"]))

    def test_failed_source_needs_become_source_gaps_and_not_evidence_records(self) -> None:
        repository = self._run_real_source_repository("m3_source_gaps")
        descriptions = {gap["missing_source_description"] for gap in repository["source_gaps"]}
        record_keys = {record["canonical_fact_key"] for record in repository["evidence_records"]}

        self.assertEqual(len(repository["source_gaps"]), 4)
        self.assertIn("Missing ownership, governance, cap table, or seller-economics evidence", descriptions)
        self.assertIn("Missing clinical, regulatory, or approval evidence", descriptions)
        self.assertIn("Missing valuation or financial-support evidence", descriptions)
        self.assertNotIn("personal_proceeds_not_verified", record_keys)
        self.assertNotIn("pre_sale_cap_table_gap", record_keys)
        self.assertTrue(all(record["support_status"] != "source_gap" for record in repository["evidence_records"]))

    def test_temporal_classifications_are_preserved(self) -> None:
        repository = self._run_real_source_repository("m3_temporal")
        self.assertTrue(
            any(
                record["canonical_fact_type"] in {"transaction_timing", "transaction_parties", "financing_or_payment_mechanics"}
                and record["evidence_time_relation_to_decision_date"] == "at_decision"
                and record["permitted_use"] == "transaction_terms_verification"
                for record in repository["evidence_records"]
            )
        )
        self.assertTrue(
            any(
                "retrospective" in record.get("supporting_time_relations", [])
                and record["permitted_use"] == "retrospective_outcome_validation"
                for record in repository["evidence_records"]
            )
        )
        for record in repository["evidence_records"]:
            if record["evidence_time_relation_to_decision_date"] in {"post_decision", "retrospective"}:
                self.assertNotEqual(record["permitted_use"], "ex_ante_deal_evaluation")

    def test_no_headline_value_fact_is_inferred_without_direct_raw_evidence(self) -> None:
        m2_artifacts = self._run_real_source_m2("m2_for_m3_no_180")
        raw_evidence = json.loads(m2_artifacts["raw_evidence"].read_text(encoding="utf-8"))
        repository = self._run_m3_from_artifacts(m2_artifacts, "m3_no_180")
        record_keys = {record["canonical_fact_key"] for record in repository["evidence_records"]}

        self.assertFalse(any(item["raw_fact_type"] == "headline_maximum_value" for item in raw_evidence["raw_evidence_items"]))
        self.assertFalse(any("180m" in key or "headline_maximum_value" in key for key in record_keys))

    def test_generic_canonical_attributes_store_values_outside_key(self) -> None:
        canonical_fact_key, canonical_fact_type, _, structured_attributes = canonicalize_raw_evidence_item(
            {
                "evidence_id": "RE-TEST-001",
                "source_id": "SRC-SYNTHETIC-001",
                "source_title": "Synthetic transaction agreement",
                "source_type": "signed agreement",
                "evidence_category": "transaction",
                "raw_fact_type": "transaction_consideration",
                "extracted_text_or_summary": "The buyer agreed to pay $42 million at closing and up to $9 million in contingent payments during 2027.",
                "related_evidence_requirement_ids": ["ER-TEST"],
                "related_source_need_ids": ["SN-TEST"],
            }
        )

        self.assertEqual(canonical_fact_type, "transaction_consideration")
        self.assertEqual(canonical_fact_key, "transaction_consideration__er_test")
        self.assertEqual(structured_attributes["amounts"], ["$42 million", "$9 million"])
        self.assertEqual(structured_attributes["currency"], "USD")
        self.assertNotIn("42", canonical_fact_key)
        self.assertNotIn("9", canonical_fact_key)

    def test_candidate_claims_from_research_are_preserved_and_mapped(self) -> None:
        m2_artifacts = self._run_real_source_m2("m2_for_m3_candidate_claims")
        raw_evidence = json.loads(m2_artifacts["raw_evidence"].read_text(encoding="utf-8"))
        manifest = json.loads(m2_artifacts["retrieved_sources_manifest"].read_text(encoding="utf-8"))
        raw_evidence["raw_evidence_items"][0]["provider_evidence_id"] = "PE-M3-001"
        manifest["failed_source_needs"][0]["provider_source_gap_id"] = "GAP-M3-001"
        raw_evidence["candidate_claims_from_research"] = [
            {
                "candidate_claim_id": "CC-M3-001",
                "claim_statement": "The candidate claim uses a real source-bounded evidence item from the repository.",
                "claim_type": "transaction_terms",
                "claim_scope": "Synthetic test claim scope.",
                "temporal_scope": raw_evidence["raw_evidence_items"][0]["evidence_time_relation_to_decision_date"],
                "permitted_use": raw_evidence["raw_evidence_items"][0]["permitted_use"],
                "supporting_evidence_item_ids": ["PE-M3-001"],
                "contradicting_evidence_item_ids": [],
                "related_source_gap_ids": ["GAP-M3-001"],
                "confidence_preliminary": "medium",
                "requires_numeric_verification": False,
                "requires_human_review": True,
                "downstream_use_warning": "Candidate claim only. M5 decides certification and report eligibility.",
            }
        ]
        raw_evidence["candidate_claim_evidence_links_from_research"] = [
            {
                "candidate_claim_id": "CC-M3-001",
                "evidence_item_id": "PE-M3-001",
                "link_type": "supports",
                "rationale": "Maps external evidence item to the repository evidence record.",
            }
        ]
        raw_path = self.root / "raw_evidence_with_candidate_claims.json"
        manifest_path = self.root / "manifest_with_provider_gap.json"
        raw_path.write_text(json.dumps(raw_evidence, indent=2), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        artifacts = run_m3_pipeline(
            raw_evidence_path=raw_path,
            retrieved_sources_manifest_path=manifest_path,
            output_dir=self.root / "m3_candidate_claims",
        )

        repository = json.loads(artifacts["evidence_repository"].read_text(encoding="utf-8"))
        validate_evidence_repository(repository)
        candidate = repository["candidate_claims_from_research"][0]
        link = repository["candidate_claim_evidence_links_from_research"][0]
        self.assertEqual(candidate["candidate_claim_id"], "CC-M3-001")
        self.assertEqual(candidate["provider_related_source_gap_ids"], ["GAP-M3-001"])
        self.assertEqual(candidate["related_source_gap_ids"], ["SG-001"])
        self.assertEqual(link["mapping_status"], "mapped_to_evidence_record")
        self.assertTrue(link["mapped_evidence_record_ids"])

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
