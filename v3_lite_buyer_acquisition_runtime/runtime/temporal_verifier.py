from __future__ import annotations

from typing import Any


def verify_temporal_alignment(graph: dict[str, Any], evidence_repository: dict[str, Any]) -> list[dict[str, Any]]:
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    results = []
    for index, claim in enumerate(graph["claim_nodes"], start=1):
        records = [records_by_id[record_id] for record_id in claim["supporting_evidence_record_ids"] if record_id in records_by_id]
        warning_preserved = bool(claim.get("hindsight_leakage_warning"))

        status = "passed"
        caveat = "Temporal scope and permitted use are aligned."
        if claim["temporal_scope"] == "source_gap":
            status = "not_applicable"
            caveat = "Source-gap claim has no evidence timing and cannot be certified from evidence."
        elif claim["temporal_scope"] in {"post_decision", "retrospective"}:
            if claim["permitted_use"] == "ex_ante_deal_evaluation":
                status = "failed"
                caveat = "Post-decision or retrospective evidence cannot support ex-ante buyer decision claims."
            elif not warning_preserved:
                status = "failed"
                caveat = "Hindsight warning is missing for post-decision or retrospective evidence."
            else:
                status = "passed_with_caveat"
                caveat = "Evidence may support retrospective validation only; it must not be worded as ex-ante buyer decision support."
        elif claim["temporal_scope"] == "at_decision":
            if claim["permitted_use"] != "transaction_terms_verification":
                status = "passed_with_caveat"
                caveat = "At-decision evidence is not being used for transaction_terms_verification; preserve narrow wording."
            elif any("post_decision" in record.get("supporting_time_relations", []) or "retrospective" in record.get("supporting_time_relations", []) for record in records):
                status = "passed_with_caveat"
                caveat = "At-decision transaction evidence is present, but the evidence record also includes later corroboration; use only decision-time sources for transaction-term certification."

        results.append(
            {
                "temporal_check_id": f"TV-{index:03d}",
                "claim_id": claim["claim_id"],
                "verification_status": status,
                "temporal_scope": claim["temporal_scope"],
                "permitted_use": claim["permitted_use"],
                "supporting_time_relations": sorted({relation for record in records for relation in record.get("supporting_time_relations", [])}),
                "hindsight_leakage_warning_preserved": warning_preserved,
                "caveat": caveat,
            }
        )
    return results
