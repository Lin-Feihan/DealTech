from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .business_contracts import load_reporting_prompts
from .review_models import (
    DeliveryOutcome,
    LifecycleTerminalStatus,
    ReviewItemState,
    ReviewItemVersion,
    TerminalStateRecord,
)
from .storage import to_primitive, write_json


SECTION_TITLES = [
    "Executive Decision Summary",
    "Scope, Mandate and Decision Question",
    "Transaction Context",
    "Buyer Strategic Need",
    "Strategic Rationale",
    "Target Attractiveness",
    "Target Capability & Business Quality",
    "Industry / Competitive Position",
    "Strategic Fit",
    "Standalone Financial Analysis",
    "Synergy Mechanism & Value Creation",
    "Valuation & Purchase Price Discipline",
    "Deal Structure & Financing Impact",
    "Returns Analysis",
    "Due Diligence",
    "Regulatory Risk",
    "Integration Risk",
    "Downside Risk",
    "Gate A Result",
    "Gate B Result",
    "Gate C Result",
    "Decision State",
    "Conditions and Required Actions",
    "Open Gaps and Human Review Items",
    "Evidence Appendix",
    "Calculation Appendix",
    "Iteration, Gap and Re-planning History",
    "PCE, Certification and Delivery Boundary",
]

MODULE_SECTION_MAP = {
    3:"A1", 4:"A2", 5:"A3", 6:"A4", 7:"A5", 8:"A6", 9:"A7",
    10:"B1", 11:"B2", 12:"B3", 13:"B4", 14:"B5",
    15:"C1", 16:"C2", 17:"C3", 18:"C4",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ids(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "None"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _lineage(claim_rows: list[dict[str, Any]], evidence_rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    evidence_ids = sorted({value for row in claim_rows for value in row.get("evidence_ids", [])})
    evidence_by_id = {row["evidence_id"]:row for row in evidence_rows}
    source_ids = sorted({evidence_by_id[value].get("source_id", "") for value in evidence_ids if value in evidence_by_id and evidence_by_id[value].get("source_id")})
    return source_ids, evidence_ids


def _citation(claims, sources, evidence, calculations=None, gates=None, reviews=None) -> str:
    return (
        f"[Claims: {_ids(claims)}; Sources: {_ids(sources)}; Evidence: {_ids(evidence)}; "
        f"Calculations: {_ids(calculations or [])}; Gate Results: {_ids(gates or [])}; "
        f"Human Review: {_ids(reviews or [])}]"
    )


def _pce_rank(status: str) -> int:
    return {"Certified":0,"Certified with Caveat":1,"Needs Human Review":2,"Not Certified":3}.get(status,3)


def _section_record(
    *, section_id: str, title: str, text: str, included: list[str], blocked: list[str],
    sources: list[str], evidence: list[str], calculations: list[str], gates: list[str],
    reviews: list[str], caveats: list[str], pce: str, allowed: bool,
) -> dict[str, Any]:
    return {
        "section_id":section_id, "section_title":title,
        "included_claim_ids":included, "excluded_or_blocked_claim_ids":blocked,
        "source_ids":sources, "evidence_ids":evidence, "calculation_ids":calculations,
        "gate_result_ids":gates, "human_review_ids":reviews, "caveats":caveats,
        "pce_status":pce, "delivery_permission":allowed,
        "generated_text_hash":_hash(text), "stable_content_reference":f"final_acquisition_strategy_report.md#{section_id}",
    }


def _module_section(module: dict[str, Any], claims: list[dict[str, Any]], evidence: list[dict[str, Any]], assumptions: list[dict[str, Any]], unknowns: list[dict[str, Any]], counter: list[dict[str, Any]], calculations: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    module_claims = [row for row in claims if row["claim_id"] in module.get("claim_ids", [])]
    included = [row["claim_id"] for row in module_claims if row.get("delivery_allowed")]
    blocked = [row["claim_id"] for row in module_claims if not row.get("delivery_allowed")]
    source_ids,evidence_ids=_lineage(module_claims,evidence)
    calc_ids=sorted({row["calculation_id"] for row in calculations if row["owning_module"]==module["module_id"]} | set(module.get("calculation_ids",[])))
    module_assumptions=[row for row in assumptions if row["assumption_id"] in module.get("assumptions",[])]
    module_unknowns=[row for row in unknowns if row["unknown_id"] in module.get("unknowns",[])]
    module_counter=[row for row in counter if row["counterevidence_id"] in module.get("counterevidence_ids",[])]
    pce=max((row.get("pce_status","Not Certified") for row in module_claims),key=_pce_rank,default="Not Certified")
    caveats=list(module.get("limitations",[]))+list(module.get("structured_output",{}).get("conditions",[]))
    if blocked: caveats.append("One or more Claims are blocked from verified delivery.")
    lines=[]
    if not module_claims:
        lines += ["**Verified conclusion:** Insufficient verified information", "", f"**Registered upstream/module limitation:** {module['business_conclusion']}"]
    elif blocked:
        lines += ["**Verified conclusion:** Insufficient verified information", "", f"**Blocked Claims:** {_ids(blocked)}", "", f"**Registered but delivery-restricted conclusion:** {module['business_conclusion']}"]
    else:
        lines += [f"**Verified business conclusion:** {module['business_conclusion']}"]
    lines += ["", "**Facts**"] + ([f"- {value}" for value in module.get("facts",[])] or ["- Insufficient verified information"])
    lines += ["", "**Inferences**"] + ([f"- {value}" for value in module.get("inferences",[])] or ["- None registered."])
    lines += ["", "**Assumptions**"] + ([f"- `{row['assumption_id']}` — {row['statement']} (supported={row['supported']})" for row in module_assumptions] or ["- None registered."])
    lines += ["", "**Unknowns**"] + ([f"- `{row['unknown_id']}` — {row['description']} Impact: {row['impact']}" for row in module_unknowns] or ["- None registered."])
    lines += ["", "**Counterevidence**"] + ([f"- `{row['counterevidence_id']}` — {row['description']} Disposition: {row['disposition']}" for row in module_counter] or ["- None registered."])
    lines += ["", "**Caveats and conditions**"] + ([f"- {value}" for value in caveats] or ["- None registered."])
    lines += ["", _citation([row['claim_id'] for row in module_claims],source_ids,evidence_ids,calc_ids)]
    text="\n".join(lines)
    meta={"included":included,"blocked":blocked,"sources":source_ids,"evidence":evidence_ids,"calculations":calc_ids,"gates":[],"reviews":[],"caveats":caveats,"pce":pce,"allowed":not blocked}
    return text,meta


def _block_c_record_text(module_id: str, records: list[dict[str, Any]]) -> str:
    if not records:
        return "\n\n**Registered Block C records**\n\n- None registered."
    lines = ["", "**Registered Block C records**", ""]
    for row in records:
        if module_id == "C1":
            lines.append(f"- `{row['finding_id']}` | workstream={row['workstream']} | severity={row['severity']} | classification={row['classification']} | status={row['status']} | issue={row['issue']}")
        elif module_id == "C2":
            lines.append(f"- `{row['regulatory_risk_id']}` | jurisdiction={row['jurisdiction']} | area={row['regulatory_area']} | severity={row['severity']} | status={row['status']} | legal review={row['legal_adviser_review_required']}")
        elif module_id == "C3":
            lines.append(f"- `{row['risk_id']}` | domain={row['integration_domain']} | severity={row['severity']} | likelihood={row['likelihood']} | status={row['status']} | residual risk={row['residual_risk']}")
        elif module_id == "C4":
            mode = "quantified from registered inputs" if row.get("financial_inputs") else "qualitative with explicit limitation"
            lines.append(f"- `{row['scenario_id']}` | {row['scenario_name']} | probability={row['probability_classification']} | mode={mode} | residual risk={row['residual_risk']}")
        source_ids = row.get("source_ids", [])
        evidence_ids = row.get("evidence_ids", [])
        if source_ids or evidence_ids:
            lines.append(f"  - Lineage: Sources {_ids(source_ids)}; Evidence {_ids(evidence_ids)}")
        for limitation in row.get("limitations", []):
            lines.append(f"  - Limitation: {limitation}")
    return "\n".join(lines)


def _evidence_appendix(sources, evidence, claims, counter) -> str:
    source_by_id={row["source_id"]:row for row in sources}; evidence_by_id={row["evidence_id"]:row for row in evidence}
    lines=["# Evidence Appendix","","Human-supplied management information is labeled as a management representation and is not independent public evidence.","","| Claim | PCE | Evidence | Source | Source classification | Limitations |","|---|---|---|---|---|---|"]
    for claim in claims:
        ids=claim.get("evidence_ids",[]) or [""]
        for evidence_id in ids:
            ev=evidence_by_id.get(evidence_id,{}) ; source=source_by_id.get(ev.get("source_id",""),{})
            lines.append(f"| `{claim['claim_id']}` | {claim.get('pce_status','Not Certified')} | `{evidence_id or 'MISSING'}` | `{ev.get('source_id','MISSING')}` | {source.get('source_type','Missing Source')} | {ev.get('limitations') or source.get('limitations') or 'None registered'} |")
    lines += ["","### Material Counterevidence",""]
    lines += [f"- `{row['counterevidence_id']}` affects {_ids(row['affected_claim_ids'])}: {row['description']} Disposition: {row['disposition']}" for row in counter] or ["- None registered."]
    return "\n".join(lines)+"\n"


def _calculation_appendix(calculations, replays, gaps) -> str:
    replay_by_id={row["calculation_id"]:row for row in replays}; gaps_by_id={row["calculation_id"]:row for row in gaps}
    lines=["# Calculation Appendix","","This appendix displays registered Decimal calculations and independent replay results. It performs no new calculation.","","| Calculation | Type | Formula | Output | Unit | Replay | Linked Claims | Limitations / Gap |","|---|---|---|---:|---|---|---|---|"]
    for row in calculations:
        replay=replay_by_id.get(row["calculation_id"],{}); gap=gaps_by_id.get(row["calculation_id"],{})
        limitation="; ".join(row.get("limitations",[])) or gap.get("description") or "None registered"
        lines.append(f"| `{row['calculation_id']}` | {row['calculation_type']} | `{row['exact_formula']}` | {row.get('output')} | {row['output_unit']} | {replay.get('status',row.get('replay_status'))} | {_ids(row.get('linked_claim_ids',[]))} | {limitation} |")
        lines.append(f"\nInput lineage for `{row['calculation_id']}` — Sources: {_ids(row.get('source_ids',[]))}; Evidence: {_ids(row.get('evidence_ids',[]))}; Assumptions: {_ids(row.get('assumption_ids',[]))}. Reviewer: {row['required_reviewer']}.")
    return "\n".join(lines)+"\n"


def _human_review_pack(case_data, reviews, claims, evidence, counter, assumptions, calculations) -> str:
    claim_by_module={row["business_module"]:row for row in claims}; evidence_by_id={row["evidence_id"]:row for row in evidence}
    lines=["# Human Review Pack","",f"Case: `{case_data['mandate']['case_id']}`",f"Transaction: {case_data['mandate']['transaction_type']} at {case_data['mandate']['process_stage']}","","This pack requests authorized decisions. It does not presume approval."]
    for item in reviews:
        module=item["owning_module"]; claim=claim_by_module.get(module.replace("C2","Regulatory Risk").replace("C3","Integration Risk").replace("C5","Decision State"),{})
        claim_ids=[claim["claim_id"]] if claim else []
        evidence_ids=[value for value in claim.get("evidence_ids",[]) if value in evidence_by_id]
        related_counter=[row for row in counter if set(row["affected_claim_ids"]) & set(claim_ids)]
        related_calcs=[row["calculation_id"] for row in calculations if row["owning_module"]==module]
        lines += ["",f"## {item['review_id']} — {module}","",f"- Exact decision requested: {item['issue']}",f"- Required reviewer role: {item['required_reviewer_role']}",f"- Originating module / Gate: {module} / Decision Gate",f"- Related Claims: {_ids(claim_ids)}",f"- Supporting Evidence: {_ids(evidence_ids)}",f"- Counterevidence: {_ids([row['counterevidence_id'] for row in related_counter])}",f"- Assumptions: {_ids([row['assumption_id'] for row in assumptions if row['owning_module']==module])}",f"- Calculations: {_ids(related_calcs)}",f"- Unresolved Gap: No separate Research Gap object; this conditional Human Review item remains `{item['status']}`.",f"- Decision impact: {item['decision_impact']}","- APPROVE_INFORMATION — register the response, run PCE, evaluate the Gap and rerun affected dependencies; no automatic approval.","- APPROVE_WITH_CONDITIONS — do the same while retaining explicit conditions in the Gate, report and terminal state.","- REJECT_INFORMATION — keep the related issue unresolved and do not improve certification.","- REQUEST_MORE_INFORMATION — keep the item open and the affected decision condition outstanding.","- DO_NOT_PROCEED — only reserved deal authority may move the case to a traceable No-Go state.","- Required conditions: preserve the item as open until an authorized response is validated.","- Response template: `human_review/response_template.json`.","- Expiry/timing: response must be effective when validated."]
    return "\n".join(lines)+"\n"


def verify_final_delivery(*, report_text: str, sections: list[dict[str, Any]], manifest: list[dict[str, Any]], claims: list[dict[str, Any]], sources: list[dict[str, Any]], evidence: list[dict[str, Any]], calculations: list[dict[str, Any]], counterevidence: list[dict[str, Any]], open_gaps: list[dict[str, Any]], human_reviews: list[dict[str, Any]], gates: list[dict[str, Any]], decision: dict[str, Any], pce_result: dict[str, Any]) -> dict[str, Any]:
    source_ids={row["source_id"] for row in sources}; evidence_by_id={row["evidence_id"]:row for row in evidence}
    missing_lineage=[]
    for claim in claims:
        for evidence_id in claim.get("evidence_ids",[]):
            ev=evidence_by_id.get(evidence_id)
            if ev is None or (ev.get("status")=="AVAILABLE" and ev.get("source_id") not in source_ids): missing_lineage.append(claim["claim_id"])
    blocked=[row["claim_id"] for row in claims if not row.get("delivery_allowed")]
    replay_failures=[row["calculation_id"] for row in calculations if row.get("replay_status")!="PASS"]
    counter_missing=[row["counterevidence_id"] for row in counterevidence if row["counterevidence_id"] not in report_text]
    review_missing=[row["review_id"] for row in human_reviews if row["review_id"] not in report_text]
    manifest_ids={row["section_id"] for row in manifest}
    hash_mismatch=[]
    section_by_id={row["section_id"]:row for row in sections}
    for row in manifest:
        if row["section_id"] not in section_by_id or row["generated_text_hash"]!=_hash(section_by_id[row["section_id"]]["text"]): hash_mismatch.append(row["section_id"])
    blocked_verified_sections=[]
    for row in manifest:
        if row.get("excluded_or_blocked_claim_ids"):
            section_text=section_by_id.get(row["section_id"],{}).get("text","")
            if "**Verified business conclusion:**" in section_text:
                blocked_verified_sections.append(row["section_id"])
    checks={
        "claim_evidence_source_lineage_complete":not missing_lineage,
        "source_eligibility_and_admissibility_checked":all(row.get("pce_eligible") and row.get("source_replay_status") in {"completed","complete","replayed","source_replay_completed"} for row in sources),
        "evidence_admissibility_checked":all("llm summary" not in f"{row.get('evidence_type','')} {row.get('extracted_fact','')}".lower() for row in evidence),
        "blocked_claims_not_presented_as_verified":not blocked_verified_sections,
        "calculation_replay_complete":not replay_failures,
        "material_counterevidence_visible":not counter_missing,
        "caveats_visible":"Caveats" in report_text or "caveat" in report_text.lower(),
        "human_review_requirements_visible":not review_missing,
        "open_gaps_visible":all(row.get("gap_id","") in report_text for row in open_gaps),
        "decision_state_consistent":decision["state"] in report_text,
        "gate_results_consistent":all(row["status"] in report_text for row in gates),
        "human_approval_boundary_visible":"not final authorized human approval" in report_text.lower(),
        "manifest_has_all_28_sections":manifest_ids=={f"section-{index:02d}" for index in range(1,29)},
        "manifest_hashes_match":not hash_mismatch,
    }
    blocking=[]
    if missing_lineage: blocking.append({"type":"MISSING_LINEAGE","objects":sorted(set(missing_lineage))})
    if replay_failures: blocking.append({"type":"CALCULATION_REPLAY_FAILURE","objects":replay_failures})
    if counter_missing: blocking.append({"type":"COUNTEREVIDENCE_HIDDEN","objects":counter_missing})
    if blocked_verified_sections: blocking.append({"type":"BLOCKED_CLAIM_PRESENTED_AS_VERIFIED","objects":blocked_verified_sections})
    if review_missing: blocking.append({"type":"HUMAN_REVIEW_NOT_VISIBLE","objects":review_missing})
    if not checks["manifest_has_all_28_sections"] or hash_mismatch: blocking.append({"type":"REPORT_MANIFEST_INCOMPLETE","objects":hash_mismatch})
    if not checks["decision_state_consistent"] or not checks["human_approval_boundary_visible"]: blocking.append({"type":"DECISION_OR_AUTHORITY_WORDING","objects":[]})
    delivery_blocking_reviews=[row["review_id"] for row in human_reviews if row.get("delivery_blocking")]
    caveats=[]
    if pce_result.get("overall_status")!="Certified": caveats.append(f"Final PCE status is {pce_result.get('overall_status')}.")
    if blocked: caveats.append(f"Blocked or restricted Claims remain visible: {', '.join(blocked)}.")
    if human_reviews: caveats.append(f"Open Human Review items remain: {', '.join(row['review_id'] for row in human_reviews)}.")
    if open_gaps: caveats.append("Open Gaps remain visible.")
    if blocking: outcome=DeliveryOutcome.NOT_DELIVERABLE
    elif delivery_blocking_reviews: outcome=DeliveryOutcome.HUMAN_REVIEW_REQUIRED
    elif caveats or counterevidence: outcome=DeliveryOutcome.DELIVERABLE_WITH_CAVEATS
    else: outcome=DeliveryOutcome.DELIVERABLE
    return {
        "verification_id":f"DELIVERY-VERIFY-{decision.get('case_id','CASE')}",
        "case_id":decision.get("case_id"), "delivery_outcome":outcome,
        "checks":checks, "blocking_issues":blocking, "caveats":caveats,
        "blocked_claim_ids":blocked, "calculation_replay_failures":replay_failures,
        "open_gap_ids":[row.get("gap_id") for row in open_gaps],
        "open_human_review_ids":[row["review_id"] for row in human_reviews],
        "business_decision_state":decision["state"],
        "business_gate_pass_does_not_grant_delivery":True,
        "economic_no_go_may_still_be_deliverable":True,
        "certificate_permitted":outcome in {DeliveryOutcome.DELIVERABLE,DeliveryOutcome.DELIVERABLE_WITH_CAVEATS},
        "policy_boundary":"Final delivery verification is separate from Gate C, PCE claim status, economic merit, and final human approval.",
        "legacy_policy_adapter":"Claim/source/evidence and calculation delivery controls use the existing read-only dealtech_certification PCE result supplied by business_certification.",
    }


def generate_reporting_package(*, output_dir: Path, case_data: dict[str, Any], mandate: Any, module_results: list[Any], sources: list[Any], evidence: list[Any], claims: list[Any], assumptions: list[Any], unknowns: list[Any], counterevidence: list[Any], calculations: list[Any], replays: list[Any], calculation_gaps: list[Any], gates: list[Any], decision: Any, certification: dict[str, Any], research_gaps: list[Any] | None = None, gate_histories: dict[str, list[Any]] | None = None, block_c_records: dict[str, list[Any]] | None = None) -> dict[str, Any]:
    prompts=load_reporting_prompts()
    mandate_d=to_primitive(mandate); modules=[to_primitive(row) for row in module_results]; sources_d=to_primitive(sources); evidence_d=to_primitive(evidence); claims_d=to_primitive(claims); assumptions_d=to_primitive(assumptions); unknowns_d=to_primitive(unknowns); counter_d=to_primitive(counterevidence); calcs=to_primitive(calculations); replays_d=to_primitive(replays); calc_gaps=to_primitive(calculation_gaps); research_gaps_d=to_primitive(research_gaps or []); gates_d=to_primitive(gates); gate_histories_d=to_primitive(gate_histories or {}); block_c_records_d=to_primitive(block_c_records or {}); decision_d=to_primitive(decision); reviews=list(case_data.get("human_review_items",[]))
    module_by_id={row["module_id"]:row for row in modules}; sections=[]; manifest=[]
    gate_ids=[row["gate_id"] for row in gates_d]; all_review_ids=[row["review_id"] for row in reviews]
    executive_claim=[row for row in claims_d if row["business_module"]=="Decision State"]; executive_sources,executive_evidence=_lineage(executive_claim,evidence_d)
    executive=(f"**Machine-generated Decision State:** `{decision_d['state']}`\n\n"+"\n".join(f"- {value}" for value in decision_d["rationale"])+"\n\n**Conditions**\n\n"+"\n".join(f"- {value}" for value in decision_d["conditions"])+"\n\n**Walk-away triggers**\n\n"+"\n".join(f"- {value}" for value in decision_d["walk_away_triggers"])+f"\n\n**Authority boundary:** {decision_d['authority_boundary']} This is not final authorized human approval.\n\n"+_citation([row['claim_id'] for row in executive_claim],executive_sources,executive_evidence,[],gate_ids,all_review_ids))
    section_meta={"included":[row["claim_id"] for row in executive_claim if row.get("delivery_allowed")],"blocked":[row["claim_id"] for row in executive_claim if not row.get("delivery_allowed")],"sources":executive_sources,"evidence":executive_evidence,"calculations":[],"gates":gate_ids,"reviews":all_review_ids,"caveats":list(decision_d["conditions"]),"pce":executive_claim[0].get("pce_status","Not Certified") if executive_claim else "Not Certified","allowed":all(row.get("delivery_allowed") for row in executive_claim)}
    sections.append({"section_id":"section-01","title":SECTION_TITLES[0],"text":executive,"meta":section_meta})
    scope=(f"- Mandate ID: `{mandate_d['mandate_id']}`\n- Buyer perspective: {mandate_d['perspective']}\n- Transaction type: {mandate_d['transaction_type']}\n- Process stage: {mandate_d['process_stage']}\n- Decision question: {mandate_d['decision_question']}\n- Maximum equity purchase price: {mandate_d['maximum_equity_purchase_price']} {mandate_d['currency']} {mandate_d['unit']}\n- Minimum ROIC / IRR: {mandate_d['minimum_roic']} / {mandate_d['minimum_irr']}\n- Maximum pro forma leverage: {mandate_d['maximum_pro_forma_leverage']}x\n- Minimum closing liquidity: {mandate_d['minimum_closing_liquidity']} {mandate_d['currency']} {mandate_d['unit']}\n- Authority limit: {mandate_d['authority_limit']}\n\nNo mandate threshold or approval has been invented.")
    sections.append({"section_id":"section-02","title":SECTION_TITLES[1],"text":scope,"meta":{"included":[],"blocked":[],"sources":[],"evidence":[],"calculations":[],"gates":[],"reviews":[],"caveats":[mandate_d["authority_limit"]],"pce":"Not Applicable","allowed":True}})
    for index,module_id in MODULE_SECTION_MAP.items():
        text,meta=_module_section(module_by_id[module_id],claims_d,evidence_d,assumptions_d,unknowns_d,counter_d,calcs)
        if module_id in {"C1","C2","C3","C4"}:
            text += _block_c_record_text(module_id,block_c_records_d.get(module_id,[]))
        related_reviews=[row["review_id"] for row in reviews if row["owning_module"] in {module_id,module_by_id[module_id]["professional_name"]}]
        meta["reviews"]=related_reviews
        sections.append({"section_id":f"section-{index:02d}","title":SECTION_TITLES[index-1],"text":text,"meta":meta})
    for index,gate in zip((19,20,21),gates_d):
        failed=gate.get("failed_criterion_ids",[]); conditions=gate.get("conditions",[])
        history=gate_histories_d.get(gate["gate_id"],[])
        history_text="\n".join(f"- version {row.get('version',position)}: `{row['status']}` | `{row.get('artifact_hash','registered-current-result')}`" for position,row in enumerate(history,1)) or f"- `{gate['status']}` (current registered result)"
        text=f"**Status:** `{gate['status']}`\n\n**Business reason:** {gate['business_reason']}\n\n**Immutable Gate history:**\n{history_text}\n\n**Failed criteria:** {_ids(failed)}\n\n**Conditions:**\n"+("\n".join(f"- {value}" for value in conditions) if conditions else "- None registered.")+"\n\nGate status is a business decision criterion result, not final human approval."
        sections.append({"section_id":f"section-{index:02d}","title":SECTION_TITLES[index-1],"text":text,"meta":{"included":[],"blocked":[],"sources":[],"evidence":[],"calculations":list(gate.get("calculation_replay_statuses",{})),"gates":[gate["gate_id"]],"reviews":list(gate.get("human_review_items",[])),"caveats":conditions,"pce":"Mixed — see claim records","allowed":gate["status"] in {"PASS","CONDITIONAL_PASS"}}})
    c5_text,c5_meta=_module_section(module_by_id["C5"],claims_d,evidence_d,assumptions_d,unknowns_d,counter_d,calcs)
    decision_text=f"**Registered machine Decision State:** `{decision_d['state']}`\n\n{c5_text}\n\nThis state is not final authorized human approval."
    c5_meta["gates"]=["GATE_C"]; c5_meta["reviews"]=all_review_ids
    sections.append({"section_id":"section-22","title":SECTION_TITLES[21],"text":decision_text,"meta":c5_meta})
    condition_text="\n".join(f"- {value}" for value in decision_d["conditions"]) or "- None registered."
    sections.append({"section_id":"section-23","title":SECTION_TITLES[22],"text":condition_text+"\n\nRequired actions retain their registered Human Review and authority owners.","meta":{"included":[],"blocked":[],"sources":[],"evidence":[],"calculations":[],"gates":gate_ids,"reviews":all_review_ids,"caveats":list(decision_d["conditions"]),"pce":"Mixed","allowed":True}})
    review_text="\n".join(f"- `{row['review_id']}` ({row['status']}) — {row['issue']} Required role: {row['required_reviewer_role']}. Impact: {row['decision_impact']}" for row in reviews) or "- No open Human Review items."
    all_open_gaps=[*research_gaps_d,*calc_gaps]
    gap_text="\n".join(f"- `{row['gap_id']}` — {row['description']}" for row in all_open_gaps) or "- No open calculation or research Gap records."
    sections.append({"section_id":"section-24","title":SECTION_TITLES[23],"text":f"**Open Gaps**\n\n{gap_text}\n\n**Open Human Review Items**\n\n{review_text}","meta":{"included":[],"blocked":[],"sources":[],"evidence":[],"calculations":[],"gates":gate_ids,"reviews":all_review_ids,"caveats":[row["decision_impact"] for row in reviews],"pce":certification["pce_result"]["overall_status"],"allowed":True}})
    evidence_appendix=_evidence_appendix(sources_d,evidence_d,claims_d,counter_d); calculation_appendix=_calculation_appendix(calcs,replays_d,calc_gaps); human_pack=_human_review_pack(case_data,reviews,claims_d,evidence_d,counter_d,assumptions_d,calcs)
    sections.append({"section_id":"section-25","title":SECTION_TITLES[24],"text":evidence_appendix.removeprefix("# Evidence Appendix\n\n"),"meta":{"included":[row["claim_id"] for row in claims_d if row.get("delivery_allowed")],"blocked":[row["claim_id"] for row in claims_d if not row.get("delivery_allowed")],"sources":[row["source_id"] for row in sources_d],"evidence":[row["evidence_id"] for row in evidence_d],"calculations":[],"gates":[],"reviews":all_review_ids,"caveats":[],"pce":certification["pce_result"]["overall_status"],"allowed":True}})
    sections.append({"section_id":"section-26","title":SECTION_TITLES[25],"text":calculation_appendix.removeprefix("# Calculation Appendix\n\n"),"meta":{"included":[],"blocked":[],"sources":sorted({value for row in calcs for value in row["source_ids"]}),"evidence":sorted({value for row in calcs for value in row["evidence_ids"]}),"calculations":[row["calculation_id"] for row in calcs],"gates":["GATE_B"],"reviews":[],"caveats":[row["description"] for row in calc_gaps],"pce":"Certified" if not calc_gaps else "Not Certified","allowed":not calc_gaps}})
    iteration_path=output_dir/"09_loop"/"iteration_records.json"; iteration_text=iteration_path.read_text(encoding="utf-8") if iteration_path.exists() else "Insufficient verified information"
    sections.append({"section_id":"section-27","title":SECTION_TITLES[26],"text":f"Registered iteration history:\n\n```json\n{iteration_text.strip()}\n```\n\nNo failed Gate was hidden or rewritten.","meta":{"included":[],"blocked":[],"sources":[],"evidence":[],"calculations":[],"gates":gate_ids,"reviews":all_review_ids,"caveats":[],"pce":"Not Applicable","allowed":True}})
    boundary=(f"- Final claim-level PCE status: `{certification['pce_result']['overall_status']}`\n- PCE controls claim delivery; it does not determine acquisition economics.\n- ER/BRB supplies evidence-row reliability and risk signals; it is not a business Gate.\n- Gate PASS does not grant delivery permission.\n- The machine Decision State `{decision_d['state']}` is not final authorized human approval.\n- Final delivery verification is performed separately against this report and its manifest.\n\nPrompt reference: `FINAL_PCE_DELIVERY_VERIFIER`.")
    sections.append({"section_id":"section-28","title":SECTION_TITLES[27],"text":boundary,"meta":{"included":[],"blocked":[row["claim_id"] for row in claims_d if not row.get("delivery_allowed")],"sources":[],"evidence":[],"calculations":[],"gates":gate_ids,"reviews":all_review_ids,"caveats":["Certification is not economic approval."],"pce":certification["pce_result"]["overall_status"],"allowed":True}})
    sections=sorted(sections,key=lambda row:row["section_id"])
    report_lines=["# Final Acquisition Strategy Report","",f"Case: `{mandate_d['case_id']}`","","> This deterministic buyer-side report uses registered objects only. The Decision State is machine-generated decision support and is not final authorized human approval.",""]
    for section in sections: report_lines += [f"## {int(section['section_id'].split('-')[1])}. {section['title']}","",section["text"],""]
    report_text="\n".join(report_lines).rstrip()+"\n"
    for section in sections:
        meta=section["meta"]
        manifest.append(_section_record(section_id=section["section_id"],title=section["title"],text=section["text"],included=meta["included"],blocked=meta["blocked"],sources=meta["sources"],evidence=meta["evidence"],calculations=meta["calculations"],gates=meta["gates"],reviews=meta["reviews"],caveats=meta["caveats"],pce=meta["pce"],allowed=meta["allowed"]))
    reporting=output_dir/"reporting"; _write_text(reporting/"final_acquisition_strategy_report.md",report_text); _write_text(reporting/"executive_decision_summary.md","# Executive Decision Summary\n\n"+executive); _write_text(reporting/"evidence_appendix.md",evidence_appendix); _write_text(reporting/"calculation_appendix.md",calculation_appendix); _write_text(reporting/"human_review_pack.md",human_pack)
    write_json(reporting/"report_manifest.json",{"schema_version":"milestone-4","case_id":mandate_d["case_id"],"report_prompt_ids":list(prompts),"sections":manifest,"report_sha256":_hash(report_text)})
    write_json(output_dir/"human_review"/"human_review_items.json",reviews); write_json(output_dir/"human_review"/"human_review_responses.json",[]); write_json(output_dir/"human_review"/"response_validation_results.json",[])
    item_history=[ReviewItemVersion(version_id=f"{row['review_id']}-V1",review_item_id=row["review_id"],version=1,case_id=mandate_d["case_id"],state=ReviewItemState.OPEN,originating_gate="Decision Gate",related_claim_ids=[claim["claim_id"] for claim in claims_d if claim["business_module"] in {row["owning_module"],row["owning_module"].replace("C2","Regulatory Risk").replace("C3","Integration Risk").replace("C5","Decision State")}],related_gap_ids=[],supplied_source_ids=[],supplied_evidence_ids=[],affected_modules=[row["owning_module"]],affected_calculations=[],affected_gate_results=["GATE_C"],response_id="",reviewer_decision="",resolution_decision="Open condition retained in final report.",conditions=[row["decision_impact"]],effective_until="",event_at=f"{mandate_d['as_of_date']}T00:00:00Z",supersedes_version_id="") for row in reviews]
    write_json(output_dir/"human_review"/"review_item_history.json",item_history)
    response_template={"response_id":"RESPONSE-ID","review_item_id":"REVIEW-ID","case_id":mandate_d["case_id"],"reviewer_name":"","reviewer_role":"","reviewer_authority_reference":"","decision":"REQUEST_MORE_INFORMATION","direct_answer":"","supplied_information":[],"supplied_document_references":[],"supplied_source_records":[],"supplied_evidence_records":[],"supplied_assumptions":[],"conditions":[],"limitations":[],"submitted_at":"","effective_until":"","signature_or_approval_reference":"","mandate_change":{},"validation_status":"PENDING","validation_errors":[]}
    write_json(output_dir/"human_review"/"response_template.json",response_template)
    terminal_status={"PROCEED":LifecycleTerminalStatus.COMPLETED_PROCEED,"PROCEED_WITH_CONDITIONS":LifecycleTerminalStatus.COMPLETED_PROCEED_WITH_CONDITIONS,"RENEGOTIATE":LifecycleTerminalStatus.COMPLETED_RENEGOTIATE,"PAUSE":LifecycleTerminalStatus.COMPLETED_PAUSE,"NO_GO":LifecycleTerminalStatus.COMPLETED_NO_GO,"HUMAN_REVIEW":LifecycleTerminalStatus.AWAITING_HUMAN_REVIEW}[decision_d["state"]]
    terminal=TerminalStateRecord(terminal_state_id=f"TS-{mandate_d['case_id']}-001",case_id=mandate_d["case_id"],sequence_number=1,status=terminal_status,gate_a_result=f"GATE_A:{gates_d[0]['status']}",gate_b_result=f"GATE_B:{gates_d[1]['status']}",gate_c_result=f"GATE_C:{gates_d[2]['status']}",decision_state=decision_d["state"],final_pce_status=certification["pce_result"]["overall_status"],open_gaps=[row["gap_id"] for row in all_open_gaps],unresolved_claims=[row["claim_id"] for row in claims_d if row["pce_status"] in {"Not Certified","Needs Human Review"}],open_human_review_items=all_review_ids,conditions=list(decision_d["conditions"]),stopping_reason="Gate C completed; final report generated with explicit economic conditions, unresolved risks and Human Review boundaries.",artifact_references=["reporting/final_acquisition_strategy_report.md","reporting/report_manifest.json","reporting/final_delivery_verification.json"],created_at=f"{mandate_d['as_of_date']}T00:00:00Z",supersedes_terminal_state_id="")
    write_json(output_dir/"state"/"terminal_state_history.json",[terminal]); write_json(output_dir/"state"/"final_terminal_state.json",terminal)
    verification=verify_final_delivery(report_text=report_text,sections=sections,manifest=manifest,claims=claims_d,sources=sources_d,evidence=evidence_d,calculations=calcs,counterevidence=counter_d,open_gaps=all_open_gaps,human_reviews=reviews,gates=gates_d,decision=decision_d,pce_result=certification["pce_result"])
    write_json(reporting/"final_delivery_verification.json",verification)
    certificate=None
    if verification["certificate_permitted"]:
        certificate={"certificate_id":f"DELIVERY-CERT-{mandate_d['case_id']}","case_id":mandate_d["case_id"],"delivery_outcome":verification["delivery_outcome"],"report_sha256":_hash(report_text),"manifest_section_count":len(manifest),"pce_status":certification["pce_result"]["overall_status"],"conditions":verification["caveats"],"human_approval_boundary":"Certificate permits delivery of the report within caveats; it is not final transaction approval.","verification_id":verification["verification_id"]}
        write_json(reporting/"final_delivery_certificate.json",certificate)
    return {"prompts":prompts,"sections":sections,"manifest":manifest,"verification":verification,"certificate":certificate,"terminal_state":terminal,"report_path":reporting/"final_acquisition_strategy_report.md"}
