from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HumanReviewDecision(str, Enum):
    APPROVE_INFORMATION = "APPROVE_INFORMATION"
    APPROVE_WITH_CONDITIONS = "APPROVE_WITH_CONDITIONS"
    REJECT_INFORMATION = "REJECT_INFORMATION"
    REQUEST_MORE_INFORMATION = "REQUEST_MORE_INFORMATION"
    ACCEPT_ASSUMPTION = "ACCEPT_ASSUMPTION"
    REJECT_ASSUMPTION = "REJECT_ASSUMPTION"
    AUTHORIZE_MANDATE_CHANGE = "AUTHORIZE_MANDATE_CHANGE"
    DO_NOT_PROCEED = "DO_NOT_PROCEED"


class ResponseValidationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ReviewItemState(str, Enum):
    OPEN = "OPEN"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
    RESOLVED = "RESOLVED"
    CONDITIONALLY_RESOLVED = "CONDITIONALLY_RESOLVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    REOPENED = "REOPENED"


class GapResolutionStatus(str, Enum):
    CLOSED = "CLOSED"
    NARROWED = "NARROWED"
    CONDITIONALLY_CLOSED = "CONDITIONALLY_CLOSED"
    STILL_OPEN = "STILL_OPEN"
    REOPENED = "REOPENED"
    SUPERSEDED = "SUPERSEDED"


class DeliveryOutcome(str, Enum):
    DELIVERABLE = "DELIVERABLE"
    DELIVERABLE_WITH_CAVEATS = "DELIVERABLE_WITH_CAVEATS"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    NOT_DELIVERABLE = "NOT_DELIVERABLE"
    INTERNAL_TRACE_ONLY = "INTERNAL_TRACE_ONLY"


class LifecycleTerminalStatus(str, Enum):
    COMPLETED_STRATEGIC_THESIS = "COMPLETED_STRATEGIC_THESIS"
    COMPLETED_CONDITIONAL_STRATEGIC_THESIS = "COMPLETED_CONDITIONAL_STRATEGIC_THESIS"
    COMPLETED_PROCEED = "COMPLETED_PROCEED"
    COMPLETED_PROCEED_WITH_CONDITIONS = "COMPLETED_PROCEED_WITH_CONDITIONS"
    COMPLETED_RENEGOTIATE = "COMPLETED_RENEGOTIATE"
    COMPLETED_PAUSE = "COMPLETED_PAUSE"
    COMPLETED_NO_GO = "COMPLETED_NO_GO"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    STOPPED_NO_PROGRESS = "STOPPED_NO_PROGRESS"
    STOPPED_ITERATION_BUDGET = "STOPPED_ITERATION_BUDGET"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"


def _required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


@dataclass
class HumanReviewResponse:
    response_id: str
    review_item_id: str
    case_id: str
    reviewer_name: str
    reviewer_role: str
    reviewer_authority_reference: str
    decision: HumanReviewDecision
    direct_answer: str
    supplied_information: list[str]
    supplied_document_references: list[str]
    supplied_source_records: list[dict[str, Any]]
    supplied_evidence_records: list[dict[str, Any]]
    supplied_assumptions: list[dict[str, Any]]
    conditions: list[str]
    limitations: list[str]
    submitted_at: str
    effective_until: str
    signature_or_approval_reference: str
    mandate_change: dict[str, Any] = field(default_factory=dict)
    validation_status: ResponseValidationStatus = ResponseValidationStatus.PENDING
    validation_errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in (
            "response_id", "review_item_id", "case_id", "reviewer_name",
            "reviewer_role", "reviewer_authority_reference", "submitted_at",
            "effective_until", "signature_or_approval_reference",
        ):
            _required(getattr(self, name), name)
        if not isinstance(self.supplied_information, list):
            raise ValueError("supplied_information must be a list")
        if not isinstance(self.supplied_document_references, list):
            raise ValueError("supplied_document_references must be a list")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HumanReviewResponse":
        values = dict(data)
        values["decision"] = HumanReviewDecision(values["decision"])
        values["validation_status"] = ResponseValidationStatus(
            values.get("validation_status", ResponseValidationStatus.PENDING.value)
        )
        values.setdefault("validation_errors", [])
        values.setdefault("mandate_change", {})
        return cls(**values)


@dataclass
class ResponseValidationResult:
    validation_id: str
    response_id: str
    review_item_id: str
    case_id: str
    status: ResponseValidationStatus
    errors: list[str]
    checks: dict[str, bool]
    validated_at: str
    may_resume: bool
    authority_boundary_preserved: bool


@dataclass
class ReviewItemVersion:
    version_id: str
    review_item_id: str
    version: int
    case_id: str
    state: ReviewItemState
    originating_gate: str
    related_claim_ids: list[str]
    related_gap_ids: list[str]
    supplied_source_ids: list[str]
    supplied_evidence_ids: list[str]
    affected_modules: list[str]
    affected_calculations: list[str]
    affected_gate_results: list[str]
    response_id: str
    reviewer_decision: str
    resolution_decision: str
    conditions: list[str]
    effective_until: str
    event_at: str
    supersedes_version_id: str


@dataclass
class GapResolutionRecord:
    resolution_id: str
    gap_id: str
    prior_status: str
    status: GapResolutionStatus
    response_id: str
    new_information: list[str]
    admissibility: str
    changed_claim_ids: list[str]
    changed_assumption_ids: list[str]
    remaining_uncertainty: list[str]
    remaining_conditions: list[str]
    modules_to_rerun: list[str]
    calculations_to_rerun: list[str]
    gates_to_rerun: list[str]
    explanation: str
    resolved_at: str


@dataclass
class TerminalStateRecord:
    terminal_state_id: str
    case_id: str
    sequence_number: int
    status: LifecycleTerminalStatus
    gate_a_result: str
    gate_b_result: str
    gate_c_result: str
    decision_state: str
    final_pce_status: str
    open_gaps: list[str]
    unresolved_claims: list[str]
    open_human_review_items: list[str]
    conditions: list[str]
    stopping_reason: str
    artifact_references: list[str]
    created_at: str
    supersedes_terminal_state_id: str


@dataclass
class MandateVersionRecord:
    mandate_version_id: str
    case_id: str
    version: int
    old_mandate: dict[str, Any]
    new_mandate: dict[str, Any]
    change_reason: str
    effective_at: str
    response_id: str
    affected_modules: list[str]
    affected_calculations: list[str]
