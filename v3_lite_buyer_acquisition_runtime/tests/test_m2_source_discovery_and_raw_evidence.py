from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.case_seed_loader import load_case_seed
from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.raw_evidence_extraction import RawEvidenceExtractionError, validate_raw_evidence
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m2 import M2FailClosed, run_m2_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.source_discovery import build_source_discovery_plan, source_discovery_plan_id
from v3_lite_buyer_acquisition_runtime.runtime.source_retrieval import PROVIDER_NOT_CONFIGURED_MESSAGE, RETRIEVAL_MODES, SourceRetrievalError, load_retrieved_sources_manifest


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM2SourceDiscoveryAndRawEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.mandate_path = RUNTIME_ROOT / "examples" / "fronthera_esker_alumis_mandate.json"
        self.case_seed_path = RUNTIME_ROOT / "case_seeds" / "fronthera_esker_alumis_case_seed.json"
        self.mandate = load_mandate(self.mandate_path)
        self.case_seed = load_case_seed(self.case_seed_path)
        self.research_plan = build_research_plan(self.mandate)
        self.research_plan_path = self.root / "research_plan.json"
        self.research_plan_path.write_text(json.dumps(self.research_plan, indent=2), encoding="utf-8")
        self.source_discovery_plan = build_source_discovery_plan(self.case_seed, self.research_plan)
        self.fixture_manifest_path = RUNTIME_ROOT / "tests" / "fixtures" / "fronthera_retrieved_sources_manifest.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_case_seed_is_not_evidence_without_retrieved_sources(self) -> None:
        output_dir = self.root / "m2_no_manifest"

        with self.assertRaises(M2FailClosed) as context:
            run_m2_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                output_dir=output_dir,
                retrieval_mode="manual_retrieved_sources",
            )

        self.assertIn(PROVIDER_NOT_CONFIGURED_MESSAGE, str(context.exception))
        self.assertTrue((output_dir / "source_discovery_plan.json").exists())
        self.assertFalse((output_dir / "retrieved_sources_manifest.json").exists())
        self.assertFalse((output_dir / "raw_evidence.json").exists())

    def test_authoritative_url_retrieval_fails_closed_without_explicit_urls(self) -> None:
        output_dir = self.root / "m2_url_no_targets"

        with self.assertRaises(M2FailClosed) as context:
            run_m2_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                output_dir=output_dir,
                retrieval_mode="authoritative_url_retrieval",
            )

        self.assertIn(PROVIDER_NOT_CONFIGURED_MESSAGE, str(context.exception))
        self.assertTrue((output_dir / "source_discovery_plan.json").exists())
        self.assertFalse((output_dir / "retrieved_sources_manifest.json").exists())
        self.assertFalse((output_dir / "raw_evidence.json").exists())

    def test_unavailable_providers_fail_closed_with_standard_message(self) -> None:
        unavailable_modes = sorted(RETRIEVAL_MODES - {"manual_retrieved_sources", "authoritative_url_retrieval"})

        for mode in unavailable_modes:
            with self.subTest(retrieval_mode=mode):
                output_dir = self.root / f"m2_{mode}_provider"
                with self.assertRaises(M2FailClosed) as context:
                    run_m2_pipeline(
                        mandate_path=self.mandate_path,
                        research_plan_path=self.research_plan_path,
                        case_seed_path=self.case_seed_path,
                        output_dir=output_dir,
                        retrieval_mode=mode,
                    )

                self.assertIn(PROVIDER_NOT_CONFIGURED_MESSAGE, str(context.exception))
                self.assertTrue((output_dir / "source_discovery_plan.json").exists())
                self.assertFalse((output_dir / "retrieved_sources_manifest.json").exists())
                self.assertFalse((output_dir / "raw_evidence.json").exists())

    def test_source_discovery_plan_contains_generic_authoritative_targets(self) -> None:
        plan_text = json.dumps(self.source_discovery_plan)

        self.assertIn("Transaction agreements, announcements, regulatory filings", plan_text)
        self.assertIn("Audited financials", plan_text)
        self.assertIn("Market, competitive, legal, regulatory, diligence", plan_text)
        self.assertIn("Find authoritative source for case seed lead without treating the seed as evidence", plan_text)
        self.assertIn("Case seed is a lead source only", self.source_discovery_plan["discovery_scope"])
        self.assertGreaterEqual(len(self.source_discovery_plan["source_needs"]), 8)
        self.assertGreaterEqual(len(self.source_discovery_plan["search_queries"]), 7)

        source_need_ids = {need["source_need_id"] for need in self.source_discovery_plan["source_needs"]}
        query_ids = {query["query_id"] for query in self.source_discovery_plan["search_queries"]}
        self.assertIn("SN-008", source_need_ids)
        self.assertIn("SQ-007", query_ids)

        for query in self.source_discovery_plan["search_queries"]:
            self.assertTrue(query["related_source_need_ids"])
            self.assertTrue(query["related_workstream_ids"])
            self.assertTrue(query["related_verification_target_ids"])

    def test_retrieval_governance_requires_source_id_and_known_source_need(self) -> None:
        manifest = json.loads(self.fixture_manifest_path.read_text(encoding="utf-8"))
        del manifest["retrieved_sources"][0]["source_id"]
        manifest_path = self._write_manifest(manifest)

        with self.assertRaises(SourceRetrievalError):
            load_retrieved_sources_manifest(manifest_path, self.source_discovery_plan)

    def test_manual_manifest_can_preserve_original_url_when_local_cache_is_present(self) -> None:
        manifest = json.loads(self.fixture_manifest_path.read_text(encoding="utf-8"))
        manifest["retrieved_sources"][0]["url_or_file"] = "https://www.sec.gov/example-authoritative-source"
        fixture_source_dir = RUNTIME_ROOT / "tests" / "fixtures" / "fronthera_authoritative_sources"
        fixture_cache_dir = self.root / "fronthera_authoritative_sources"
        fixture_cache_dir.mkdir()
        for original_fixture in fixture_source_dir.glob("*.txt"):
            (fixture_cache_dir / original_fixture.name).write_text(original_fixture.read_text(encoding="utf-8"), encoding="utf-8")
        manifest_path = self._write_manifest(manifest)
        output_dir = self.root / "m2_manual_manifest_with_original_url"

        artifacts = run_m2_pipeline(
            mandate_path=self.mandate_path,
            research_plan_path=self.research_plan_path,
            case_seed_path=self.case_seed_path,
            output_dir=output_dir,
            retrieval_mode="manual_retrieved_sources",
            retrieved_sources_manifest_path=manifest_path,
        )

        retrieved_manifest = json.loads(artifacts["retrieved_sources_manifest"].read_text(encoding="utf-8"))
        self.assertEqual(retrieved_manifest["retrieved_sources"][0]["url_or_file"], "https://www.sec.gov/example-authoritative-source")
        self.assertTrue((output_dir / "cache" / "SRC-SEC-SPA-001.txt").exists())

    def test_raw_evidence_rejects_unlisted_source_id(self) -> None:
        manifest = load_retrieved_sources_manifest(self.fixture_manifest_path, self.source_discovery_plan)
        raw_evidence = {
            "case_id": self.case_seed["case_id"],
            "generated_artifact": "raw_evidence.json",
            "stage": "M2_raw_evidence_extraction",
            "source_bounded": True,
            "evidence_coverage_status": manifest["evidence_coverage_status"],
            "failed_source_needs": manifest["failed_source_needs"],
            "external_retrieval_performed": False,
            "source_discovery_plan_id": source_discovery_plan_id(self.source_discovery_plan),
            "retrieved_sources_manifest_id": "RSM-test",
            "raw_evidence_items": [self._raw_evidence_item(source_id="UNLISTED-SOURCE")],
        }

        with self.assertRaises(RawEvidenceExtractionError):
            validate_raw_evidence(raw_evidence, manifest, self.source_discovery_plan)

    def test_fixture_backed_authoritative_manifest_generates_source_bounded_raw_evidence(self) -> None:
        output_dir = self.root / "m2_with_manifest"

        artifacts = run_m2_pipeline(
            mandate_path=self.mandate_path,
            research_plan_path=self.research_plan_path,
            case_seed_path=self.case_seed_path,
            output_dir=output_dir,
            retrieval_mode="manual_retrieved_sources",
            retrieved_sources_manifest_path=self.fixture_manifest_path,
        )

        self.assertTrue(artifacts["raw_evidence"].exists())
        self.assertTrue((output_dir / "source_discovery_plan.json").exists())
        self.assertTrue((output_dir / "retrieved_sources_manifest.json").exists())
        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertFalse((output_dir / "evidence_repository.json").exists())
        self.assertFalse((output_dir / "claim_evidence_graph.json").exists())
        self.assertFalse((output_dir / "certification_result.json").exists())
        self.assertTrue((output_dir / "cache" / "SRC-SEC-SPA-001.txt").exists())
        self.assertTrue((output_dir / "cache" / "SRC-ALUMIS-10K-001.txt").exists())
        self.assertTrue((output_dir / "cache" / "SRC-HAISCO-001.txt").exists())
        self.assertTrue((output_dir / "cache" / "SRC-PATENT-TYK2-001.txt").exists())
        self.assertTrue((output_dir / "cache" / "SRC-ALUMIS-PIPELINE-001.txt").exists())

        raw_evidence = json.loads(artifacts["raw_evidence"].read_text(encoding="utf-8"))
        raw_fact_types = {item["raw_fact_type"] for item in raw_evidence["raw_evidence_items"]}
        self.assertTrue(raw_evidence["raw_evidence_items"])
        self.assertTrue(raw_fact_types.issubset({
            "transaction_background",
            "transaction_timing",
            "transaction_document_date",
            "transaction_parties",
            "transaction_consideration",
            "contingent_consideration",
            "milestone_payment",
            "financing_or_payment_mechanics",
            "entity_identity",
            "entity_lineage",
            "asset_or_product_identity",
            "ownership_or_governance",
            "management_or_key_person",
            "intellectual_property",
            "regulatory_or_clinical",
            "financial_performance",
            "valuation_input",
            "synergy_or_value_creation",
            "market_or_competitive_position",
            "legal_or_regulatory_risk",
            "integration_or_operational_risk",
            "source_gap",
            "generic_fact",
        }))
        self.assertIn("transaction_timing", raw_fact_types)

        manifest = json.loads(artifacts["retrieved_sources_manifest"].read_text(encoding="utf-8"))
        manifest_source_ids = {source["source_id"] for source in manifest["retrieved_sources"]}
        manifest_sources_by_id = {source["source_id"]: source for source in manifest["retrieved_sources"]}
        self.assertEqual(manifest["retrieval_mode"], "manual_retrieved_sources")
        self.assertEqual(manifest["evidence_coverage_status"], "partial")
        self.assertEqual(raw_evidence["evidence_coverage_status"], "partial")
        self.assertEqual(raw_evidence["failed_source_needs"], manifest["failed_source_needs"])
        self.assertTrue(manifest["failed_source_needs"])

        for source in manifest["retrieved_sources"]:
            self.assertTrue(source["source_date_or_period"])
            self.assertIn(source["source_time_relation_to_decision_date"], {"pre_decision", "at_decision", "post_decision", "retrospective", "unknown"})
            self.assertIn(source["permitted_use"], {"ex_ante_deal_evaluation", "transaction_terms_verification", "retrospective_outcome_validation", "source_lead_only", "gap_tracking"})
        self.assertEqual(manifest_sources_by_id["SRC-SEC-SPA-001"]["source_time_relation_to_decision_date"], "at_decision")
        self.assertEqual(manifest_sources_by_id["SRC-SEC-SPA-001"]["permitted_use"], "transaction_terms_verification")
        self.assertEqual(manifest_sources_by_id["SRC-ALUMIS-PIPELINE-001"]["source_time_relation_to_decision_date"], "retrospective")
        self.assertEqual(manifest_sources_by_id["SRC-ALUMIS-PIPELINE-001"]["permitted_use"], "retrospective_outcome_validation")

        for item in raw_evidence["raw_evidence_items"]:
            self.assertTrue(item["source_id"])
            self.assertIn(item["source_id"], manifest_source_ids)
            self.assertTrue(item["source_tier"])
            self.assertNotEqual(item["source_type"], "web_search")
            self.assertTrue(item["extraction_location"])
            self.assertTrue(item["related_source_need_ids"])
            self.assertTrue(item["downstream_use_warning"])
            self.assertFalse(item["case_seed_only"])
            self.assertNotIn("case_seed", item["source_id"].lower())
            self.assertNotIn("mandate", item["source_id"].lower())
            source = manifest_sources_by_id[item["source_id"]]
            self.assertEqual(item["evidence_time_relation_to_decision_date"], source["source_time_relation_to_decision_date"])
            self.assertEqual(item["permitted_use"], source["permitted_use"])
            self.assertTrue(item["hindsight_leakage_warning"])
            if item["evidence_time_relation_to_decision_date"] in {"post_decision", "retrospective"}:
                self.assertNotEqual(item["permitted_use"], "ex_ante_deal_evaluation")
                self.assertIn("Hindsight leakage warning", item["hindsight_leakage_warning"])

        pipeline_items = [item for item in raw_evidence["raw_evidence_items"] if item["source_id"] == "SRC-ALUMIS-PIPELINE-001"]
        self.assertTrue(pipeline_items)
        self.assertTrue(all(item["evidence_time_relation_to_decision_date"] == "retrospective" for item in pipeline_items))

    def test_partial_manifest_generates_raw_evidence_and_preserves_missing_needs(self) -> None:
        manifest = json.loads(self.fixture_manifest_path.read_text(encoding="utf-8"))
        manifest["retrieved_sources"] = [
            source
            for source in manifest["retrieved_sources"]
            if source["source_id"] in {"SRC-SEC-SPA-001", "SRC-ALUMIS-PIPELINE-001"}
        ]
        manifest["failed_source_needs"] = [
            {"source_need_id": "SN-005", "reason": "Ownership and governance source unavailable; do not verify role or shareholding."},
            {"source_need_id": "SN-006", "reason": "Official intellectual-property record unavailable; do not fabricate IP evidence."},
            {"source_need_id": "SN-008", "reason": "Seller proceeds and immediate pre-sale cap table unavailable."},
        ]
        manifest["evidence_coverage_status"] = "partial"
        manifest_path = self._write_manifest(manifest)
        fixture_source_dir = RUNTIME_ROOT / "tests" / "fixtures" / "fronthera_authoritative_sources"
        fixture_cache_dir = self.root / "fronthera_authoritative_sources"
        fixture_cache_dir.mkdir()
        for original_fixture in fixture_source_dir.glob("*.txt"):
            (fixture_cache_dir / original_fixture.name).write_text(original_fixture.read_text(encoding="utf-8"), encoding="utf-8")
        output_dir = self.root / "m2_partial_manifest"

        artifacts = run_m2_pipeline(
            mandate_path=self.mandate_path,
            research_plan_path=self.research_plan_path,
            case_seed_path=self.case_seed_path,
            output_dir=output_dir,
            retrieval_mode="manual_retrieved_sources",
            retrieved_sources_manifest_path=manifest_path,
        )

        raw_evidence = json.loads(artifacts["raw_evidence"].read_text(encoding="utf-8"))
        fact_types = {item["raw_fact_type"] for item in raw_evidence["raw_evidence_items"]}
        self.assertEqual(raw_evidence["evidence_coverage_status"], "partial")
        self.assertEqual(len(raw_evidence["failed_source_needs"]), 3)
        self.assertTrue(fact_types)
        self.assertTrue(fact_types.issubset({
            "transaction_background",
            "transaction_timing",
            "transaction_document_date",
            "transaction_parties",
            "transaction_consideration",
            "contingent_consideration",
            "milestone_payment",
            "financing_or_payment_mechanics",
            "entity_identity",
            "entity_lineage",
            "asset_or_product_identity",
            "ownership_or_governance",
            "management_or_key_person",
            "intellectual_property",
            "regulatory_or_clinical",
            "financial_performance",
            "valuation_input",
            "synergy_or_value_creation",
            "market_or_competitive_position",
            "legal_or_regulatory_risk",
            "integration_or_operational_risk",
            "source_gap",
            "generic_fact",
        }))
        self.assertNotIn("founder_role", fact_types)
        self.assertNotIn("shareholding_2017", fact_types)
        self.assertNotIn("patent_record", fact_types)
        self.assertFalse(any(item["source_id"] == "SRC-HAISCO-001" for item in raw_evidence["raw_evidence_items"]))
        self.assertFalse((output_dir / "evidence_repository.json").exists())
        self.assertFalse((output_dir / "claim_evidence_graph.json").exists())
        self.assertFalse((output_dir / "certification_result.json").exists())
        self.assertFalse((output_dir / "final_report.md").exists())

    def test_post_decision_raw_evidence_cannot_override_source_permitted_use_to_ex_ante(self) -> None:
        manifest = load_retrieved_sources_manifest(self.fixture_manifest_path, self.source_discovery_plan)
        item = self._raw_evidence_item(source_id="SRC-ALUMIS-10K-001")
        item["evidence_time_relation_to_decision_date"] = "post_decision"
        item["permitted_use"] = "ex_ante_deal_evaluation"
        item["hindsight_leakage_warning"] = "test warning without caveat"
        raw_evidence = {
            "case_id": self.case_seed["case_id"],
            "generated_artifact": "raw_evidence.json",
            "stage": "M2_raw_evidence_extraction",
            "source_bounded": True,
            "evidence_coverage_status": manifest["evidence_coverage_status"],
            "failed_source_needs": manifest["failed_source_needs"],
            "external_retrieval_performed": False,
            "source_discovery_plan_id": source_discovery_plan_id(self.source_discovery_plan),
            "retrieved_sources_manifest_id": "RSM-test",
            "raw_evidence_items": [item],
        }

        with self.assertRaises(RawEvidenceExtractionError):
            validate_raw_evidence(raw_evidence, manifest, self.source_discovery_plan)

    def test_zero_retrieved_sources_fail_closed_even_with_missing_needs_recorded(self) -> None:
        manifest = json.loads(self.fixture_manifest_path.read_text(encoding="utf-8"))
        manifest["retrieved_sources"] = []
        manifest["failed_source_needs"] = [{"source_need_id": "SN-005", "reason": "No authoritative source retrieved."}]
        manifest["evidence_coverage_status"] = "partial"
        manifest_path = self._write_manifest(manifest)
        output_dir = self.root / "m2_zero_sources"

        with self.assertRaises(M2FailClosed) as context:
            run_m2_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                output_dir=output_dir,
                retrieval_mode="manual_retrieved_sources",
                retrieved_sources_manifest_path=manifest_path,
            )

        self.assertIn("zero-source manifests fail closed", str(context.exception))
        self.assertTrue((output_dir / "source_discovery_plan.json").exists())
        self.assertFalse((output_dir / "raw_evidence.json").exists())

    def _write_manifest(self, manifest: dict) -> Path:
        path = self.root / "retrieved_sources_manifest.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path

    def _raw_evidence_item(self, source_id: str) -> dict:
        return {
            "evidence_id": "RE-TEST-001",
            "case_id": self.case_seed["case_id"],
            "source_id": source_id,
            "source_title": "Unknown source",
            "source_url_or_file": "unknown.txt",
            "source_type": "SEC filing fixture",
            "source_tier": "Tier 1",
            "retrieval_date": "2026-07-28",
            "extraction_location": {"file_path": "unknown.txt", "line": 1, "anchor": "anchor"},
            "extracted_text_or_summary": "summary",
            "extraction_mode": "bounded_summary",
            "related_source_need_ids": ["SN-001"],
            "related_workstream_ids": ["WS-001"],
            "related_evidence_requirement_ids": ["ER-001"],
            "related_verification_target_ids": ["VT-001"],
            "evidence_category": "transaction_terms",
            "raw_fact_type": "transaction_agreement",
            "confidence_preliminary": "medium",
            "source_is_authoritative": True,
            "case_seed_only": False,
            "extraction_notes": "test",
            "downstream_use_warning": "test warning",
            "evidence_time_relation_to_decision_date": "unknown",
            "permitted_use": "source_lead_only",
            "hindsight_leakage_warning": "test temporal warning",
        }


if __name__ == "__main__":
    unittest.main()
