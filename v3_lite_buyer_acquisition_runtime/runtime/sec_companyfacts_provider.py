from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable


SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_USER_AGENT_ENV = "SEC_USER_AGENT"

CompanyfactsFetcher = Callable[[str, str, float], dict[str, Any]]
SecCompanyfactsProvider = Callable[[str, str, str, str], dict[str, Any]]


def normalize_cik(cik: str | int) -> str:
    digits = "".join(char for char in str(cik).strip() if char.isdigit())
    if not digits:
        raise ValueError("CIK must contain digits.")
    if len(digits) > 10:
        raise ValueError("CIK cannot exceed 10 digits.")
    return digits.zfill(10)


def make_sec_companyfacts_provider(
    user_agent: str | None = None,
    fetcher: CompanyfactsFetcher | None = None,
    timeout_seconds: float = 10.0,
) -> SecCompanyfactsProvider:
    effective_fetcher = fetcher or _fetch_companyfacts_json

    def provider(cik: str, taxonomy_tag: str, period: str, unit: str) -> dict[str, Any]:
        effective_user_agent = (user_agent if user_agent is not None else os.environ.get(SEC_USER_AGENT_ENV, "")).strip()
        if not effective_user_agent:
            return {"status": "provider_unavailable"}
        try:
            normalized_cik = normalize_cik(cik)
            payload = effective_fetcher(SEC_COMPANYFACTS_URL.format(cik=normalized_cik), effective_user_agent, timeout_seconds)
        except (ValueError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return {"status": "provider_unavailable"}

        fact = _match_companyfact(payload, taxonomy_tag, period, unit)
        if fact is None:
            return {"status": "not_found"}
        return {"status": "ok", "observed_value": fact.get("val")}

    return provider


def _fetch_companyfacts_json(url: str, user_agent: str, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _match_companyfact(payload: dict[str, Any], taxonomy_tag: str, period: str, unit: str) -> dict[str, Any] | None:
    facts = payload.get("facts", {})
    us_gaap = facts.get("us-gaap", {}) if isinstance(facts, dict) else {}
    tag_payload = us_gaap.get(taxonomy_tag, {}) if isinstance(us_gaap, dict) else {}
    units = tag_payload.get("units", {}) if isinstance(tag_payload, dict) else {}
    unit_facts = units.get(unit, []) if isinstance(units, dict) else []
    if not isinstance(unit_facts, list):
        return None

    period_text = str(period).strip()
    matches = [fact for fact in unit_facts if isinstance(fact, dict) and str(fact.get("end", "")).strip() == period_text]
    if not matches and len(period_text) == 4 and period_text.isdigit():
        matches = [fact for fact in unit_facts if isinstance(fact, dict) and str(fact.get("fy", "")).strip() == period_text]
    if not matches:
        return None
    return _best_fact(matches)


def _best_fact(facts: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(facts, key=lambda fact: (str(fact.get("filed", "")), str(fact.get("accn", ""))))[-1]
