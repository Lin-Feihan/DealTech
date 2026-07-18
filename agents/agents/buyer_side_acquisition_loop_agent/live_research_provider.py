from __future__ import annotations

import base64
import importlib.util
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .attachment_ingestion import attachment_source
from .business_contracts import load_prompt_registry
from .business_models import (
    AssumptionRecord,
    BusinessModuleContract,
    BusinessModuleResult,
    CounterEvidenceRecord,
    ResearchRequest,
    ResearchResponse,
    UnknownRecord,
)
from .live_research_models import (
    AttachmentRecord,
    ProviderConfigurationError,
    ProviderDependencyError,
    ProviderExecution,
    ProviderMode,
    ProviderOutputValidationError,
    ProviderTechnicalError,
    ProviderValidationStatus,
)
from .models import Claim, Evidence, EvidenceStatus, PCEStatus, Source
from .provider_validation import OBJECT_COLLECTIONS, validate_provider_output
from .research_provider import ResearchBundle
from .storage import to_primitive


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _string_array() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}}


SOURCE_SCHEMA = _strict_object(
    {
        "source_id": {"type": "string"},
        "url": {"type": "string"},
        "page_title": {"type": "string"},
        "publisher_or_owner": {"type": "string"},
        "source_type": {"type": "string"},
        "source_tier": {"type": "string"},
        "publication_date": {"type": "string"},
        "retrieval_timestamp": {"type": "string"},
        "author": {"type": "string"},
        "exact_relevant_locator": {"type": "string"},
        "discovery_query": {"type": "string"},
        "provider_response_reference": {"type": "string"},
        "pce_eligible": {"type": "boolean"},
        "limitations": {"type": "string"},
        "confidentiality_classification": {"type": "string"},
        "source_kind": {"type": "string", "enum": ["web", "attachment"]},
        "original_filename": {"type": "string"},
        "file_hash_sha256": {"type": "string"},
        "file_type": {"type": "string"},
        "supplied_by": {"type": "string"},
        "document_date": {"type": "string"},
        "extraction_method": {"type": "string"},
    }
)
EVIDENCE_SCHEMA = _strict_object(
    {
        "evidence_id": {"type": "string"},
        "claim_id": {"type": "string"},
        "source_id": {"type": "string"},
        "extracted_fact": {"type": "string"},
        "exact_locator": {"type": "string"},
        "direction": {"type": "string", "enum": ["support", "contradict"]},
        "evidence_type": {"type": "string"},
        "strength": {"type": "string"},
        "limitations": {"type": "string"},
        "extraction_timestamp": {"type": "string"},
    }
)
CLAIM_SCHEMA = _strict_object(
    {
        "claim_id": {"type": "string"},
        "claim_text": {"type": "string"},
        "claim_class": {"type": "string"},
        "materiality": {"type": "string"},
        "supporting_evidence_ids": _string_array(),
        "counterevidence_ids": _string_array(),
        "confidence": {"type": "string"},
        "limitations": {"type": "string"},
        "owning_module": {"type": "string"},
        "decision_relevance": {"type": "string"},
        "delivery_request": {"type": "string"},
        "human_review_required": {"type": "boolean"},
        "claim_family_id": {"type": "string"},
        "claim_version": {"type": "integer"},
        "supersedes_claim_id": {"type": "string"},
    }
)
ASSUMPTION_SCHEMA = _strict_object(
    {
        "assumption_id": {"type": "string"},
        "owning_module": {"type": "string"},
        "statement": {"type": "string"},
        "materiality": {"type": "string"},
        "basis": {"type": "string"},
        "supported": {"type": "boolean"},
        "source_ids": _string_array(),
        "evidence_ids": _string_array(),
        "human_review_required": {"type": "boolean"},
    }
)
UNKNOWN_SCHEMA = _strict_object(
    {
        "unknown_id": {"type": "string"},
        "owning_module": {"type": "string"},
        "description": {"type": "string"},
        "materiality": {"type": "string"},
        "impact": {"type": "string"},
        "closure_requirement": {"type": "string"},
        "human_review_required": {"type": "boolean"},
    }
)
COUNTEREVIDENCE_SCHEMA = _strict_object(
    {
        "counterevidence_id": {"type": "string"},
        "owning_module": {"type": "string"},
        "description": {"type": "string"},
        "source_ids": _string_array(),
        "evidence_ids": _string_array(),
        "affected_claim_ids": _string_array(),
        "disposition": {"type": "string"},
    }
)
CITATION_SCHEMA = _strict_object(
    {
        "url": {"type": "string"},
        "title": {"type": "string"},
        "start_index": {"type": "integer"},
        "end_index": {"type": "integer"},
    }
)
A5_PROVIDER_OUTPUT_SCHEMA = _strict_object(
    {
        "sources": {"type": "array", "items": SOURCE_SCHEMA},
        "evidence": {"type": "array", "items": EVIDENCE_SCHEMA},
        "claims": {"type": "array", "items": CLAIM_SCHEMA},
        "assumptions": {"type": "array", "items": ASSUMPTION_SCHEMA},
        "unknowns": {"type": "array", "items": UNKNOWN_SCHEMA},
        "counterevidence": {"type": "array", "items": COUNTEREVIDENCE_SCHEMA},
        "suggested_follow_up_questions": _string_array(),
        "retrieval_summary": {"type": "string"},
        "searched_queries": _string_array(),
        "pages_or_files_inspected": _string_array(),
        "unresolved_conflicts": _string_array(),
        "returned_citations": {"type": "array", "items": CITATION_SCHEMA},
        "provider_metadata": _strict_object(
            {
                "provider_response_reference": {"type": "string"},
                "research_scope": {"type": "string"},
                "as_of_date": {"type": "string"},
                "limitations": _string_array(),
            }
        ),
        "module_assessment": _strict_object(
            {
                "business_conclusion": {"type": "string"},
                "criterion_outcome": {"type": "string", "enum": ["PASS", "CONDITION", "FAIL"]},
                "conditions": _string_array(),
                "limitations": _string_array(),
                "structured_output": _strict_object(
                    {
                        "capabilities": _string_array(),
                        "business_quality": _string_array(),
                        "customer_quality": _string_array(),
                        "scalability": _string_array(),
                        "durability": _string_array(),
                        "material_limitations": _string_array(),
                        "missing_private_information": _string_array(),
                        "distinction_boundaries": _string_array(),
                    }
                ),
            }
        ),
    }
)

