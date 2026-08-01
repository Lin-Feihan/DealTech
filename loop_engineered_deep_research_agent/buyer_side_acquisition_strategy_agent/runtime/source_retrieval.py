"""Retrieval provider boundary for Buyer-Side Acquisition Strategy Agent M2.

Buyer-Side Acquisition Strategy Agent is provider-agnostic orchestration code. External systems such as
manual source collection, URL fetchers, search APIs, SEC EDGAR APIs, patent
APIs, clinical-trial APIs, or GPT/Claude/Deep Research systems may supply
source leads or retrieved-source manifests, but raw_evidence.json is extracted
only from sources listed in retrieved_sources_manifest.json. case_seed remains a
lead artifact and is never evidence.
"""

from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.source_discovery import source_discovery_plan_id


class SourceRetrievalError(ValueError):
    pass


PROVIDER_NOT_CONFIGURED_MESSAGE = "Provider not configured; no retrieval performed; case_seed cannot be used as evidence."

RETRIEVAL_MODES = {
    "manual_retrieved_sources",
    "authoritative_url_retrieval",
    "web_search",
    "sec_edgar",
    "patent",
    "clinical_trials",
    "deep_research",
}
IMPLEMENTED_PROVIDERS = {
    "manual_retrieved_sources": "manual_retrieved_sources_provider",
    "authoritative_url_retrieval": "authoritative_url_retrieval_provider",
}
FAIL_CLOSED_STUB_PROVIDERS = {
    "web_search": "web_search_provider",
    "sec_edgar": "sec_edgar_provider",
    "patent": "patent_provider",
    "clinical_trials": "clinical_trials_provider",
    "deep_research": "deep_research_provider",
}
SOURCE_TIERS = {"Tier 1", "Tier 2", "Tier 3", "Tier 4"}
SOURCE_TIME_RELATIONS = {"pre_decision", "at_decision", "post_decision", "retrospective", "unknown"}
PERMITTED_USES = {
    "ex_ante_deal_evaluation",
    "transaction_terms_verification",
    "retrospective_outcome_validation",
    "source_lead_only",
    "gap_tracking",
}
REQUIRED_SOURCE_FIELDS = (
    "source_id",
    "title",
    "url_or_file",
    "source_type",
    "source_tier",
    "source_owner",
    "retrieval_date",
    "retrieved_by",
    "related_source_need_ids",
    "related_search_query_ids",
    "reliability_reason",
    "use_limitations",
    "source_date_or_period",
    "source_time_relation_to_decision_date",
    "permitted_use",
    "local_cache_path",
)

UNAVAILABLE_PROVIDER_MESSAGES = {mode: PROVIDER_NOT_CONFIGURED_MESSAGE for mode in FAIL_CLOSED_STUB_PROVIDERS}


