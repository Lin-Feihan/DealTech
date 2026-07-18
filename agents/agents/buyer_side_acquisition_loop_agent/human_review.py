from __future__ import annotations

from typing import Any

from .models import Claim, HumanReviewItem, HumanReviewStatus, ResearchGap


def create_human_review_item(
    *,
    case_id: str,
    claim: Claim,
    gap: ResearchGap,
    config: dict[str, Any],
    iteration: int,
) -> HumanReviewItem:
    return HumanReviewItem(
        review_id=config["review_id"],
        case_id=case_id,
        owning_block="Block A: Strategic Thesis",
        owning_module=gap.return_target,
        originating_gate=gap.originating_gate,
        related_claim_ids=[claim.claim_id],
        related_gap_ids=[gap.gap_id],
        issue_type=gap.gap_type.value,
        issue_description=config["issue_description"],
        exact_question_for_reviewer=config["exact_question_for_reviewer"],
        required_reviewer_role=config["required_reviewer_role"],
        required_documents_or_information=list(
            config["required_documents_or_information"]
        ),
        status=HumanReviewStatus.OPEN,
        created_iteration=iteration,
        resolution="",
        reviewer="",
        conditions=list(config.get("conditions", [])),
        created_at=config["created_at"],
        resolved_at="",
    )