BLOCK_A_SOURCE_SCHEMA = _strict_object(
    {
        **SOURCE_SCHEMA["properties"],
        "document_identity": {"type": "string"},
        "publication_identity": {"type": "string"},
        "version": {"type": "string"},
    }
)
BLOCK_A_CLAIM_SCHEMA = _strict_object(
    {
        **CLAIM_SCHEMA["properties"],
        "dependency_claim_ids": _string_array(),
    }
)
CONFLICT_SCHEMA = _strict_object(
    {
        "conflict_id": {"type": "string"},
        "related_claim_ids": _string_array(),
        "supporting_evidence_ids": _string_array(),
        "contradicting_evidence_ids": _string_array(),
        "conflict_type": {"type": "string"},
        "materiality": {"type": "string"},
        "possible_explanations": _string_array(),
        "resolution_status": {"type": "string"},
        "human_review_required": {"type": "boolean"},
    }
)

FINANCIAL_DATA_POINT_SCHEMA = _strict_object(
    {
        "data_point_id": {"type": "string"},
        "owning_module": {"type": "string"},
        "metric": {"type": "string"},
        "value": {"type": "string"},
        "original_value": {"type": "string"},
        "normalized_value": {"type": "string"},
        "currency": {"type": "string"},
        "unit": {"type": "string"},
        "scale": {"type": "string"},
        "fiscal_period": {"type": "string"},
        "period_classification": {"type": "string", "enum": ["historical", "forecast"]},
        "metric_classification": {"type": "string", "enum": ["reported", "adjusted", "estimated"]},
        "company_perimeter": {"type": "string"},
        "source_id": {"type": "string"},
        "evidence_id": {"type": "string"},
        "exact_locator": {"type": "string"},
        "assumption_ids": _string_array(),
        "limitations": _string_array(),
        "version": {"type": "integer"},
        "provider_attempt_id": {"type": "string"},
        "scenario": {"type": "string"},
    }
)

NORMALIZATION_RECORD_SCHEMA = _strict_object(
    {
        "normalization_id": {"type": "string"},
        "data_point_id": {"type": "string"},
        "rule": {"type": "string"},
        "original_value": {"type": "string"},
        "normalized_value": {"type": "string"},
        "from_currency": {"type": "string"},
        "to_currency": {"type": "string"},
        "from_unit": {"type": "string"},
        "to_unit": {"type": "string"},
        "from_scale": {"type": "string"},
        "to_scale": {"type": "string"},
        "from_period": {"type": "string"},
        "to_period": {"type": "string"},
        "conversion_factor": {"type": "string"},
        "source_ids": _string_array(),
        "evidence_ids": _string_array(),
        "assumption_ids": _string_array(),
        "limitations": _string_array(),
    }
)

SYNERGY_RECORD_SCHEMA = _strict_object(
    {
        "synergy_id": {"type": "string"},
        "owning_module": {"type": "string"},
        "synergy_type": {"type": "string"},
        "mechanism": {"type": "string"},
        "baseline": {"type": "string"},
        "driver": {"type": "string"},
        "period": {"type": "string"},
        "currency": {"type": "string"},
        "unit": {"type": "string"},
        "scale": {"type": "string"},
        "realization_rate": {"type": "string"},
        "probability": {"type": "string"},
        "source_ids": _string_array(),
        "evidence_ids": _string_array(),
        "assumption_ids": _string_array(),
        "one_time_cost": {"type": "string"},
        "recurring_cost": {"type": "string"},
        "dis_synergy": {"type": "string"},
        "dependencies": _string_array(),
        "downside_assumptions": _string_array(),
        "limitations": _string_array(),
        "quantified": {"type": "boolean"},
        "version": {"type": "integer"},
        "provider_attempt_id": {"type": "string"},
    }
)


def block_a_provider_output_schema(contract: BusinessModuleContract) -> dict[str, Any]:
    return _strict_object(
        {
            "sources": {"type": "array", "items": BLOCK_A_SOURCE_SCHEMA},
            "evidence": {"type": "array", "items": EVIDENCE_SCHEMA},
            "claims": {"type": "array", "items": BLOCK_A_CLAIM_SCHEMA},
            "assumptions": {"type": "array", "items": ASSUMPTION_SCHEMA},
            "unknowns": {"type": "array", "items": UNKNOWN_SCHEMA},
            "counterevidence": {"type": "array", "items": COUNTEREVIDENCE_SCHEMA},
            "conflicts": {"type": "array", "items": CONFLICT_SCHEMA},
            "suggested_follow_up_questions": _string_array(),
            "retrieval_summary": {"type": "string"},
            "searched_queries": _string_array(),
            "pages_or_files_inspected": _string_array(),
            "unresolved_conflicts": _string_array(),
            "returned_citations": {"type": "array", "items": CITATION_SCHEMA},
            "provider_metadata": _strict_object(
                {
                    "provider_response_reference": {"type": "string"},
                    "research_scope": {"type": "string"},
                    "as_of_date": {"type": "string"},
                    "limitations": _string_array(),
                }
            ),
            "module_assessment": _strict_object(
                {
                    "business_conclusion": {"type": "string"},
                    "criterion_outcome": {
                        "type": "string",
                        "enum": ["PASS", "CONDITION", "FAIL"],
                    },
                    "conditions": _string_array(),
                    "limitations": _string_array(),
                    "structured_output": _strict_object(
                        {field: _string_array() for field in contract.structured_output_fields}
                    ),
                }
            ),
        }
    )