def load_retrieved_sources_manifest(path: Path, source_discovery_plan: dict[str, Any]) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except FileNotFoundError as exc:
        raise SourceRetrievalError(f"Retrieved sources manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceRetrievalError(f"Invalid JSON retrieved sources manifest: {exc}") from exc

    manifest = _with_temporal_defaults(manifest)
    validate_retrieved_sources_manifest(manifest, source_discovery_plan, manifest_path=path)
    return manifest


def validate_retrieved_sources_manifest(
    manifest: Any,
    source_discovery_plan: dict[str, Any],
    manifest_path: Path | None = None,
    allow_remote_sources: bool = False,
) -> None:
    if not isinstance(manifest, dict):
        raise SourceRetrievalError("retrieved_sources_manifest must be an object.")
    required = (
        "case_id",
        "generated_artifact",
        "retrieval_mode",
        "retrieval_date",
        "source_discovery_plan_id",
        "evidence_coverage_status",
        "retrieved_sources",
        "failed_source_needs",
    )
    missing = [field for field in required if field not in manifest]
    if missing:
        raise SourceRetrievalError(f"Missing retrieved sources manifest field(s): {', '.join(missing)}")
    if manifest["case_id"] != source_discovery_plan["case_id"]:
        raise SourceRetrievalError("retrieved_sources_manifest case_id must match source_discovery_plan case_id.")
    if manifest["generated_artifact"] != "retrieved_sources_manifest.json":
        raise SourceRetrievalError("generated_artifact must be retrieved_sources_manifest.json.")
    if manifest["retrieval_mode"] not in RETRIEVAL_MODES:
        raise SourceRetrievalError(f"retrieval_mode must be one of: {', '.join(sorted(RETRIEVAL_MODES))}.")
    if manifest["source_discovery_plan_id"] != source_discovery_plan_id(source_discovery_plan):
        raise SourceRetrievalError("source_discovery_plan_id mismatch.")
    if manifest["evidence_coverage_status"] not in {"complete", "partial"}:
        raise SourceRetrievalError("evidence_coverage_status must be complete or partial.")
    if not isinstance(manifest["retrieved_sources"], list):
        raise SourceRetrievalError("retrieved_sources must be an array.")
    if not manifest["retrieved_sources"]:
        raise SourceRetrievalError("retrieved_sources must include at least one valid authoritative source; zero-source manifests fail closed.")
    if not isinstance(manifest["failed_source_needs"], list):
        raise SourceRetrievalError("failed_source_needs must be an array.")
    if manifest["failed_source_needs"] and manifest["evidence_coverage_status"] != "partial":
        raise SourceRetrievalError("evidence_coverage_status must be partial when failed_source_needs are present.")

    source_need_ids = {need["source_need_id"] for need in source_discovery_plan["source_needs"]}
    search_query_ids = {query["query_id"] for query in source_discovery_plan["search_queries"]}
    source_ids: set[str] = set()

    for source in manifest["retrieved_sources"]:
        _validate_source(source, source_need_ids, search_query_ids, source_ids, manifest_path, allow_remote_sources)
    if not any(source["source_tier"] in {"Tier 1", "Tier 2"} for source in manifest["retrieved_sources"]):
        raise SourceRetrievalError("retrieved_sources must include at least one Tier 1 or Tier 2 authoritative source.")
    for failed_need in manifest["failed_source_needs"]:
        _validate_failed_source_need(failed_need, source_need_ids)


def retrieve_sources_with_provider(
    retrieval_mode: str,
    source_discovery_plan: dict[str, Any],
    output_dir: Path,
    retrieved_sources_manifest_path: Path | None = None,
) -> dict[str, Any]:
    require_retrieval_inputs(retrieval_mode, retrieved_sources_manifest_path, source_discovery_plan)
    if retrieval_mode == "manual_retrieved_sources":
        assert retrieved_sources_manifest_path is not None
        return manual_retrieved_sources_provider(retrieved_sources_manifest_path, source_discovery_plan, output_dir)
    if retrieval_mode == "authoritative_url_retrieval":
        return authoritative_url_retrieval_provider(source_discovery_plan, output_dir, retrieved_sources_manifest_path)
    if retrieval_mode == "web_search":
        return web_search_provider()
    if retrieval_mode == "sec_edgar":
        return sec_edgar_provider()
    if retrieval_mode == "patent":
        return patent_provider()
    if retrieval_mode == "clinical_trials":
        return clinical_trials_provider()
    if retrieval_mode == "deep_research":
        return deep_research_provider()
    raise SourceRetrievalError(UNAVAILABLE_PROVIDER_MESSAGES[retrieval_mode])


def require_retrieval_inputs(retrieval_mode: str, retrieved_sources_manifest_path: Path | None, source_discovery_plan: dict[str, Any] | None = None) -> None:
    if retrieval_mode not in RETRIEVAL_MODES:
        raise SourceRetrievalError(f"retrieval_mode must be one of: {', '.join(sorted(RETRIEVAL_MODES))}.")
    if retrieval_mode in UNAVAILABLE_PROVIDER_MESSAGES:
        raise SourceRetrievalError(UNAVAILABLE_PROVIDER_MESSAGES[retrieval_mode])
    if retrieved_sources_manifest_path is None:
        if retrieval_mode == "manual_retrieved_sources":
            raise SourceRetrievalError(f"manual_retrieved_sources_provider requires --retrieved-sources-manifest. {PROVIDER_NOT_CONFIGURED_MESSAGE}")
        if retrieval_mode == "authoritative_url_retrieval" and source_discovery_plan is not None and not _explicit_url_targets(source_discovery_plan):
            raise SourceRetrievalError(f"authoritative_url_retrieval_provider found no explicit authoritative URL targets. {PROVIDER_NOT_CONFIGURED_MESSAGE}")


def manifest_id(manifest: dict[str, Any]) -> str:
    return f"RSM-{manifest['case_id']}-{manifest['retrieval_date']}"


def resolve_source_path(source: dict[str, Any], manifest_path: Path | None) -> Path:
    value = source.get("local_cache_path") or source["url_or_file"]
    if value.startswith("http://") or value.startswith("https://"):
        raise SourceRetrievalError(f"URL retrieval is not configured for source_id {source['source_id']}; provide a local retrieved file.")
    path = Path(value)
    if not path.is_absolute() and manifest_path is not None:
        path = manifest_path.parent / path
    if not path.exists():
        raise SourceRetrievalError(f"Source file unavailable for source_id {source['source_id']}: {path}")
    return path


def _validate_source(
    source: Any,
    source_need_ids: set[str],
    search_query_ids: set[str],
    seen_source_ids: set[str],
    manifest_path: Path | None,
    allow_remote_sources: bool,
) -> None:
    if not isinstance(source, dict):
        raise SourceRetrievalError("Each retrieved source must be an object.")
    missing = [field for field in REQUIRED_SOURCE_FIELDS if field not in source]
    if missing:
        raise SourceRetrievalError(f"Missing retrieved source field(s): {', '.join(missing)}")
    if source["source_id"] in seen_source_ids:
        raise SourceRetrievalError(f"Duplicate source_id: {source['source_id']}")
    seen_source_ids.add(source["source_id"])
    if source["source_tier"] not in SOURCE_TIERS:
        raise SourceRetrievalError(f"Invalid source_tier for {source['source_id']}.")
    if source["source_time_relation_to_decision_date"] not in SOURCE_TIME_RELATIONS:
        raise SourceRetrievalError(f"Invalid source_time_relation_to_decision_date for {source['source_id']}.")
    if source["permitted_use"] not in PERMITTED_USES:
        raise SourceRetrievalError(f"Invalid permitted_use for {source['source_id']}.")
    if source["source_time_relation_to_decision_date"] in {"post_decision", "retrospective"} and source["permitted_use"] == "ex_ante_deal_evaluation":
        raise SourceRetrievalError(f"{source['source_id']} is post-decision/retrospective and cannot be silently marked ex_ante_deal_evaluation.")
    if not source["related_source_need_ids"]:
        raise SourceRetrievalError(f"{source['source_id']} must map to at least one source_need.")
    unknown_needs = set(source["related_source_need_ids"]) - source_need_ids
    if unknown_needs:
        raise SourceRetrievalError(f"{source['source_id']} references unknown source_need_id(s): {sorted(unknown_needs)}")
    unknown_queries = set(source["related_search_query_ids"]) - search_query_ids
    if unknown_queries:
        raise SourceRetrievalError(f"{source['source_id']} references unknown search_query_id(s): {sorted(unknown_queries)}")
    if source["source_type"] == "web_search":
        raise SourceRetrievalError(f"{source['source_id']} may not cite web_search as a source type.")
    if not allow_remote_sources:
        resolve_source_path(source, manifest_path)


def _validate_failed_source_need(failed_need: Any, source_need_ids: set[str]) -> None:
    if not isinstance(failed_need, dict):
        raise SourceRetrievalError("Each failed_source_needs entry must be an object.")
    missing = [field for field in ("source_need_id", "reason") if field not in failed_need]
    if missing:
        raise SourceRetrievalError(f"Missing failed_source_needs field(s): {', '.join(missing)}")
    if failed_need["source_need_id"] not in source_need_ids:
        raise SourceRetrievalError(f"failed_source_needs references unknown source_need_id: {failed_need['source_need_id']}")
    if not isinstance(failed_need["reason"], str) or not failed_need["reason"].strip():
        raise SourceRetrievalError("failed_source_needs reason must be a non-empty string.")


def manual_retrieved_sources_provider(manifest_path: Path, source_discovery_plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    manifest = load_retrieved_sources_manifest(manifest_path, source_discovery_plan)
    if manifest["retrieval_mode"] != "manual_retrieved_sources":
        raise SourceRetrievalError("manual_retrieved_sources_provider requires manifest retrieval_mode manual_retrieved_sources.")
    return _cache_manifest_sources(manifest, source_discovery_plan, output_dir, source_manifest_path=manifest_path, retrieved_by_suffix="manual_retrieved_sources_provider")


def authoritative_url_retrieval_provider(
    source_discovery_plan: dict[str, Any],
    output_dir: Path,
    retrieved_sources_manifest_path: Path | None,
) -> dict[str, Any]:
    if retrieved_sources_manifest_path is not None:
        manifest = load_retrieved_sources_manifest(retrieved_sources_manifest_path, source_discovery_plan)
        if manifest["retrieval_mode"] != "authoritative_url_retrieval":
            raise SourceRetrievalError("authoritative_url_retrieval_provider requires manifest retrieval_mode authoritative_url_retrieval.")
        return _fetch_or_cache_manifest_sources(manifest, source_discovery_plan, output_dir, source_manifest_path=retrieved_sources_manifest_path)

    explicit_targets = _explicit_url_targets(source_discovery_plan)
    if not explicit_targets:
        raise SourceRetrievalError(f"authoritative_url_retrieval_provider found no explicit authoritative URL targets. {PROVIDER_NOT_CONFIGURED_MESSAGE}")

    sources = []
    for index, target in enumerate(explicit_targets, start=1):
        url = target["url"]
        source_id = f"SRC-AUTH-URL-{index:03d}"
        cache_path = _fetch_url_to_cache(url, source_id, output_dir)
        sources.append(
            {
                "source_id": source_id,
                "title": target.get("title") or target.get("target_description") or url,
                "url_or_file": url,
                "source_type": target.get("expected_source_type", "authoritative URL source"),
                "source_tier": target.get("source_tier") or _tier_for_source_type(target.get("expected_source_type", "")),
                "source_owner": target.get("likely_source_owner", "explicit_authoritative_url_target"),
                "retrieval_date": _today_utc_date(),
                "retrieved_by": "authoritative_url_retrieval_provider",
                "related_source_need_ids": target["related_source_need_ids"],
                "related_search_query_ids": _related_search_query_ids(source_discovery_plan, target["related_source_need_ids"]),
                "reliability_reason": "Retrieved from explicit authoritative URL target in source_discovery_plan; no live search performed and case_seed was not used as evidence.",
                "use_limitations": "Raw retrieved text only; conflicts and certification are handled downstream.",
                "source_date_or_period": target.get("source_date_or_period", "unknown"),
                "source_time_relation_to_decision_date": target.get("source_time_relation_to_decision_date", "unknown"),
                "permitted_use": target.get("permitted_use", "source_lead_only"),
                "local_cache_path": str(cache_path.relative_to(output_dir)),
            }
        )

    manifest = {
        "case_id": source_discovery_plan["case_id"],
        "generated_artifact": "retrieved_sources_manifest.json",
        "retrieval_mode": "authoritative_url_retrieval",
        "retrieval_date": _today_utc_date(),
        "source_discovery_plan_id": source_discovery_plan_id(source_discovery_plan),
        "evidence_coverage_status": "complete",
        "retrieved_sources": sources,
        "failed_source_needs": [],
    }
    validate_retrieved_sources_manifest(manifest, source_discovery_plan, manifest_path=output_dir / "retrieved_sources_manifest.json")
    return manifest


def web_search_provider() -> dict[str, Any]:
    raise SourceRetrievalError(PROVIDER_NOT_CONFIGURED_MESSAGE)


def sec_edgar_provider() -> dict[str, Any]:
    raise SourceRetrievalError(PROVIDER_NOT_CONFIGURED_MESSAGE)


def patent_provider() -> dict[str, Any]:
    raise SourceRetrievalError(PROVIDER_NOT_CONFIGURED_MESSAGE)


def clinical_trials_provider() -> dict[str, Any]:
    raise SourceRetrievalError(PROVIDER_NOT_CONFIGURED_MESSAGE)


def deep_research_provider() -> dict[str, Any]:
    raise SourceRetrievalError(PROVIDER_NOT_CONFIGURED_MESSAGE)


def _fetch_or_cache_manifest_sources(manifest: dict[str, Any], source_discovery_plan: dict[str, Any], output_dir: Path, source_manifest_path: Path) -> dict[str, Any]:
    normalized = {**manifest, "retrieved_sources": []}
    for source in manifest["retrieved_sources"]:
        source_copy = dict(source)
        if source_copy["url_or_file"].startswith(("http://", "https://")):
            cache_path = _fetch_url_to_cache(source_copy["url_or_file"], source_copy["source_id"], output_dir)
            source_copy["local_cache_path"] = str(cache_path.relative_to(output_dir))
        else:
            cache_path = _copy_source_to_cache(resolve_source_path(source_copy, source_manifest_path), source_copy["source_id"], output_dir)
            source_copy["local_cache_path"] = str(cache_path.relative_to(output_dir))
        normalized["retrieved_sources"].append(source_copy)
    validate_retrieved_sources_manifest(normalized, source_discovery_plan, manifest_path=output_dir / "retrieved_sources_manifest.json")
    return normalized


def _cache_manifest_sources(
    manifest: dict[str, Any],
    source_discovery_plan: dict[str, Any],
    output_dir: Path,
    source_manifest_path: Path,
    retrieved_by_suffix: str,
) -> dict[str, Any]:
    normalized = {**manifest, "retrieved_sources": []}
    for source in manifest["retrieved_sources"]:
        source_copy = dict(source)
        cache_input = source_copy.get("local_cache_path") or source_copy["url_or_file"]
        if cache_input.startswith(("http://", "https://")):
            raise SourceRetrievalError(f"manual_retrieved_sources_provider cannot fetch URL source_id {source_copy['source_id']}; provide a local_cache_path or use authoritative_url_retrieval_provider.")
        cache_path = _copy_source_to_cache(resolve_source_path(source_copy, source_manifest_path), source_copy["source_id"], output_dir)
        source_copy["local_cache_path"] = str(cache_path.relative_to(output_dir))
        if retrieved_by_suffix not in source_copy["retrieved_by"]:
            source_copy["retrieved_by"] = f"{source_copy['retrieved_by']} + {retrieved_by_suffix}"
        normalized["retrieved_sources"].append(source_copy)
    validate_retrieved_sources_manifest(normalized, source_discovery_plan, manifest_path=output_dir / "retrieved_sources_manifest.json")
    return normalized


def _copy_source_to_cache(source_path: Path, source_id: str, output_dir: Path) -> Path:
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix or ".txt"
    target_path = cache_dir / f"{_safe_id(source_id)}{suffix}"
    shutil.copyfile(source_path, target_path)
    return target_path


def _fetch_url_to_cache(url: str, source_id: str, output_dir: Path) -> Path:
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_path = cache_dir / f"{_safe_id(source_id)}.txt"
    request = urllib.request.Request(url, headers={"User-Agent": "DealTech-Buyer-Side Acquisition Strategy Agent-M2b/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SourceRetrievalError(f"authoritative_url_retrieval_provider could not retrieve {url}: {exc}") from exc
    target_path.write_text(body.decode("utf-8", errors="replace"), encoding="utf-8")
    return target_path


def _explicit_url_targets(source_discovery_plan: dict[str, Any]) -> list[dict[str, Any]]:
    explicit: list[dict[str, Any]] = []
    for target in source_discovery_plan.get("retrieval_targets", []):
        if target.get("url"):
            explicit.append({**target, "url": target["url"]})
        for url in target.get("candidate_urls", []):
            explicit.append({**target, "url": url})
    return explicit


def _related_search_query_ids(source_discovery_plan: dict[str, Any], source_need_ids: list[str]) -> list[str]:
    source_need_id_set = set(source_need_ids)
    return [
        query["query_id"]
        for query in source_discovery_plan.get("search_queries", [])
        if source_need_id_set.intersection(query.get("related_source_need_ids", []))
    ]


def _tier_for_source_type(source_type: str) -> str:
    lower = source_type.lower()
    if any(marker in lower for marker in ("sec", "agreement", "regulator", "stock exchange", "patent", "clinical")):
        return "Tier 1"
    if any(marker in lower for marker in ("company", "pipeline", "official website", "press release")):
        return "Tier 2"
    return "Tier 3"


def _with_temporal_defaults(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("retrieved_sources"), list):
        return manifest
    normalized = {**manifest, "retrieved_sources": []}
    for source in manifest["retrieved_sources"]:
        if not isinstance(source, dict):
            normalized["retrieved_sources"].append(source)
            continue
        defaults = _temporal_defaults_for_source(source)
        normalized["retrieved_sources"].append({**defaults, **source})
    return normalized


def _temporal_defaults_for_source(source: dict[str, Any]) -> dict[str, str]:
    source_text = " ".join(
        str(source.get(field, ""))
        for field in ("source_id", "title", "source_type", "source_owner", "url_or_file", "local_cache_path")
    ).lower()
    if "stock purchase agreement" in source_text or "sec-spa" in source_text:
        source_date = _source_date_or_unknown(source)
        return {
            "source_date_or_period": source_date,
            "source_time_relation_to_decision_date": "at_decision",
            "permitted_use": "transaction_terms_verification",
        }
    if "424b4" in source_text or "prospectus" in source_text:
        existing = _existing_temporal_metadata(source)
        return {
            "source_date_or_period": existing["source_date_or_period"],
            "source_time_relation_to_decision_date": existing["source_time_relation_to_decision_date"] or "post_decision",
            "permitted_use": "retrospective_outcome_validation",
        }
    if "10-k" in source_text or "annual report" in source_text:
        existing = _existing_temporal_metadata(source)
        return {
            "source_date_or_period": existing["source_date_or_period"],
            "source_time_relation_to_decision_date": existing["source_time_relation_to_decision_date"] or "post_decision",
            "permitted_use": "retrospective_outcome_validation",
        }
    if "pipeline" in source_text:
        retrieval_date = str(source.get("retrieval_date", "retrieval date unknown"))
        return {
            "source_date_or_period": f"current as of retrieval date {retrieval_date}",
            "source_time_relation_to_decision_date": "retrospective",
            "permitted_use": "retrospective_outcome_validation",
        }
    if "stock exchange" in source_text or "ownership disclosure" in source_text or "company filing" in source_text:
        return {
            "source_date_or_period": str(source.get("source_date_or_period") or source.get("source_date") or "unknown"),
            "source_time_relation_to_decision_date": "pre_decision",
            "permitted_use": "ex_ante_deal_evaluation",
        }
    if "patent" in source_text:
        return {
            "source_date_or_period": "patent publication/filing period",
            "source_time_relation_to_decision_date": "unknown",
            "permitted_use": "source_lead_only",
        }
    return {
        "source_date_or_period": "unknown",
        "source_time_relation_to_decision_date": "unknown",
        "permitted_use": "source_lead_only",
    }


def _existing_temporal_metadata(source: dict[str, Any]) -> dict[str, str]:
    return {
        "source_date_or_period": _source_date_or_unknown(source),
        "source_time_relation_to_decision_date": str(source.get("source_time_relation_to_decision_date") or ""),
    }


def _source_date_or_unknown(source: dict[str, Any]) -> str:
    return str(source.get("source_date_or_period") or source.get("source_date") or "unknown")


def _today_utc_date() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).date().isoformat()


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
