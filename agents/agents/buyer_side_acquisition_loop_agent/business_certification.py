from __future__ import annotations

from typing import Any

from dealtech_certification.er_brb import run_er_brb
from dealtech_certification.models import ClaimMapRecord, EvidenceRecord, SourceRecord
from dealtech_certification.pce import run_pce

from .models import Claim, Evidence, EvidenceStatus, PCEStatus, Source


def run_business_certification(
    *, case_id: str, sources: list[Source], evidence: list[Evidence], claims: list[Claim]
) -> dict[str, Any]:
    """Use legacy PCE and ER/BRB as read-only controls through explicit adapters."""

    source_records = [
        SourceRecord(
            source_id=item.source_id,
            source_name=item.source_name,
            source_type=item.source_type,
            url_or_file=item.url_or_file,
            used_for=item.used_for,
            reliability_tier=item.reliability_tier,
            PCE_eligible=item.pce_eligible,
            source_replay_status=item.source_replay_status,
            limitations=item.limitations,
        )
        for item in sources
    ]
    available = [
        item
        for item in evidence
        if item.status == EvidenceStatus.AVAILABLE and item.supports_claim and item.source_id
    ]
    latest_by_claim: dict[str, Evidence] = {}
    for item in available:
        latest_by_claim[item.claim_id] = item
    evidence_records = [
        EvidenceRecord(
            evidence_id=item.evidence_id,
            claim_id=item.claim_id,
            source_id=item.source_id,
            extracted_fact=item.extracted_fact,
            evidence_type=item.evidence_type,
            confidence=item.confidence,
            limitations=item.limitations,
            human_review_required=item.human_review_required,
            PCE_status="Certified with Caveat" if item.human_review_required else "Certified",
        )
        for item in available
    ]
    claim_records: list[ClaimMapRecord] = []
    for claim in claims:
        selected = latest_by_claim.get(claim.claim_id)
        claim_records.append(
            ClaimMapRecord(
                claim_id=claim.claim_id,
                evidence_id=selected.evidence_id if selected else "",
                source_id=selected.source_id if selected else "",
                claim_text=claim.claim_text,
                calculation_required=claim.calculation_required,
                calculation_replayed=claim.calculation_replayed,
                human_review_required=claim.human_review_required,
                certification_status="Certified with Caveat" if claim.human_review_required else "Certified",
            )
        )
    er_brb = run_er_brb(evidence_records, source_records, claim_records)
    pce = run_pce(
        case_id=case_id,
        agent_slug="buyer-side-acquisition-loop-agent",
        case_dir=None,
        evidence=evidence_records,
        sources=source_records,
        claims=claim_records,
        er_results=er_brb,
    )
    pce_by_claim = {item["claim_id"]: item for item in pce["claim_results"]}
    for claim in claims:
        status = pce_by_claim.get(claim.claim_id, {}).get("PCE_status", "Not Certified")
        claim.pce_status = PCEStatus(status)
        claim.delivery_allowed = status in {"Certified", "Certified with Caveat"}
    return {
        "er_brb_results": er_brb,
        "pce_result": pce,
        "adapter_boundary": {
            "reused_code": [
                "agents/dealtech_certification/er_brb.py::run_er_brb",
                "agents/dealtech_certification/pce.py::run_pce",
            ],
            "read_only": True,
            "meaning": (
                "ER/BRB evaluates evidence-row reliability and risk using the legacy "
                "rule implementation; PCE controls claim delivery. Neither substitutes "
                "for Gate A, Gate B, Gate C, or human deal approval."
            ),
        },
    }
