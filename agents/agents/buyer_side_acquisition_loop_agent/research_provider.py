from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .business_models import (
    AssumptionRecord,
    BusinessModuleContract,
    BusinessModuleResult,
    CounterEvidenceRecord,
    ResearchRequest,
    ResearchResponse,
    UnknownRecord,
)
from .models import Claim, Evidence, EvidenceStatus, PCEStatus, Source


@dataclass
class ResearchBundle:
    response: ResearchResponse
    sources: list[Source]
    evidence: list[Evidence]
    claims: list[Claim]
    assumptions: list[AssumptionRecord]
    unknowns: list[UnknownRecord]
    counterevidence: list[CounterEvidenceRecord]
    module_result: BusinessModuleResult
    provider_artifacts: dict[str, Any] = field(default_factory=dict)


class ResearchProvider(Protocol):
    def research(
        self, request: ResearchRequest, contract: BusinessModuleContract
    ) -> ResearchBundle: ...


class DeterministicResearchProvider:
    """Reads only registered case fixtures; it performs no web or LLM research."""

    def __init__(
        self,
        fixtures: dict[str, dict[str, Any]],
        *,
        source_registry: dict[str, dict[str, Any]] | None = None,
        evidence_registry: dict[str, dict[str, Any]] | None = None,
        claim_registry: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._fixtures = fixtures
        self._source_registry = source_registry or {}
        self._evidence_registry = evidence_registry or {}
        self._claim_registry = claim_registry or {}

    def research(
        self, request: ResearchRequest, contract: BusinessModuleContract
    ) -> ResearchBundle:
        if request.module_id not in self._fixtures:
            raise ValueError(f"no deterministic fixture registered for {request.module_id}")
        fixture = self._fixtures[request.module_id]
        source_rows = fixture.get("sources") or [self._source_registry[item] for item in fixture.get("source_ids", [])]
        evidence_rows = fixture.get("evidence") or [self._evidence_registry[item] for item in fixture.get("evidence_ids", [])]
        claim_rows = fixture.get("claims") or [self._claim_registry[item] for item in fixture.get("claim_ids", [])]
        sources = [Source(**item) for item in source_rows]
        evidence = [
            Evidence(**{**item, "status": EvidenceStatus(item["status"])})
            for item in evidence_rows
        ]
        claims = [Claim(**item) for item in claim_rows]
        evidence_by_claim: dict[str, list[Evidence]] = {}
        for item in evidence:
            evidence_by_claim.setdefault(item.claim_id, []).append(item)
        for claim in claims:
            for item in evidence_by_claim.get(claim.claim_id, []):
                claim.add_lineage(item)
        assumptions = [AssumptionRecord(**item) for item in fixture.get("assumptions", [])]
        unknowns = [UnknownRecord(**item) for item in fixture.get("unknowns", [])]
        counterevidence = [
            CounterEvidenceRecord(**item) for item in fixture.get("counterevidence", [])
        ]
        result_payload = dict(fixture.get("result_payload", {}))
        module_result = BusinessModuleResult(
            module_id=contract.module_id,
            professional_name=contract.professional_name,
            owning_block=contract.owning_block,
            prompt_reference=contract.prompt_reference,
            research_question_ids=[f"RQ-{contract.module_id}-{i:02d}" for i, _ in enumerate(contract.required_research_questions, 1)],
            facts=list(result_payload.get("facts", [])),
            inferences=list(result_payload.get("inferences", [])),
            assumptions=[item.assumption_id for item in assumptions],
            unknowns=[item.unknown_id for item in unknowns],
            limitations=list(result_payload.get("limitations", [])),
            supporting_evidence_ids=[item.evidence_id for item in evidence if item.supports_claim],
            counterevidence_ids=[item.counterevidence_id for item in counterevidence],
            claim_ids=[item.claim_id for item in claims],
            calculation_ids=list(result_payload.get("calculation_ids", [])),
            pce_status=PCEStatus.NOT_CERTIFIED,
            er_brb_result={},
            business_conclusion=result_payload["business_conclusion"],
            human_review_triggers=list(result_payload.get("human_review_triggers", [])),
            structured_output=dict(result_payload["structured_output"]),
            possible_gap_types=list(contract.possible_gap_types),
        )
        response = ResearchResponse(
            response_id=f"RESP-{request.module_id}",
            request_id=request.request_id,
            module_id=request.module_id,
            prompt_reference=request.prompt_reference,
            source_ids=[item.source_id for item in sources],
            evidence_ids=[item.evidence_id for item in evidence],
            claim_ids=[item.claim_id for item in claims],
            assumption_ids=[item.assumption_id for item in assumptions],
            unknown_ids=[item.unknown_id for item in unknowns],
            counterevidence_ids=[item.counterevidence_id for item in counterevidence],
            result_payload=result_payload,
            provenance="deterministic_case_fixture",
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
        )
