from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from .certification_policy import FINAL_DELIVERY_READY

if TYPE_CHECKING:
    from .policy_pi import PolicyPi

CLAIM_RE = re.compile(r"CLM-[A-Z]+-[0-9]{5}")


def final_delivery_allowed(status: str, blockers: list[str], policy: "PolicyPi | None" = None) -> bool:
    """Backward-compatible status/blocker gate used by unit tests and simple callers."""
    ready_statuses = policy.final_delivery_ready_statuses if policy else FINAL_DELIVERY_READY
    return status in ready_statuses and not blockers


def referenced_claim_ids(text: str, pattern: str | None = None) -> set[str]:
    claim_re = re.compile(pattern) if pattern else CLAIM_RE
    return set(claim_re.findall(text or ""))


def validate_final_delivery_claims(
    example_dir: Path,
    pce_rows: list[dict[str, str]],
    claim_rows: list[dict[str, str]],
    policy: "PolicyPi | None" = None,
) -> dict:
    """Validate material claim references in delivery files against claim map + PCE audit.

    Delivery documents may include narrative content that is not claim-level certified.
    Any explicit CLM-* material claim reference must exist in both claim_to_evidence_map
    and PCE audit, and its external-final status must be allowed.
    """
    delivery_dir = example_dir / "delivery"
    delivery_files = [delivery_dir / name.removeprefix("delivery/") for name in policy.required_delivery_files] if policy else [
        delivery_dir / "tuntun_hk_case_study.md",
        delivery_dir / "top_candidate_dd_review_pack.md",
    ]
    claim_map_ids = {r.get("claim_id", "") for r in claim_rows if r.get("claim_id")}
    pce_by_claim = {r.get("claim_id", ""): r for r in pce_rows if r.get("claim_id")}
    allowed_statuses = policy.allowed_external_statuses if policy else {"Certified", "Certified with Caveat"}
    blocked_statuses = policy.blocked_statuses if policy else {"Internal Trace Only", "Needs Human Review", "Not Certified"}

    referenced: set[str] = set()
    missing_files: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    for path in delivery_files:
        if not path.exists():
            missing_files.append(str(path.relative_to(example_dir)))
            continue
        ids = referenced_claim_ids(
            path.read_text(encoding="utf-8", errors="ignore"),
            policy.material_claim_reference_pattern if policy else None,
        )
        referenced.update(ids)

    if missing_files:
        blockers.append("missing delivery files: " + ", ".join(missing_files))

    missing_from_claim_map = sorted(x for x in referenced if x not in claim_map_ids)
    missing_from_pce = sorted(x for x in referenced if x not in pce_by_claim)
    if missing_from_claim_map:
        blockers.append("delivery references claims absent from claim_to_evidence_map: " + ", ".join(missing_from_claim_map[:20]))
    if missing_from_pce:
        blockers.append("delivery references claims absent from PCE audit: " + ", ".join(missing_from_pce[:20]))

    blocked_refs: list[str] = []
    caveated_refs: list[str] = []
    for claim_id in sorted(referenced):
        row = pce_by_claim.get(claim_id)
        if not row:
            continue
        status = row.get("certification_status", "")
        scope = row.get("delivery_scope", "")
        if scope == "external_final" and status in blocked_statuses:
            blocked_refs.append(f"{claim_id}:{status}")
        elif scope == "external_final" and status not in allowed_statuses:
            blocked_refs.append(f"{claim_id}:{status or 'missing_status'}")
        elif status == "Certified with Caveat":
            caveated_refs.append(claim_id)

    if blocked_refs:
        blockers.append("delivery references claims not allowed for external delivery: " + ", ".join(blocked_refs[:30]))
    if caveated_refs:
        warnings.append(f"{len(caveated_refs)} referenced claims are Certified with Caveat")
    if not referenced:
        blockers.append(
            "delivery files contain no explicit CLM-* material claim references; "
            "final delivery cannot be certified until material claims are mapped to claim_to_evidence_map and PCE audit"
        )

    return {
        "referenced_claim_count": len(referenced),
        "referenced_claim_ids": sorted(referenced)[:200],
        "missing_files": missing_files,
        "blockers": blockers,
        "warnings": warnings,
        "allowed": not blockers,
    }
