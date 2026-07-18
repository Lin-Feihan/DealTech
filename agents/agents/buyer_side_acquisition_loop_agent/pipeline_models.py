from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .storage import to_primitive


RC_SCHEMA_VERSION = "release-candidate-1"
SUPPORTED_PIPELINE_SCHEMAS = {RC_SCHEMA_VERSION}


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        to_primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class BlockBInputBundle:
    schema_version: str
    case_id: str
    run_id: str
    as_of_date: str
    mandate_reference: dict[str, Any]
    research_contract_reference: dict[str, Any]
    gate_a_history: list[dict[str, Any]]
    admitted_claims: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    assumptions: list[dict[str, Any]]
    unknowns: list[dict[str, Any]]
    counterevidence: list[dict[str, Any]]
    open_research_gaps: list[dict[str, Any]]
    human_review_items: list[dict[str, Any]]
    mandate_constraints: dict[str, Any]
    provenance: dict[str, Any]
    artifact_references: dict[str, str]
    artifact_hashes: dict[str, str]

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "BlockBInputBundle":
        return cls(**row)


BLOCK_B_HASHED_FIELDS = (
    "mandate_reference",
    "research_contract_reference",
    "gate_a_history",
    "admitted_claims",
    "sources",
    "evidence",
    "assumptions",
    "unknowns",
    "counterevidence",
)


def validate_block_b_input_bundle(
    row: dict[str, Any], *, case_id: str, run_id: str, as_of_date: str
) -> BlockBInputBundle:
    bundle = BlockBInputBundle.from_dict(row)
    if bundle.schema_version not in SUPPORTED_PIPELINE_SCHEMAS:
        raise ValueError(f"Unsupported BlockBInputBundle schema: {bundle.schema_version}")
    identities = {
        bundle.case_id,
        str(bundle.mandate_reference.get("case_id", "")),
        str(bundle.research_contract_reference.get("case_id", "")),
        case_id,
    }
    if "" in identities or len(identities) != 1:
        raise ValueError("BlockBInputBundle contains mismatched case IDs")
    if bundle.run_id != run_id:
        raise ValueError("BlockBInputBundle contains a mismatched run ID")
    if bundle.as_of_date != as_of_date:
        raise ValueError("BlockBInputBundle contains a mismatched as-of date")
    if not bundle.gate_a_history:
        raise ValueError("BlockBInputBundle requires append-only Gate A history")
    final_gate = bundle.gate_a_history[-1]
    if final_gate.get("status") not in {"PASS", "CONDITIONAL_PASS"}:
        raise ValueError("Block B requires PASS or CONDITIONAL_PASS at Gate A")
    for index, gate in enumerate(bundle.gate_a_history, start=1):
        if gate.get("gate_id") != "GATE_A" or gate.get("case_id") != case_id:
            raise ValueError("Gate A history contains mismatched provenance")
        if gate.get("version") != index or not gate.get("artifact_hash"):
            raise ValueError("Gate A history is not append-only or lacks a hash")
        expected = canonical_sha256({k: v for k, v in gate.items() if k != "artifact_hash"})
        if gate["artifact_hash"] != expected:
            raise ValueError("Gate A history was altered")
    missing = [name for name in BLOCK_B_HASHED_FIELDS if name not in bundle.artifact_hashes]
    if missing:
        raise ValueError(f"BlockBInputBundle artifact hashes are incomplete: {missing}")
    changed = [
        name
        for name in BLOCK_B_HASHED_FIELDS
        if bundle.artifact_hashes[name] != canonical_sha256(getattr(bundle, name))
    ]
    if changed:
        raise ValueError(f"BlockBInputBundle upstream artifacts were altered: {changed}")
    if not bundle.provenance.get("producer") or not bundle.artifact_references:
        raise ValueError("BlockBInputBundle is missing provenance")
    return bundle
