from __future__ import annotations

from .models import EvidenceRecord, SourceRecord, ClaimMapRecord


def _reliability(source: SourceRecord | None, evidence: EvidenceRecord) -> str:
    if source is None:
        return 'Missing Source'
    text = f'{source.reliability_tier} {source.source_type} {evidence.confidence}'.lower()
    if 'tier 1' in text and not source.is_imported_artifact:
        return 'High'
    if 'imported artifact' in text or 'tier 2' in text or 'medium' in text:
        return 'Medium'
    if 'tier 3' in text or 'tier 4' in text or 'low' in text or 'not evidence' in text:
        return 'Low'
    return 'Medium'


def _risk_levels(source: SourceRecord | None, evidence: EvidenceRecord, claim: ClaimMapRecord | None) -> tuple[str, str, str]:
    text = ' '.join([
        source.source_type if source else '', source.limitations if source else '',
        evidence.evidence_type, evidence.limitations, evidence.extracted_fact,
        claim.claim_text if claim else '',
    ]).lower()
    business = 'Low'
    regulatory = 'Low'
    reputational = 'Low'
    if any(k in text for k in ['valuation', 'pricing', 'fairness', 'recommendation', 'go / no-go', 'accept / reject', 'synergy']):
        business = 'High'
        reputational = 'Medium'
    elif any(k in text for k in ['imported artifact', 'source replay pending', 'secondary source pending', 'connector design']):
        business = 'Medium'
        reputational = 'Medium'
    if any(k in text for k in ['regulatory', 'public float', 'hkex', 'sec', 'listing', 'compliance']):
        regulatory = 'Medium' if evidence.human_review_required else 'Low'
    if source is None or evidence.is_llm_summary:
        business = regulatory = reputational = 'High'
    return business, regulatory, reputational


def run_er_brb(evidence: list[EvidenceRecord], sources: list[SourceRecord], claims: list[ClaimMapRecord]) -> list[dict]:
    source_by_id = {s.source_id: s for s in sources}
    claim_by_id = {c.claim_id: c for c in claims}
    results = []
    for ev in evidence:
        source = source_by_id.get(ev.source_id)
        claim = claim_by_id.get(ev.claim_id)
        reliability = _reliability(source, ev)
        business_risk, regulatory_risk, reputational_risk = _risk_levels(source, ev, claim)
        human_review = ev.human_review_required or (claim.human_review_required if claim else False)
        source_ok = bool(source and source.PCE_eligible and not source.is_imported_artifact and not source.replay_pending)
        if source is None or ev.is_llm_summary:
            status = 'Not Certified'
            reason = 'Missing source or LLM summary is not admissible evidence.'
            human_review = True
        elif human_review and source.PCE_eligible:
            status = 'Certified with Caveat'
            reason = 'Evidence exists and source is PCE-eligible, but human review/caveat flags remain visible.'
        elif human_review or source.is_imported_artifact or source.replay_pending or not source.PCE_eligible:
            status = 'Needs Human Review'
            reason = 'Evidence chain is incomplete, imported, non-PCE-eligible, or source replay is pending.'
            human_review = True
        elif source_ok:
            status = 'Certified'
            reason = 'PCE-eligible source with sufficient non-imported evidence.'
        else:
            status = 'Certified with Caveat'
            reason = 'Evidence is usable only with caveats.'
        results.append({
            'claim_id': ev.claim_id,
            'claim_text': claim.claim_text if claim and claim.claim_text else ev.extracted_fact,
            'evidence_id': ev.evidence_id,
            'source_id': ev.source_id,
            'evidence_reliability': reliability,
            'business_risk': business_risk,
            'regulatory_risk': regulatory_risk,
            'reputational_risk': reputational_risk,
            'evidence_sufficiency': 'Sufficient with caveat' if status == 'Certified with Caveat' else ('Insufficient' if status in {'Needs Human Review', 'Not Certified'} else 'Sufficient'),
            'human_review_required': human_review,
            'certification_status': status,
            'reason': reason,
        })
    return results
