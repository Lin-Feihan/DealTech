from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PCEStatus(str, Enum):
    NOT_CERTIFIED = "Not Certified"
    CERTIFIED_WITH_CAVEAT = "Certified with Caveat"
    NEEDS_HUMAN_REVIEW = "Needs Human Review"
    CERTIFIED = "Certified"


class GateStatus(str, Enum):
    FAIL_RESEARCH_GAP = "FAIL_RESEARCH_GAP"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    PASS = "PASS"


class GapType(str, Enum):
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    HUMAN_ONLY_INFORMATION = "HUMAN_ONLY_INFORMATION"


class EvidenceStatus(str, Enum):
    MISSING = "MISSING"
    AVAILABLE = "AVAILABLE"


class QuestionStatus(str, Enum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"


class GapStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class LoopStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED_STRATEGIC_THESIS = "COMPLETED_STRATEGIC_THESIS"
    COMPLETED_CONDITIONAL_STRATEGIC_THESIS = "COMPLETED_CONDITIONAL_STRATEGIC_THESIS"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    STOPPED_NO_PROGRESS = "STOPPED_NO_PROGRESS"
    STOPPED_ITERATION_BUDGET = "STOPPED_ITERATION_BUDGET"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"
    COMPLETED_ACQUISITION_BUSINESS_LAYER = "COMPLETED_ACQUISITION_BUSINESS_LAYER"


class TerminalStatus(str, Enum):
    COMPLETED_STRATEGIC_THESIS = "COMPLETED_STRATEGIC_THESIS"
    COMPLETED_CONDITIONAL_STRATEGIC_THESIS = "COMPLETED_CONDITIONAL_STRATEGIC_THESIS"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    STOPPED_NO_PROGRESS = "STOPPED_NO_PROGRESS"
    STOPPED_ITERATION_BUDGET = "STOPPED_ITERATION_BUDGET"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"
    COMPLETED_ACQUISITION_BUSINESS_LAYER = "COMPLETED_ACQUISITION_BUSINESS_LAYER"


class ControllerDecision(str, Enum):
    RETRY_TARGETED_RESEARCH = "RETRY_TARGETED_RESEARCH"
    USE_ALTERNATE_METHOD = "USE_ALTERNATE_METHOD"
    ESCALATE_HUMAN_REVIEW = "ESCALATE_HUMAN_REVIEW"
    STOP_NO_PROGRESS = "STOP_NO_PROGRESS"
    STOP_ITERATION_BUDGET = "STOP_ITERATION_BUDGET"
    ADVANCE = "ADVANCE"
    FAIL_TECHNICAL = "FAIL_TECHNICAL"


class HumanReviewStatus(str, Enum):
    OPEN = "OPEN"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
    RESOLVED = "RESOLVED"
    CONDITIONALLY_RESOLVED = "CONDITIONALLY_RESOLVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    REOPENED = "REOPENED"


class ResearchAttemptStatus(str, Enum):
    COMPLETED_ADMISSIBLE_EVIDENCE = "COMPLETED_ADMISSIBLE_EVIDENCE"
    COMPLETED_INSUFFICIENT_EVIDENCE = "COMPLETED_INSUFFICIENT_EVIDENCE"
    COMPLETED_NO_EVIDENCE = "COMPLETED_NO_EVIDENCE"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"


def _required(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")


@dataclass
class Mandate:
    mandate_id: str
    case_id: str
    perspective: str
    buyer_name: str
    target_name: str
    decision_question: str
    transaction_context: str
    buyer_strategic_need: str
    strategic_rationale: str
    target_attractiveness: str
    target_capability_business_quality: str
    industry_competitive_position: str
    strategic_fit_hypothesis: str
    max_iterations: int = 2

    def __post_init__(self) -> None:
        for name in (
            "mandate_id",
            "case_id",
            "buyer_name",
            "target_name",
            "decision_question",
            "transaction_context",
            "buyer_strategic_need",
            "strategic_rationale",
            "target_attractiveness",
            "target_capability_business_quality",
            "industry_competitive_position",
            "strategic_fit_hypothesis",
        ):
            _required(getattr(self, name), name)
        if self.perspective.strip().lower() != "buyer-side":
            raise ValueError("perspective must be buyer-side")
        if self.max_iterations < 2:
            raise ValueError("Milestone 1 requires an iteration budget of at least 2")


@dataclass
class ResearchContract:
    contract_id: str
    case_id: str
    block_name: str
    gate_name: str
    business_modules: list[str]
    gate_criteria: list[str]
    evidence_rule: str
    iteration_budget: int
    maximum_no_progress_iterations: int = 2

    def __post_init__(self) -> None:
        for name in ("contract_id", "case_id", "block_name", "gate_name", "evidence_rule"):
            _required(getattr(self, name), name)
        if self.gate_name != "Strategic Thesis Gate":
            raise ValueError("Milestone 1 contract must use Strategic Thesis Gate")
        if self.iteration_budget < 2:
            raise ValueError("iteration_budget must be at least 2")
        if self.maximum_no_progress_iterations < 1:
            raise ValueError("maximum_no_progress_iterations must be positive")
        if not self.business_modules or not self.gate_criteria:
            raise ValueError("business_modules and gate_criteria cannot be empty")


@dataclass
class ResearchQuestion:
    question_id: str
    owner_module: str
    question_text: str
    purpose: str
    iteration: int
    status: QuestionStatus = QuestionStatus.PLANNED

    def __post_init__(self) -> None:
        for name in ("question_id", "owner_module", "question_text", "purpose"):
            _required(getattr(self, name), name)
        if self.iteration < 1:
            raise ValueError("iteration must be positive")


@dataclass
class Source:
    source_id: str
    source_name: str
    source_type: str
    url_or_file: str
    used_for: str
    reliability_tier: str
    pce_eligible: bool
    source_replay_status: str
    limitations: str = ""

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "source_name",
            "source_type",
            "url_or_file",
            "used_for",
            "reliability_tier",
            "source_replay_status",
        ):
            _required(getattr(self, name), name)


@dataclass
class Evidence:
    evidence_id: str
    claim_id: str
    source_id: str
    extracted_fact: str
    evidence_type: str
    confidence: str
    status: EvidenceStatus
    supports_claim: bool
    human_review_required: bool = False
    limitations: str = ""

    def __post_init__(self) -> None:
        _required(self.evidence_id, "evidence_id")
        _required(self.claim_id, "claim_id")
        if self.status == EvidenceStatus.AVAILABLE:
            for name in ("source_id", "extracted_fact", "evidence_type", "confidence"):
                _required(getattr(self, name), name)
        if self.status == EvidenceStatus.MISSING and self.supports_claim:
            raise ValueError("missing evidence cannot support a claim")


@dataclass
class Claim:
    claim_id: str
    claim_text: str
    business_module: str
    evidence_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    pce_status: PCEStatus = PCEStatus.NOT_CERTIFIED
    human_review_required: bool = False
    claim_class: str = "evidence-supported inference"
    materiality: str = "material"
    calculation_required: bool = False
    calculation_replayed: bool = False
    calculation_ids: list[str] = field(default_factory=list)
    counterevidence_ids: list[str] = field(default_factory=list)
    delivery_allowed: bool = False

    def __post_init__(self) -> None:
        for name in ("claim_id", "claim_text", "business_module"):
            _required(getattr(self, name), name)

    def add_lineage(self, evidence: Evidence) -> None:
        if evidence.claim_id != self.claim_id:
            raise ValueError("evidence claim_id does not match claim")
        if evidence.evidence_id not in self.evidence_ids:
            self.evidence_ids.append(evidence.evidence_id)
        if evidence.source_id and evidence.source_id not in self.source_ids:
            self.source_ids.append(evidence.source_id)


@dataclass
class GateResult:
    gate_name: str
    iteration: int
    status: GateStatus
    pce_status: PCEStatus
    criteria: dict[str, bool]
    reason: str
    failed_criterion: str = ""
    return_target: str = ""
    decision_scope: str = "Block A strategic thesis only"


@dataclass
class ResearchGap:
    gap_id: str
    gap_type: GapType
    originating_gate: str
    failed_criterion: str
    affected_claim_id: str
    description: str
    required_action: str
    return_target: str
    status: GapStatus = GapStatus.OPEN
    gap_family_id: str = "GAP-A-STRATEGIC-FIT"
    version: int = 1
    previous_gap_id: str = ""
    created_iteration: int = 1


@dataclass
class ResearchAttempt:
    attempt_id: str
    case_id: str
    iteration: int
    action_key: str
    method: str
    question_id: str
    return_target: str
    status: ResearchAttemptStatus
    source_ids_added: list[str]
    evidence_ids_added: list[str]
    outcome: str

    def __post_init__(self) -> None:
        for name in ("attempt_id", "case_id", "action_key", "method", "question_id", "return_target", "outcome"):
            _required(getattr(self, name), name)
        if self.iteration < 1:
            raise ValueError("research attempt iteration must be positive")


@dataclass
class EvidenceSnapshot:
    snapshot_id: str
    iteration: int
    source_ids: list[str]
    admissible_source_ids: list[str]
    evidence_ids: list[str]
    supporting_evidence_ids: list[str]
    claim_evidence_ids: list[str]
    pce_status: PCEStatus
    gate_status: GateStatus
    passed_gate_criteria: int


@dataclass
class NoProgressAssessment:
    assessment_id: str
    case_id: str
    current_iteration: int
    compared_to_iteration: int
    new_source_ids: list[str]
    new_admissible_source_ids: list[str]
    new_evidence_ids: list[str]
    pce_improved: bool
    gate_criteria_improved: bool
    identical_action_repeated: bool
    material_progress: bool
    reasons: list[str]


@dataclass
class ControllerDecisionRecord:
    decision_id: str
    iteration: int
    decision: ControllerDecision
    reason: str
    return_target: str
    next_iteration: int | None
    related_gap_ids: list[str]


@dataclass
class HumanReviewItem:
    review_id: str
    case_id: str
    owning_block: str
    owning_module: str
    originating_gate: str
    related_claim_ids: list[str]
    related_gap_ids: list[str]
    issue_type: str
    issue_description: str
    exact_question_for_reviewer: str
    required_reviewer_role: str
    required_documents_or_information: list[str]
    status: HumanReviewStatus
    created_iteration: int
    resolution: str
    reviewer: str
    conditions: list[str]
    created_at: str
    resolved_at: str

    def __post_init__(self) -> None:
        for name in (
            "review_id",
            "case_id",
            "owning_block",
            "owning_module",
            "originating_gate",
            "issue_type",
            "issue_description",
            "exact_question_for_reviewer",
            "required_reviewer_role",
            "created_at",
        ):
            _required(getattr(self, name), name)
        if not self.related_claim_ids or not self.related_gap_ids:
            raise ValueError("HumanReviewItem must link to a Claim and a Research Gap")
        if not self.required_documents_or_information:
            raise ValueError("HumanReviewItem must state the required information")
        if self.created_iteration < 1:
            raise ValueError("created_iteration must be positive")


@dataclass
class TerminalState:
    status: TerminalStatus
    case_id: str
    final_gate_a_status: GateStatus
    final_pce_status: PCEStatus
    open_gaps: list[str]
    unresolved_claims: list[str]
    human_review_items: list[str]
    iterations_used: int
    no_progress_count: int
    stopping_reason: str
    generated_artifact_references: list[str]

    def __post_init__(self) -> None:
        _required(self.case_id, "case_id")
        _required(self.stopping_reason, "stopping_reason")
        if self.iterations_used < 1:
            raise ValueError("iterations_used must be positive")


@dataclass
class LoopState:
    loop_id: str
    case_id: str
    current_iteration: int
    maximum_iterations: int
    status: LoopStatus
    current_stage: str
    no_progress_count: int = 0
    maximum_no_progress_iterations: int = 2
    attempted_research_actions: list[str] = field(default_factory=list)
    open_gap_ids: list[str] = field(default_factory=list)
    resolved_gap_ids: list[str] = field(default_factory=list)
    current_return_target: str = ""
    human_review_required: bool = False
    terminal_state: TerminalStatus | None = None
    stopping_reason: str = ""
    completed_iterations: int = 0
    gate_history: list[GateStatus] = field(default_factory=list)
    final_gate_status: GateStatus | None = None


@dataclass
class IterationRecord:
    iteration: int
    research_question_ids: list[str]
    modules_executed: list[str]
    source_ids: list[str]
    evidence_ids: list[str]
    claim_evidence_ids: list[str]
    pce_status: PCEStatus
    gate_status: GateStatus
    gap_ids: list[str]
    change_summary: str
    research_attempt_id: str = ""
    evidence_snapshot_id: str = ""
    no_progress_assessment_id: str = ""
    controller_decision: ControllerDecision | None = None
