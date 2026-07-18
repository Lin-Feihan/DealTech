from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .review_models import (
    HumanReviewDecision,
    HumanReviewResponse,
    ResponseValidationResult,
    ResponseValidationStatus,
    ReviewItemState,
)


ANSWERABLE_STATES = {
    ReviewItemState.OPEN.value,
    ReviewItemState.REOPENED.value,
    ReviewItemState.RESPONSE_RECEIVED.value,
    ReviewItemState.CONDITIONALLY_RESOLVED.value,
}


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalise_role(value: str) -> str:
    return " ".join(value.lower().split())


def validate_human_review_response(
    *,
    response: HumanReviewResponse,
    item: dict[str, Any] | None,
    current_state: str,
    validated_at: str,
) -> ResponseValidationResult:
    errors: list[str] = []
    checks: dict[str, bool] = {}

    checks["item_exists"] = item is not None
    if item is None:
        errors.append("HumanReviewItem does not exist.")
        item = {}
    checks["item_answerable"] = current_state in ANSWERABLE_STATES
    if not checks["item_answerable"]:
        errors.append(f"HumanReviewItem state {current_state} cannot receive this response.")
    checks["case_id_matches"] = response.case_id == item.get("case_id")
    if not checks["case_id_matches"]:
        errors.append("Response case_id does not match the HumanReviewItem.")
    checks["review_item_id_matches"] = response.review_item_id == item.get("review_id")
    if not checks["review_item_id_matches"]:
        errors.append("Response review_item_id does not match the HumanReviewItem.")
    checks["reviewer_role_authorized"] = _normalise_role(response.reviewer_role) == _normalise_role(
        str(item.get("required_reviewer_role", ""))
    )
    if not checks["reviewer_role_authorized"]:
        errors.append("Reviewer role is not authorized for this HumanReviewItem.")
    checks["direct_answer_supplied"] = bool(response.direct_answer.strip())
    if not checks["direct_answer_supplied"]:
        errors.append("The required review question was not directly answered.")
    checks["required_information_supplied"] = bool(
        response.supplied_information or response.supplied_document_references
    )
    if not checks["required_information_supplied"]:
        errors.append("Required information or document references were not supplied.")
    checks["registered_object_supplied"] = bool(
        response.supplied_source_records
        or response.supplied_evidence_records
        or response.supplied_assumptions
        or response.decision == HumanReviewDecision.AUTHORIZE_MANDATE_CHANGE
    )
    if not checks["registered_object_supplied"]:
        errors.append("Human-supplied information must be registered as Source, Evidence, Assumption, or Mandate change.")
    checks["material_conditions_explicit"] = (
        response.decision != HumanReviewDecision.APPROVE_WITH_CONDITIONS
        or bool(response.conditions)
    )
    if not checks["material_conditions_explicit"]:
        errors.append("APPROVE_WITH_CONDITIONS requires explicit conditions.")
    try:
        checks["response_not_expired"] = _timestamp(response.effective_until) > _timestamp(validated_at)
        checks["submission_precedes_expiry"] = _timestamp(response.submitted_at) < _timestamp(response.effective_until)
    except ValueError:
        checks["response_not_expired"] = False
        checks["submission_precedes_expiry"] = False
    if not checks["response_not_expired"]:
        errors.append("HumanReviewResponse is expired or has an invalid effective_until timestamp.")
    if not checks["submission_precedes_expiry"]:
        errors.append("HumanReviewResponse submitted_at must precede effective_until.")

    reserved_decision = response.decision in {
        HumanReviewDecision.AUTHORIZE_MANDATE_CHANGE,
        HumanReviewDecision.DO_NOT_PROCEED,
    }
    has_deal_authority = any(
        marker in _normalise_role(response.reviewer_role)
        for marker in ("deal authority", "investment committee", "board")
    )
    checks["reserved_authority_preserved"] = not reserved_decision or has_deal_authority
    if not checks["reserved_authority_preserved"]:
        errors.append("Response contradicts the reserved deal-authority boundary.")
    checks["approval_reference_supplied"] = bool(response.signature_or_approval_reference.strip())
    if not checks["approval_reference_supplied"]:
        errors.append("Signature or approval reference is required.")

    has_mandate_change = bool(response.mandate_change)
    checks["mandate_not_silently_changed"] = (
        not has_mandate_change
        or response.decision == HumanReviewDecision.AUTHORIZE_MANDATE_CHANGE
    )
    if not checks["mandate_not_silently_changed"]:
        errors.append("Mandate change was supplied without AUTHORIZE_MANDATE_CHANGE.")
    if response.decision == HumanReviewDecision.AUTHORIZE_MANDATE_CHANGE:
        required_markers = ("old_mandate", "new_mandate", "change_reason", "effective_at", "affected_modules", "affected_calculations")
        checks["mandate_change_complete"] = all(response.mandate_change.get(marker) not in (None, "", []) for marker in required_markers)
        if not checks["mandate_change_complete"]:
            errors.append("Authorized Mandate change must include old/new versions, reason, affected modules, and affected calculations.")
    else:
        checks["mandate_change_complete"] = True

    supplied_source_ids = {row.get("source_id", "") for row in response.supplied_source_records}
    checks["evidence_links_to_supplied_source"] = all(
        row.get("source_id") in supplied_source_ids for row in response.supplied_evidence_records
    )
    if response.supplied_evidence_records and not checks["evidence_links_to_supplied_source"]:
        errors.append("Supplied Evidence does not link to a supplied Source.")
    related_claim_ids = set(item.get("related_claim_ids", []))
    checks["evidence_links_to_related_claim"] = all(
        row.get("claim_id") in related_claim_ids for row in response.supplied_evidence_records
    )
    if response.supplied_evidence_records and not checks["evidence_links_to_related_claim"]:
        errors.append("Supplied Evidence does not link to a Claim on the HumanReviewItem.")
    checks["response_does_not_self_certify"] = all(
        str(row.get("PCE_status", row.get("pce_status", ""))).lower() != "certified"
        for row in response.supplied_evidence_records
    )
    if not checks["response_does_not_self_certify"]:
        errors.append("A HumanReviewResponse cannot directly certify Evidence or a Claim.")
    if item.get("issue_type") == "HUMAN_ONLY_INFORMATION":
        checks["management_source_classified_correctly"] = bool(response.supplied_source_records) and all(
            "management" in str(row.get("source_type", "")).lower()
            and "public independent" not in str(row.get("source_type", "")).lower()
            for row in response.supplied_source_records
        )
        if not checks["management_source_classified_correctly"]:
            errors.append("Management-only information must be classified as a management source, not public independent evidence.")
    else:
        checks["management_source_classified_correctly"] = True

    status = ResponseValidationStatus.ACCEPTED if not errors else ResponseValidationStatus.REJECTED
    response.validation_status = status
    response.validation_errors = list(errors)
    return ResponseValidationResult(
        validation_id=f"VALIDATION-{response.response_id}",
        response_id=response.response_id,
        review_item_id=response.review_item_id,
        case_id=response.case_id,
        status=status,
        errors=errors,
        checks=checks,
        validated_at=validated_at,
        may_resume=status == ResponseValidationStatus.ACCEPTED,
        authority_boundary_preserved=checks["reserved_authority_preserved"] and checks["mandate_not_silently_changed"],
    )
