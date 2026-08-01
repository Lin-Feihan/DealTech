from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.loop_controller import LoopController
from v3_lite_buyer_acquisition_runtime.tests.test_full_agent_run import _passing_response


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteRepairLoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.case_path = RUNTIME_ROOT / "examples" / "synthetic_acquisition_mandate.json"
        self.run_dir = self.root / "synthetic_repair_run"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_gap_response_enters_repair_and_blocks_after_two_attempts(self) -> None:
        controller = LoopController(self.run_dir)

        first_state = controller.start(self.case_path)
        self.assertEqual(first_state["status"], "awaiting_external_research")

        response_path = self.root / "gap_response.json"
        response_path.write_text(json.dumps(_gap_response("gap-001"), indent=2), encoding="utf-8")
        repair_state_1 = controller.resume(response_path)

        self.assertEqual(repair_state_1["status"], "awaiting_external_research")
        self.assertEqual(repair_state_1["current_stage"], "M5_repair_external_research")
        self.assertEqual(repair_state_1["iteration"], 1)
        self.assertTrue((self.run_dir / "repair_request.json").exists())
        self.assertIn("M5_1_repair_loop", repair_state_1["completed_stages"])

        response_path.write_text(json.dumps(_gap_response("gap-002"), indent=2), encoding="utf-8")
        repair_state_2 = controller.resume(response_path)
        self.assertEqual(repair_state_2["status"], "awaiting_external_research")
        self.assertEqual(repair_state_2["iteration"], 2)

        response_path.write_text(json.dumps(_gap_response("gap-003"), indent=2), encoding="utf-8")
        final_state = controller.resume(response_path)

        self.assertEqual(final_state["status"], "blocked_by_missing_evidence")
        self.assertEqual(final_state["current_stage"], "M5_loop_certification")
        self.assertEqual(final_state["iteration"], 2)
        self.assertIn("Maximum repair iterations reached", final_state["next_action"])

    def test_repair_response_can_continue_to_report_when_gap_is_resolved(self) -> None:
        controller = LoopController(self.run_dir)
        controller.start(self.case_path)

        gap_path = self.root / "gap_response.json"
        gap_path.write_text(json.dumps(_gap_response("gap-before-repair"), indent=2), encoding="utf-8")
        repair_state = controller.resume(gap_path)
        self.assertEqual(repair_state["status"], "awaiting_external_research")
        self.assertEqual(repair_state["iteration"], 1)

        fixed_path = self.root / "fixed_response.json"
        fixed_path.write_text(json.dumps(_passing_response(), indent=2), encoding="utf-8")
        final_state = controller.resume(fixed_path)

        self.assertEqual(final_state["status"], "report_generated")
        self.assertTrue((self.run_dir / "final_report.md").exists())


def _gap_response(response_id: str) -> dict:
    return {
        "case_id": "synthetic_buyer_acquisition_m1",
        "provider": "synthetic_test_research",
        "model": "synthetic",
        "response_id": response_id,
        "completed_at": "2026-01-15T00:00:00Z",
        "sources": [
            {
                "provider_source_id": "PS-GAP-001",
                "title": "Synthetic unsuccessful source lead",
                "url": "synthetic://unresolved-source-lead",
                "source_type": "transaction agreement",
                "source_owner": "AcquirerCo and TargetCo",
                "source_date_or_period": "2026-01-15",
                "source_reliability_rationale": "Synthetic Tier 1 authoritative source record used only to document an unresolved retrieval attempt.",
                "source_limitations": "No report-supporting evidence item is attached.",
                "source_tier": "Tier 1",
                "source_time_relation_to_decision_date": "unknown",
                "permitted_use": "source_lead_only",
            }
        ],
        "evidence_items": [],
        "candidate_claims": [
            {
                "candidate_claim_id": "CC-GAP-001",
                "claim_statement": "Source gap blocks support for the transaction agreement identity claim.",
                "claim_type": "transaction_terms",
                "claim_scope": "Gap-only placeholder for repair loop testing.",
                "temporal_scope": "source_gap",
                "permitted_use": "gap_tracking",
                "supporting_evidence_item_ids": [],
                "contradicting_evidence_item_ids": [],
                "related_source_gap_ids": ["SG-001"],
                "confidence_preliminary": "low",
                "requires_numeric_verification": False,
                "requires_human_review": False,
                "downstream_use_warning": "Repair tracking only; do not use as report fact.",
            }
        ],
        "claim_evidence_links": [],
        "source_gaps": [
            {
                "source_gap_id": "SG-001",
                "gap_description": "Authoritative transaction agreement excerpt confirming buyer and target identity is missing.",
                "missing_fact_or_source": "Authoritative transaction agreement excerpt confirming buyer and target identity.",
                "why_it_matters": "Without this source the transaction identity claim cannot be certified.",
                "reason_unresolved": "Synthetic test intentionally withholds source-backed evidence to trigger repair.",
                "attempted_source_types": ["transaction agreement", "official filing"],
                "affected_workstream_ids": ["WS-005"],
                "affected_evidence_requirement_ids": ["ER-006"],
                "affected_verification_target_ids": ["VT-001"],
                "recommended_next_search": "Find official transaction agreement or authoritative filing.",
                "priority": "high",
            }
        ],
        "provider_notes": ["Synthetic gap package for repair loop tests."],
    }


if __name__ == "__main__":
    unittest.main()
