from __future__ import annotations


def dd_decision(
    risk_belief: float,
    confidence: float,
    *,
    missing_evidence: bool = False,
    conflicting_evidence: bool = False,
    low_source_reliability: bool = False,
    metadata_only_evidence: bool = False,
    needs_human_review: bool = False,
) -> dict:
    """Return DD ER/BRB decision with recommendation/ranking support.

    Output contract: risk_level / recommendation_support / ranking_support /
    confidence / caveat / human_review_required.
    """
    reasons: list[str] = []
    human_review_required = bool(needs_human_review)
    adjusted_confidence = max(0.0, min(1.0, confidence))

    if missing_evidence:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.30)
        human_review_required = True
        reasons.append('missing DD evidence')
    if conflicting_evidence:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.25)
        human_review_required = True
        reasons.append('conflicting DD evidence')
    if low_source_reliability:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.15)
        reasons.append('low source reliability')
    if metadata_only_evidence:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.30)
        human_review_required = True
        reasons.append('metadata/title-level evidence only')

    if human_review_required or adjusted_confidence < 0.40:
        return {
            'risk_level': 'unresolved',
            'recommendation_support': 'caveated',
            'ranking_support': 'deprioritize_until_reviewed',
            'confidence': adjusted_confidence,
            'caveat': '; '.join(reasons or ['DD evidence incomplete']),
            'human_review_required': True,
        }
    if risk_belief >= 0.70:
        return {
            'risk_level': 'high',
            'recommendation_support': 'negative',
            'ranking_support': 'deprioritize',
            'confidence': adjusted_confidence,
            'caveat': '; '.join(reasons or ['high DD risk']),
            'human_review_required': False,
        }
    if risk_belief >= 0.40:
        return {
            'risk_level': 'medium',
            'recommendation_support': 'conditional',
            'ranking_support': 'rank_with_caveat',
            'confidence': adjusted_confidence,
            'caveat': '; '.join(reasons or ['manageable only with review']),
            'human_review_required': False,
        }
    return {
        'risk_level': 'low',
        'recommendation_support': 'supportive',
        'ranking_support': 'eligible_for_shortlist',
        'confidence': adjusted_confidence,
        'caveat': '; '.join(reasons),
        'human_review_required': False,
    }
