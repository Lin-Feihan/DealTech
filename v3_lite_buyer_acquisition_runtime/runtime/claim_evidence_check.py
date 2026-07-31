from __future__ import annotations

import re
from typing import Any


class ClaimEvidenceCheckError(ValueError):
    pass


MONEY_RE = re.compile(r"\$\s?\d+(?:\.\d+)?\s?(?:million|billion|thousand|m|bn|mm)?", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
ISO_DATE_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
ENTITY_RE = re.compile(r"\b[A-Z][A-Za-z0-9&.-]*(?:\s+[A-Z][A-Za-z0-9&.-]*){0,4}\b")


def run_claim_evidence_check(claim_evidence_graph: dict[str, Any], evidence_repository: dict[str, Any]) -> list[dict[str, Any]]:
    _validate_graph_shape(claim_evidence_graph, evidence_repository)
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    edges_by_claim_id: dict[str, list[dict[str, Any]]] = {}
    for edge in claim_evidence_graph["evidence_edges"]:
        edges_by_claim_id.setdefault(edge["claim_id"], []).append(edge)
    return [
        _check_claim(index, claim, records_by_id, edges_by_claim_id.get(claim["claim_id"], []))
        for index, claim in enumerate(claim_evidence_graph["claim_nodes"], start=1)
    ]


def claim_evidence_results_by_claim_id(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {result["claim_id"]: result for result in results}


def _validate_graph_shape(claim_evidence_graph: dict[str, Any], evidence_repository: dict[str, Any]) -> None:
    if claim_evidence_graph.get("generated_artifact") != "claim_evidence_graph.json":
        raise ClaimEvidenceCheckError("Claim-Evidence Check requires claim_evidence_graph.json.")
    if evidence_repository.get("generated_artifact") != "evidence_repository.json":
        raise ClaimEvidenceCheckError("Claim-Evidence Check requires evidence_repository.json.")
    if claim_evidence_graph.get("case_id") != evidence_repository.get("case_id"):
        raise ClaimEvidenceCheckError("Claim-Evidence Check requires matching case_id values.")
    if not isinstance(claim_evidence_graph.get("claim_nodes"), list):
        raise ClaimEvidenceCheckError("claim_evidence_graph.claim_nodes must be an array.")
    if not isinstance(claim_evidence_graph.get("evidence_edges"), list):
        raise ClaimEvidenceCheckError("claim_evidence_graph.evidence_edges must be an array.")
    if not isinstance(evidence_repository.get("evidence_records"), list):
        raise ClaimEvidenceCheckError("evidence_repository.evidence_records must be an array.")
    claim_ids = {claim.get("claim_id") for claim in claim_evidence_graph["claim_nodes"]}
    record_ids = {record.get("evidence_record_id") for record in evidence_repository["evidence_records"]}
    for edge in claim_evidence_graph["evidence_edges"]:
        if edge.get("claim_id") not in claim_ids:
            raise ClaimEvidenceCheckError(f"evidence_edge references unknown claim_id: {edge.get('claim_id')}")
        if edge.get("evidence_record_id") not in record_ids:
            raise ClaimEvidenceCheckError(f"evidence_edge references unknown evidence_record_id: {edge.get('evidence_record_id')}")
    for claim in claim_evidence_graph["claim_nodes"]:
        for field in ("claim_id", "claim_statement", "supporting_evidence_record_ids", "contradicting_evidence_record_ids", "support_level"):
            if field not in claim:
                raise ClaimEvidenceCheckError(f"claim_node missing required field: {field}")
        for record_id in claim.get("supporting_evidence_record_ids", []) + claim.get("contradicting_evidence_record_ids", []):
            if record_id not in record_ids:
                raise ClaimEvidenceCheckError(f"claim references unknown evidence_record_id: {claim['claim_id']} -> {record_id}")
        if claim.get("support_level") in {"gap_only", "unsupported"} and claim.get("supporting_evidence_record_ids"):
            raise ClaimEvidenceCheckError(f"gap-only or unsupported claim cannot have supporting evidence: {claim['claim_id']}")


def _check_claim(
    index: int,
    claim: dict[str, Any],
    records_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    supporting_records = [records_by_id[record_id] for record_id in claim.get("supporting_evidence_record_ids", [])]
    failures: list[str] = []
    caveats: list[str] = []
    repair_actions: list[dict[str, str]] = []

    edge_integrity_status = "passed"
    fact_match_status = _fact_match_status(claim, supporting_records, failures, caveats, repair_actions)
    support_status = _support_sufficiency_status(claim, supporting_records, edges, failures, caveats, repair_actions)
    overclaim_status = _overclaim_status(claim, supporting_records, failures, caveats, repair_actions)
    conflict_status = _conflict_status(claim, supporting_records, failures, caveats, repair_actions)

    if failures:
        check_status = "failed"
    elif repair_actions:
        check_status = "repair_required"
    elif caveats:
        check_status = "passed_with_caveat"
    else:
        check_status = "passed"

    return {
        "claim_evidence_check_id": f"CEC-{index:03d}",
        "claim_id": claim["claim_id"],
        "claim_statement": claim["claim_statement"],
        "check_status": check_status,
        "edge_integrity_check_status": edge_integrity_status,
        "fact_match_check_status": fact_match_status,
        "support_sufficiency_check_status": support_status,
        "overclaim_check_status": overclaim_status,
        "conflict_ambiguity_check_status": conflict_status,
        "supporting_evidence_record_ids": list(claim.get("supporting_evidence_record_ids", [])),
        "required_caveats": _ordered_unique(caveats),
        "blocking_reasons": _ordered_unique(failures),
        "repair_actions": _dedupe_actions(repair_actions),
    }


def _fact_match_status(
    claim: dict[str, Any],
    records: list[dict[str, Any]],
    failures: list[str],
    caveats: list[str],
    repair_actions: list[dict[str, str]],
) -> str:
    if claim.get("support_level") in {"gap_only", "unsupported"}:
        return "not_applicable"
    evidence_text = _evidence_text(records)
    statement = claim["claim_statement"]
    money_values = _money_tokens(statement)
    if money_values and not all(_money_equivalent(token) in _money_equivalents(evidence_text) for token in money_values):
        reason = "Claim money amount is not matched by supporting evidence text or summary."
        failures.append(reason)
        repair_actions.append(_repair_action("M4_claim_evidence_graph", "repair_claim_fact_match", reason))
        return "failed"
    date_tokens = _date_tokens(statement)
    if date_tokens and not any(token in evidence_text for token in date_tokens):
        reason = "Claim date or year is not matched by supporting evidence."
        failures.append(reason)
        repair_actions.append(_repair_action("M4_claim_evidence_graph", "repair_claim_fact_match", reason))
        return "failed"
    entity_tokens = _entity_tokens(statement)
    if entity_tokens and evidence_text and not any(token.lower() in evidence_text.lower() for token in entity_tokens):
        caveats.append("No important entity token from claim_statement was matched in supporting evidence; human review should verify wording.")
        return "passed_with_caveat"
    return "passed"


def _support_sufficiency_status(
    claim: dict[str, Any],
    records: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    failures: list[str],
    caveats: list[str],
    repair_actions: list[dict[str, str]],
) -> str:
    support_level = claim.get("support_level")
    claim_type = claim.get("claim_type", "generic_fact")
    if support_level == "gap_only":
        reason = "Gap-only claim remains blocked until source repair."
        failures.append(reason)
        repair_actions.append(_repair_action("M2_source_retrieval", "repair_source_gap", reason))
        return "failed"
    if support_level == "unsupported" or not records:
        reason = "Unsupported claim lacks source-bounded supporting evidence."
        failures.append(reason)
        repair_actions.append(_repair_action("M2_source_retrieval", "retrieve_supporting_source", reason))
        return "failed"
    if support_level == "partially_supported" or any(edge.get("edge_type") in {"partially_supports", "contextualizes", "requires_verification"} for edge in edges):
        caveats.append("Claim is only partially supported or contextualized; it cannot be uncaveated.")
        return "passed_with_caveat"
    if _is_judgment_claim(claim_type, claim["claim_statement"]) and len(records) < 2:
        reason = "Recommendation, valuation, or strategic judgment claim requires dependencies and cannot be certified from one factual evidence edge."
        failures.append(reason)
        repair_actions.append(_repair_action("M4_claim_evidence_graph", "add_required_judgment_dependencies", reason))
        return "failed"
    return "passed"


def _overclaim_status(
    claim: dict[str, Any],
    records: list[dict[str, Any]],
    failures: list[str],
    caveats: list[str],
    repair_actions: list[dict[str, str]],
) -> str:
    statement = claim["claim_statement"].lower()
    evidence_text = _evidence_text(records).lower()
    triggered: list[str] = []
    if _contains_any(statement, {"proceeds", "received", "personal proceeds"}) and "%" in evidence_text and "proceeds" not in evidence_text:
        triggered.append("ownership percentage times transaction value cannot support personal proceeds without direct proceeds evidence")
    if _contains_any(statement, {"attractive", "low-risk", "recommend", "recommendation"}) and _contains_any(evidence_text, {"milestone", "pipeline", "current status"}):
        triggered.append("later milestone or current pipeline evidence cannot prove ex-ante deal attractiveness")
    if _contains_any(statement, {"upfront", "base consideration", "closing payment"}) and _contains_any(evidence_text, {"headline", "maximum", "up to", "milestone cap"}):
        triggered.append("headline deal value or milestone cap must not be treated as guaranteed upfront/base consideration")
    if _contains_any(statement, {"known at decision", "ex-ante", "ex ante"}) and _contains_any(evidence_text, {"current pipeline", "currently", "now"}):
        triggered.append("current pipeline status cannot prove what was known at transaction decision date")
    if triggered:
        for reason in triggered:
            failures.append(reason)
            repair_actions.append(_repair_action("M4_claim_evidence_graph", "repair_overclaim", reason))
        return "failed"
    return "passed"


def _conflict_status(
    claim: dict[str, Any],
    records: list[dict[str, Any]],
    failures: list[str],
    caveats: list[str],
    repair_actions: list[dict[str, str]],
) -> str:
    text = f"{claim['claim_statement']} {_evidence_text(records)}".lower()
    ambiguities = []
    for left, right, reason in (
        ("upfront", "headline", "upfront/base consideration vs headline maximum value ambiguity"),
        ("base consideration", "maximum", "upfront/base consideration vs headline maximum value ambiguity"),
        ("signing", "closing", "signing date vs closing date ambiguity"),
        ("enterprise value", "equity value", "enterprise value vs equity value ambiguity"),
        ("announced value", "paid consideration", "announced value vs paid consideration ambiguity"),
        ("retrospective", "ex-ante", "retrospective outcome vs ex-ante decision evidence ambiguity"),
    ):
        if left in text and right in text:
            ambiguities.append(reason)
    if ambiguities:
        for reason in sorted(set(ambiguities)):
            caveats.append(reason)
            repair_actions.append(_repair_action("M4_claim_evidence_graph", "resolve_claim_ambiguity", reason))
        return "passed_with_caveat"
    return "passed"


def _money_tokens(text: str) -> list[str]:
    return MONEY_RE.findall(text or "")


def _money_equivalent(value: str) -> str:
    return " ".join(value.lower().replace(",", "").split())


def _money_equivalents(text: str) -> set[str]:
    tokens = set()
    for value in _money_tokens(text):
        normalized = _money_equivalent(value)
        tokens.add(normalized)
        tokens.add(normalized.replace("$ ", "$"))
    return tokens


def _date_tokens(text: str) -> list[str]:
    return _ordered_unique([*ISO_DATE_RE.findall(text or ""), *YEAR_RE.findall(text or "")])


def _entity_tokens(text: str) -> list[str]:
    generic = {"The", "This", "M5", "M4", "Tier", "Claim", "Source", "Evidence", "Generic"}
    tokens = []
    for token in ENTITY_RE.findall(text or ""):
        cleaned = token.strip()
        if cleaned in generic or MONEY_RE.search(cleaned):
            continue
        if any(character.isdigit() for character in cleaned):
            continue
        if len(cleaned) < 4:
            continue
        tokens.append(cleaned)
    return _ordered_unique(tokens[:5])


def _evidence_text(records: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for record in records:
        parts.extend(
            [
                str(record.get("canonical_fact_key", "")),
                str(record.get("canonical_fact_type", "")),
                str(record.get("normalized_fact_summary", "")),
                str(record.get("structured_attributes", "")),
                " ".join(record.get("source_titles", [])),
                " ".join(record.get("source_ids", [])),
            ]
        )
    return " ".join(parts)


def _is_judgment_claim(claim_type: str, statement: str) -> bool:
    text = f"{claim_type} {statement}".lower()
    return _contains_any(text, {"recommend", "recommendation", "valuation_conclusion", "strategic_fit", "attractive", "low-risk", "walk away", "proceed"})


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _repair_action(target: str, action: str, reason: str) -> dict[str, str]:
    return {"target": target, "action": action, "reason": reason}


def _dedupe_actions(actions: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    deduped = []
    for action in actions:
        key = (action.get("target"), action.get("action"), action.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen or value in {None, ""}:
            continue
        seen.add(value)
        unique.append(value)
    return unique
