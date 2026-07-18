from __future__ import annotations

from typing import Any

from dealtech_certification.models import ClaimMapRecord, EvidenceRecord, SourceRecord
from dealtech_certification.pce import run_pce

from .models import Claim, Evidence, EvidenceStatus, PCEStatus, Source


def _eligible_evidence_for_claim(claim: Claim, evidence: list[Evidence]) -> list[Evidence]:
    return [
        item
        for item in evidence
        if item.claim_id == claim.claim_id
        and item.evidence_id in claim.evidence_ids
        and item.status == EvidenceStatus.AVAILABLE
        and item.supports_claim
        and bool(item.source_id)
    ]


def run_claim_pce_precheck(
    *,
    case_id: str,
    claim: Claim,
    sources: list[Source],
    evidence: list[Evidence],
) -> dict[str, Any]:
    """Adapt the loop's multi-evidence claim to the existing single-link PCE API.

    The loop keeps every evidence link. For one PCE invocation, the adapter selects
    the latest available supporting record. A missing-evidence marker is retained in
    memory but is intentionally not presented to PCE as admissible evidence.
    """

    available = _eligible_evidence_for_claim(claim, evidence)
    selected = available[-1] if available else None
    source_by_id = {item.source_id: item for item in sources}
    selected_source = source_by_id.get(selected.source_id) if selected else None

    legacy_sources: list[SourceRecord] = []
    legacy_evidence: list[EvidenceRecord] = []
    if selected_source:
        legacy_sources.append(
            SourceRecord(
                source_id=selected_source.source_id,
                source_name=selected_source.source_name,
                source_type=selected_source.source_type,
                url_or_file=selected_source.url_or_file,
                used_for=selected_source.used_for,
                reliability_tier=selected_source.reliability_tier,
                PCE_eligible=selected_source.pce_eligible,
                source_replay_status=selected_source.source_replay_status,
                limitations=selected_source.limitations,
            )
        )
    if selected:
        legacy_evidence.append(
            EvidenceRecord(
                evidence_id=selected.evidence_id,
                claim_id=selected.claim_id,
                source_id=selected.source_id,
                extracted_fact=selected.extracted_fact,
                evidence_type=selected.evidence_type,
                confidence=selected.confidence,
                limitations=selected.limitations,
                human_review_required=selected.human_review_required,
                PCE_status="Certified",
            )
        )

    mapped_claim = ClaimMapRecord(
        claim_id=claim.claim_id,
        evidence_id=selected.evidence_id if selected else "",
        source_id=selected.source_id if selected else "",
        claim_text=claim.claim_text,
        calculation_required=claim.calculation_required,
        calculation_replayed=claim.calculation_replayed,
        human_review_required=claim.human_review_required,
        certification_status="Certified",
    )
    legacy_result = run_pce(
        case_id=case_id,
        agent_slug="buyer-side-acquisition-loop-agent",
        case_dir=None,
        evidence=legacy_evidence,
        sources=legacy_sources,
        claims=[mapped_claim],
        er_results=[],
    )
    status = PCEStatus(legacy_result["overall_status"])
    claim.pce_status = status
    return {
        "status": status,
        "selected_evidence_id": selected.evidence_id if selected else None,
        "selected_source_id": selected.source_id if selected else None,
        "all_claim_evidence_ids_retained": list(claim.evidence_ids),
        "legacy_pce_result": legacy_result,
        "adapter_boundary": (
            "The existing PCE API checks one evidence/source link per claim; "
            "the loop memory retains the complete lineage and passes the latest "
            "available supporting link for this precheck."
        ),
    }
