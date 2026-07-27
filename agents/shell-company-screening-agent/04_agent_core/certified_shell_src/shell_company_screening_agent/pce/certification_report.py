from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .audit_rules import normalize_legacy_status
from .calculation_check import calculation_ok
from .final_delivery_gate import final_delivery_allowed, validate_final_delivery_claims
from .policy_pi import PolicyPi

REQUIRED_TRACE = [
    "candidate_universe_table.csv",
    "hard_filter_table.csv",
    "exclusion_reason_table.csv",
    "dd_evidence_table.csv",
    "er_brb_scoring_table.csv",
    "risk_matrix.csv",
    "financial_calculation_sheet.csv",
    "claim_to_evidence_map.csv",
    "human_review_checklist.csv",
    "workflow_pce_er_brb_map.csv",
]

PCE_FIELDS = [
    "trace_id",
    "case_name",
    "stage",
    "company_name",
    "action_taken",
    "claim_id",
    "claim_text",
    "source_id",
    "source_type",
    "source_link_or_file",
    "evidence_status",
    "calculation_required",
    "calculation_replayed",
    "risk_flag",
    "uncertainty_label",
    "human_review_required",
    "delivery_scope",
    "certification_status",
    "reviewer_note",
]

BLOCKING = {"Needs Human Review", "Not Certified"}
CAVEAT = "Certified with Caveat"
CERTIFIED = "Certified"
INTERNAL = "Internal Trace Only"
NEEDS_REVIEW = "Needs Human Review"
NOT_CERTIFIED = "Not Certified"


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def yes(value: str | None) -> bool:
    return (value or "").strip().lower() in {"yes", "true", "1", "y"}


