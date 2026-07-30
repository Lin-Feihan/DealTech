from __future__ import annotations

from typing import Any


FORBIDDEN_SOURCE_MARKERS = (
    "case_seed",
    "mandate",
    "bohan pdf",
    "tests/fixtures",
    "fixtures/fronthera",
    "fronthera_authoritative_sources",
)


def verify_citations(graph: dict[str, Any], evidence_repository: dict[str, Any]) -> list[dict[str, Any]]:
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    edges_by_claim_id: dict[str, list[dict[str, Any]]] = {}
    for edge in graph["evidence_edges"]:
        edges_by_claim_id.setdefault(edge["claim_id"], []).append(edge)

    results = []
    for index, claim in enumerate(graph["claim_nodes"], start=1):
        claim_edges = edges_by_claim_id.get(claim["claim_id"], [])
        cited_records = [records_by_id[edge["evidence_record_id"]] for edge in claim_edges if edge["evidence_record_id"] in records_by_id]
        missing_record_ids = [edge["evidence_record_id"] for edge in claim_edges if edge["evidence_record_id"] not in records_by_id]
        forbidden_markers = sorted(_forbidden_markers(cited_records))
        provenance_present = all(_has_required_provenance(record) for record in cited_records)
        gap_only = claim["support_level"] in {"gap_only", "unsupported"} or not claim["supporting_evidence_record_ids"]

        if missing_record_ids or forbidden_markers:
            status = "failed"
        elif gap_only:
            status = "not_applicable"
        elif not claim_edges:
            status = "failed"
        elif not provenance_present:
            status = "failed"
        else:
            status = "passed"

        results.append(
            {
                "citation_check_id": f"CV-{index:03d}",
                "claim_id": claim["claim_id"],
                "verification_status": status,
                "supporting_edge_ids": [edge["edge_id"] for edge in claim_edges],
                "supporting_evidence_record_ids": [record["evidence_record_id"] for record in cited_records],
                "source_ids": sorted({source_id for record in cited_records for source_id in record["source_ids"]}),
                "source_tiers": sorted({tier for record in cited_records for tier in record["source_tiers"]}),
                "raw_evidence_ids": sorted({raw_id for record in cited_records for raw_id in record["raw_evidence_ids"]}),
                "provenance_fields_present": provenance_present,
                "forbidden_source_markers_detected": forbidden_markers,
                "caveat": _citation_caveat(claim, status),
            }
        )
    return results


def _has_required_provenance(record: dict[str, Any]) -> bool:
    return bool(record.get("source_ids")) and bool(record.get("source_tiers")) and bool(record.get("raw_evidence_ids"))


def _forbidden_markers(records: list[dict[str, Any]]) -> set[str]:
    markers = set()
    for record in records:
        haystack = " ".join(
            [
                record.get("canonical_fact_key", ""),
                record.get("normalized_fact_summary", ""),
                " ".join(record.get("source_ids", [])),
                " ".join(record.get("source_titles", [])),
                " ".join(record.get("raw_evidence_ids", [])),
            ]
        ).lower()
        for marker in FORBIDDEN_SOURCE_MARKERS:
            if marker in haystack:
                markers.add(marker)
    return markers


def _citation_caveat(claim: dict[str, Any], status: str) -> str:
    if status == "not_applicable":
        return "No source citation applies because this claim is gap-only or unsupported."
    if status == "passed" and claim["support_level"] == "requires_numeric_verification":
        return "Citations support the numeric inputs only; they do not directly quote the derived output value."
    if status == "passed":
        return "Supporting evidence edges and raw evidence provenance are present."
    return "Citation verification failed; claim must not be certified."
