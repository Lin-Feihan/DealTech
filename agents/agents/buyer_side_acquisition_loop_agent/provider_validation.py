from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .block_a_registry import source_identity
from .live_research_models import ProviderOutputValidation, ProviderValidationStatus


OBJECT_COLLECTIONS = (
    "sources",
    "evidence",
    "claims",
    "assumptions",
    "unknowns",
    "counterevidence",
)
ID_FIELDS = {
    "sources": "source_id",
    "evidence": "evidence_id",
    "claims": "claim_id",
    "assumptions": "assumption_id",
    "unknowns": "unknown_id",
    "counterevidence": "counterevidence_id",
}

SOURCE_FIELDS = {
    "source_id", "url", "page_title", "publisher_or_owner", "source_type",
    "source_tier", "publication_date", "retrieval_timestamp", "author",
    "exact_relevant_locator", "discovery_query", "provider_response_reference",
    "pce_eligible", "limitations", "confidentiality_classification", "source_kind",
}
EVIDENCE_FIELDS = {
    "evidence_id", "claim_id", "source_id", "extracted_fact", "exact_locator",
    "direction", "evidence_type", "strength", "limitations", "extraction_timestamp",
}
CLAIM_FIELDS = {
    "claim_id", "claim_text", "claim_class", "materiality",
    "supporting_evidence_ids", "counterevidence_ids", "confidence", "limitations",
    "owning_module", "decision_relevance", "delivery_request", "human_review_required",
    "claim_family_id", "claim_version", "supersedes_claim_id",
}


def _normalised_url(url: str) -> str:
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def _nonempty_string(row: dict[str, Any], field: str) -> bool:
    return isinstance(row.get(field), str) and bool(row[field].strip())


