from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.case_seed_loader import load_case_seed
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.mandate_intake import load_mandate
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.research_planning import build_research_plan
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.run_m2_deep_research import (
    M2DeepResearchFailClosed,
    run_m2_deep_research_pipeline,
)
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.source_discovery import build_source_discovery_plan


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class BuyerSideAcquisitionStrategyAgentM2DeepResearchProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.mandate_path = RUNTIME_ROOT / "examples" / "synthetic_acquisition_mandate.json"
        self.case_seed_path = RUNTIME_ROOT / "case_seeds" / "synthetic_acquisition_case_seed.json"
        mandate = load_mandate(self.mandate_path)
        case_seed = load_case_seed(self.case_seed_path)
        research_plan = build_research_plan(mandate)
        source_discovery_plan = build_source_discovery_plan(case_seed, research_plan)
        self.research_plan_path = self.root / "research_plan.json"
        self.source_discovery_plan_path = self.root / "source_discovery_plan.json"
        self.research_plan_path.write_text(json.dumps(research_plan, indent=2), encoding="utf-8")
        self.source_discovery_plan_path.write_text(json.dumps(source_discovery_plan, indent=2), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_missing_openai_api_key_fails_closed_after_request_artifact(self) -> None:
        output_dir = self.root / "live_missing_key"
        with patch.dict(os.environ, {"OPENAI_DEEP_RESEARCH_MODEL": "o3-deep-research-test"}, clear=False):
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
                with self.assertRaises(M2DeepResearchFailClosed) as context:
                    run_m2_deep_research_pipeline(
                        mandate_path=self.mandate_path,
                        research_plan_path=self.research_plan_path,
                        case_seed_path=self.case_seed_path,
                        source_discovery_plan_path=self.source_discovery_plan_path,
                        output_dir=output_dir,
                        mode="live_openai_deep_research",
                    )

        self.assertIn("Missing OPENAI_API_KEY", str(context.exception))
        self.assertTrue((output_dir / "deep_research_request.json").exists())
        self.assertFalse((output_dir / "deep_research_response.raw.json").exists())
        self.assertFalse((output_dir / "retrieved_sources_manifest.json").exists())
        self.assertFalse((output_dir / "raw_evidence.json").exists())

    def test_missing_model_config_fails_closed_after_request_artifact(self) -> None:
        output_dir = self.root / "live_missing_model"
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_DEEP_RESEARCH_MODEL": ""}, clear=False):
            with self.assertRaises(M2DeepResearchFailClosed) as context:
                run_m2_deep_research_pipeline(
                    mandate_path=self.mandate_path,
                    research_plan_path=self.research_plan_path,
                    case_seed_path=self.case_seed_path,
                    source_discovery_plan_path=self.source_discovery_plan_path,
                    output_dir=output_dir,
                    mode="live_openai_deep_research",
                )

        self.assertIn("Missing OPENAI_DEEP_RESEARCH_MODEL", str(context.exception))
        self.assertTrue((output_dir / "deep_research_request.json").exists())
        self.assertFalse((output_dir / "deep_research_response.raw.json").exists())
        self.assertFalse((output_dir / "retrieved_sources_manifest.json").exists())
        self.assertFalse((output_dir / "raw_evidence.json").exists())

    def test_external_replay_response_normalizes_into_manifest_and_raw_evidence(self) -> None:
        output_dir = self.root / "replay_success"
        replay_path = self._write_replay_response(self._valid_replay_response())

        artifacts = run_m2_deep_research_pipeline(
            mandate_path=self.mandate_path,
            research_plan_path=self.research_plan_path,
            case_seed_path=self.case_seed_path,
            source_discovery_plan_path=self.source_discovery_plan_path,
            output_dir=output_dir,
            mode="replay_deep_research_response",
            replay_response_path=replay_path,
        )

        manifest = self._load_json(artifacts["retrieved_sources_manifest"])
        raw_evidence = self._load_json(artifacts["raw_evidence"])
        source_ids = {source["source_id"] for source in manifest["retrieved_sources"]}
        sources_by_id = {source["source_id"]: source for source in manifest["retrieved_sources"]}

        self.assertNotIn("deep_research_request", artifacts)
        self.assertNotIn("deep_research_response_raw", artifacts)
        self.assertFalse((output_dir / "deep_research_request.json").exists())
        self.assertFalse((output_dir / "deep_research_response.raw.json").exists())
        self.assertEqual(manifest["retrieval_mode"], "deep_research")
        self.assertEqual(raw_evidence["generated_artifact"], "raw_evidence.json")
        self.assertTrue(raw_evidence["external_retrieval_performed"])
        self.assertEqual(manifest["evidence_coverage_status"], "partial")
        self.assertEqual(raw_evidence["evidence_coverage_status"], "partial")
        self.assertTrue(manifest["failed_source_needs"])

        self.assertEqual(sources_by_id["SRC-DR-PS-001"]["source_tier"], "Tier 1")
        self.assertEqual(sources_by_id["SRC-DR-PS-002"]["source_tier"], "Tier 2")
        self.assertEqual(sources_by_id["SRC-DR-PS-003"]["source_tier"], "Tier 3")
        self.assertEqual(sources_by_id["SRC-DR-PS-004"]["source_tier"], "Tier 4")

        self.assertEqual(sources_by_id["SRC-DR-PS-001"]["source_time_relation_to_decision_date"], "at_decision")
        self.assertEqual(sources_by_id["SRC-DR-PS-001"]["permitted_use"], "transaction_terms_verification")
        self.assertEqual(sources_by_id["SRC-DR-PS-002"]["source_time_relation_to_decision_date"], "retrospective")
        self.assertEqual(sources_by_id["SRC-DR-PS-002"]["permitted_use"], "retrospective_outcome_validation")
        self.assertEqual(sources_by_id["SRC-DR-PS-003"]["source_time_relation_to_decision_date"], "post_decision")

        raw_source_ids = {item["source_id"] for item in raw_evidence["raw_evidence_items"]}
        self.assertTrue(raw_source_ids.issubset(source_ids))
        self.assertIn("SRC-DR-PS-001", raw_source_ids)
        self.assertIn("SRC-DR-PS-002", raw_source_ids)
        self.assertIn("SRC-DR-PS-003", raw_source_ids)
        self.assertNotIn("SRC-DR-PS-004", raw_source_ids)

        for item in raw_evidence["raw_evidence_items"]:
            self.assertEqual(item["evidence_time_relation_to_decision_date"], sources_by_id[item["source_id"]]["source_time_relation_to_decision_date"])
            self.assertEqual(item["permitted_use"], sources_by_id[item["source_id"]]["permitted_use"])
            self.assertTrue(item["hindsight_leakage_warning"])

        failed_reasons = "\n".join(entry["reason"] for entry in manifest["failed_source_needs"])
        self.assertIn("Tier 4 material", failed_reasons)
        self.assertIn("forbidden non-source material", failed_reasons)
        self.assertEqual(raw_evidence["candidate_claims_from_research"][0]["candidate_claim_id"], "CC-001")
        self.assertEqual(raw_evidence["candidate_claim_evidence_links_from_research"][0]["evidence_item_id"], "PE-001")

    def test_external_source_tier_and_temporal_classification_are_preserved(self) -> None:
        output_dir = self.root / "replay_preserve_classification"
        response = self._valid_replay_response()
        response["sources"][2]["source_tier"] = "Tier 2"
        response["sources"][2]["source_time_relation_to_decision_date"] = "pre_decision"
        response["sources"][2]["permitted_use"] = "source_lead_only"
        replay_path = self._write_replay_response(response)

        artifacts = run_m2_deep_research_pipeline(
            mandate_path=self.mandate_path,
            research_plan_path=self.research_plan_path,
            case_seed_path=self.case_seed_path,
            source_discovery_plan_path=self.source_discovery_plan_path,
            output_dir=output_dir,
            mode="replay_deep_research_response",
            replay_response_path=replay_path,
        )

        manifest = self._load_json(artifacts["retrieved_sources_manifest"])
        raw_evidence = self._load_json(artifacts["raw_evidence"])
        source = {item["source_id"]: item for item in manifest["retrieved_sources"]}["SRC-DR-PS-003"]
        evidence = [item for item in raw_evidence["raw_evidence_items"] if item["source_id"] == "SRC-DR-PS-003"][0]

        self.assertEqual(source["source_tier"], "Tier 2")
        self.assertEqual(source["source_time_relation_to_decision_date"], "pre_decision")
        self.assertEqual(source["permitted_use"], "source_lead_only")
        self.assertEqual(evidence["source_tier"], "Tier 2")
        self.assertEqual(evidence["evidence_time_relation_to_decision_date"], "pre_decision")
        self.assertEqual(evidence["permitted_use"], "source_lead_only")

    def test_invalid_external_package_fails_closed(self) -> None:
        output_dir = self.root / "replay_invalid_package"
        response = self._valid_replay_response()
        del response["sources"]
        replay_path = self._write_replay_response(response)

        with self.assertRaises(M2DeepResearchFailClosed) as context:
            run_m2_deep_research_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                source_discovery_plan_path=self.source_discovery_plan_path,
                output_dir=output_dir,
                mode="replay_deep_research_response",
                replay_response_path=replay_path,
            )

        self.assertIn("deep_research_response missing field(s): sources", str(context.exception))
        self.assertFalse((output_dir / "deep_research_request.json").exists())
        self.assertFalse((output_dir / "deep_research_response.raw.json").exists())
        self.assertFalse((output_dir / "retrieved_sources_manifest.json").exists())
        self.assertFalse((output_dir / "raw_evidence.json").exists())

    def test_source_less_evidence_item_is_rejected(self) -> None:
        output_dir = self.root / "replay_missing_source"
        response = self._valid_replay_response()
        response["evidence_items"].append(
            {
                "provider_evidence_id": "PE-MISSING",
                "provider_source_id": "PS-MISSING",
                "extracted_text_or_summary": "Unsupported unsourced claim.",
                "extraction_location_if_available": None,
                "fact_type": "transaction_consideration",
                "related_workstream_ids": ["WS-005"],
                "related_evidence_requirement_ids": ["ER-006"],
                "related_verification_target_ids": ["VT-003"],
                "confidence_preliminary": "medium",
                "caveats": ["No supporting source provided."],
            }
        )
        replay_path = self._write_replay_response(response)

        with self.assertRaises(M2DeepResearchFailClosed):
            run_m2_deep_research_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                source_discovery_plan_path=self.source_discovery_plan_path,
                output_dir=output_dir,
                mode="replay_deep_research_response",
                replay_response_path=replay_path,
            )

        self.assertFalse((output_dir / "deep_research_request.json").exists())
        self.assertFalse((output_dir / "deep_research_response.raw.json").exists())
        self.assertFalse((output_dir / "retrieved_sources_manifest.json").exists())
        self.assertFalse((output_dir / "raw_evidence.json").exists())

    def test_no_downstream_artifacts_are_generated(self) -> None:
        output_dir = self.root / "replay_no_downstream"
        replay_path = self._write_replay_response(self._valid_replay_response())

        run_m2_deep_research_pipeline(
            mandate_path=self.mandate_path,
            research_plan_path=self.research_plan_path,
            case_seed_path=self.case_seed_path,
            source_discovery_plan_path=self.source_discovery_plan_path,
            output_dir=output_dir,
            mode="replay_deep_research_response",
            replay_response_path=replay_path,
        )

        self.assertFalse((output_dir / "evidence_repository.json").exists())
        self.assertFalse((output_dir / "claim_evidence_graph.json").exists())
        self.assertFalse((output_dir / "certification_result.json").exists())
        self.assertFalse((output_dir / "analysis_package.json").exists())
        self.assertFalse((output_dir / "final_report.md").exists())
        self.assertFalse((output_dir / "recommendation_decision.json").exists())
        self.assertFalse((output_dir / "deep_research_request.json").exists())
        self.assertFalse((output_dir / "deep_research_response.raw.json").exists())

    def test_external_research_package_template_validates(self) -> None:
        template_path = RUNTIME_ROOT / "external_research_packages" / "template_deep_research_response.json"
        template = self._load_json(template_path)
        replay_path = self._write_replay_response(template)

        with self.assertRaises(M2DeepResearchFailClosed) as context:
            run_m2_deep_research_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                source_discovery_plan_path=self.source_discovery_plan_path,
                output_dir=self.root / "template_case_mismatch",
                mode="replay_deep_research_response",
                replay_response_path=replay_path,
            )

        self.assertIn("case_id must match", str(context.exception))

    def test_external_research_package_with_candidate_claims_validates_successfully(self) -> None:
        output_dir = self.root / "replay_candidate_claims"
        replay_path = self._write_replay_response(self._valid_replay_response())

        artifacts = run_m2_deep_research_pipeline(
            mandate_path=self.mandate_path,
            research_plan_path=self.research_plan_path,
            case_seed_path=self.case_seed_path,
            source_discovery_plan_path=self.source_discovery_plan_path,
            output_dir=output_dir,
            mode="replay_deep_research_response",
            replay_response_path=replay_path,
        )

        raw_evidence = self._load_json(artifacts["raw_evidence"])
        self.assertEqual(len(raw_evidence["candidate_claims_from_research"]), 3)
        self.assertEqual(len(raw_evidence["candidate_claim_evidence_links_from_research"]), 2)

    def test_candidate_claim_id_uniqueness_is_enforced(self) -> None:
        output_dir = self.root / "replay_duplicate_candidate_claim_id"
        response = self._valid_replay_response()
        duplicate = dict(response["candidate_claims"][1])
        duplicate["candidate_claim_id"] = response["candidate_claims"][0]["candidate_claim_id"]
        response["candidate_claims"].append(duplicate)
        replay_path = self._write_replay_response(response)

        with self.assertRaises(M2DeepResearchFailClosed) as context:
            run_m2_deep_research_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                source_discovery_plan_path=self.source_discovery_plan_path,
                output_dir=output_dir,
                mode="replay_deep_research_response",
                replay_response_path=replay_path,
            )

        self.assertIn("Duplicate Deep Research candidate_claim_id", str(context.exception))

    def test_claim_evidence_link_missing_evidence_item_fails_closed(self) -> None:
        response = self._valid_replay_response()
        response["claim_evidence_links"][0]["evidence_item_id"] = "PE-MISSING"
        replay_path = self._write_replay_response(response)

        with self.assertRaises(M2DeepResearchFailClosed) as context:
            run_m2_deep_research_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                source_discovery_plan_path=self.source_discovery_plan_path,
                output_dir=self.root / "replay_missing_evidence_link",
                mode="replay_deep_research_response",
                replay_response_path=replay_path,
            )

        self.assertIn("claim_evidence_link references missing evidence_item_id", str(context.exception))

    def test_claim_evidence_link_missing_candidate_claim_fails_closed(self) -> None:
        response = self._valid_replay_response()
        response["claim_evidence_links"][0]["candidate_claim_id"] = "CC-MISSING"
        replay_path = self._write_replay_response(response)

        with self.assertRaises(M2DeepResearchFailClosed) as context:
            run_m2_deep_research_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                source_discovery_plan_path=self.source_discovery_plan_path,
                output_dir=self.root / "replay_missing_claim_link",
                mode="replay_deep_research_response",
                replay_response_path=replay_path,
            )

        self.assertIn("claim_evidence_link references missing candidate_claim_id", str(context.exception))

    def test_final_report_text_is_not_structured_package_substitute(self) -> None:
        response = self._valid_replay_response()
        response["final_report"] = "This narrative is not accepted as structured research output."
        replay_path = self._write_replay_response(response)

        with self.assertRaises(M2DeepResearchFailClosed) as context:
            run_m2_deep_research_pipeline(
                mandate_path=self.mandate_path,
                research_plan_path=self.research_plan_path,
                case_seed_path=self.case_seed_path,
                source_discovery_plan_path=self.source_discovery_plan_path,
                output_dir=self.root / "replay_final_report_substitute",
                mode="replay_deep_research_response",
                replay_response_path=replay_path,
            )

        self.assertIn("final report text is not accepted", str(context.exception))

    def _write_replay_response(self, response: dict) -> Path:
        path = self.root / "deep_research_replay_response.json"
        path.write_text(json.dumps(response, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _load_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _valid_replay_response() -> dict:
        return {
            "case_id": "synthetic_buyer_acquisition_m1",
            "provider": "openai_deep_research",
            "model": "o3-deep-research-test",
            "response_id": "resp_test_001",
            "completed_at": "2026-07-29T22:40:00Z",
            "sources": [
                {
                    "provider_source_id": "PS-001",
                    "title": "SEC Exhibit Transaction Agreement",
                    "url": "https://www.sec.gov/Archives/example-spa.htm",
                    "source_type": "SEC filing",
                    "source_owner": "SEC / buyer registrant",
                    "source_date_or_period": "at decision date",
                    "source_reliability_rationale": "Primary SEC filing containing the signed agreement.",
                    "source_limitations": "Agreement supports transaction terms only; later certification still required."
                },
                {
                    "provider_source_id": "PS-002",
                    "title": "Official buyer product pipeline page",
                    "url": "https://www.example-buyer.com/pipeline/product-candidate",
                    "source_type": "official company pipeline page",
                    "source_owner": "buyer company",
                    "source_date_or_period": "current as of retrieval date 2026-07-29",
                    "source_reliability_rationale": "Official company pipeline page for current product naming.",
                    "source_limitations": "Current page is retrospective to the 2021 decision date."
                },
                {
                    "provider_source_id": "PS-003",
                    "title": "Reuters coverage of later milestone events",
                    "url": "https://www.reuters.com/example-future-milestone",
                    "source_type": "reputable financial news",
                    "source_owner": "Reuters",
                    "source_date_or_period": "2027",
                    "source_reliability_rationale": "Reputable financial news with later outcome context.",
                    "source_limitations": "Secondary source and post-decision."
                },
                {
                    "provider_source_id": "PS-004",
                    "title": "Deep Research summary memo",
                    "url": "deep-research-summary://memo-1",
                    "source_type": "model-generated research summary",
                    "source_owner": "OpenAI Deep Research",
                    "source_date_or_period": "2026-07-29",
                    "source_reliability_rationale": "Provider synthesis only.",
                    "source_limitations": "Not an original authoritative source."
                },
                {
                    "provider_source_id": "PS-005",
                    "title": "User notes on seller proceeds",
                    "url": "file://user-provided-notes",
                    "source_type": "user-provided case brief",
                    "source_owner": "user-provided",
                    "source_date_or_period": "unknown",
                    "source_reliability_rationale": "User-provided notes only.",
                    "source_limitations": "Not authoritative evidence."
                }
            ],
            "evidence_items": [
                {
                    "provider_evidence_id": "PE-001",
                    "provider_source_id": "PS-001",
                    "extracted_text_or_summary": "The transaction agreement states base consideration and possible contingent consideration tied to future milestones.",
                    "extraction_location_if_available": {"section": "Consideration", "page": 3},
                    "fact_type": "transaction_consideration",
                    "related_workstream_ids": ["WS-005"],
                    "related_evidence_requirement_ids": ["ER-001", "ER-006"],
                    "related_verification_target_ids": ["VT-001", "VT-003"],
                    "confidence_preliminary": "high",
                    "caveats": []
                },
                {
                    "provider_evidence_id": "PE-002",
                    "provider_source_id": "PS-002",
                    "extracted_text_or_summary": "The official pipeline page identifies the acquired program under its current product candidate name.",
                    "extraction_location_if_available": {"section": "Pipeline"},
                    "fact_type": "asset_or_product_identity",
                    "related_workstream_ids": ["WS-003", "WS-008"],
                    "related_evidence_requirement_ids": ["ER-005"],
                    "related_verification_target_ids": ["VT-006"],
                    "confidence_preliminary": "medium",
                    "caveats": ["Current pipeline page is retrospective to 2021."]
                },
                {
                    "provider_evidence_id": "PE-003",
                    "provider_source_id": "PS-003",
                    "extracted_text_or_summary": "Reuters reported a later milestone event tied to the acquired program after the transaction date.",
                    "extraction_location_if_available": "article body",
                    "fact_type": "milestone_payment",
                    "related_workstream_ids": ["WS-006"],
                    "related_evidence_requirement_ids": ["ER-002", "ER-006"],
                    "related_verification_target_ids": ["VT-001", "VT-002"],
                    "confidence_preliminary": "low",
                    "caveats": ["Secondary source; requires downstream confirmation."]
                },
                {
                    "provider_evidence_id": "PE-004",
                    "provider_source_id": "PS-004",
                    "extracted_text_or_summary": "Deep Research summary says the transaction had a headline value.",
                    "extraction_location_if_available": "provider memo",
                    "fact_type": "transaction_consideration",
                    "related_workstream_ids": ["WS-005"],
                    "related_evidence_requirement_ids": ["ER-006"],
                    "related_verification_target_ids": ["VT-003"],
                    "confidence_preliminary": "medium",
                    "caveats": ["Provider summary only."]
                },
                {
                    "provider_evidence_id": "PE-005",
                    "provider_source_id": "PS-005",
                    "extracted_text_or_summary": "User notes suggest seller economics and personal proceeds.",
                    "extraction_location_if_available": "PDF note",
                    "fact_type": "ownership_or_governance",
                    "related_workstream_ids": ["WS-004", "WS-009"],
                    "related_evidence_requirement_ids": ["ER-007"],
                    "related_verification_target_ids": ["VT-004", "VT-007"],
                    "confidence_preliminary": "low",
                    "caveats": ["User note only."]
                }
            ],
            "candidate_claims": [
                {
                    "candidate_claim_id": "CC-001",
                    "claim_statement": "The transaction agreement states base consideration and possible contingent consideration tied to future milestones.",
                    "claim_type": "transaction_consideration",
                    "claim_scope": "Transaction consideration terms only; not valuation or recommendation.",
                    "temporal_scope": "at_decision",
                    "permitted_use": "transaction_terms_verification",
                    "supporting_evidence_item_ids": ["PE-001"],
                    "contradicting_evidence_item_ids": [],
                    "related_source_gap_ids": [],
                    "confidence_preliminary": "high",
                    "requires_numeric_verification": True,
                    "requires_human_review": True,
                    "downstream_use_warning": "Candidate claim only. M5 must verify citations, arithmetic, caveats, and report eligibility."
                },
                {
                    "candidate_claim_id": "CC-002",
                    "claim_statement": "The official buyer pipeline page identifies the acquired program under its current product candidate name, but it is retrospective to the transaction decision date.",
                    "claim_type": "asset_or_product_identity",
                    "claim_scope": "Asset naming context only.",
                    "temporal_scope": "retrospective",
                    "permitted_use": "retrospective_outcome_validation",
                    "supporting_evidence_item_ids": ["PE-002"],
                    "contradicting_evidence_item_ids": [],
                    "related_source_gap_ids": [],
                    "confidence_preliminary": "medium",
                    "requires_numeric_verification": False,
                    "requires_human_review": True,
                    "downstream_use_warning": "Retrospective candidate claim only; do not use as ex-ante buyer decision support."
                },
                {
                    "candidate_claim_id": "CC-003",
                    "claim_statement": "Seller realized proceeds remain unresolved because no direct authoritative support was located.",
                    "claim_type": "source_gap_claim",
                    "claim_scope": "Source gap tracking only.",
                    "temporal_scope": "source_gap",
                    "permitted_use": "gap_tracking",
                    "supporting_evidence_item_ids": [],
                    "contradicting_evidence_item_ids": [],
                    "related_source_gap_ids": ["GAP-001"],
                    "confidence_preliminary": "low",
                    "requires_numeric_verification": False,
                    "requires_human_review": True,
                    "downstream_use_warning": "Gap-only candidate claim. Block from report assertions until source repair."
                }
            ],
            "claim_evidence_links": [
                {
                    "candidate_claim_id": "CC-001",
                    "evidence_item_id": "PE-001",
                    "link_type": "requires_verification",
                    "rationale": "The evidence supports consideration components but requires later numeric and wording verification."
                },
                {
                    "candidate_claim_id": "CC-002",
                    "evidence_item_id": "PE-002",
                    "link_type": "contextualizes",
                    "rationale": "The evidence supports current asset naming but is retrospective."
                }
            ],
            "source_gaps": [
                {
                    "source_gap_id": "GAP-001",
                    "gap_description": "Direct authoritative support for seller realized proceeds remains unresolved.",
                    "attempted_source_types": ["stock exchange announcement", "company filing"],
                    "reason_unresolved": "Deep Research did not identify a direct authoritative source.",
                    "recommended_next_search": "Search official company filings and exchange disclosures for seller proceeds or cap table evidence."
                }
            ],
            "provider_notes": [
                "Primary official sources were preferred where available.",
                "Secondary and retrospective sources remain caveated."
            ]
        }


if __name__ == "__main__":
    unittest.main()
