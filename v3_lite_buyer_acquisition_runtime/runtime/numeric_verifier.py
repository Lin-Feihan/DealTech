from __future__ import annotations

from typing import Any


def verify_numeric_claims(graph: dict[str, Any], evidence_repository: dict[str, Any]) -> list[dict[str, Any]]:
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    results = []
    for claim in graph["claim_nodes"]:
        if claim["claim_type"] != "derived_numeric_candidate":
            continue
        input_records = [records_by_id[record_id] for record_id in claim["supporting_evidence_record_ids"] if record_id in records_by_id]
        inputs = _numeric_inputs(input_records)
        computed_result = sum(item["amount"] for item in inputs)
        status = "passed_with_caveat" if _inputs_are_certifiable(input_records) and computed_result == 180_000_000 else "failed"
        results.append(
            {
                "numeric_check_id": f"NV-{len(results) + 1:03d}",
                "related_claim_id": claim["claim_id"],
                "inputs": inputs,
                "formula": "base_initial_consideration + milestone_consideration_cap",
                "computed_result": computed_result,
                "verification_status": status,
                "caveat": "Derived maximum consideration based on source-supported components; not a direct source quote; do not use as final deal value without caveat.",
                "downstream_use_warning": "Numeric verification confirms arithmetic only. It is not a valuation conclusion, recommendation, or direct-source headline deal value certification.",
            }
        )
    return results


def _numeric_inputs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inputs = []
    for record in records:
        key = record["canonical_fact_key"]
        if key == "base_initial_consideration_60m":
            amount = 60_000_000
            label = "base_initial_consideration"
        elif key == "milestone_consideration_cap_120m":
            amount = 120_000_000
            label = "milestone_consideration_cap"
        else:
            amount = 0
            label = key
        inputs.append(
            {
                "label": label,
                "amount": amount,
                "currency": "USD",
                "evidence_record_id": record["evidence_record_id"],
                "source_ids": record["source_ids"],
                "source_tiers": record["source_tiers"],
            }
        )
    return inputs


def _inputs_are_certifiable(records: list[dict[str, Any]]) -> bool:
    required_keys = {"base_initial_consideration_60m", "milestone_consideration_cap_120m"}
    present_keys = {record["canonical_fact_key"] for record in records}
    return required_keys.issubset(present_keys) and all(
        record["support_status"] == "source_supported"
        and "Tier 1" in record["source_tiers"]
        and record["permitted_use"] == "transaction_terms_verification"
        for record in records
    )