def validate_provider_output(
    payload: dict[str, Any],
    *,
    prior_objects: dict[str, list[dict[str, Any]]] | None = None,
    expected_module_id: str = "A5",
    expected_module_name: str = "Target Capability & Business Quality",
    require_counterevidence: bool = False,
    allow_reused_sources: bool = False,
) -> ProviderOutputValidation:
    prior = prior_objects or {name: [] for name in OBJECT_COLLECTIONS}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: dict[str, bool] = {}

    top_level = {
        *OBJECT_COLLECTIONS,
        "suggested_follow_up_questions", "retrieval_summary", "searched_queries",
        "pages_or_files_inspected", "unresolved_conflicts", "provider_metadata",
        "module_assessment",
    }
    checks["top_level_contract"] = isinstance(payload, dict) and top_level.issubset(payload)
    if not checks["top_level_contract"]:
        missing = sorted(top_level - set(payload if isinstance(payload, dict) else {}))
        errors.append({"type": "MALFORMED_OUTPUT", "object_id": "provider_response", "reason": f"Missing fields: {missing}"})
    for name in OBJECT_COLLECTIONS:
        if not isinstance(payload.get(name), list):
            errors.append({"type": "MALFORMED_OUTPUT", "object_id": name, "reason": "Collection must be a list."})
    if errors:
        return ProviderOutputValidation(
            status=ProviderValidationStatus.REJECTED,
            errors=errors,
            warnings=warnings,
            admitted_object_ids={name: [] for name in OBJECT_COLLECTIONS},
            rejected_objects=[{"object_type": "response", "reason": "Top-level structured output is malformed."}],
            checks=checks,
        )

    all_rows = {name: list(payload[name]) for name in OBJECT_COLLECTIONS}
    for required_collection in ("sources", "evidence", "claims"):
        if required_collection == "sources" and allow_reused_sources and prior.get("sources"):
            continue
        if not all_rows[required_collection]:
            errors.append(
                {
                    "type": "EMPTY_RESEARCH_RESULT",
                    "object_id": required_collection,
                    "reason": f"{required_collection} cannot be empty for a provider attempt.",
                }
            )
    if require_counterevidence and not all_rows["counterevidence"]:
        errors.append(
            {
                "type": "COUNTEREVIDENCE_REQUIRED",
                "object_id": expected_module_id,
                "reason": "Every Block A module must return a counterevidence record.",
            }
        )
    ids_by_collection: dict[str, list[str]] = {}
    for name, rows in all_rows.items():
        id_field = ID_FIELDS[name]
        ids = [str(row.get(id_field, "")) for row in rows if isinstance(row, dict)]
        ids_by_collection[name] = ids
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append({"type": "MALFORMED_OBJECT", "object_id": f"{name}[{index}]", "reason": "Object must be a mapping."})
            elif not _nonempty_string(row, id_field):
                errors.append({"type": "MISSING_ID", "object_id": f"{name}[{index}]", "reason": f"{id_field} is required."})

    all_ids = [item for values in ids_by_collection.values() for item in values if item]
    duplicate_ids = sorted(item for item, count in Counter(all_ids).items() if count > 1)
    prior_ids = {
        str(row.get(ID_FIELDS[name], ""))
        for name in OBJECT_COLLECTIONS
        for row in prior.get(name, [])
    }
    reused_ids = sorted(set(all_ids) & prior_ids)
    checks["unique_ids"] = not duplicate_ids and not reused_ids
    for item in duplicate_ids:
        errors.append({"type": "DUPLICATE_ID", "object_id": item, "reason": "ID is duplicated in the provider response."})
    for item in reused_ids:
        errors.append({"type": "DUPLICATE_ID", "object_id": item, "reason": "ID already exists in admitted Memory."})

    source_ids = set(ids_by_collection["sources"]) | {
        str(row.get("source_id", "")) for row in prior.get("sources", [])
    }
    evidence_ids = set(ids_by_collection["evidence"]) | {
        str(row.get("evidence_id", "")) for row in prior.get("evidence", [])
    }
    claim_ids = set(ids_by_collection["claims"]) | {
        str(row.get("claim_id", "")) for row in prior.get("claims", [])
    }
    counter_ids = set(ids_by_collection["counterevidence"]) | {
        str(row.get("counterevidence_id", "")) for row in prior.get("counterevidence", [])
    }

    prior_source_identities = {
        source_identity(row) for row in prior.get("sources", [])
    }
    response_source_identities: list[tuple[str, ...]] = []
    for row in all_rows["sources"]:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id", ""))
        missing = sorted(field for field in SOURCE_FIELDS if field not in row)
        if missing:
            errors.append({"type": "MALFORMED_SOURCE", "object_id": source_id, "reason": f"Missing fields: {missing}"})
            continue
        source_kind = str(row.get("source_kind", "")).lower()
        if source_kind == "web":
            url = str(row.get("url", ""))
            if not url.startswith(("https://", "http://")):
                errors.append({"type": "UNRECOVERABLE_SOURCE", "object_id": source_id, "reason": "Web Source requires a recoverable HTTP(S) URL."})
            else:
                response_source_identities.append(source_identity(row))
            if not _nonempty_string(row, "exact_relevant_locator"):
                errors.append({"type": "MISSING_LOCATOR", "object_id": source_id, "reason": "Web Source requires an exact relevant locator."})
        elif source_kind == "attachment":
            attachment_required = {
                "original_filename", "file_hash_sha256", "file_type", "supplied_by",
                "document_date", "extraction_method",
            }
            missing_attachment = sorted(field for field in attachment_required if not _nonempty_string(row, field))
            if missing_attachment:
                errors.append({"type": "MALFORMED_ATTACHMENT_SOURCE", "object_id": source_id, "reason": f"Missing provenance: {missing_attachment}"})
        else:
            errors.append({"type": "INVALID_SOURCE_KIND", "object_id": source_id, "reason": "source_kind must be web or attachment."})
        if not isinstance(row.get("pce_eligible"), bool):
            errors.append({"type": "MALFORMED_SOURCE", "object_id": source_id, "reason": "pce_eligible must be boolean."})
        if "model" in str(row.get("source_type", "")).lower():
            errors.append({"type": "MODEL_PROSE_IS_NOT_SOURCE", "object_id": source_id, "reason": "Model-generated prose cannot be registered as a Source."})
        if "management" in str(row.get("source_type", "")).lower():
            if "management" not in str(row.get("limitations", "")).lower():
                errors.append({"type": "MANAGEMENT_LIMITATION_MISSING", "object_id": source_id, "reason": "Management-only Source requires an explicit limitation."})

    duplicate_source_identities = sorted(
        item for item, count in Counter(response_source_identities).items() if count > 1
    )
    duplicate_source_identities.extend(
        sorted(set(response_source_identities) & prior_source_identities)
    )
    checks["no_duplicate_sources"] = not duplicate_source_identities
    for identity in sorted(set(duplicate_source_identities)):
        errors.append(
            {
                "type": "DUPLICATE_SOURCE",
                "object_id": "|".join(identity),
                "reason": "The same recoverable Source and version was already returned.",
            }
        )

    for row in all_rows["evidence"]:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidence_id", ""))
        missing = sorted(field for field in EVIDENCE_FIELDS if field not in row)
        if missing:
            errors.append({"type": "MALFORMED_EVIDENCE", "object_id": evidence_id, "reason": f"Missing fields: {missing}"})
            continue
        if row.get("source_id") not in source_ids:
            errors.append({"type": "ORPHAN_EVIDENCE", "object_id": evidence_id, "reason": "Evidence references an unknown Source."})
        if row.get("claim_id") not in claim_ids:
            errors.append({"type": "ORPHAN_EVIDENCE", "object_id": evidence_id, "reason": "Evidence references an unknown Claim."})
        if str(row.get("direction")) not in {"support", "contradict"}:
            errors.append({"type": "MALFORMED_EVIDENCE", "object_id": evidence_id, "reason": "direction must be support or contradict."})
        evidence_type = str(row.get("evidence_type", "")).lower()
        if "snippet" in evidence_type or "search result" in evidence_type:
            errors.append({"type": "SEARCH_SNIPPET_ONLY", "object_id": evidence_id, "reason": "Search-result snippets cannot be admitted as Evidence."})
        if str(row.get("source_id", "")).lower() in {"model", "llm", "assistant"}:
            errors.append({"type": "MODEL_PROSE_IS_NOT_EVIDENCE", "object_id": evidence_id, "reason": "Model prose has no admissible Source lineage."})
        if not _nonempty_string(row, "exact_locator"):
            errors.append({"type": "MISSING_LOCATOR", "object_id": evidence_id, "reason": "Evidence requires an exact page, section, line or row locator."})

    for row in all_rows["claims"]:
        if not isinstance(row, dict):
            continue
        claim_id = str(row.get("claim_id", ""))
        missing = sorted(field for field in CLAIM_FIELDS if field not in row)
        if missing:
            errors.append({"type": "MALFORMED_CLAIM", "object_id": claim_id, "reason": f"Missing fields: {missing}"})
            continue
        links = row.get("supporting_evidence_ids")
        if not isinstance(links, list) or not links:
            errors.append({"type": "ORPHAN_CLAIM", "object_id": claim_id, "reason": "Claim requires at least one supporting Evidence ID."})
        else:
            for evidence_id in links:
                if evidence_id not in evidence_ids:
                    errors.append({"type": "ORPHAN_CLAIM", "object_id": claim_id, "reason": f"Unknown supporting Evidence: {evidence_id}"})
        for counter_id in row.get("counterevidence_ids", []):
            if counter_id not in counter_ids:
                errors.append({"type": "ORPHAN_COUNTEREVIDENCE_LINK", "object_id": claim_id, "reason": f"Unknown Counterevidence: {counter_id}"})
        if row.get("owning_module") != expected_module_name:
            errors.append(
                {
                    "type": "OUT_OF_SCOPE_CLAIM",
                    "object_id": claim_id,
                    "reason": f"Provider Claims must be owned by {expected_module_id} - {expected_module_name} only.",
                }
            )
        dependency_claim_ids = row.get("dependency_claim_ids", [])
        if dependency_claim_ids is not None and not isinstance(dependency_claim_ids, list):
            errors.append(
                {
                    "type": "MALFORMED_CLAIM_DEPENDENCY",
                    "object_id": claim_id,
                    "reason": "dependency_claim_ids must be a list and never substitutes for Evidence support.",
                }
            )
        else:
            for dependency_claim_id in dependency_claim_ids or []:
                if dependency_claim_id not in claim_ids:
                    errors.append(
                        {
                            "type": "ORPHAN_CLAIM_DEPENDENCY",
                            "object_id": claim_id,
                            "reason": f"Unknown upstream Claim dependency: {dependency_claim_id}",
                        }
                    )
        supersedes = str(row.get("supersedes_claim_id", ""))
        if supersedes and supersedes not in claim_ids:
            errors.append({"type": "INVALID_CLAIM_VERSION", "object_id": claim_id, "reason": f"Superseded Claim is not registered: {supersedes}"})

    for row in all_rows["counterevidence"]:
        if not isinstance(row, dict):
            continue
        counter_id = str(row.get("counterevidence_id", ""))
        for source_id in row.get("source_ids", []):
            if source_id not in source_ids:
                errors.append({"type": "ORPHAN_COUNTEREVIDENCE", "object_id": counter_id, "reason": f"Unknown Source: {source_id}"})
        for evidence_id in row.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append({"type": "ORPHAN_COUNTEREVIDENCE", "object_id": counter_id, "reason": f"Unknown Evidence: {evidence_id}"})
        for claim_id in row.get("affected_claim_ids", []):
            if claim_id not in claim_ids:
                errors.append({"type": "ORPHAN_COUNTEREVIDENCE", "object_id": counter_id, "reason": f"Unknown Claim: {claim_id}"})

    source_urls = {
        _normalised_url(str(row.get("url", "")))
        for row in all_rows["sources"] + list(prior.get("sources", []))
        if row.get("url")
    }
    citations = payload.get("returned_citations", [])
    if not isinstance(citations, list):
        errors.append({"type": "MALFORMED_CITATIONS", "object_id": "returned_citations", "reason": "returned_citations must be a list."})
    else:
        for index, citation in enumerate(citations):
            url = str(citation.get("url", "")) if isinstance(citation, dict) else ""
            if not url or _normalised_url(url) not in source_urls:
                errors.append({"type": "UNSUPPORTED_CITATION", "object_id": f"citation[{index}]", "reason": "Citation has no matching recoverable Source record."})

    assessment = payload.get("module_assessment")
    assessment_required = {"business_conclusion", "criterion_outcome", "conditions", "limitations", "structured_output"}
    checks["module_assessment_complete"] = isinstance(assessment, dict) and assessment_required.issubset(assessment)
    if not checks["module_assessment_complete"]:
        errors.append({"type": "MALFORMED_MODULE_ASSESSMENT", "object_id": "module_assessment", "reason": f"{expected_module_id} module assessment is incomplete."})
    elif assessment.get("criterion_outcome") not in {"PASS", "CONDITION", "FAIL"}:
        errors.append({"type": "MALFORMED_MODULE_ASSESSMENT", "object_id": "module_assessment", "reason": "criterion_outcome must be PASS, CONDITION or FAIL."})

    checks["source_evidence_claim_lineage"] = not any(
        item["type"] in {"ORPHAN_EVIDENCE", "ORPHAN_CLAIM", "UNSUPPORTED_CITATION"}
        for item in errors
    )
    checks["raw_model_cannot_self_certify"] = all(
        str(row.get("pce_status", "")).lower() not in {"certified", "certified with caveat"}
        for row in all_rows["claims"] + all_rows["evidence"]
        if isinstance(row, dict)
    )
    if not checks["raw_model_cannot_self_certify"]:
        errors.append({"type": "PROVIDER_SELF_CERTIFICATION", "object_id": "provider_response", "reason": "Provider output cannot set PCE certification."})

    prohibited_gate_fields = {
        "gate_a_result", "gate_b_result", "gate_result", "downstream_permission", "go_no_go",
        "gate_c_result", "final_recommendation", "decision_state", "delivery_permission",
        "final_human_transaction_approval",
    }
    present_prohibited = sorted(prohibited_gate_fields & set(payload))
    checks["provider_did_not_choose_gate"] = not present_prohibited
    checks["provider_did_not_choose_gate_a"] = not present_prohibited
    for field in present_prohibited:
        errors.append(
            {
                "type": "PROVIDER_GATE_AUTHORITY_VIOLATION",
                "object_id": field,
                "reason": "A research provider cannot choose Gate A, Gate B, or a transaction recommendation.",
            }
        )
    structured_output = (
        payload.get("module_assessment", {}).get("structured_output", {})
        if isinstance(payload.get("module_assessment"), dict)
        else {}
    )
    nested_reserved = {
        field: structured_output.get(field)
        for field in ("gate_c_result", "decision_state", "delivery_permission", "final_human_transaction_approval")
        if isinstance(structured_output, dict) and structured_output.get(field) not in (None, "", [], {})
    }
    checks["provider_did_not_choose_gate_c_or_decision_state"] = not nested_reserved and not present_prohibited
    for field in sorted(nested_reserved):
        errors.append(
            {
                "type": "PROVIDER_GATE_AUTHORITY_VIOLATION",
                "object_id": f"module_assessment.structured_output.{field}",
                "reason": "A research provider cannot choose Gate C, the final Decision State, delivery permission, or final human approval.",
            }
        )

    status = ProviderValidationStatus.REJECTED if errors else ProviderValidationStatus.ACCEPTED
    admitted = {
        name: ([] if errors else list(ids_by_collection[name]))
        for name in OBJECT_COLLECTIONS
    }
    rejected = [
        {"object_type": item["type"], "object_id": item["object_id"], "reason": item["reason"]}
        for item in errors
    ]
    return ProviderOutputValidation(
        status=status,
        errors=errors,
        warnings=warnings,
        admitted_object_ids=admitted,
        rejected_objects=rejected,
        checks=checks,
    )
