from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .live_research_models import ProviderMode


BLOCK_A_MODULE_NAMES = {
    "A1": "Transaction Context",
    "A2": "Buyer Strategic Need",
    "A3": "Strategic Rationale",
    "A4": "Target Attractiveness",
    "A5": "Target Capability & Business Quality",
    "A6": "Industry / Competitive Position",
    "A7": "Strategic Fit",
}

BLOCK_A_ORDER = ["A1", "A2", "A4", "A5", "A6", "A3", "A7"]

BLOCK_A_DEPENDENCIES = {
    "A1": [],
    "A2": ["A1"],
    "A4": ["A1", "A2"],
    "A5": ["A1", "A4"],
    "A6": ["A1", "A4", "A5"],
    "A3": ["A1", "A2", "A4", "A5", "A6"],
    "A7": ["A2", "A5", "A6", "A3", "A4"],
}


class BlockAOutcome(str, Enum):
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    FAIL_RESEARCH_GAP = "FAIL_RESEARCH_GAP"
    FAIL_MANDATE_GAP = "FAIL_MANDATE_GAP"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    FATAL_STRATEGIC_MISMATCH = "FATAL_STRATEGIC_MISMATCH"
    STOPPED_NO_PROGRESS = "STOPPED_NO_PROGRESS"
    STOPPED_ITERATION_BUDGET = "STOPPED_ITERATION_BUDGET"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"


@dataclass
class BlockAResearchPlan:
    plan_id: str
    case_id: str
    as_of_date: str
    modules_selected: list[str]
    module_order: list[str]
    dependency_graph: dict[str, list[str]]
    research_questions: dict[str, list[str]]
    preferred_source_types: dict[str, list[str]]
    evidence_thresholds: dict[str, dict[str, Any]]
    counterevidence_requirements: dict[str, str]
    attachment_use: dict[str, list[str]]
    confidentiality_restrictions: list[str]
    per_module_search_budget: dict[str, dict[str, Any]]
    total_block_a_budget: dict[str, Any]
    repair_budget: dict[str, Any]
    human_review_boundaries: list[str]
    completion_criteria: list[str]
    prompt_manifest: dict[str, str]


@dataclass
class ConflictRecord:
    conflict_id: str
    owning_module: str
    related_claim_ids: list[str]
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    conflict_type: str
    materiality: str
    possible_explanations: list[str]
    resolution_status: str
    human_review_required: bool
    iteration: int
    provider_attempt: str
    timestamp: str


@dataclass
class BlockAModuleExecution:
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
    pce_statuses: dict[str, str]
    er_brb_statuses: dict[str, Any]
    gap_ids: list[str] = field(default_factory=list)
    invalidated_by: list[str] = field(default_factory=list)


@dataclass
class BlockARunResult:
    case_id: str
    provider_mode: ProviderMode
    outcome: BlockAOutcome
    output_dir: str
    iterations: int
    module_executions: int
    gate_a_result: dict[str, Any]
    terminal_state: dict[str, Any]
