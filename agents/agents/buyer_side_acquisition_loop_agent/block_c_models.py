from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .live_research_models import ProviderMode


BLOCK_C_MODULE_NAMES = {
    "C1": "Due Diligence",
    "C2": "Regulatory Risk",
    "C3": "Integration Risk",
    "C4": "Downside Risk",
    "C5": "Decision State",
}

BLOCK_C_ORDER = ["C1", "C2", "C3", "C4", "C5"]

# Only Block C dependencies are expressed here. Frozen Block A and Block B
# objects are inputs and are never executable dependencies of this runtime.
BLOCK_C_DEPENDENCIES = {
    "C1": [],
    "C2": [],
    "C3": [],
    "C4": ["C1", "C2", "C3"],
    "C5": ["C1", "C2", "C3", "C4"],
}


class BlockCResearchGapType(str, Enum):
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    REGULATORY_EVIDENCE_CONFLICT = "REGULATORY_EVIDENCE_CONFLICT"
    INTEGRATION_ASSUMPTION_UNSUPPORTED = "INTEGRATION_ASSUMPTION_UNSUPPORTED"
    DOWNSIDE_SCENARIO_INCOMPLETE = "DOWNSIDE_SCENARIO_INCOMPLETE"
    DECISION_SYNTHESIS_INCONSISTENT = "DECISION_SYNTHESIS_INCONSISTENT"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class BlockCOutcome(str, Enum):
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    RENEGOTIATE = "RENEGOTIATE"
    PAUSE = "PAUSE"
    NO_GO = "NO_GO"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    FAIL_RESEARCH_GAP = "FAIL_RESEARCH_GAP"
    FATAL_RISK = "FATAL_RISK"
    STOPPED_ITERATION_BUDGET = "STOPPED_ITERATION_BUDGET"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"


def _required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _version(value: int, name: str = "version") -> None:
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


@dataclass
class BlockCInputBundle:
    case_id: str
    mandate_reference: dict[str, Any]
    research_contract_reference: dict[str, Any]
    gate_a_history: list[dict[str, Any]]
    gate_b_history: list[dict[str, Any]]
    admitted_strategic_claims: list[dict[str, Any]]
    admitted_financial_claims: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    assumptions: list[dict[str, Any]]
    unknowns: list[dict[str, Any]]
    counterevidence: list[dict[str, Any]]
    calculations: list[dict[str, Any]]
    calculation_replays: list[dict[str, Any]]
    open_research_gaps: list[dict[str, Any]]
    open_calculation_gaps: list[dict[str, Any]]
    human_review_items: list[dict[str, Any]]
    price_constraints: dict[str, Any]
    financing_constraints: dict[str, Any]
    return_thresholds: dict[str, Any]
    transaction_jurisdictions: list[str]
    transaction_stage: str
    upstream_module_results: list[dict[str, Any]]
    provenance: dict[str, Any]
    artifact_hashes: dict[str, str]
    schema_version: str = "milestone-8-block-c"
    run_id: str = ""
    as_of_date: str = ""
    artifact_references: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required(self.case_id, "case_id")
        _required(self.transaction_stage, "transaction_stage")
        if not self.transaction_jurisdictions:
            raise ValueError("transaction_jurisdictions cannot be empty")
        if not self.gate_a_history or not self.gate_b_history:
            raise ValueError("Gate A and Gate B provenance histories are required")

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "BlockCInputBundle":
        return cls(**row)


@dataclass
class BlockCResearchPlan:
    plan_id: str
    case_id: str
    module_order: list[str]
    dependency_graph: dict[str, list[str]]
    selected_diligence_workstreams: list[str]
    module_questions: dict[str, list[str]]
    jurisdictions: list[str]
    transaction_stage: str
    materiality_thresholds: dict[str, Any]
    severity_thresholds: dict[str, Any]
    preferred_source_types: dict[str, list[str]]
    confidentiality_permissions: dict[str, list[str]]
    private_information_boundaries: list[str]
    research_budgets: dict[str, dict[str, Any]]
    repair_budget: dict[str, Any]
    human_review_roles: list[str]
    completion_criteria: list[str]
    prompt_manifest: dict[str, str]


