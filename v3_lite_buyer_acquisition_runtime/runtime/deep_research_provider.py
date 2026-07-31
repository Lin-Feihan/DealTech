from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DeepResearchProviderError(ValueError):
    pass


OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL_ENV = "OPENAI_DEEP_RESEARCH_MODEL"
OPENAI_TOOL_MODE_ENV = "OPENAI_DEEP_RESEARCH_TOOL_MODE"

DEEP_RESEARCH_MODES = {"live_openai_deep_research", "replay_deep_research_response"}
DEEP_RESEARCH_RESPONSE_REQUIRED_FIELDS = {
    "case_id",
    "provider",
    "model",
    "response_id",
    "completed_at",
    "sources",
    "evidence_items",
    "candidate_claims",
    "claim_evidence_links",
    "source_gaps",
    "provider_notes",
}
FINAL_REPORT_SUBSTITUTE_FIELDS = {
    "final_report",
    "final_report_text",
    "report",
    "report_text",
    "investment_memo",
    "recommendation",
    "recommendation_decision",
}
ALLOWED_CLAIM_TYPES = {
    "transaction_background",
    "transaction_terms",
    "transaction_timing",
    "transaction_document_date",
    "transaction_parties",
    "transaction_consideration",
    "contingent_consideration",
    "milestone_economics",
    "milestone_payment",
    "financing_or_payment_mechanics",
    "entity_identity",
    "entity_lineage",
    "asset_or_product_identity",
    "scientific_asset",
    "asset_lineage",
    "ownership_or_governance",
    "management_or_key_person",
    "intellectual_property",
    "regulatory_or_clinical",
    "financial_performance",
    "valuation_input",
    "synergy_or_value_creation",
    "market_or_competitive_position",
    "legal_or_regulatory_risk",
    "integration_or_operational_risk",
    "source_gap_claim",
    "generic_fact",
    "derived_numeric_candidate",
}
CLAIM_EVIDENCE_LINK_TYPES = {
    "supports",
    "partially_supports",
    "contextualizes",
    "contradicts",
    "requires_verification",
}


