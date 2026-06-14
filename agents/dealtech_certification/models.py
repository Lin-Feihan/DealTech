from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class SourceRecord:
    source_id: str
    source_name: str = ""
    source_type: str = ""
    url_or_file: str = ""
    used_for: str = ""
    reliability_tier: str = ""
    PCE_eligible: bool = False
    source_replay_status: str = ""
    limitations: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_imported_artifact(self) -> bool:
        text = f"{self.source_type} {self.reliability_tier} {self.limitations}".lower()
        return "imported artifact" in text

    @property
    def is_secondary_only(self) -> bool:
        text = f"{self.source_type} {self.reliability_tier} {self.limitations}".lower()
        return "secondary" in text and "tier 1" not in text

    @property
    def replay_pending(self) -> bool:
        status = self.source_replay_status.strip().lower()
        if status in {"completed", "complete", "replayed", "source_replay_completed"}:
            return not self.has_real_url_or_file
        if status in {"pending", "source replay pending", "not started", "incomplete"}:
            return True
        text = f"{self.url_or_file} {self.used_for} {self.reliability_tier} {self.limitations}".lower()
        return "pending" in text or "source replay pending" in text or "not pce-eligible" in text

    @property
    def source_replay_completed(self) -> bool:
        return self.source_replay_status.strip().lower() in {"completed", "complete", "replayed", "source_replay_completed"}

    @property
    def has_real_url_or_file(self) -> bool:
        value = self.url_or_file.strip()
        if not value:
            return False
        lower = value.lower()
        placeholders = ["pending", "tbd", "to be determined", "n/a", "unknown", "placeholder"]
        if any(token in lower for token in placeholders):
            return False
        return lower.startswith(("http://", "https://")) or "." in value or "/" in value


@dataclass
class EvidenceRecord:
    evidence_id: str
    claim_id: str
    source_id: str
    extracted_fact: str = ""
    evidence_type: str = ""
    confidence: str = ""
    limitations: str = ""
    human_review_required: bool = False
    PCE_status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_llm_summary(self) -> bool:
        text = f"{self.evidence_type} {self.extracted_fact}".lower()
        return "llm summary" in text or "ai summary" in text

    @property
    def is_metadata_level(self) -> bool:
        text = f"{self.evidence_type} {self.extracted_fact} {self.limitations}".lower()
        return "metadata" in text or "source registry" in text or "trace artifact" in text

    @property
    def calculation_replay_required(self) -> bool:
        text = f"{self.evidence_type} {self.extracted_fact} {self.limitations} {self.PCE_status}".lower()
        return "calculation" in text and ("pending" in text or "not replay" in text or "replay" in text)


@dataclass
class ClaimMapRecord:
    claim_id: str
    evidence_id: str = ""
    source_id: str = ""
    claim_text: str = ""
    calculation_required: bool = False
    calculation_replayed: bool = False
    human_review_required: bool = False
    certification_status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    slug: str
    package: str
    display_name: str
    doc_dir: Path
    default_case: str | None = None
    allowed_views: tuple[str, ...] = ()
    framework_only: bool = False
    framework_reason: str = ""


@dataclass
class CasePaths:
    agent_dir: Path
    case_dir: Path | None
    output_dir: Path
    view: str | None = None


@dataclass
class RunResult:
    agent: str
    agent_slug: str
    case_id: str | None
    view: str | None
    status: str
    reason: str
    sources_loaded: int = 0
    evidence_records_loaded: int = 0
    claims_checked: int = 0
    er_brb_completed: bool = False
    pce_completed: bool = False
    output_written_to: str | None = None
    output_files: list[str] = field(default_factory=list)
    business_metrics: dict[str, Any] = field(default_factory=dict)
    source_registry: list[dict[str, Any]] = field(default_factory=list)
    evidence_records: list[dict[str, Any]] = field(default_factory=list)
    er_brb_results: list[dict[str, Any]] = field(default_factory=list)
    pce_result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