@dataclass
class DiligenceFinding:
    finding_id: str
    workstream: str
    issue: str
    finding_type: str
    severity: str
    materiality: str
    source_ids: list[str]
    evidence_ids: list[str]
    affected_claim_ids: list[str]
    counterevidence_ids: list[str]
    classification: str
    supported_impact: str
    required_follow_up: str
    mitigation: str
    human_review_required: bool
    confidentiality: str
    status: str
    version: int
    provider_attempt_id: str

    def __post_init__(self) -> None:
        for name in ("finding_id", "workstream", "issue", "finding_type", "severity", "materiality", "classification", "status", "provider_attempt_id"):
            _required(getattr(self, name), name)
        if self.classification not in {"confirmed", "suspected", "unknown"}:
            raise ValueError("Diligence finding classification must be confirmed, suspected or unknown")
        _version(self.version)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "DiligenceFinding":
        return cls(**row)


@dataclass
class RegulatoryRisk:
    regulatory_risk_id: str
    jurisdiction: str
    regulatory_area: str
    trigger: str
    current_status: str
    probability_classification: str
    severity: str
    timing_range: str
    approval_dependency: str
    remedy_risk: str
    source_ids: list[str]
    evidence_ids: list[str]
    assumption_ids: list[str]
    unknown_ids: list[str]
    limitations: list[str]
    legal_adviser_review_required: bool
    status: str
    version: int
    provider_attempt_id: str

    def __post_init__(self) -> None:
        for name in ("regulatory_risk_id", "jurisdiction", "regulatory_area", "trigger", "current_status", "probability_classification", "severity", "status", "provider_attempt_id"):
            _required(getattr(self, name), name)
        _version(self.version)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "RegulatoryRisk":
        return cls(**row)


@dataclass
class IntegrationRisk:
    risk_id: str
    integration_domain: str
    dependency: str
    severity: str
    likelihood: str
    timing: str
    affected_synergy_or_claim_ids: list[str]
    expected_impact: str
    mitigation: str
    responsible_owner: str
    leading_indicator: str
    human_review_required: bool
    source_ids: list[str]
    evidence_ids: list[str]
    assumption_ids: list[str]
    limitations: list[str]
    residual_risk: str
    status: str
    version: int
    provider_attempt_id: str

    def __post_init__(self) -> None:
        for name in ("risk_id", "integration_domain", "dependency", "severity", "likelihood", "timing", "expected_impact", "residual_risk", "status", "provider_attempt_id"):
            _required(getattr(self, name), name)
        if not self.source_ids or not self.evidence_ids:
            raise ValueError("Integration risk cannot be inferred solely from Strategic Fit")
        _version(self.version)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "IntegrationRisk":
        return cls(**row)


@dataclass
class DownsideScenario:
    scenario_id: str
    scenario_name: str
    trigger: str
    probability_classification: str
    affected_claim_ids: list[str]
    affected_calculation_ids: list[str]
    changed_assumption_ids: list[str]
    financial_inputs: dict[str, str]
    resulting_metrics: dict[str, str]
    source_ids: list[str]
    evidence_ids: list[str]
    assumption_ids: list[str]
    mitigation: str
    residual_risk: str
    monitoring_indicators: list[str]
    human_review_required: bool
    limitations: list[str]
    status: str
    version: int
    provider_attempt_id: str

    def __post_init__(self) -> None:
        for name in ("scenario_id", "scenario_name", "trigger", "probability_classification", "residual_risk", "status", "provider_attempt_id"):
            _required(getattr(self, name), name)
        if bool(self.financial_inputs) != bool(self.resulting_metrics):
            raise ValueError("A quantified downside requires both registered inputs and resulting metrics")
        if not self.financial_inputs and not self.limitations:
            raise ValueError("A qualitative downside requires an explicit limitation")
        _version(self.version)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "DownsideScenario":
        return cls(**row)


@dataclass
class BlockCResearchGap:
    gap_id: str
    gap_type: BlockCResearchGapType
    owning_module: str
    description: str
    required_action: str
    closure_test: str
    status: str
    created_iteration: int
    resolved_iteration: int | None = None
    supersedes_gap_id: str = ""


@dataclass
class BlockCModuleExecution:
    module_id: str
    module_name: str
    version: int
    iteration: int
    request_id: str
    provider_attempt_id: str
    prompt_reference: str
    dependency_claim_ids: list[str]
    status: str
    result: dict[str, Any]
    registered_record_ids: list[str]
    pce_statuses: dict[str, str]
    er_brb_statuses: dict[str, Any]
    gap_ids: list[str] = field(default_factory=list)
    invalidated_by: list[str] = field(default_factory=list)


@dataclass
class BlockCRunResult:
    case_id: str
    provider_mode: ProviderMode
    outcome: BlockCOutcome
    output_dir: str
    iterations: int
    module_executions: int
    gate_c_result: dict[str, Any]
    decision_state: dict[str, Any]
    delivery_outcome: str
    terminal_state: dict[str, Any]
