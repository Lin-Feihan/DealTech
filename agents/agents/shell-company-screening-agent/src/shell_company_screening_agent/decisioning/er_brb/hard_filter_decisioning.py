from __future__ import annotations


def hard_filter_decision(
    belief: float,
    confidence: float,
    hard_exclusion: bool = False,
    *,
    missing_evidence: bool = False,
    conflicting_evidence: bool = False,
    low_source_reliability: bool = False,
    metadata_only_evidence: bool = False,
    needs_human_review: bool = False,
) -> dict:
    """Return ER/BRB hard-filter decision with explicit review propagation.

    Output contract: pass / exclude / watchlist / DD escalation / confidence /
    rationale / human_review_required.
    """
    reasons: list[str] = []
    human_review_required = bool(needs_human_review)
    adjusted_confidence = max(0.0, min(1.0, confidence))

    if missing_evidence:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.25)
        human_review_required = True
        reasons.append('missing evidence')
    if conflicting_evidence:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.20)
        human_review_required = True
        reasons.append('conflicting evidence')
    if low_source_reliability:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.15)
        reasons.append('low source reliability')
    if metadata_only_evidence:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.20)
        human_review_required = True
        reasons.append('metadata-only evidence')

    if hard_exclusion:
        return {
            'decision': 'exclude',
            'confidence': max(adjusted_confidence, 0.8),
            'rationale': '; '.join(['binding hard exclusion gate'] + reasons),
            'human_review_required': human_review_required,
        }

    if human_review_required or adjusted_confidence < 0.35:
        return {
            'decision': 'DD escalation',
            'confidence': adjusted_confidence,
            'rationale': '; '.join(reasons or ['low confidence / incomplete evidence']),
            'human_review_required': True,
        }
    if belief >= 0.65 and adjusted_confidence >= 0.55:
        return {
            'decision': 'pass',
            'confidence': adjusted_confidence,
            'rationale': '; '.join(reasons or ['positive shell-screening signal']),
            'human_review_required': False,
        }
    if belief >= 0.45:
        return {
            'decision': 'watchlist',
            'confidence': adjusted_confidence,
            'rationale': '; '.join(reasons or ['mixed evidence; preserve for DD']),
            'human_review_required': human_review_required,
        }
    return {
        'decision': 'exclude',
        'confidence': adjusted_confidence,
        'rationale': '; '.join(reasons or ['insufficient shell-screening signal']),
        'human_review_required': human_review_required,
    }
