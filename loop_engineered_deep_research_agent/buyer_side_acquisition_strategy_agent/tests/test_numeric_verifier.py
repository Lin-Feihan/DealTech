from __future__ import annotations

import unittest

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.numeric_verifier import verify_numeric_claims


class BuyerSideAcquisitionStrategyAgentNumericVerifierTest(unittest.TestCase):
    def test_explicit_formula_is_replayed_from_structured_amounts(self) -> None:
        graph = {
            "claim_nodes": [
                {
                    "claim_id": "CL-001",
                    "claim_type": "derived_numeric_candidate",
                    "supporting_evidence_record_ids": ["ER-001"],
                    "numeric_formula": {"expression": "base_amount + contingent_amount", "expected_result": 150},
                }
            ]
        }
        repository = {
            "evidence_records": [
                {
                    "evidence_record_id": "ER-001",
                    "structured_attributes": {
                        "amounts": [100, 50],
                        "amount_labels": ["base_amount", "contingent_amount"],
                        "currency": "USD",
                    },
                    "source_ids": ["SRC-001"],
                    "source_tiers": ["Tier 1"],
                }
            ]
        }

        results = verify_numeric_claims(graph, repository)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["computed_result"], 150)
        self.assertEqual(results[0]["verification_status"], "passed_with_caveat")
        self.assertEqual(results[0]["formula"], "base_amount + contingent_amount")

    def test_missing_formula_inputs_fail_closed(self) -> None:
        graph = {
            "claim_nodes": [
                {
                    "claim_id": "CL-001",
                    "claim_type": "derived_numeric_candidate",
                    "supporting_evidence_record_ids": ["ER-001"],
                    "numeric_formula": {"expression": "base_amount + missing_amount", "expected_result": 150},
                }
            ]
        }
        repository = {
            "evidence_records": [
                {
                    "evidence_record_id": "ER-001",
                    "structured_attributes": {
                        "amounts": [100],
                        "amount_labels": ["base_amount"],
                        "currency": "USD",
                    },
                    "source_ids": ["SRC-001"],
                    "source_tiers": ["Tier 1"],
                }
            ]
        }

        results = verify_numeric_claims(graph, repository)

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]["computed_result"])
        self.assertEqual(results[0]["verification_status"], "insufficient_numeric_support")
        self.assertIn("missing numeric input", results[0]["caveat"])

    def test_no_formula_produces_no_numeric_results(self) -> None:
        graph = {
            "claim_nodes": [
                {
                    "claim_id": "CL-001",
                    "claim_type": "transaction_consideration",
                    "supporting_evidence_record_ids": ["ER-001"],
                }
            ]
        }
        repository = {
            "evidence_records": [
                {
                    "evidence_record_id": "ER-001",
                    "structured_attributes": {"amounts": [100], "amount_labels": ["base_amount"]},
                    "source_ids": ["SRC-001"],
                    "source_tiers": ["Tier 1"],
                }
            ]
        }

        self.assertEqual(verify_numeric_claims(graph, repository), [])


if __name__ == "__main__":
    unittest.main()