def norm_code(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if "." in v:
        return v.upper()
    if v.isdigit():
        return v.zfill(5) + ".HK"
    return v.upper()


def is_metadata_only(row: dict[str, str]) -> bool:
    text = " ".join([row.get("notes", ""), row.get("field_name", ""), row.get("field_value", "")]).lower()
    markers = [
        "metadata-level evidence only",
        "title-level signal",
        "document review still required",
        "underlying pdfs/html not parsed yet",
        "not parsed yet",
    ]
    return any(m in text for m in markers)


def load_trace(example_dir: Path, required_trace: list[str] | None = None) -> dict:
    trace = example_dir / "trace"
    tables: dict[str, list[dict[str, str]]] = {}
    fields: dict[str, list[str]] = {}
    for name in required_trace or REQUIRED_TRACE:
        rows, flds = read_csv(trace / name)
        tables[name] = rows
        fields[name] = flds
    pce_rows, pce_fields = read_csv(example_dir / "pce_audit" / "pce_audit_current_run.csv")
    tables["pce_audit_current_run.csv"] = pce_rows
    fields["pce_audit_current_run.csv"] = pce_fields
    return {"tables": tables, "fields": fields}


def build_indexes(tables: dict[str, list[dict[str, str]]]) -> dict:
    dd_by_evidence = {r.get("evidence_id", ""): r for r in tables["dd_evidence_table.csv"] if r.get("evidence_id")}
    calc_by_id = {r.get("calc_id", ""): r for r in tables["financial_calculation_sheet.csv"] if r.get("calc_id")}
    risk_by_id = {r.get("risk_id", ""): r for r in tables["risk_matrix.csv"] if r.get("risk_id")}
    er_by_claim: dict[str, list[dict[str, str]]] = {}
    for r in tables["er_brb_scoring_table.csv"]:
        if r.get("linked_claim_id"):
            er_by_claim.setdefault(r["linked_claim_id"], []).append(r)
    hf_by_code: dict[str, list[dict[str, str]]] = {}
    for r in tables["hard_filter_table.csv"]:
        hf_by_code.setdefault(norm_code(r.get("stock_code")), []).append(r)
    risk_by_code: dict[str, list[dict[str, str]]] = {}
    for r in tables["risk_matrix.csv"]:
        risk_by_code.setdefault(norm_code(r.get("stock_code")), []).append(r)
    return {
        "dd_by_evidence": dd_by_evidence,
        "calc_by_id": calc_by_id,
        "risk_by_id": risk_by_id,
        "er_by_claim": er_by_claim,
        "hf_by_code": hf_by_code,
        "risk_by_code": risk_by_code,
    }


def derive_claim_status(claim: dict[str, str], idx: dict) -> tuple[str, list[str], str, str]:
    reasons: list[str] = []
    status = normalize_legacy_status(claim.get("certification_status", "")) or CERTIFIED
    delivery_scope = claim.get("delivery_scope") or "internal_trace"

    if delivery_scope != "external_final" and status == CERTIFIED:
        status = INTERNAL

    if not claim.get("source_id") and not claim.get("evidence_id") and not claim.get("calc_id") and not claim.get("risk_id"):
        return NOT_CERTIFIED, ["claim has no linked source/evidence/calculation/risk"], "missing", "Yes"

    human_review = yes(claim.get("human_review_required"))
    evidence_status = "sufficient"

    evidence_id = claim.get("evidence_id", "")
    if evidence_id:
        ev = idx["dd_by_evidence"].get(evidence_id)
        if not ev:
            reasons.append(f"evidence_id {evidence_id} missing from dd_evidence_table")
            evidence_status = "missing"
            status = NOT_CERTIFIED
        else:
            verification = (ev.get("verification_status") or "").strip().lower()
            notes_meta = is_metadata_only(ev)
            evidence_status = verification or "unknown"
            if verification in {"needs_review", "unresolved", "metadata_only", "title_only"}:
                reasons.append(f"DD evidence {evidence_id} verification_status={verification}")
                human_review = True
                status = NEEDS_REVIEW if delivery_scope == "external_final" else INTERNAL
            elif notes_meta:
                reasons.append(f"DD evidence {evidence_id} is metadata/title-level or unparsed body evidence")
                human_review = True
                status = NEEDS_REVIEW if delivery_scope == "external_final" else INTERNAL
            elif verification in {"document_derived", "partial_support"} and status == CERTIFIED:
                reasons.append(f"DD evidence {evidence_id} is {verification}; caveat retained")
                status = CAVEAT

    calc_id = claim.get("calc_id", "")
    if yes(claim.get("calculation_required")) or calc_id:
        calc = idx["calc_by_id"].get(calc_id)
        if not calc:
            reasons.append(f"calculation {calc_id or '[missing calc_id]'} missing from financial_calculation_sheet")
            human_review = True
            status = NEEDS_REVIEW
        elif not calculation_ok(calc):
            reasons.append(f"calculation {calc_id} not replayed")
            human_review = True
            status = NEEDS_REVIEW

    risk_id = claim.get("risk_id", "")
    if risk_id:
        risk = idx["risk_by_id"].get(risk_id)
        if risk:
            if yes(risk.get("human_review_required")):
                reasons.append(f"risk {risk_id} requires human review")
                human_review = True
                status = NEEDS_REVIEW if delivery_scope == "external_final" else INTERNAL
            if (risk.get("severity") or "").lower() == "high":
                reasons.append(f"risk {risk_id} is high severity")
                status = NEEDS_REVIEW if delivery_scope == "external_final" else CAVEAT
        else:
            reasons.append(f"risk_id {risk_id} missing from risk_matrix")
            status = CAVEAT if delivery_scope == "external_final" else INTERNAL

    for er in idx["er_by_claim"].get(claim.get("claim_id", ""), []):
        if yes(er.get("human_review_required")):
            reasons.append(f"ER/BRB {er.get('er_brb_id')} requires human review")
            human_review = True
            status = NEEDS_REVIEW if delivery_scope == "external_final" else INTERNAL
        if (er.get("uncertainty_label") or "").lower() not in {"", "none"} and status == CERTIFIED:
            reasons.append(f"ER/BRB uncertainty={er.get('uncertainty_label')}")
            status = CAVEAT

    code = norm_code(claim.get("stock_code") or "")
    if code:
        for hf in idx["hf_by_code"].get(code, []):
            if yes(hf.get("human_review_required")) and claim.get("stage") in {"hard_filter", "filtered_candidate_set"}:
                reasons.append(f"hard filter {hf.get('filter_record_id')} requires human review")
                human_review = True
                status = NEEDS_REVIEW if delivery_scope == "external_final" else INTERNAL
        for risk in idx["risk_by_code"].get(code, []):
            if yes(risk.get("human_review_required")) and claim.get("stage") in {"risk", "dd_evidence", "recommendation"}:
                reasons.append(f"risk row {risk.get('risk_id')} requires human review")
                human_review = True
                status = NEEDS_REVIEW if delivery_scope == "external_final" else INTERNAL

    uncertainty = claim.get("uncertainty_label") or "none"
    if uncertainty.lower() not in {"", "none"} and status == CERTIFIED:
        status = CAVEAT
        reasons.append(f"claim uncertainty={uncertainty}")

    if human_review and delivery_scope == "external_final" and status not in {NOT_CERTIFIED, NEEDS_REVIEW}:
        status = NEEDS_REVIEW
        reasons.append("human review propagated to external_final claim")

    return status, sorted(set(reasons)), evidence_status, "Yes" if human_review else "No"


def build_pce_rows_from_claims(example_dir: Path, tables: dict[str, list[dict[str, str]]], idx: dict) -> tuple[list[dict[str, str]], dict]:
    claim_rows = tables["claim_to_evidence_map.csv"]
    existing_by_claim = {r.get("claim_id", ""): r for r in tables["pce_audit_current_run.csv"] if r.get("claim_id")}
    rows: list[dict[str, str]] = []
    transition_counts = Counter()
    reason_counts = Counter()

    for claim in claim_rows:
        claim_id = claim.get("claim_id", "")
        old = existing_by_claim.get(claim_id, {})
        status, reasons, evidence_status, human_review = derive_claim_status(claim, idx)
        old_status = old.get("certification_status") or claim.get("certification_status") or ""
        transition_counts[f"{old_status or 'missing'} -> {status}"] += 1
        for reason in reasons:
            reason_counts[reason.split(";", 1)[0]] += 1
        ev = idx["dd_by_evidence"].get(claim.get("evidence_id", ""), {})
        risk = idx["risk_by_id"].get(claim.get("risk_id", ""), {})
        row = {
            "trace_id": old.get("trace_id") or "TRACE-TUNTUN-001",
            "case_name": old.get("case_name") or "吨吨健康科技集团港股上市公司重组标的筛选",
            "stage": claim.get("stage") or old.get("stage") or "unknown",
            "company_name": claim.get("company_name") or old.get("company_name") or ev.get("company_name", ""),
            "action_taken": "trace_cross_check_certification",
            "claim_id": claim_id,
            "claim_text": claim.get("claim_text") or old.get("claim_text", ""),
            "source_id": claim.get("source_id") or old.get("source_id") or ev.get("source_id", ""),
            "source_type": old.get("source_type") or ev.get("support_level") or "trace",
            "source_link_or_file": ev.get("source_link_or_file") or old.get("source_link_or_file") or claim.get("evidence_id") or claim.get("calc_id") or claim.get("risk_id"),
            "evidence_status": evidence_status,
            "calculation_required": claim.get("calculation_required", "No"),
            "calculation_replayed": claim.get("calculation_replayed", "No"),
            "risk_flag": risk.get("risk_flag") or old.get("risk_flag") or "none",
            "uncertainty_label": claim.get("uncertainty_label") or old.get("uncertainty_label") or "none",
            "human_review_required": human_review,
            "delivery_scope": claim.get("delivery_scope") or old.get("delivery_scope") or "internal_trace",
            "certification_status": status,
            "reviewer_note": "; ".join(reasons) if reasons else "Cross-checked against upstream trace tables by PCE.",
        }
        rows.append(row)

    stats = {
        "transition_counts": dict(transition_counts),
        "top_reason_counts": dict(reason_counts.most_common(25)),
    }
    return rows, stats


def build_upstream_obligation_rows(tables: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    """Create PCE rows for upstream trace obligations not represented as final claims.

    The claim map is the final claim ledger, but upstream tables can still carry
    obligations: hard-filter rows requiring review, ER/BRB evidence gaps, DD
    evidence that is title/metadata-only, and risk rows with unresolved flags.
    These rows must remain visible to PCE rather than being silently washed out.
    """
    rows: list[dict[str, str]] = []

    def base_row(
        stage: str,
        trace_key: str,
        company: str,
        text: str,
        source_id: str,
        status: str,
        human_review: str,
        note: str,
    ) -> dict[str, str]:
        return {
            "trace_id": "TRACE-TUNTUN-001",
            "case_name": "吨吨健康科技集团港股上市公司重组标的筛选",
            "stage": stage,
            "company_name": company,
            "action_taken": "upstream_trace_obligation_check",
            "claim_id": trace_key,
            "claim_text": text,
            "source_id": source_id,
            "source_type": "upstream_trace",
            "source_link_or_file": trace_key,
            "evidence_status": "upstream_obligation",
            "calculation_required": "No",
            "calculation_replayed": "No",
            "risk_flag": "review_obligation" if human_review == "Yes" else "none",
            "uncertainty_label": "upstream_human_review_required" if human_review == "Yes" else "none",
            "human_review_required": human_review,
            "delivery_scope": "internal_trace",
            "certification_status": status,
            "reviewer_note": note,
        }

    for row in tables["hard_filter_table.csv"]:
        if yes(row.get("human_review_required")):
            rows.append(
                base_row(
                    "hard_filter",
                    "TRACE-HF-" + (row.get("filter_record_id") or "UNKNOWN"),
                    row.get("company_name", ""),
                    f"Hard filter row {row.get('filter_record_id')} for {row.get('stock_code')} requires human review: {row.get('rationale', '')}",
                    row.get("source_id", ""),
                    NEEDS_REVIEW,
                    "Yes",
                    "Upstream hard_filter_table.human_review_required=Yes propagated to PCE obligation row.",
                )
            )

    for row in tables["er_brb_scoring_table.csv"]:
        if yes(row.get("human_review_required")) or row.get("evidence_gap_note"):
            human = "Yes" if yes(row.get("human_review_required")) else "No"
            status = NEEDS_REVIEW if human == "Yes" else INTERNAL
            rows.append(
                base_row(
                    "er_brb_" + (row.get("stage") or "unknown"),
                    "TRACE-ERBRB-" + (row.get("er_brb_id") or "UNKNOWN"),
                    row.get("company_name", ""),
                    f"ER/BRB row {row.get('er_brb_id')} decision={row.get('decision_output')} evidence_gap={row.get('evidence_gap_note', '')}",
                    row.get("source_id", ""),
                    status,
                    human,
                    "Upstream ER/BRB evidence gap or human-review flag retained in PCE.",
                )
            )

    for row in tables["dd_evidence_table.csv"]:
        verification = (row.get("verification_status") or "").lower()
        if verification in {"needs_review", "unresolved", "metadata_only", "title_only"} or is_metadata_only(row):
            rows.append(
                base_row(
                    "dd_evidence",
                    "TRACE-DD-" + (row.get("evidence_id") or "UNKNOWN"),
                    row.get("company_name", ""),
                    f"DD evidence {row.get('evidence_id')} is not final-certifiable: verification_status={row.get('verification_status')} notes={row.get('notes', '')}",
                    row.get("source_id", ""),
                    NEEDS_REVIEW,
                    "Yes",
                    "Metadata/title-level or needs_review DD evidence cannot support external final certification without document/body review.",
                )
            )

    for row in tables["risk_matrix.csv"]:
        risk_flag = (row.get("risk_flag") or "").lower()
        if yes(row.get("human_review_required")) or risk_flag in {"unknown", "unresolved", "needs_review"}:
            human = "Yes" if yes(row.get("human_review_required")) else "No"
            status = NEEDS_REVIEW if human == "Yes" else INTERNAL
            rows.append(
                base_row(
                    "risk_matrix",
                    "TRACE-RISK-" + (row.get("risk_id") or "UNKNOWN"),
                    row.get("company_name", ""),
                    f"Risk row {row.get('risk_id')} flag={row.get('risk_flag')} severity={row.get('severity')}: {row.get('risk_description', '')}",
                    row.get("source_id", ""),
                    status,
                    human,
                    "Risk row retained as upstream PCE obligation; unknown risks remain internal trace unless promoted to final claim.",
                )
            )

    return rows


def update_claim_map_status(example_dir: Path, pce_rows: list[dict[str, str]]) -> None:
    claim_path = example_dir / "trace" / "claim_to_evidence_map.csv"
    rows, fields = read_csv(claim_path)
    by_claim = {r.get("claim_id", ""): r for r in pce_rows if r.get("claim_id")}
    if "certification_status" not in fields:
        fields.append("certification_status")
    if "human_review_required" not in fields:
        fields.append("human_review_required")
    for row in rows:
        pce = by_claim.get(row.get("claim_id", ""))
        if pce:
            row["certification_status"] = pce.get("certification_status", row.get("certification_status", ""))
            row["human_review_required"] = pce.get("human_review_required", row.get("human_review_required", ""))
    write_csv(claim_path, rows, fields)



def certify_example(example_dir: Path, policy: PolicyPi | None = None) -> dict:
    if policy is None:
        from .certifier_agent import PCECertifierAgent

        policy = PCECertifierAgent.for_example(example_dir).policy
    trace = example_dir / "trace"
    pce = example_dir / "pce_audit"
    pce.mkdir(parents=True, exist_ok=True)
    required_trace = policy.required_trace_tables or REQUIRED_TRACE
    loaded = load_trace(example_dir, required_trace)
    tables = loaded["tables"]

    blockers: list[str] = []
    warnings: list[str] = []
    missing_trace = [name for name in required_trace if not (trace / name).exists()]
    if missing_trace:
        blockers.append("missing trace files: " + ", ".join(missing_trace))

    idx = build_indexes(tables)
    pce_rows, pce_stats = build_pce_rows_from_claims(example_dir, tables, idx)
    upstream_rows = build_upstream_obligation_rows(tables)
    pce_rows = pce_rows + upstream_rows
    pce_stats["upstream_obligation_row_count"] = len(upstream_rows)
    write_csv(pce / "pce_audit_current_run.csv", pce_rows, PCE_FIELDS)
    update_claim_map_status(example_dir, pce_rows)

    status_counts = Counter(r.get("certification_status", "") for r in pce_rows)
    scope_status_counts = Counter((r.get("delivery_scope", ""), r.get("certification_status", "")) for r in pce_rows)
    human_review_count = sum(1 for r in pce_rows if yes(r.get("human_review_required")))
    blocking_statuses = policy.blocked_statuses or BLOCKING | {INTERNAL}
    external_blocked = [r for r in pce_rows if r.get("delivery_scope") == "external_final" and r.get("certification_status") in blocking_statuses]
    external_caveated = [r for r in pce_rows if r.get("delivery_scope") == "external_final" and r.get("certification_status") == CAVEAT]

    if external_blocked:
        blockers.append(f"{len(external_blocked)} external_final claims are blocked or require human review")
    if external_caveated:
        warnings.append(f"{len(external_caveated)} external_final claims are Certified with Caveat")
    if human_review_count:
        warnings.append(f"{human_review_count} total PCE rows carry human_review_required=Yes")

    claim_rows, _ = read_csv(trace / "claim_to_evidence_map.csv")
    delivery_gate = validate_final_delivery_claims(example_dir, pce_rows, claim_rows, policy=policy)
    blockers.extend(delivery_gate["blockers"])
    warnings.extend(delivery_gate["warnings"])

    overall = CERTIFIED
    if blockers:
        overall = NEEDS_REVIEW
    elif status_counts.get(CAVEAT, 0) or status_counts.get(INTERNAL, 0) or warnings:
        overall = CAVEAT

    allowed = final_delivery_allowed(overall, blockers, policy=policy) and delivery_gate["allowed"]
    result = {
        "certification_status": overall,
        "final_delivery_allowed": allowed,
        "policy_pi": str(policy.path.relative_to(policy.path.parents[2]) if len(policy.path.parents) > 2 else policy.path),
        "canonical_output_states": policy.canonical_output_states,
        "required_trace_tables": required_trace,
        "status_counts": dict(status_counts),
        "scope_status_counts": {f"{k[0]}::{k[1]}": v for k, v in scope_status_counts.items()},
        "human_review_required_count": human_review_count,
        "external_final_blocked_count": len(external_blocked),
        "external_final_caveated_count": len(external_caveated),
        "certified_claim_count": status_counts.get(CERTIFIED, 0),
        "caveated_claim_count": status_counts.get(CAVEAT, 0),
        "internal_trace_only_count": status_counts.get(INTERNAL, 0),
        "needs_human_review_claim_count": status_counts.get(NEEDS_REVIEW, 0),
        "not_certified_claim_count": status_counts.get(NOT_CERTIFIED, 0),
        "delivery_gate": delivery_gate,
        "pce_cross_check": pce_stats,
        "blockers": sorted(set(blockers))[:100],
        "warnings": sorted(set(warnings))[:100],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (pce / "certification_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    cert = example_dir / "delivery" / "final_delivery_certificate.md"
    cert.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Final Delivery Certificate",
        "",
        f"- **certification_status:** {overall}",
        f"- **final_delivery_allowed:** {allowed}",
        f"- **generated_at:** {result['generated_at']}",
        "- **basis:** PCE cross-checks upstream trace tables: hard filters, ER/BRB, DD evidence, risk matrix, calculations, claim map, and final delivery references.",
        "",
        "## Status Counts",
    ]
    lines.extend(f"- {k}: {v}" for k, v in sorted(status_counts.items()))
    lines.extend(["", "## Delivery Gate"])
    lines.append(f"- Referenced claim count: {delivery_gate['referenced_claim_count']}")
    lines.append(f"- Gate allowed: {delivery_gate['allowed']}")
    lines.extend(["", "## Referenced External-Final Claims"])
    refs = delivery_gate.get("referenced_claim_ids", [])
    if not refs:
        lines.append("- None")
    else:
        pce_by_claim = {r.get("claim_id", ""): r for r in pce_rows if r.get("claim_id")}
        for claim_id in refs[:200]:
            row = pce_by_claim.get(claim_id, {})
            status = row.get("certification_status", "missing")
            scope = row.get("delivery_scope", "missing")
            claim_text = row.get("claim_text", "")
            if len(claim_text) > 220:
                claim_text = claim_text[:217] + "..."
            lines.append(f"- `{claim_id}` — {status} / {scope}: {claim_text}")
    lines.extend(["", "## Blockers"])
    lines.extend(["- None"] if not blockers else [f"- {b}" for b in sorted(set(blockers))[:50]])
    lines.extend(["", "## Warnings / Caveats"])
    lines.extend(["- None"] if not warnings else [f"- {w}" for w in sorted(set(warnings))[:50]])
    lines.extend(["", "This certificate does not provide investment, legal, tax, regulatory or financial advice."])
    cert.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    return result