def block_b_provider_output_schema(contract: BusinessModuleContract) -> dict[str, Any]:
    properties = dict(block_a_provider_output_schema(contract)["properties"])
    properties.update(
        {
            "financial_data_points": {"type": "array", "items": FINANCIAL_DATA_POINT_SCHEMA},
            "normalization_records": {"type": "array", "items": NORMALIZATION_RECORD_SCHEMA},
            "synergy_records": {"type": "array", "items": SYNERGY_RECORD_SCHEMA},
        }
    )
    return _strict_object(properties)


DILIGENCE_FINDING_SCHEMA = _strict_object(
    {
        "finding_id": {"type": "string"}, "workstream": {"type": "string"},
        "issue": {"type": "string"}, "finding_type": {"type": "string"},
        "severity": {"type": "string"}, "materiality": {"type": "string"},
        "source_ids": _string_array(), "evidence_ids": _string_array(),
        "affected_claim_ids": _string_array(), "counterevidence_ids": _string_array(),
        "classification": {"type": "string", "enum": ["confirmed", "suspected", "unknown"]},
        "supported_impact": {"type": "string"}, "required_follow_up": {"type": "string"},
        "mitigation": {"type": "string"}, "human_review_required": {"type": "boolean"},
        "confidentiality": {"type": "string"}, "status": {"type": "string"},
        "version": {"type": "integer"}, "provider_attempt_id": {"type": "string"},
    }
)

REGULATORY_RISK_SCHEMA = _strict_object(
    {
        "regulatory_risk_id": {"type": "string"}, "jurisdiction": {"type": "string"},
        "regulatory_area": {"type": "string"}, "trigger": {"type": "string"},
        "current_status": {"type": "string"}, "probability_classification": {"type": "string"},
        "severity": {"type": "string"}, "timing_range": {"type": "string"},
        "approval_dependency": {"type": "string"}, "remedy_risk": {"type": "string"},
        "source_ids": _string_array(), "evidence_ids": _string_array(),
        "assumption_ids": _string_array(), "unknown_ids": _string_array(),
        "limitations": _string_array(), "legal_adviser_review_required": {"type": "boolean"},
        "status": {"type": "string"}, "version": {"type": "integer"},
        "provider_attempt_id": {"type": "string"},
    }
)

INTEGRATION_RISK_SCHEMA = _strict_object(
    {
        "risk_id": {"type": "string"}, "integration_domain": {"type": "string"},
        "dependency": {"type": "string"}, "severity": {"type": "string"},
        "likelihood": {"type": "string"}, "timing": {"type": "string"},
        "affected_synergy_or_claim_ids": _string_array(), "expected_impact": {"type": "string"},
        "mitigation": {"type": "string"}, "responsible_owner": {"type": "string"},
        "leading_indicator": {"type": "string"}, "human_review_required": {"type": "boolean"},
        "source_ids": _string_array(), "evidence_ids": _string_array(),
        "assumption_ids": _string_array(), "limitations": _string_array(),
        "residual_risk": {"type": "string"}, "status": {"type": "string"},
        "version": {"type": "integer"}, "provider_attempt_id": {"type": "string"},
    }
)

DOWNSIDE_SCENARIO_SCHEMA = _strict_object(
    {
        "scenario_id": {"type": "string"}, "scenario_name": {"type": "string"},
        "trigger": {"type": "string"}, "probability_classification": {"type": "string"},
        "affected_claim_ids": _string_array(), "affected_calculation_ids": _string_array(),
        "changed_assumption_ids": _string_array(),
        "financial_inputs": {"type": "object", "additionalProperties": {"type": "string"}},
        "resulting_metrics": {"type": "object", "additionalProperties": {"type": "string"}},
        "source_ids": _string_array(), "evidence_ids": _string_array(),
        "assumption_ids": _string_array(), "mitigation": {"type": "string"},
        "residual_risk": {"type": "string"}, "monitoring_indicators": _string_array(),
        "human_review_required": {"type": "boolean"}, "limitations": _string_array(),
        "status": {"type": "string"}, "version": {"type": "integer"},
        "provider_attempt_id": {"type": "string"},
    }
)

DECISION_INPUT_SCHEMA = _strict_object(
    {
        "synthesis_input_id": {"type": "string"},
        "description": {"type": "string"},
        "source_object_ids": _string_array(),
    }
)


def block_c_provider_output_schema(contract: BusinessModuleContract) -> dict[str, Any]:
    properties = dict(block_a_provider_output_schema(contract)["properties"])
    name, schema = {
        "C1": ("diligence_findings", DILIGENCE_FINDING_SCHEMA),
        "C2": ("regulatory_risks", REGULATORY_RISK_SCHEMA),
        "C3": ("integration_risks", INTEGRATION_RISK_SCHEMA),
        "C4": ("downside_scenarios", DOWNSIDE_SCENARIO_SCHEMA),
        "C5": ("decision_inputs", DECISION_INPUT_SCHEMA),
    }[contract.module_id]
    properties[name] = {"type": "array", "items": schema}
    return _strict_object(properties)


def _redact(value: Any, secret: str = "") -> Any:
    sensitive_keys = {"api_key", "authorization", "headers", "bearer", "client_secret"}
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if str(key).lower() in sensitive_keys else _redact(item, secret)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, secret) for item in value]
    if isinstance(value, str) and secret:
        return value.replace(secret, "[REDACTED]")
    return value


def _sanitised_error(exc: Exception, secret: str = "") -> str:
    text = str(exc)
    if secret:
        text = text.replace(secret, "[REDACTED]")
    if "Bearer " in text:
        text = text.split("Bearer ", 1)[0] + "Bearer [REDACTED]"
    return text[:1000]


def _source_model(row: dict[str, Any], module_name: str = "Target Capability & Business Quality") -> Source:
    location = row.get("url") or row.get("original_filename")
    return Source(
        source_id=row["source_id"],
        source_name=row["page_title"],
        source_type=row["source_type"],
        url_or_file=location,
        used_for=module_name,
        reliability_tier=row["source_tier"],
        pce_eligible=bool(row["pce_eligible"]),
        source_replay_status="completed",
        limitations=row["limitations"],
    )


