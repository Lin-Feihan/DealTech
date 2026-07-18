from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalised_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return value.strip().lower()
    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, "")
    )


def source_identity(row: dict[str, Any]) -> tuple[str, ...]:
    if str(row.get("source_kind", "")).lower() == "attachment":
        return (
            "attachment",
            str(row.get("file_hash_sha256", "")).lower(),
            str(row.get("version", "")),
        )
    return (
        "web",
        normalised_url(str(row.get("url", ""))),
        str(row.get("document_identity", "") or row.get("publication_identity", "")).strip().lower(),
        str(row.get("version", "")).strip().lower(),
    )


class SharedBlockARegistry:
    """One append-only Block A Source Registry and Evidence/Claim ledger."""

    def __init__(self) -> None:
        self.sources: list[dict[str, Any]] = []
        self.source_uses: list[dict[str, Any]] = []
        self.evidence: list[dict[str, Any]] = []
        self.claims: list[dict[str, Any]] = []
        self.assumptions: list[dict[str, Any]] = []
        self.unknowns: list[dict[str, Any]] = []
        self.counterevidence: list[dict[str, Any]] = []
        self.conflicts: list[dict[str, Any]] = []
        self.claim_dependencies: list[dict[str, Any]] = []
        self._source_by_identity: dict[tuple[str, ...], str] = {}

    def prior_objects(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "sources": self.sources,
            "evidence": self.evidence,
            "claims": self.claims,
            "assumptions": self.assumptions,
            "unknowns": self.unknowns,
            "counterevidence": self.counterevidence,
        }

    def canonicalise_payload(
        self, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
        canonical = copy.deepcopy(payload)
        aliases: dict[str, str] = {}
        rejected: list[dict[str, Any]] = []
        retained: list[dict[str, Any]] = []
        seen_in_response: dict[tuple[str, ...], str] = {}
        for row in canonical.get("sources", []):
            identity = source_identity(row)
            existing = self._source_by_identity.get(identity) or seen_in_response.get(identity)
            if existing:
                aliases[str(row.get("source_id", ""))] = existing
                rejected.append(
                    {
                        "object_type": "DUPLICATE_SOURCE_CANDIDATE",
                        "object_id": row.get("source_id", ""),
                        "canonical_source_id": existing,
                        "reason": "Duplicate Source candidate was not admitted and cannot increase source diversity.",
                    }
                )
            else:
                retained.append(row)
                seen_in_response[identity] = str(row.get("source_id", ""))
        canonical["sources"] = retained
        for row in canonical.get("evidence", []):
            if row.get("source_id") in aliases:
                row["source_id"] = aliases[row["source_id"]]
        for row in canonical.get("counterevidence", []):
            row["source_ids"] = [aliases.get(item, item) for item in row.get("source_ids", [])]
        return canonical, rejected, aliases

    def admit(
        self,
        *,
        admitted: dict[str, list[dict[str, Any]]],
        conflicts: list[dict[str, Any]],
        module_id: str,
        module_name: str,
        research_question_id: str,
        iteration: int,
        provider_attempt: str,
        source_aliases: dict[str, str] | None = None,
    ) -> None:
        timestamp = utc_now()
        aliases = source_aliases or {}
        for row in admitted.get("sources", []):
            item = copy.deepcopy(row)
            identity = source_identity(item)
            if identity in self._source_by_identity:
                raise ValueError("Duplicate Source reached the admission boundary.")
            self._source_by_identity[identity] = item["source_id"]
            item["source_identity"] = list(identity)
            item["admitted_iteration"] = iteration
            item["provider_attempt"] = provider_attempt
            item["timestamp"] = timestamp
            self.sources.append(item)
        used_source_ids = {
            row.get("source_id", "") for row in admitted.get("evidence", []) if row.get("source_id")
        }
        used_source_ids.update(aliases.values())
        for source_id in sorted(used_source_ids):
            self.source_uses.append(
                {
                    "source_use_id": f"USE-{provider_attempt}-{source_id}",
                    "source_id": source_id,
                    "owning_module": module_id,
                    "module_name": module_name,
                    "originating_research_question": research_question_id,
                    "iteration": iteration,
                    "provider_attempt": provider_attempt,
                    "timestamp": timestamp,
                }
            )
        source_limits = {row["source_id"]: row.get("limitations", "") for row in self.sources}
        for row in admitted.get("evidence", []):
            item = copy.deepcopy(row)
            limitation_parts = [item.get("limitations", ""), source_limits.get(item.get("source_id", ""), "")]
            item["limitations"] = " | ".join(part for part in limitation_parts if part)
            item.update(
                {
                    "owning_module": module_id,
                    "originating_research_question": research_question_id,
                    "iteration": iteration,
                    "provider_attempt": provider_attempt,
                    "timestamp": timestamp,
                    "pce_status": "PENDING",
                    "er_brb_status": "PENDING",
                }
            )
            self.evidence.append(item)
        evidence_limits = {row["evidence_id"]: row.get("limitations", "") for row in self.evidence}
        for row in admitted.get("claims", []):
            item = copy.deepcopy(row)
            propagated = [evidence_limits.get(value, "") for value in item.get("supporting_evidence_ids", [])]
            parts = [item.get("limitations", ""), *propagated]
            item["limitations"] = " | ".join(dict.fromkeys(part for part in parts if part))
            item.update(
                {
                    "owning_module_id": module_id,
                    "originating_research_question": research_question_id,
                    "iteration": iteration,
                    "provider_attempt": provider_attempt,
                    "timestamp": timestamp,
                    "pce_status": "PENDING",
                    "er_brb_status": "PENDING",
                }
            )
            self.claims.append(item)
            for dependency_id in item.get("dependency_claim_ids", []):
                self.claim_dependencies.append(
                    {
                        "dependency_id": f"DEP-{item['claim_id']}-{dependency_id}",
                        "claim_id": item["claim_id"],
                        "depends_on_claim_id": dependency_id,
                        "dependency_type": "analytical_dependency_not_primary_evidence",
                        "owning_module": module_id,
                        "iteration": iteration,
                        "provider_attempt": provider_attempt,
                        "timestamp": timestamp,
                    }
                )
        for collection_name in ("assumptions", "unknowns", "counterevidence"):
            target = getattr(self, collection_name)
            for row in admitted.get(collection_name, []):
                item = copy.deepcopy(row)
                item.update(
                    {
                        "owning_module_id": module_id,
                        "originating_research_question": research_question_id,
                        "iteration": iteration,
                        "provider_attempt": provider_attempt,
                        "timestamp": timestamp,
                        "pce_status": "NOT_APPLICABLE",
                        "er_brb_status": "NOT_APPLICABLE",
                    }
                )
                target.append(item)
        for row in conflicts:
            item = copy.deepcopy(row)
            item.update(
                {
                    "owning_module": module_id,
                    "iteration": iteration,
                    "provider_attempt": provider_attempt,
                    "timestamp": timestamp,
                }
            )
            self.conflicts.append(item)

    def apply_certification(self, certification: dict[str, Any]) -> None:
        pce = {
            row["claim_id"]: row.get("PCE_status", "Not Certified")
            for row in certification.get("pce_result", {}).get("claim_results", [])
        }
        er: dict[str, list[dict[str, Any]]] = {}
        for row in certification.get("er_brb_results", []):
            er.setdefault(row.get("claim_id", ""), []).append(row)
        for claim in self.claims:
            claim["pce_status"] = pce.get(claim["claim_id"], "Not Certified")
            claim["er_brb_status"] = er.get(claim["claim_id"], [])
        claim_by_evidence = {
            evidence_id: claim["claim_id"]
            for claim in self.claims
            for evidence_id in claim.get("supporting_evidence_ids", [])
        }
        for evidence in self.evidence:
            claim_id = claim_by_evidence.get(evidence["evidence_id"], evidence.get("claim_id", ""))
            evidence["pce_status"] = pce.get(claim_id, "Not Certified")
            evidence["er_brb_status"] = er.get(claim_id, [])

    def source_output(self) -> list[dict[str, Any]]:
        uses: dict[str, list[dict[str, Any]]] = {}
        for row in self.source_uses:
            uses.setdefault(row["source_id"], []).append(row)
        return [{**row, "module_uses": uses.get(row["source_id"], [])} for row in self.sources]
