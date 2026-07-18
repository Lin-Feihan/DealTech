from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderMode(str, Enum):
    DETERMINISTIC = "deterministic"
    RECORDED = "recorded"
    OPENAI_LIVE = "openai_live"


class ProviderValidationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class A5Outcome(str, Enum):
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    FAIL_RESEARCH_GAP = "FAIL_RESEARCH_GAP"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    STOPPED_NO_PROGRESS = "STOPPED_NO_PROGRESS"
    STOPPED_ITERATION_BUDGET = "STOPPED_ITERATION_BUDGET"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"


class ProviderError(RuntimeError):
    """Base class for failures that must remain separate from business Gaps."""


class ProviderConfigurationError(ProviderError):
    pass


class ProviderDependencyError(ProviderError):
    pass


class ProviderTechnicalError(ProviderError):
    pass


class ProviderOutputValidationError(ProviderError):
    def __init__(
        self,
        message: str,
        *,
        validation: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.validation = validation or {}
        self.artifacts = artifacts or {}


class AttachmentValidationError(ProviderError):
    pass


@dataclass
class AttachmentRecord:
    attachment_id: str
    original_filename: str
    relative_path: str
    file_hash_sha256: str
    file_type: str
    confidentiality: str
    supplied_by: str
    document_date: str
    locator: str
    extraction_method: str
    extraction_limitations: str
    allow_provider_upload: bool
    source_id: str
    local_text: str = field(default="", repr=False)
    absolute_path: str = field(default="", repr=False)


@dataclass
class ProviderExecution:
    provider_type: ProviderMode
    model_identifier: str
    response_id: str
    structured_response: dict[str, Any]
    raw_response: dict[str, Any]
    trace: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    search_queries: list[str]
    returned_citations: list[dict[str, Any]]


@dataclass
class ProviderOutputValidation:
    status: ProviderValidationStatus
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    admitted_object_ids: dict[str, list[str]]
    rejected_objects: list[dict[str, Any]]
    checks: dict[str, bool]


@dataclass
class A5RunResult:
    case_id: str
    provider_mode: ProviderMode
    outcome: A5Outcome
    output_dir: str
    attempts: int
    gate_dependency_result: dict[str, Any]
    terminal_state: dict[str, Any]
    admitted_objects: dict[str, list[dict[str, Any]]]