def build_provider_bundle(
    *,
    execution: ProviderExecution,
    request: ResearchRequest,
    contract: BusinessModuleContract,
    prior_objects: dict[str, list[dict[str, Any]]] | None = None,
    require_counterevidence: bool = False,
    allow_reused_sources: bool = False,
    pre_rejected_objects: list[dict[str, Any]] | None = None,
) -> ResearchBundle:
    validation = validate_provider_output(
        execution.structured_response,
        prior_objects=prior_objects,
        expected_module_id=contract.module_id,
        expected_module_name=contract.professional_name,
        require_counterevidence=require_counterevidence,
        allow_reused_sources=allow_reused_sources,
    )
    execution.trace["tool_calls"] = execution.tool_calls
    execution.trace["search_queries"] = execution.search_queries
    execution.trace["returned_citations"] = execution.returned_citations
    execution.trace["validation_outcome"] = validation.status.value
    execution.trace["admitted_object_ids"] = validation.admitted_object_ids
    extra_rejected = list(pre_rejected_objects or [])
    execution.trace["rejected_object_summaries"] = [*validation.rejected_objects, *extra_rejected]
    if validation.status != ProviderValidationStatus.ACCEPTED:
        execution.trace["error_class"] = "ProviderOutputValidationError"
        raise ProviderOutputValidationError(
            "Provider output failed Source-Evidence-Claim validation.",
            validation=to_primitive(validation),
            artifacts={
                "provider_response_raw": execution.raw_response,
                "provider_response_structured": execution.structured_response,
                "provider_trace": execution.trace,
                "tool_calls": execution.tool_calls,
                "search_queries": execution.search_queries,
                "returned_citations": execution.returned_citations,
                "validation_result": to_primitive(validation),
                "admitted_objects": {name: [] for name in OBJECT_COLLECTIONS},
                "rejected_objects": [*validation.rejected_objects, *extra_rejected],
                "follow_up_questions": execution.structured_response.get("suggested_follow_up_questions", []),
            },
        )

    payload = execution.structured_response
    structured_fields = set(payload["module_assessment"]["structured_output"])
    missing_contract_fields = sorted(set(contract.structured_output_fields) - structured_fields)
    if missing_contract_fields:
        raise ProviderOutputValidationError(
            f"{contract.module_id} module contract fields are missing: {missing_contract_fields}",
            validation={
                "status": "REJECTED",
                "errors": [{"type": "MODULE_CONTRACT_FAILURE", "reason": str(missing_contract_fields)}],
            },
            artifacts={
                "provider_response_raw": execution.raw_response,
                "provider_response_structured": payload,
                "provider_trace": {**execution.trace, "validation_outcome": "REJECTED", "error_class": "MODULE_CONTRACT_FAILURE"},
                "tool_calls": execution.tool_calls,
                "search_queries": execution.search_queries,
                "returned_citations": execution.returned_citations,
                "validation_result": {"status": "REJECTED"},
                "admitted_objects": {name: [] for name in OBJECT_COLLECTIONS},
                "rejected_objects": [{"object_type": "MODULE_CONTRACT_FAILURE", "reason": str(missing_contract_fields)}],
                "follow_up_questions": payload.get("suggested_follow_up_questions", []),
            },
        )
    sources = [_source_model(row, contract.professional_name) for row in payload["sources"]]
    evidence = [
        Evidence(
            evidence_id=row["evidence_id"],
            claim_id=row["claim_id"],
            source_id=row["source_id"],
            extracted_fact=row["extracted_fact"],
            evidence_type=row["evidence_type"],
            confidence=row["strength"],
            status=EvidenceStatus.AVAILABLE,
            supports_claim=row["direction"] == "support",
            human_review_required="management" in row["evidence_type"].lower(),
            limitations=row["limitations"],
        )
        for row in payload["evidence"]
    ]
    evidence_by_id = {item.evidence_id: item for item in evidence}
    prior_source_by_evidence = {
        row["evidence_id"]: row.get("source_id", "")
        for row in (prior_objects or {}).get("evidence", [])
    }
    claims: list[Claim] = []
    for row in payload["claims"]:
        source_ids = []
        for evidence_id in row["supporting_evidence_ids"]:
            source_id = (
                evidence_by_id[evidence_id].source_id
                if evidence_id in evidence_by_id
                else prior_source_by_evidence.get(evidence_id, "")
            )
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
        claims.append(
            Claim(
                claim_id=row["claim_id"],
                claim_text=row["claim_text"],
                business_module=contract.professional_name,
                evidence_ids=list(row["supporting_evidence_ids"]),
                source_ids=source_ids,
                pce_status=PCEStatus.NOT_CERTIFIED,
                human_review_required=bool(row["human_review_required"]),
                claim_class=row["claim_class"],
                materiality=row["materiality"],
                counterevidence_ids=list(row["counterevidence_ids"]),
                delivery_allowed=False,
            )
        )
    assumptions = [AssumptionRecord(**row) for row in payload["assumptions"]]
    unknowns = [UnknownRecord(**row) for row in payload["unknowns"]]
    counterevidence = [CounterEvidenceRecord(**row) for row in payload["counterevidence"]]
    assessment = payload["module_assessment"]
    supporting_ids = [row["evidence_id"] for row in payload["evidence"] if row["direction"] == "support"]
    module_result = BusinessModuleResult(
        module_id=contract.module_id,
        professional_name=contract.professional_name,
        owning_block=contract.owning_block,
        prompt_reference=contract.prompt_reference,
        research_question_ids=[request.request_id],
        facts=[row["extracted_fact"] for row in payload["evidence"] if row["direction"] == "support"],
        inferences=[row["claim_text"] for row in payload["claims"]],
        assumptions=[row["assumption_id"] for row in payload["assumptions"]],
        unknowns=[row["unknown_id"] for row in payload["unknowns"]],
        limitations=list(assessment["limitations"]),
        supporting_evidence_ids=supporting_ids,
        counterevidence_ids=[row["counterevidence_id"] for row in payload["counterevidence"]],
        claim_ids=[row["claim_id"] for row in payload["claims"]],
        calculation_ids=[],
        pce_status=PCEStatus.NOT_CERTIFIED,
        er_brb_result={},
        business_conclusion=assessment["business_conclusion"],
        human_review_triggers=[
            row["description"] for row in payload["unknowns"] if row["human_review_required"]
        ],
        structured_output={
            **assessment["structured_output"],
            "criterion_outcome": assessment["criterion_outcome"],
            "conditions": assessment["conditions"],
        },
        possible_gap_types=list(contract.possible_gap_types),
    )
    response = ResearchResponse(
        response_id=execution.response_id,
        request_id=request.request_id,
        module_id=request.module_id,
        prompt_reference=request.prompt_reference,
        source_ids=[row["source_id"] for row in payload["sources"]],
        evidence_ids=[row["evidence_id"] for row in payload["evidence"]],
        claim_ids=[row["claim_id"] for row in payload["claims"]],
        assumption_ids=[row["assumption_id"] for row in payload["assumptions"]],
        unknown_ids=[row["unknown_id"] for row in payload["unknowns"]],
        counterevidence_ids=[row["counterevidence_id"] for row in payload["counterevidence"]],
        result_payload=assessment,
        provenance=execution.provider_type.value,
    )
    return ResearchBundle(
        response=response,
        sources=sources,
        evidence=evidence,
        claims=claims,
        assumptions=assumptions,
        unknowns=unknowns,
        counterevidence=counterevidence,
        module_result=module_result,
        provider_artifacts={
            "provider_type": execution.provider_type.value,
            "provider_response_raw": execution.raw_response,
            "provider_response_structured": payload,
            "provider_trace": execution.trace,
            "tool_calls": execution.tool_calls,
            "search_queries": execution.search_queries,
            "returned_citations": execution.returned_citations,
            "validation_result": to_primitive(validation),
            "admitted_objects": {name: payload[name] for name in OBJECT_COLLECTIONS},
            "rejected_objects": [*validation.rejected_objects, *extra_rejected],
            "follow_up_questions": payload["suggested_follow_up_questions"],
            "conflicts": list(payload.get("conflicts", [])),
        },
    )