def build_deep_research_request(
    mandate: dict[str, Any],
    research_plan: dict[str, Any],
    case_seed: dict[str, Any],
    source_discovery_plan: dict[str, Any],
    model: str,
    targeted_source_discovery_plan: dict[str, Any] | None = None,
    repair_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    must_answer_questions = [need["target_fact_or_question"] for need in source_discovery_plan["source_needs"]]
    if targeted_source_discovery_plan is not None:
        for target in targeted_source_discovery_plan.get("targeted_source_needs", []):
            if target.get("target_fact_or_question"):
                must_answer_questions.append(target["target_fact_or_question"])
    if repair_plan is not None:
        for step in repair_plan.get("repair_steps", []):
            if step.get("reason"):
                must_answer_questions.append(step["reason"])

    required_source_categories = sorted(
        {
            source_type
            for need in source_discovery_plan["source_needs"]
            for source_type in need.get("preferred_source_types", [])
        }
    )

    request = {
        "case_id": mandate["case_id"],
        "generated_artifact": "deep_research_request.json",
        "stage": "M2_deep_research_provider_request",
        "provider": "openai_deep_research",
        "model": model,
        "created_at": _now_utc_iso(),
        "research_objective": research_plan["research_objective"],
        "source_priority_rules": source_discovery_plan["source_priority_rules"],
        "must_answer_questions": must_answer_questions,
        "required_source_categories": required_source_categories,
        "forbidden_source_uses": [
            *source_discovery_plan["forbidden_source_uses"],
            "Do not rely on model memory.",
            "Do not use the case_seed as evidence.",
            "Do not treat summaries or prior reports as authoritative evidence.",
            "Do not treat user-provided case briefs, mandate notes, case seeds, model memory, or unverified local notes as evidence.",
        ],
        "output_requirements": [
            "You are not writing the final acquisition report.",
            "You are acting as a source discovery and evidence collection provider for a downstream M&A agent runtime.",
            "Return structured JSON with sources, evidence_items, candidate_claims, claim_evidence_links, source_gaps, uncertainties or limitations, and provider_notes.",
            "Candidate claims are not certified claims; M5 decides certification, caveats, repair, human review, and report eligibility.",
            "Prefer primary and official sources over summaries.",
            "For personal proceeds or founder economics, require direct authoritative evidence or mark unresolved.",
        ],
        "source_manifest_requirements": [
            "Every source must include provider_source_id, title, url or document identifier, source_type, source_owner, source_date_or_period, source_reliability_rationale, and source_limitations.",
            "Original cited sources matter; provider summaries are not authoritative sources.",
        ],
        "raw_evidence_requirements": [
            "Every evidence item must include a source reference, source URL or document identifier, extracted quote or bounded summary, source type, source date or period, reliability rationale, supported fact, and caveats.",
            "No source-less evidence is allowed.",
            "Only original cited authoritative sources may become evidence.",
        ],
    }
    validate_deep_research_request(request)
    return request


def validate_deep_research_request(request: Any) -> None:
    if not isinstance(request, dict):
        raise DeepResearchProviderError("deep_research_request must be an object.")
    required = {
        "case_id",
        "generated_artifact",
        "stage",
        "provider",
        "model",
        "created_at",
        "research_objective",
        "source_priority_rules",
        "must_answer_questions",
        "required_source_categories",
        "forbidden_source_uses",
        "output_requirements",
        "source_manifest_requirements",
        "raw_evidence_requirements",
    }
    missing = sorted(field for field in required if field not in request)
    if missing:
        raise DeepResearchProviderError(f"deep_research_request missing field(s): {', '.join(missing)}")
    if request["generated_artifact"] != "deep_research_request.json":
        raise DeepResearchProviderError("generated_artifact must be deep_research_request.json.")
    if request["stage"] != "M2_deep_research_provider_request":
        raise DeepResearchProviderError("stage must be M2_deep_research_provider_request.")
    if request["provider"] != "openai_deep_research":
        raise DeepResearchProviderError("provider must be openai_deep_research.")
    if not isinstance(request["model"], str) or not request["model"].strip():
        raise DeepResearchProviderError("model must be a non-empty string.")
    for field in (
        "source_priority_rules",
        "must_answer_questions",
        "required_source_categories",
        "forbidden_source_uses",
        "output_requirements",
        "source_manifest_requirements",
        "raw_evidence_requirements",
    ):
        if not isinstance(request[field], list) or not request[field]:
            raise DeepResearchProviderError(f"{field} must be a non-empty array.")


def load_replay_response(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise DeepResearchProviderError(f"Replay Deep Research response not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DeepResearchProviderError(f"Replay Deep Research response is invalid JSON: {exc}") from exc


def call_openai_deep_research(
    request_artifact: dict[str, Any],
    api_key: str | None,
    model: str | None,
    tool_mode: str | None,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    api_key_value = (api_key or os.getenv(OPENAI_API_KEY_ENV, "")).strip()
    model_value = (model or os.getenv(OPENAI_MODEL_ENV, "")).strip()
    if not api_key_value:
        raise DeepResearchProviderError(f"Missing {OPENAI_API_KEY_ENV}; Deep Research live mode failed closed.")
    if not model_value:
        raise DeepResearchProviderError(f"Missing {OPENAI_MODEL_ENV}; Deep Research live mode failed closed.")

    prompt = _deep_research_prompt(request_artifact)
    payload: dict[str, Any] = {
        "model": model_value,
        "input": prompt,
    }
    tool_mode_value = (tool_mode or os.getenv(OPENAI_TOOL_MODE_ENV, "")).strip()
    if tool_mode_value:
        payload["tools"] = [{"type": tool_mode_value}]

    request_body = json.dumps(payload).encode("utf-8")
    http_request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=request_body,
        headers={
            "Authorization": f"Bearer {api_key_value}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DeepResearchProviderError(f"OpenAI Deep Research live mode failed closed: HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DeepResearchProviderError(f"OpenAI Deep Research live mode failed closed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DeepResearchProviderError(f"OpenAI Deep Research live mode returned invalid JSON: {exc}") from exc


def extract_normalized_response(raw_payload: dict[str, Any], expected_case_id: str) -> dict[str, Any]:
    if _looks_like_normalized_response(raw_payload):
        response = dict(raw_payload)
    else:
        extracted = _extract_json_text(raw_payload)
        try:
            response = json.loads(extracted)
        except json.JSONDecodeError as exc:
            raise DeepResearchProviderError("OpenAI Deep Research response did not contain parseable structured JSON.") from exc
        if not isinstance(response, dict):
            raise DeepResearchProviderError("Deep Research structured response must decode to an object.")
        response.setdefault("provider", "openai_deep_research")
        response.setdefault("model", str(raw_payload.get("model", "unknown_model")))
        response.setdefault("response_id", str(raw_payload.get("id", "unknown_response")))
        response.setdefault("completed_at", str(raw_payload.get("completed_at") or raw_payload.get("created_at") or _now_utc_iso()))
        response.setdefault("case_id", expected_case_id)
        response.setdefault("provider_notes", [])

    validate_deep_research_response(response)
    if response["case_id"] != expected_case_id:
        raise DeepResearchProviderError("Deep Research response case_id must match request case_id.")
    return response


def validate_deep_research_response(response: Any) -> None:
    if not isinstance(response, dict):
        raise DeepResearchProviderError("deep_research_response must be an object.")
    forbidden_report_fields = sorted(FINAL_REPORT_SUBSTITUTE_FIELDS.intersection(response))
    if forbidden_report_fields:
        raise DeepResearchProviderError(
            "Deep Research response must be structured research material; final report text is not accepted as a substitute for sources, evidence_items, candidate_claims, claim_evidence_links, and source_gaps. "
            f"Forbidden field(s): {', '.join(forbidden_report_fields)}"
        )
    missing = sorted(field for field in DEEP_RESEARCH_RESPONSE_REQUIRED_FIELDS if field not in response)
    if missing:
        raise DeepResearchProviderError(f"deep_research_response missing field(s): {', '.join(missing)}")
    for field in ("case_id", "provider", "model", "response_id", "completed_at"):
        if not isinstance(response[field], str) or not response[field].strip():
            raise DeepResearchProviderError(f"deep_research_response field {field} must be a non-empty string.")
    for field in ("sources", "evidence_items", "candidate_claims", "claim_evidence_links", "source_gaps", "provider_notes"):
        if not isinstance(response[field], list):
            raise DeepResearchProviderError(f"deep_research_response field {field} must be an array.")

    for source in response["sources"]:
        _validate_source(source)
    known_provider_source_ids = {source["provider_source_id"] for source in response["sources"]}
    known_evidence_item_ids: set[str] = set()
    for evidence_item in response["evidence_items"]:
        _validate_evidence_item(evidence_item, known_provider_source_ids, known_evidence_item_ids)
    known_source_gap_ids: set[str] = set()
    for source_gap in response["source_gaps"]:
        _validate_source_gap(source_gap, known_source_gap_ids)
    known_candidate_claim_ids: set[str] = set()
    for candidate_claim in response["candidate_claims"]:
        _validate_candidate_claim(candidate_claim, known_evidence_item_ids, known_source_gap_ids, known_candidate_claim_ids)
    for link in response["claim_evidence_links"]:
        _validate_claim_evidence_link(link, known_candidate_claim_ids, known_evidence_item_ids)


def _validate_source(source: Any) -> None:
    required = {
        "provider_source_id",
        "title",
        "url",
        "source_type",
        "source_owner",
        "source_date_or_period",
        "source_reliability_rationale",
        "source_limitations",
    }
    if not isinstance(source, dict):
        raise DeepResearchProviderError("Each Deep Research source must be an object.")
    missing = sorted(field for field in required if field not in source)
    if missing:
        raise DeepResearchProviderError(f"Deep Research source missing field(s): {', '.join(missing)}")
    for field in required:
        if not isinstance(source[field], str) or not source[field].strip():
            raise DeepResearchProviderError(f"Deep Research source field {field} must be a non-empty string.")
    if "source_tier" in source and source["source_tier"] not in {"Tier 1", "Tier 2", "Tier 3", "Tier 4"}:
        raise DeepResearchProviderError("Deep Research source source_tier must be Tier 1, Tier 2, Tier 3, or Tier 4.")
    if "source_time_relation_to_decision_date" in source and source["source_time_relation_to_decision_date"] not in {
        "pre_decision",
        "at_decision",
        "post_decision",
        "retrospective",
        "unknown",
    }:
        raise DeepResearchProviderError("Deep Research source source_time_relation_to_decision_date is invalid.")
    if "permitted_use" in source and source["permitted_use"] not in {
        "ex_ante_deal_evaluation",
        "transaction_terms_verification",
        "retrospective_outcome_validation",
        "source_lead_only",
        "gap_tracking",
    }:
        raise DeepResearchProviderError("Deep Research source permitted_use is invalid.")


def _validate_evidence_item(evidence_item: Any, known_provider_source_ids: set[str], seen_evidence_item_ids: set[str]) -> None:
    required = {
        "provider_evidence_id",
        "provider_source_id",
        "extracted_text_or_summary",
        "extraction_location_if_available",
        "fact_type",
        "related_workstream_ids",
        "related_evidence_requirement_ids",
        "related_verification_target_ids",
        "confidence_preliminary",
        "caveats",
    }
    if not isinstance(evidence_item, dict):
        raise DeepResearchProviderError("Each Deep Research evidence_item must be an object.")
    missing = sorted(field for field in required if field not in evidence_item)
    if missing:
        raise DeepResearchProviderError(f"Deep Research evidence_item missing field(s): {', '.join(missing)}")
    for field in ("provider_evidence_id", "provider_source_id", "extracted_text_or_summary", "fact_type", "confidence_preliminary"):
        if not isinstance(evidence_item[field], str) or not evidence_item[field].strip():
            raise DeepResearchProviderError(f"Deep Research evidence_item field {field} must be a non-empty string.")
    if evidence_item["provider_source_id"] not in known_provider_source_ids:
        raise DeepResearchProviderError(
            f"Deep Research evidence_item references unknown provider_source_id: {evidence_item['provider_source_id']}"
        )
    if evidence_item["provider_evidence_id"] in seen_evidence_item_ids:
        raise DeepResearchProviderError(f"Duplicate Deep Research provider_evidence_id: {evidence_item['provider_evidence_id']}")
    seen_evidence_item_ids.add(evidence_item["provider_evidence_id"])
    if not isinstance(evidence_item["related_workstream_ids"], list):
        raise DeepResearchProviderError("Deep Research evidence_item related_workstream_ids must be an array.")
    if not isinstance(evidence_item["related_evidence_requirement_ids"], list):
        raise DeepResearchProviderError("Deep Research evidence_item related_evidence_requirement_ids must be an array.")
    if not isinstance(evidence_item["related_verification_target_ids"], list):
        raise DeepResearchProviderError("Deep Research evidence_item related_verification_target_ids must be an array.")
    if not isinstance(evidence_item["caveats"], list):
        raise DeepResearchProviderError("Deep Research evidence_item caveats must be an array.")


def _validate_source_gap(source_gap: Any, seen_source_gap_ids: set[str]) -> None:
    required = {
        "source_gap_id",
        "gap_description",
        "attempted_source_types",
        "reason_unresolved",
        "recommended_next_search",
    }
    if not isinstance(source_gap, dict):
        raise DeepResearchProviderError("Each Deep Research source_gap must be an object.")
    missing = sorted(field for field in required if field not in source_gap)
    if missing:
        raise DeepResearchProviderError(f"Deep Research source_gap missing field(s): {', '.join(missing)}")
    for field in ("source_gap_id", "gap_description", "reason_unresolved", "recommended_next_search"):
        if not isinstance(source_gap[field], str) or not source_gap[field].strip():
            raise DeepResearchProviderError(f"Deep Research source_gap field {field} must be a non-empty string.")
    if source_gap["source_gap_id"] in seen_source_gap_ids:
        raise DeepResearchProviderError(f"Duplicate Deep Research source_gap_id: {source_gap['source_gap_id']}")
    seen_source_gap_ids.add(source_gap["source_gap_id"])
    if not isinstance(source_gap["attempted_source_types"], list):
        raise DeepResearchProviderError("Deep Research source_gap attempted_source_types must be an array.")


def _validate_candidate_claim(
    candidate_claim: Any,
    known_evidence_item_ids: set[str],
    known_source_gap_ids: set[str],
    seen_candidate_claim_ids: set[str],
) -> None:
    required = {
        "candidate_claim_id",
        "claim_statement",
        "claim_type",
        "claim_scope",
        "temporal_scope",
        "permitted_use",
        "supporting_evidence_item_ids",
        "contradicting_evidence_item_ids",
        "related_source_gap_ids",
        "confidence_preliminary",
        "requires_numeric_verification",
        "requires_human_review",
        "downstream_use_warning",
    }
    if not isinstance(candidate_claim, dict):
        raise DeepResearchProviderError("Each Deep Research candidate_claim must be an object.")
    missing = sorted(field for field in required if field not in candidate_claim)
    if missing:
        raise DeepResearchProviderError(f"Deep Research candidate_claim missing field(s): {', '.join(missing)}")
    for field in ("candidate_claim_id", "claim_statement", "claim_type", "claim_scope", "temporal_scope", "permitted_use", "confidence_preliminary", "downstream_use_warning"):
        if not isinstance(candidate_claim[field], str) or not candidate_claim[field].strip():
            raise DeepResearchProviderError(f"Deep Research candidate_claim field {field} must be a non-empty string.")
    if candidate_claim["candidate_claim_id"] in seen_candidate_claim_ids:
        raise DeepResearchProviderError(f"Duplicate Deep Research candidate_claim_id: {candidate_claim['candidate_claim_id']}")
    seen_candidate_claim_ids.add(candidate_claim["candidate_claim_id"])
    if candidate_claim["claim_type"] not in ALLOWED_CLAIM_TYPES:
        raise DeepResearchProviderError(f"Deep Research candidate_claim claim_type is outside the allowed taxonomy: {candidate_claim['claim_type']}")
    if candidate_claim["temporal_scope"] not in {"pre_decision", "at_decision", "post_decision", "retrospective", "unknown", "source_gap"}:
        raise DeepResearchProviderError(f"Deep Research candidate_claim temporal_scope is invalid: {candidate_claim['candidate_claim_id']}")
    if candidate_claim["permitted_use"] not in {
        "ex_ante_deal_evaluation",
        "transaction_terms_verification",
        "retrospective_outcome_validation",
        "source_lead_only",
        "gap_tracking",
    }:
        raise DeepResearchProviderError(f"Deep Research candidate_claim permitted_use is invalid: {candidate_claim['candidate_claim_id']}")
    if candidate_claim["temporal_scope"] in {"post_decision", "retrospective"} and candidate_claim["permitted_use"] == "ex_ante_deal_evaluation":
        raise DeepResearchProviderError(f"Post-decision or retrospective candidate_claim cannot be ex_ante_deal_evaluation: {candidate_claim['candidate_claim_id']}")
    if candidate_claim["temporal_scope"] == "source_gap" and candidate_claim["permitted_use"] != "gap_tracking":
        raise DeepResearchProviderError(f"source_gap candidate_claim must be permitted for gap_tracking only: {candidate_claim['candidate_claim_id']}")
    if candidate_claim["confidence_preliminary"] not in {"low", "medium", "high"}:
        raise DeepResearchProviderError(f"Deep Research candidate_claim confidence_preliminary is invalid: {candidate_claim['candidate_claim_id']}")
    for field in ("requires_numeric_verification", "requires_human_review"):
        if not isinstance(candidate_claim[field], bool):
            raise DeepResearchProviderError(f"Deep Research candidate_claim {field} must be boolean: {candidate_claim['candidate_claim_id']}")
    if candidate_claim.get("certification_status") == "certified" or candidate_claim.get("is_certified") is True or candidate_claim.get("certified") is True:
        raise DeepResearchProviderError(f"Deep Research candidate_claim must not be treated as certified: {candidate_claim['candidate_claim_id']}")
    for field in ("supporting_evidence_item_ids", "contradicting_evidence_item_ids", "related_source_gap_ids"):
        if not isinstance(candidate_claim[field], list):
            raise DeepResearchProviderError(f"Deep Research candidate_claim {field} must be an array: {candidate_claim['candidate_claim_id']}")
    unknown_supporting = sorted(set(candidate_claim["supporting_evidence_item_ids"]) - known_evidence_item_ids)
    unknown_contradicting = sorted(set(candidate_claim["contradicting_evidence_item_ids"]) - known_evidence_item_ids)
    unknown_gaps = sorted(set(candidate_claim["related_source_gap_ids"]) - known_source_gap_ids)
    if unknown_supporting:
        raise DeepResearchProviderError(f"candidate_claim references missing supporting evidence_item_id(s): {candidate_claim['candidate_claim_id']} -> {', '.join(unknown_supporting)}")
    if unknown_contradicting:
        raise DeepResearchProviderError(f"candidate_claim references missing contradicting evidence_item_id(s): {candidate_claim['candidate_claim_id']} -> {', '.join(unknown_contradicting)}")
    if unknown_gaps:
        raise DeepResearchProviderError(f"candidate_claim references missing source_gap_id(s): {candidate_claim['candidate_claim_id']} -> {', '.join(unknown_gaps)}")


def _validate_claim_evidence_link(link: Any, known_candidate_claim_ids: set[str], known_evidence_item_ids: set[str]) -> None:
    required = {"candidate_claim_id", "evidence_item_id", "link_type", "rationale"}
    if not isinstance(link, dict):
        raise DeepResearchProviderError("Each Deep Research claim_evidence_link must be an object.")
    missing = sorted(field for field in required if field not in link)
    if missing:
        raise DeepResearchProviderError(f"Deep Research claim_evidence_link missing field(s): {', '.join(missing)}")
    for field in required:
        if not isinstance(link[field], str) or not link[field].strip():
            raise DeepResearchProviderError(f"Deep Research claim_evidence_link field {field} must be a non-empty string.")
    if link["candidate_claim_id"] not in known_candidate_claim_ids:
        raise DeepResearchProviderError(f"claim_evidence_link references missing candidate_claim_id: {link['candidate_claim_id']}")
    if link["evidence_item_id"] not in known_evidence_item_ids:
        raise DeepResearchProviderError(f"claim_evidence_link references missing evidence_item_id: {link['evidence_item_id']}")
    if link["link_type"] not in CLAIM_EVIDENCE_LINK_TYPES:
        raise DeepResearchProviderError(f"claim_evidence_link link_type is invalid: {link['link_type']}")


def _deep_research_prompt(request_artifact: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are not writing the final acquisition report.",
            "You are acting as a source discovery and evidence collection provider for a downstream M&A agent runtime.",
            "Return structured JSON only.",
            "Top-level keys: case_id, provider, model, response_id, completed_at, sources, evidence_items, candidate_claims, claim_evidence_links, source_gaps, provider_notes.",
            "candidate_claims are not certified claims; M5 verifier decides certification, caveats, repair, human review, and report eligibility.",
            "Do not provide final report text, investment memo prose, or recommendation text as a substitute for structured claims and evidence.",
            "Do not rely on model memory.",
            "Do not use the case_seed as evidence.",
            "Do not treat summaries or prior reports as authoritative evidence.",
            "Prefer primary and official sources.",
            "For transaction economics, prefer SEC filings, signed agreements, stock exchange disclosures, regulator filings, or company official filings.",
            "For company, product, or pipeline information, prefer official company materials and filings.",
            "For patents, prefer official patent-office sources where available.",
            "For clinical information, prefer official clinical trial registries and regulator or company filings.",
            "For personal proceeds or founder economics, require direct authoritative evidence or mark unresolved.",
            "Every evidence item must include source reference, source URL or document identifier, extracted quote or bounded summary, source type, source date or period, why the source is reliable, what fact it supports, and limitations or caveats.",
            "Request artifact follows as JSON:",
            json.dumps(request_artifact, indent=2, ensure_ascii=False),
        ]
    )


def _looks_like_normalized_response(raw_payload: dict[str, Any]) -> bool:
    return DEEP_RESEARCH_RESPONSE_REQUIRED_FIELDS.issubset(raw_payload.keys())


def _extract_json_text(raw_payload: dict[str, Any]) -> str:
    candidates: list[str] = []
    output_text = raw_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        candidates.append(output_text)
    for container_key in ("output", "content"):
        container = raw_payload.get(container_key)
        if isinstance(container, list):
            for item in container:
                if isinstance(item, dict):
                    _collect_text_candidates(item, candidates)
    if not candidates:
        raise DeepResearchProviderError("OpenAI Deep Research response did not contain structured JSON text.")
    for candidate in candidates:
        stripped = _strip_code_fence(candidate)
        if stripped.startswith("{"):
            return stripped
    raise DeepResearchProviderError("OpenAI Deep Research response did not contain a JSON object payload.")


def _collect_text_candidates(item: dict[str, Any], candidates: list[str]) -> None:
    for key in ("text", "output_text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value)
    content = item.get("content")
    if isinstance(content, list):
        for content_item in content:
            if isinstance(content_item, dict):
                text_value = content_item.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    candidates.append(text_value)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped[3:-3].strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    return stripped


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
