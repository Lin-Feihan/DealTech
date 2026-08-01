from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.loop_controller import LoopController


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteFullAgentRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.case_path = RUNTIME_ROOT / "examples" / "synthetic_acquisition_mandate.json"
        self.run_dir = self.root / "synthetic_agent_run"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_start_waits_for_external_research_then_resume_generates_report(self) -> None:
        controller = LoopController(self.run_dir)

        start_state = controller.start(self.case_path)

        self.assertEqual(start_state["status"], "awaiting_external_research")
        self.assertEqual(start_state["current_stage"], "M2_external_research")
        self.assertEqual(start_state["iteration"], 0)
        self.assertTrue((self.run_dir / "run_state.json").exists())
        self.assertTrue((self.run_dir / "research_request.json").exists())
        request = self._load(self.run_dir / "research_request.json")
        self.assertEqual(request["generated_artifact"], "research_request.json")
        self.assertEqual(request["provider"], "openclaw_external_research")

        response_path = self.root / "synthetic_deep_research_response.json"
        response_path.write_text(json.dumps(_passing_response(), indent=2), encoding="utf-8")
        final_state = controller.resume(response_path)

        self.assertEqual(final_state["status"], "report_generated")
        self.assertEqual(final_state["current_stage"], "M7_1_report_render")
        for stage in (
            "M1_mandate_to_research_plan",
            "M2_source_discovery_plan",
            "M2_external_research_ingestion",
            "M3_evidence_repository",
            "M4_claim_evidence_graph",
            "M5_loop_certification",
            "M6_evidence_bounded_deal_analysis",
            "M7_report_rendering_gate",
            "Step6A_audit_package",
            "M7_1_report_render",
        ):
            self.assertIn(stage, final_state["completed_stages"])
        for filename in (
            "mandate.json",
            "research_plan.json",
            "source_discovery_plan.json",
            "deep_research_response.json",
            "retrieved_sources_manifest.json",
            "raw_evidence.json",
            "evidence_repository.json",
            "claim_evidence_graph.json",
            "certification_result.json",
            "analysis_package.json",
            "report_manifest.json",
            "audit_package.json",
            "final_report.md",
        ):
            self.assertTrue((self.run_dir / filename).exists(), filename)

    def test_numeric_formula_results_are_written_by_m5(self) -> None:
        controller = LoopController(self.run_dir)
        controller.start(self.case_path)
        response_path = self.root / "numeric_deep_research_response.json"
        response_path.write_text(json.dumps(_numeric_response(), indent=2), encoding="utf-8")

        state = controller.resume(response_path)

        self.assertIn(state["status"], {"report_generated", "human_review_required"})
        certification = self._load(self.run_dir / "certification_result.json")
        numeric_results = certification["numeric_verification_results"]
        self.assertEqual(len(numeric_results), 1)
        self.assertEqual(numeric_results[0]["computed_result"], 150)
        self.assertEqual(numeric_results[0]["verification_status"], "passed_with_caveat")
        claim_cert = certification["claim_certifications"][0]
        self.assertEqual(claim_cert["deterministic_numeric_check_status"], "passed_with_caveat")

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


def _passing_response() -> dict:
    return {
        "case_id": "synthetic_buyer_acquisition_m1",
        "provider": "synthetic_test_research",
        "model": "synthetic",
        "response_id": "synthetic-pass-001",
        "completed_at": "2026-01-15T00:00:00Z",
        "sources": [
            {
                "provider_source_id": "PS-001",
                "title": "Synthetic transaction agreement excerpt",
                "url": "synthetic://transaction-agreement",
                "source_type": "transaction agreement",
                "source_owner": "AcquirerCo and TargetCo",
                "source_date_or_period": "2026-01-15",
                "source_reliability_rationale": "Synthetic Tier 1 official transaction document fixture for automated tests.",
                "source_limitations": "Synthetic fixture only; not a real case source.",
                "source_tier": "Tier 1",
                "source_time_relation_to_decision_date": "at_decision",
                "permitted_use": "transaction_terms_verification",
            }
        ],
        "evidence_items": [
            {
                "provider_evidence_id": "PE-001",
                "provider_source_id": "PS-001",
                "extracted_text_or_summary": "AcquirerCo agreed to acquire TargetCo under the transaction agreement.",
                "extraction_location_if_available": "Section 1",
                "fact_type": "transaction_terms",
                "related_workstream_ids": ["WS-005"],
                "related_evidence_requirement_ids": ["ER-006"],
                "related_verification_target_ids": ["VT-001"],
                "confidence_preliminary": "high",
                "caveats": ["Synthetic evidence for automated tests."],
            }
        ],
        "candidate_claims": [
            {
                "candidate_claim_id": "CC-001",
                "claim_statement": "AcquirerCo agreed to acquire TargetCo under the transaction agreement.",
                "claim_type": "transaction_terms",
                "claim_scope": "Transaction agreement identity only.",
                "temporal_scope": "at_decision",
                "permitted_use": "transaction_terms_verification",
                "supporting_evidence_item_ids": ["PE-001"],
                "contradicting_evidence_item_ids": [],
                "related_source_gap_ids": [],
                "confidence_preliminary": "high",
                "requires_numeric_verification": False,
                "requires_human_review": False,
                "downstream_use_warning": "Use only as a source-bounded transaction identity claim.",
            }
        ],
        "claim_evidence_links": [
            {
                "candidate_claim_id": "CC-001",
                "evidence_item_id": "PE-001",
                "link_type": "supports",
                "rationale": "The source text directly supports the claim.",
            }
        ],
        "source_gaps": [],
        "provider_notes": ["Synthetic structured research package for full Agent tests."],
    }


def _numeric_response() -> dict:
    response = _passing_response()
    response["response_id"] = "synthetic-numeric-001"
    response["evidence_items"][0]["fact_type"] = "transaction_consideration"
    response["evidence_items"][0]["extracted_text_or_summary"] = "AcquirerCo agreed to pay TargetCo base consideration of $100 and contingent consideration of $50."
    response["candidate_claims"][0].update(
        {
            "claim_statement": "AcquirerCo agreed to pay TargetCo base consideration of $100 and contingent consideration of $50.",
            "claim_type": "transaction_consideration",
            "requires_numeric_verification": True,
            "numeric_formula": {"expression": "input_6_1 + input_6_2", "expected_result": 150},
        }
    )
    return response


if __name__ == "__main__":
    unittest.main()