def _expand_compact_recorded_response(
    compact: dict[str, Any], *, row: dict[str, Any], contract: BusinessModuleContract
) -> dict[str, Any]:
    """Expand a concise recorded fixture before the normal admission validator.

    The expanded object uses exactly the same Source-Evidence-Claim contract as
    live output. This helper changes fixture authoring only; it does not bypass
    validation, certification, Gate authority, or provider traces.
    """

    response_id = str(row["response_id"])
    timestamp = str(row.get("response_timestamp", ""))
    sources = []
    for item in compact.get("sources", []):
        sources.append({
            "source_id": item["source_id"],
            "url": item["url"],
            "page_title": item["page_title"],
            "publisher_or_owner": item["publisher_or_owner"],
            "source_type": item["source_type"],
            "source_tier": item.get("source_tier", "Tier 1 authoritative public source"),
            "publication_date": item.get("publication_date", ""),
            "retrieval_timestamp": timestamp,
            "author": item.get("author", item["publisher_or_owner"]),
            "exact_relevant_locator": item["exact_relevant_locator"],
            "discovery_query": item.get("discovery_query", "recorded Block C research query"),
            "provider_response_reference": response_id,
            "pce_eligible": bool(item.get("pce_eligible", True)),
            "limitations": item.get("limitations", "Public-source research is not complete private due diligence."),
            "confidentiality_classification": item.get("confidentiality_classification", "public"),
            "source_kind": item.get("source_kind", "web"),
        })
    evidence = []
    for item in compact.get("evidence", []):
        evidence.append({
            "evidence_id": item["evidence_id"],
            "claim_id": item["claim_id"],
            "source_id": item["source_id"],
            "extracted_fact": item["extracted_fact"],
            "exact_locator": item["exact_locator"],
            "direction": item.get("direction", "support"),
            "evidence_type": item.get("evidence_type", "authoritative public document"),
            "strength": item.get("strength", "medium"),
            "limitations": item.get("limitations", "Public-source research is not complete private due diligence."),
            "extraction_timestamp": timestamp,
        })
    claims = []
    for item in compact.get("claims", []):
        claims.append({
            "claim_id": item["claim_id"],
            "claim_text": item["claim_text"],
            "claim_class": item.get("claim_class", "evidence-supported inference"),
            "materiality": item.get("materiality", "material"),
            "supporting_evidence_ids": list(item["supporting_evidence_ids"]),
            "counterevidence_ids": list(item.get("counterevidence_ids", [])),
            "confidence": item.get("confidence", "medium"),
            "limitations": item.get("limitations", "Public-source research is not complete private due diligence."),
            "owning_module": contract.professional_name,
            "decision_relevance": item.get("decision_relevance", contract.decision_relevance),
            "delivery_request": item.get("delivery_request", "conditional delivery only"),
            "human_review_required": bool(item.get("human_review_required", False)),
            "claim_family_id": item.get("claim_family_id", item["claim_id"]),
            "claim_version": int(item.get("claim_version", 1)),
            "supersedes_claim_id": item.get("supersedes_claim_id", ""),
            "dependency_claim_ids": list(item.get("dependency_claim_ids", [])),
        })
    return {
        "sources": sources,
        "evidence": evidence,
        "claims": claims,
        "assumptions": list(compact.get("assumptions", [])),
        "unknowns": list(compact.get("unknowns", [])),
        "counterevidence": list(compact.get("counterevidence", [])),
        "conflicts": list(compact.get("conflicts", [])),
        "suggested_follow_up_questions": list(compact.get("suggested_follow_up_questions", [])),
        "retrieval_summary": compact.get("retrieval_summary", f"Recorded {contract.module_id} research result."),
        "searched_queries": list(compact.get("searched_queries", [])),
        "pages_or_files_inspected": list(compact.get("pages_or_files_inspected", [])),
        "unresolved_conflicts": list(compact.get("unresolved_conflicts", [])),
        "returned_citations": list(compact.get("returned_citations", [])),
        "provider_metadata": {
            "provider_response_reference": response_id,
            "research_scope": contract.module_id,
            "as_of_date": compact.get("as_of_date", ""),
            "limitations": list(compact.get("provider_limitations", ["Recorded research is subject to the registered case boundaries."])),
        },
        "module_assessment": dict(compact["module_assessment"]),
        **dict(compact.get("module_records", {})),
    }


class RecordedResearchProvider:
    """Replays recorded provider output through the same validator as live output."""

    def __init__(
        self,
        recording_path: Path,
        *,
        attempt_index: int,
        attachments: list[AttachmentRecord] | None = None,
        prior_objects: dict[str, list[dict[str, Any]]] | None = None,
        shared_registry: Any | None = None,
        execution_mode: ProviderMode = ProviderMode.RECORDED,
    ) -> None:
        self.recording_path = recording_path
        self.attempt_index = attempt_index
        self.attachments = attachments or []
        self.prior_objects = prior_objects or {name: [] for name in OBJECT_COLLECTIONS}
        self.shared_registry = shared_registry
        self.execution_mode = execution_mode

    def research(self, request: ResearchRequest, contract: BusinessModuleContract) -> ResearchBundle:
        if request.module_id != contract.module_id:
            raise ProviderConfigurationError("ResearchRequest and module contract ownership do not match.")
        recording = json.loads(self.recording_path.read_text(encoding="utf-8"))
        if isinstance(recording.get("modules"), dict):
            attempts = recording["modules"].get(request.module_id, {}).get("attempts", [])
        else:
            attempts = recording.get("attempts", [])
        if self.attempt_index >= len(attempts):
            raise ProviderTechnicalError(
                f"Recorded provider has no {request.module_id} response for attempt {self.attempt_index + 1}."
            )
        row = attempts[self.attempt_index]
        raw_payload = json.loads(json.dumps(
            row["structured_response"]
            if "structured_response" in row
            else _expand_compact_recorded_response(row["compact_response"], row=row, contract=contract)
        ))
        payload = json.loads(json.dumps(raw_payload))
        if self.attempt_index == 0 and self.attachments:
            allowed_attachment_ids = set(request.attachment_use)
            selected_attachments = [
                item
                for item in self.attachments
                if item.attachment_id in allowed_attachment_ids
                or (request.module_id == "A5" and not allowed_attachment_ids)
            ]
            attachment_sources = {item.source_id: attachment_source(item) for item in selected_attachments}
            returned_sources = {item.get("source_id"): item for item in payload.get("sources", [])}
            returned_sources.update({key: item for key, item in attachment_sources.items() if key not in returned_sources})
            payload["sources"] = list(returned_sources.values())
        raw_for_artifact = json.loads(json.dumps(payload))
        duplicate_rejections: list[dict[str, Any]] = []
        source_aliases: dict[str, str] = {}
        if self.shared_registry is not None:
            payload, duplicate_rejections, source_aliases = self.shared_registry.canonicalise_payload(payload)
        execution = ProviderExecution(
            provider_type=self.execution_mode,
            model_identifier=str(recording.get("model_identifier", "recorded-provider")),
            response_id=str(row["response_id"]),
            structured_response=payload,
            raw_response={
                "recording_id": recording.get("recording_id"),
                "attempt_index": self.attempt_index,
                "recorded_response": raw_for_artifact,
            },
            trace={
                "provider_type": self.execution_mode.value,
                "model_identifier": recording.get("model_identifier", "recorded-provider"),
                "response_id": row["response_id"],
                "request_timestamp": row["request_timestamp"],
                "response_timestamp": row["response_timestamp"],
                "elapsed_seconds": row.get("elapsed_seconds", 0),
                "retry_count": 0,
                "timeout_seconds": 0,
                "usage": row.get("usage", {}),
                "file_references": row.get("file_references", []),
                "error_class": "",
            },
            tool_calls=list(row.get("tool_calls", [])),
            search_queries=list(payload.get("searched_queries", [])),
            returned_citations=list(payload.get("returned_citations", [])),
        )
        bundle = build_provider_bundle(
            execution=execution,
            request=request,
            contract=contract,
            prior_objects=self.prior_objects,
            require_counterevidence=isinstance(recording.get("modules"), dict),
            allow_reused_sources=isinstance(recording.get("modules"), dict),
            pre_rejected_objects=duplicate_rejections,
        )
        bundle.provider_artifacts["source_aliases"] = source_aliases
        return bundle


class DeterministicBlockAResearchProvider(RecordedResearchProvider):
    """Deterministic Block A replay through the same contract and admission path."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["execution_mode"] = ProviderMode.DETERMINISTIC
        super().__init__(*args, **kwargs)


def check_openai_live_configuration() -> dict[str, Any]:
    key_present = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    model_present = bool(os.environ.get("OPENAI_MODEL", "").strip())
    sdk_available = importlib.util.find_spec("openai") is not None
    issues = []
    if not key_present:
        issues.append("OPENAI_API_KEY is not set.")
    if not model_present:
        issues.append("OPENAI_MODEL is not set.")
    if not sdk_available:
        issues.append("OpenAI SDK is unavailable; install the new agent's requirements-live.txt.")
    for name in (
        "OPENAI_RESEARCH_TIMEOUT",
        "OPENAI_MAX_TOOL_CALLS",
        "OPENAI_MAX_PROVIDER_ATTEMPTS",
        "OPENAI_MAX_ESTIMATED_TOKENS",
        "OPENAI_BLOCK_A_REQUEST_BUDGET",
        "OPENAI_BLOCK_B_REQUEST_BUDGET",
        "OPENAI_BLOCK_C_REQUEST_BUDGET",
        "OPENAI_PER_MODULE_BUDGET",
    ):
        value = os.environ.get(name)
        if value:
            try:
                if float(value) <= 0:
                    raise ValueError
            except ValueError:
                issues.append(f"{name} must be a positive number.")
    return {
        "ready": not issues,
        "checks": {
            "api_key_present": key_present,
            "model_present": model_present,
            "sdk_available": sdk_available,
        },
        "issues": issues,
        "paid_request_made": False,
    }


def _extract_openai_trace(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    tool_calls: list[dict[str, Any]] = []
    queries: list[str] = []
    citations: list[dict[str, Any]] = []
    for item in raw.get("output", []):
        if item.get("type") == "web_search_call":
            action = item.get("action") or {}
            tool_calls.append(
                {
                    "id": item.get("id", ""),
                    "type": "web_search_call",
                    "status": item.get("status", ""),
                    "action": action,
                }
            )
            for query in action.get("queries", []) or ([action.get("query")] if action.get("query") else []):
                if query and query not in queries:
                    queries.append(query)
        if item.get("type") == "message":
            for content in item.get("content", []):
                for annotation in content.get("annotations", []):
                    if annotation.get("type") == "url_citation":
                        citation = {
                            "url": annotation.get("url", ""),
                            "title": annotation.get("title", ""),
                            "start_index": int(annotation.get("start_index", 0)),
                            "end_index": int(annotation.get("end_index", 0)),
                        }
                        if citation not in citations:
                            citations.append(citation)
    return tool_calls, queries, citations


class OpenAIResearchProvider:
    """Acquisition-module Responses API provider with no recorded fallback."""

    def __init__(
        self,
        *,
        attachments: list[AttachmentRecord],
        prior_objects: dict[str, list[dict[str, Any]]] | None = None,
        shared_registry: Any | None = None,
    ) -> None:
        self.attachments = attachments
        self.prior_objects = prior_objects or {name: [] for name in OBJECT_COLLECTIONS}
        self.shared_registry = shared_registry

    def _configuration(self, request: ResearchRequest) -> dict[str, Any]:
        check = check_openai_live_configuration()
        if not check["ready"]:
            raise ProviderConfigurationError("; ".join(check["issues"]))
        budget = request.search_budget
        return {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model": os.environ["OPENAI_MODEL"],
            "timeout": float(os.environ.get("OPENAI_RESEARCH_TIMEOUT", budget.get("timeout_seconds", 180))),
            "max_tool_calls": int(os.environ.get("OPENAI_MAX_TOOL_CALLS", budget.get("maximum_tool_calls", 8))),
            "max_provider_attempts": int(os.environ.get("OPENAI_MAX_PROVIDER_ATTEMPTS", budget.get("maximum_provider_attempts", 2))),
            "max_estimated_tokens": int(os.environ.get("OPENAI_MAX_ESTIMATED_TOKENS", budget.get("maximum_estimated_tokens", 12000))),
        }

    def _input(self, request: ResearchRequest, contract: BusinessModuleContract) -> list[dict[str, Any]]:
        prompt_id = contract.prompt_reference.rsplit("#", 1)[-1]
        approved_prompt = load_prompt_registry()[prompt_id]
        is_block_b = request.owning_block.value == "Block B: Value Creation and Pricing"
        is_block_c = request.owning_block.value == "Block C: Risk, Diligence and Decision"
        boundary = (
            "The provider researches only its owning Block C module. It does not certify Claims, evaluate Gate C, "
            "select the final Decision State, grant delivery permission, give definitive legal advice, or make final human transaction approval."
            if is_block_c
            else
            "The provider does not certify Claims, evaluate Gate B, perform Block C, choose price, "
            "or make a transaction recommendation. Deterministic calculations and replay occur after admission."
            if is_block_b
            else "The provider does not certify Claims, evaluate Gate A, perform Block B or Block C, "
            "value the target, or make a transaction recommendation."
        )
        system_text = (
            f"Execute the approved {contract.module_id} acquisition research prompt below exactly within its authority limits. "
            f"Return only the required structured output. {boundary}\n\n"
            + json.dumps(approved_prompt, ensure_ascii=False, indent=2)
        )
        request_payload = to_primitive(request)
        user_parts: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": f"{contract.module_id} ResearchRequest:\n" + json.dumps(request_payload, ensure_ascii=False, indent=2),
            }
        ]
        allowed_attachment_ids = set(request.attachment_use)
        selected_attachments = [
            item
            for item in self.attachments
            if item.attachment_id in allowed_attachment_ids
            or (request.module_id == "A5" and not allowed_attachment_ids)
        ]
        for attachment in selected_attachments:
            if attachment.confidentiality.lower() != "public" and not attachment.allow_provider_upload:
                raise ProviderConfigurationError(
                    f"Confidential attachment {attachment.attachment_id} is not permitted for provider upload."
                )
            if attachment.file_type == "pdf":
                encoded = base64.b64encode(Path(attachment.absolute_path).read_bytes()).decode("ascii")
                user_parts.append(
                    {
                        "type": "input_file",
                        "filename": attachment.original_filename,
                        "file_data": f"data:application/pdf;base64,{encoded}",
                    }
                )
            else:
                user_parts.append(
                    {
                        "type": "input_text",
                        "text": (
                            f"Attachment Source ID {attachment.source_id}; filename {attachment.original_filename}; "
                            f"hash {attachment.file_hash_sha256}; locator policy {attachment.locator}.\n"
                            f"---BEGIN ATTACHMENT---\n{attachment.local_text}\n---END ATTACHMENT---"
                        ),
                    }
                )
        return [
            {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
            {"role": "user", "content": user_parts},
        ]

    def research(self, request: ResearchRequest, contract: BusinessModuleContract) -> ResearchBundle:
        if request.module_id != contract.module_id or request.module_id not in {
            "A1", "A2", "A3", "A4", "A5", "A6", "A7", "B1", "B2", "B3", "B4", "B5",
            "C1", "C2", "C3", "C4", "C5",
        }:
            raise ProviderConfigurationError("OpenAI live research is restricted to the owning acquisition module.")
        config = self._configuration(request)
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise ProviderDependencyError(
                "OpenAI SDK is unavailable; install requirements-live.txt inside the new agent."
            ) from exc

        client = OpenAI(api_key=config["api_key"], timeout=config["timeout"], max_retries=0)
        started = time.monotonic()
        requested_at = _now()
        last_error: Exception | None = None
        response = None
        retry_count = 0
        for attempt in range(config["max_provider_attempts"]):
            try:
                response = client.responses.create(
                    model=config["model"],
                    tools=[{"type": "web_search", "search_context_size": "high"}],
                    tool_choice="auto",
                    include=["web_search_call.action.sources"],
                    input=self._input(request, contract),
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": f"{contract.owning_block.name.lower()}_{contract.module_id.lower()}_research",
                            "strict": True,
                            "schema": (
                                A5_PROVIDER_OUTPUT_SCHEMA
                                if request.module_id == "A5" and not request.dependency_claims
                                else (
                                    block_b_provider_output_schema(contract)
                                    if request.module_id.startswith("B")
                                    else block_c_provider_output_schema(contract)
                                    if request.module_id.startswith("C")
                                    else block_a_provider_output_schema(contract)
                                )
                            ),
                        }
                    },
                    max_tool_calls=config["max_tool_calls"],
                    max_output_tokens=config["max_estimated_tokens"],
                )
                retry_count = attempt
                break
            except Exception as exc:  # SDK exception classes are optional until lazy import succeeds.
                last_error = exc
                transient = exc.__class__.__name__ in {
                    "RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError"
                }
                if not transient or attempt + 1 >= config["max_provider_attempts"]:
                    raise ProviderTechnicalError(
                        f"OpenAI provider failure ({exc.__class__.__name__}): "
                        f"{_sanitised_error(exc, config['api_key'])}"
                    ) from exc
                retry_count = attempt + 1
        if response is None:
            raise ProviderTechnicalError(
                f"OpenAI provider returned no response: {_sanitised_error(last_error or RuntimeError('empty response'), config['api_key'])}"
            )
        raw = _redact(response.model_dump(mode="json"), config["api_key"])
        tool_calls, queries, citations = _extract_openai_trace(raw)
        if len(tool_calls) > config["max_tool_calls"]:
            raise ProviderTechnicalError("OpenAI provider exceeded the configured maximum tool-call budget.")
        output_text = getattr(response, "output_text", "")
        if not output_text:
            raise ProviderTechnicalError("OpenAI provider returned an empty structured research result.")
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ProviderOutputValidationError(
                "OpenAI structured output was not valid JSON.",
                validation={
                    "status": "REJECTED",
                    "errors": [{"type": "MALFORMED_OUTPUT", "reason": "Response was not valid JSON."}],
                },
                artifacts={
                    "provider_response_raw": raw,
                    "provider_response_structured": {},
                    "provider_trace": {
                        "provider_type": ProviderMode.OPENAI_LIVE.value,
                        "model_identifier": config["model"],
                        "response_id": raw.get("id", ""),
                        "request_timestamp": requested_at,
                        "response_timestamp": _now(),
                        "elapsed_seconds": round(time.monotonic() - started, 6),
                        "retry_count": retry_count,
                        "timeout_seconds": config["timeout"],
                        "validation_outcome": "REJECTED",
                        "error_class": "MALFORMED_OUTPUT",
                    },
                    "tool_calls": tool_calls,
                    "search_queries": queries,
                    "returned_citations": citations,
                    "validation_result": {"status": "REJECTED"},
                    "admitted_objects": {name: [] for name in OBJECT_COLLECTIONS},
                    "rejected_objects": [{"object_type": "MALFORMED_OUTPUT", "reason": "Response was not valid JSON."}],
                    "follow_up_questions": [],
                },
            ) from exc
        allowed_attachment_ids = set(request.attachment_use)
        selected_attachments = [
            item
            for item in self.attachments
            if item.attachment_id in allowed_attachment_ids
            or (request.module_id == "A5" and not allowed_attachment_ids)
        ]
        attachment_sources = {item.source_id: attachment_source(item) for item in selected_attachments}
        returned_sources = {row.get("source_id"): row for row in payload.get("sources", [])}
        returned_sources.update({key: row for key, row in attachment_sources.items() if key not in returned_sources})
        payload["sources"] = list(returned_sources.values())
        payload["returned_citations"] = citations
        duplicate_rejections: list[dict[str, Any]] = []
        source_aliases: dict[str, str] = {}
        if self.shared_registry is not None:
            payload, duplicate_rejections, source_aliases = self.shared_registry.canonicalise_payload(payload)
        usage = raw.get("usage") or {}
        total_tokens = usage.get("total_tokens")
        if isinstance(total_tokens, int) and total_tokens > config["max_estimated_tokens"]:
            raise ProviderTechnicalError("OpenAI provider exceeded the configured token budget.")
        execution = ProviderExecution(
            provider_type=ProviderMode.OPENAI_LIVE,
            model_identifier=config["model"],
            response_id=str(raw.get("id", "")),
            structured_response=payload,
            raw_response=raw,
            trace={
                "provider_type": ProviderMode.OPENAI_LIVE.value,
                "model_identifier": config["model"],
                "response_id": raw.get("id", ""),
                "request_timestamp": requested_at,
                "response_timestamp": _now(),
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "tool_call_count": len(tool_calls),
                "retry_count": retry_count,
                "timeout_seconds": config["timeout"],
                "usage": usage,
                "file_references": [item.source_id for item in self.attachments],
                "error_class": "",
            },
            tool_calls=tool_calls,
            search_queries=queries,
            returned_citations=citations,
        )
        bundle = build_provider_bundle(
            execution=execution,
            request=request,
            contract=contract,
            prior_objects=self.prior_objects,
            require_counterevidence=self.shared_registry is not None,
            allow_reused_sources=self.shared_registry is not None,
            pre_rejected_objects=duplicate_rejections,
        )
        bundle.provider_artifacts["source_aliases"] = source_aliases
        return bundle
