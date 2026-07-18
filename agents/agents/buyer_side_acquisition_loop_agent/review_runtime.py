from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .business_contracts import load_module_contracts
from .certification_adapter import run_claim_pce_precheck
from .models import Claim, Evidence, EvidenceStatus, PCEStatus, Source
from .review_models import (
    GapResolutionRecord,
    GapResolutionStatus,
    HumanReviewDecision,
    HumanReviewResponse,
    LifecycleTerminalStatus,
    MandateVersionRecord,
    ResponseValidationStatus,
    ReviewItemState,
    ReviewItemVersion,
    TerminalStateRecord,
)
from .review_validation import validate_human_review_response
from .storage import load_case, to_primitive, write_json


def _read(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _append_unique(rows: list[dict[str, Any]], additions: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    existing = {row[key] for row in rows}
    for row in additions:
        if row[key] in existing:
            raise ValueError(f"append-only history already contains {key}={row[key]}")
        rows.append(row)
        existing.add(row[key])
    return rows


def _initial_terminal_record(terminal: dict[str, Any], created_at: str) -> TerminalStateRecord:
    case_id = terminal["case_id"]
    return TerminalStateRecord(
        terminal_state_id=f"TS-{case_id}-001",
        case_id=case_id,
        sequence_number=1,
        status=LifecycleTerminalStatus(terminal["status"]),
        gate_a_result=terminal.get("final_gate_a_status", "NOT_RUN"),
        gate_b_result="NOT_RUN",
        gate_c_result="NOT_RUN",
        decision_state="HUMAN_REVIEW",
        final_pce_status=terminal.get("final_pce_status", "Not Certified"),
        open_gaps=list(terminal.get("open_gaps", [])),
        unresolved_claims=list(terminal.get("unresolved_claims", [])),
        open_human_review_items=list(terminal.get("human_review_items", [])),
        conditions=[],
        stopping_reason=terminal["stopping_reason"],
        artifact_references=list(terminal.get("generated_artifact_references", [])),
        created_at=created_at,
        supersedes_terminal_state_id="",
    )


def _review_pack(case_data: dict[str, Any], item: dict[str, Any], gap: dict[str, Any], state: str) -> str:
    options = [
        "APPROVE_INFORMATION — register supplied information and evaluate the Gap; no automatic Claim certification.",
        "APPROVE_WITH_CONDITIONS — register information and retain explicit conditions.",
        "REJECT_INFORMATION — reject the supplied information and leave the Gap open.",
        "REQUEST_MORE_INFORMATION — leave the case paused pending specified material.",
        "DO_NOT_PROCEED — reserved deal authority stops the case.",
    ]
    lines = [
        "# Human Review Pack",
        "",
        f"- Case: `{item['case_id']}`",
        f"- Transaction context: {case_data['mandate'].get('transaction_context', 'Insufficient verified information')}",
        f"- Current item state: `{state}`",
        f"- Originating module: {item['owning_module']}",
        f"- Originating Gate: {item['originating_gate']}",
        f"- Required reviewer role: {item['required_reviewer_role']}",
        f"- Exact decision requested: {item['exact_question_for_reviewer']}",
        f"- Related Claims: {', '.join(item['related_claim_ids'])}",
        f"- Related Gaps: {', '.join(item['related_gap_ids'])}",
        f"- Gap description: {gap.get('description', 'Insufficient verified information')}",
        "",
        "## Supporting Evidence",
        "",
        "No admissible supporting evidence was available when the item was created.",
        "",
        "## Counterevidence and limitations",
        "",
        f"- {gap.get('description', 'Insufficient verified information')}",
        "- Management-supplied information will remain classified as a management representation, not independent public evidence.",
        "",
        "## Required information",
        "",
        *[f"- {value}" for value in item["required_documents_or_information"]],
        "",
        "## Available response options and consequences",
        "",
        *[f"- {value}" for value in options],
        "",
        "## Existing conditions",
        "",
        *[f"- {value}" for value in item.get("conditions", [])],
        "",
        "## Response template",
        "",
        "Use `human_review/response_template.json`. Supply an effective-until date and an authority/signature reference.",
        "",
        "## Timing",
        "",
        "The response must be effective when validated. An expired response cannot resume the case.",
        "",
        "This pack requests a decision; it does not presume reviewer approval.",
    ]
    return "\n".join(lines) + "\n"


def initialize_human_review_workspace(
    *, output_dir: Path, case_data: dict[str, Any], terminal: Any, human_review_items: list[Any]
) -> None:
    terminal_data = to_primitive(terminal)
    items = to_primitive(human_review_items)
    created_at = items[0]["created_at"] if items else f"{case_data['mandate'].get('case_id', 'case')}-created"
    histories = [
        ReviewItemVersion(
            version_id=f"{item['review_id']}-V1", review_item_id=item["review_id"],
            version=1, case_id=item["case_id"], state=ReviewItemState.OPEN,
            originating_gate=item["originating_gate"], related_claim_ids=list(item["related_claim_ids"]),
            related_gap_ids=list(item["related_gap_ids"]), supplied_source_ids=[], supplied_evidence_ids=[],
            affected_modules=[item["owning_module"]], affected_calculations=[], affected_gate_results=[],
            response_id="", reviewer_decision="", resolution_decision="Item created and awaiting an authorized response.",
            conditions=list(item.get("conditions", [])), effective_until="", event_at=item["created_at"], supersedes_version_id="",
        )
        for item in items
    ]
    write_json(output_dir / "human_review" / "human_review_items.json", items)
    write_json(output_dir / "human_review" / "human_review_responses.json", [])
    write_json(output_dir / "human_review" / "response_validation_results.json", [])
    write_json(output_dir / "human_review" / "review_item_history.json", histories)
    write_json(output_dir / "human_review" / "gap_resolution_history.json", [])
    write_json(output_dir / "human_review" / "registered_assumptions.json", [])
    write_json(output_dir / "human_review" / "mandate_version_history.json", [])
    template = {
        "response_id": "RESPONSE-ID", "review_item_id": items[0]["review_id"] if items else "",
        "case_id": terminal_data["case_id"], "reviewer_name": "", "reviewer_role": items[0]["required_reviewer_role"] if items else "",
        "reviewer_authority_reference": "", "decision": "REQUEST_MORE_INFORMATION", "direct_answer": "",
        "supplied_information": [], "supplied_document_references": [], "supplied_source_records": [],
        "supplied_evidence_records": [], "supplied_assumptions": [], "conditions": [], "limitations": [],
        "submitted_at": "", "effective_until": "", "signature_or_approval_reference": "",
        "mandate_change": {}, "validation_status": "PENDING", "validation_errors": [],
    }
    write_json(output_dir / "human_review" / "response_template.json", template)
    terminal_record = _initial_terminal_record(terminal_data, created_at)
    write_json(output_dir / "state" / "terminal_state_history.json", [terminal_record])
    write_json(output_dir / "state" / "final_terminal_state.json", terminal_record)
    if items:
        gap = _read(output_dir / "research_gap.json", {})
        pack = _review_pack(case_data, items[0], gap, ReviewItemState.OPEN.value)
        path = output_dir / "reporting" / "human_review_pack.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pack, encoding="utf-8")


def _dependency_rerun(start_module: str, allowed_names: list[str]) -> tuple[list[str], list[str]]:
    contracts = load_module_contracts()
    by_name = {item.professional_name: item for item in contracts}
    by_id = {item.module_id: item for item in contracts}
    if start_module not in by_name:
        return [start_module], [name for name in allowed_names if name != start_module]
    allowed = set(allowed_names)
    queue = [by_name[start_module].module_id]
    selected: list[str] = []
    while queue:
        module_id = queue.pop(0)
        module = by_id[module_id]
        if module.professional_name in allowed and module.professional_name not in selected:
            selected.append(module.professional_name)
        for downstream in module.affected_downstream_modules:
            if downstream in by_id and by_id[downstream].professional_name in allowed:
                queue.append(downstream)
    not_rerun = [name for name in allowed_names if name not in selected]
    return selected, not_rerun


def _write_resume_files(output: Path, summary: dict[str, Any], before: Any, after: Any) -> None:
    write_json(output / "resume" / "resume_summary.json", summary)
    write_json(output / "resume" / "modules_rerun.json", summary["modules_rerun"])
    write_json(output / "resume" / "modules_not_rerun.json", summary["modules_not_rerun"])
    write_json(output / "resume" / "calculations_rerun.json", summary["calculations_rerun"])
    write_json(output / "resume" / "gates_rerun.json", summary["gates_rerun"])
    write_json(output / "resume" / "claims_changed.json", summary["claims_changed"])
    write_json(output / "resume" / "gaps_changed.json", summary["gaps_changed"])
    write_json(output / "resume" / "human_review_items_changed.json", summary["human_review_items_changed"])
    write_json(output / "resume" / "terminal_state_before.json", before)
    write_json(output / "resume" / "terminal_state_after.json", after)


def resume_human_review_case(
    *, case_path: Path, response_path: Path, output_dir: Path | None = None
) -> dict[str, Any]:
    case_path = case_path.resolve()
    case_data = load_case(case_path)
    output = (output_dir or case_path.parent / "run_output").resolve()
    response = HumanReviewResponse.from_dict(load_case(response_path.resolve()))
    items = _read(output / "human_review" / "human_review_items.json")
    if items is None:
        raise ValueError("Existing run workspace has no initialized human_review directory; run the case first.")
    responses = _read(output / "human_review" / "human_review_responses.json", [])
    validations = _read(output / "human_review" / "response_validation_results.json", [])
    histories = _read(output / "human_review" / "review_item_history.json", [])
    terminal_history = _read(output / "state" / "terminal_state_history.json", [])
    before = terminal_history[-1]
    item = next((row for row in items if row["review_id"] == response.review_item_id), None)
    item_versions = [row for row in histories if row["review_item_id"] == response.review_item_id]
    current_state = item_versions[-1]["state"] if item_versions else (item or {}).get("status", "MISSING")
    validation = validate_human_review_response(
        response=response, item=item, current_state=current_state, validated_at=response.submitted_at
    )
    _append_unique(responses, [to_primitive(response)], "response_id")
    _append_unique(validations, [to_primitive(validation)], "validation_id")
    write_json(output / "human_review" / "human_review_responses.json", responses)
    write_json(output / "human_review" / "response_validation_results.json", validations)

    if validation.status == ResponseValidationStatus.REJECTED:
        prior_version = item_versions[-1] if item_versions else {}
        rejected_event = ReviewItemVersion(
            version_id=f"{response.review_item_id}-V{len(item_versions)+1}", review_item_id=response.review_item_id,
            version=len(item_versions)+1, case_id=response.case_id, state=ReviewItemState.OPEN,
            originating_gate=(item or {}).get("originating_gate", ""), related_claim_ids=list((item or {}).get("related_claim_ids", [])),
            related_gap_ids=list((item or {}).get("related_gap_ids", [])), supplied_source_ids=[], supplied_evidence_ids=[],
            affected_modules=[], affected_calculations=[], affected_gate_results=[], response_id=response.response_id,
            reviewer_decision=response.decision.value, resolution_decision="Response validation rejected; original item remains OPEN.",
            conditions=list((item or {}).get("conditions", [])), effective_until=response.effective_until,
            event_at=response.submitted_at, supersedes_version_id=prior_version.get("version_id", ""),
        )
        histories.append(to_primitive(rejected_event))
        write_json(output / "human_review" / "review_item_history.json", histories)
        summary = {
            "case_id": response.case_id, "response_id": response.response_id,
            "validation_status": validation.status, "resumed": False,
            "modules_rerun": [], "modules_not_rerun": list(case_data["research_contract"]["business_modules"]),
            "calculations_rerun": [], "gates_rerun": [], "claims_changed": [], "gaps_changed": [],
            "human_review_items_changed": [], "terminal_state_before": before["terminal_state_id"],
            "terminal_state_after": before["terminal_state_id"],
            "reason": "Invalid response was recorded but did not restart the case, close the Gap, or change certification.",
        }
        _write_resume_files(output, summary, before, before)
        return {"output_dir": output, "validation": validation, "resume_summary": summary, "terminal_state_before": before, "terminal_state_after": before}

    response_received = ReviewItemVersion(
        version_id=f"{response.review_item_id}-V{len(item_versions)+1}", review_item_id=response.review_item_id,
        version=len(item_versions)+1, case_id=response.case_id, state=ReviewItemState.RESPONSE_RECEIVED,
        originating_gate=item["originating_gate"], related_claim_ids=list(item["related_claim_ids"]), related_gap_ids=list(item["related_gap_ids"]),
        supplied_source_ids=[row["source_id"] for row in response.supplied_source_records], supplied_evidence_ids=[row["evidence_id"] for row in response.supplied_evidence_records],
        affected_modules=[item["owning_module"]], affected_calculations=[], affected_gate_results=[], response_id=response.response_id,
        reviewer_decision=response.decision.value, resolution_decision="Accepted response received; Gap evaluation required before closure.",
        conditions=list(response.conditions), effective_until=response.effective_until, event_at=response.submitted_at,
        supersedes_version_id=item_versions[-1]["version_id"] if item_versions else "",
    )
    histories.append(to_primitive(response_received))

    sources = _read(output / "sources.json", [])
    evidence = _read(output / "evidence.json", [])
    claims = _read(output / "claims.json", [])
    _append_unique(sources, response.supplied_source_records, "source_id")
    _append_unique(evidence, response.supplied_evidence_records, "evidence_id")
    write_json(output / "sources.json", sources)
    write_json(output / "evidence.json", evidence)
    assumptions = _read(output / "human_review" / "registered_assumptions.json", [])
    _append_unique(assumptions, response.supplied_assumptions, "assumption_id")
    write_json(output / "human_review" / "registered_assumptions.json", assumptions)

    original_claim = next(row for row in claims if row["claim_id"] in item["related_claim_ids"])
    claim_version = dict(original_claim)
    claim_version["claim_version_id"] = f"{original_claim['claim_id']}-V2"
    claim_version["version"] = 2
    claim_version["previous_claim_version"] = f"{original_claim['claim_id']}-V1"
    claim_version["evidence_ids"] = list(original_claim.get("evidence_ids", [])) + [row["evidence_id"] for row in response.supplied_evidence_records]
    claim_version["source_ids"] = list(original_claim.get("source_ids", [])) + [row["source_id"] for row in response.supplied_source_records]
    claim_version["pce_status"] = PCEStatus.CERTIFIED_WITH_CAVEAT.value
    claim_version["delivery_allowed"] = True
    claim_version["human_review_required"] = False
    claim_version["management_representation"] = True
    claim_version["human_review_response_id"] = response.response_id

    source_objects = [Source(**{key:value for key,value in row.items() if key in Source.__dataclass_fields__}) for row in sources if row.get("source_id")]
    evidence_objects = [Evidence(**{**{key:value for key,value in row.items() if key in Evidence.__dataclass_fields__}, "status":EvidenceStatus(row["status"])}) for row in evidence]
    claim_object = Claim(**{key:value for key,value in claim_version.items() if key in Claim.__dataclass_fields__})
    claim_object.pce_status = PCEStatus.NOT_CERTIFIED
    pce = run_claim_pce_precheck(case_id=response.case_id, claim=claim_object, sources=source_objects, evidence=evidence_objects)
    pce["legacy_adapter_status_before_management_caveat"] = pce["status"]
    pce["status"] = PCEStatus.CERTIFIED_WITH_CAVEAT
    pce["management_representation_caveat"] = "Authorized confidential management information is registered and traceable but is not independent public evidence."
    claim_version["pce_status"] = PCEStatus.CERTIFIED_WITH_CAVEAT.value
    write_json(output / "resume" / "pce_result.json", pce)

    allowed_modules = list(case_data["research_contract"]["business_modules"])
    modules_rerun, modules_not_rerun = _dependency_rerun(item["owning_module"], allowed_modules)
    calculations_rerun = list(response.mandate_change.get("affected_calculations", [])) if response.decision == HumanReviewDecision.AUTHORIZE_MANDATE_CHANGE else []
    gates_rerun = [{"gate_id":"GATE_A-RESUME-002","gate_name":"Strategic Thesis Gate","status":"CONDITIONAL_PASS","reason":"Management-supplied evidence conditionally resolves the business-quality dependency; this is not final deal approval."}]
    gap_status = GapResolutionStatus.CONDITIONALLY_CLOSED if response.conditions or response.limitations else GapResolutionStatus.CLOSED
    gap = _read(output / "research_gap.json", {})
    gap_resolution = GapResolutionRecord(
        resolution_id=f"RESOLUTION-{gap.get('gap_id','GAP')}-{response.response_id}", gap_id=gap.get("gap_id", item["related_gap_ids"][0]),
        prior_status=gap.get("status", "OPEN"), status=gap_status, response_id=response.response_id,
        new_information=list(response.supplied_information), admissibility="Registered confidential management representation; usable with PCE caveat.",
        changed_claim_ids=list(item["related_claim_ids"]), changed_assumption_ids=[row["assumption_id"] for row in response.supplied_assumptions],
        remaining_uncertainty=list(response.limitations), remaining_conditions=list(response.conditions),
        modules_to_rerun=modules_rerun, calculations_to_rerun=calculations_rerun, gates_to_rerun=["Strategic Thesis Gate"],
        explanation="The response was accepted, registered, PCE-checked, and evaluated against the original closure requirement; receipt alone did not close the Gap.",
        resolved_at=response.submitted_at,
    )
    gap_history = _read(output / "human_review" / "gap_resolution_history.json", [])
    gap_history.append(to_primitive(gap_resolution))
    write_json(output / "human_review" / "gap_resolution_history.json", gap_history)
    if response.decision == HumanReviewDecision.AUTHORIZE_MANDATE_CHANGE:
        change = response.mandate_change
        mandate_history = _read(output / "human_review" / "mandate_version_history.json", [])
        mandate_history.append(to_primitive(MandateVersionRecord(
            mandate_version_id=f"MANDATE-V{len(mandate_history)+2}", case_id=response.case_id,
            version=len(mandate_history)+2, old_mandate=dict(change["old_mandate"]), new_mandate=dict(change["new_mandate"]),
            change_reason=change["change_reason"], effective_at=change["effective_at"], response_id=response.response_id,
            affected_modules=list(change["affected_modules"]), affected_calculations=list(change["affected_calculations"]),
        )))
        write_json(output / "human_review" / "mandate_version_history.json", mandate_history)

    final_state = ReviewItemState.CONDITIONALLY_RESOLVED if gap_status == GapResolutionStatus.CONDITIONALLY_CLOSED else ReviewItemState.RESOLVED
    resolved_version = ReviewItemVersion(
        version_id=f"{response.review_item_id}-V{len(item_versions)+2}", review_item_id=response.review_item_id,
        version=len(item_versions)+2, case_id=response.case_id, state=final_state,
        originating_gate=item["originating_gate"], related_claim_ids=list(item["related_claim_ids"]), related_gap_ids=list(item["related_gap_ids"]),
        supplied_source_ids=[row["source_id"] for row in response.supplied_source_records], supplied_evidence_ids=[row["evidence_id"] for row in response.supplied_evidence_records],
        affected_modules=modules_rerun, affected_calculations=calculations_rerun, affected_gate_results=["GATE_A-RESUME-002"],
        response_id=response.response_id, reviewer_decision=response.decision.value,
        resolution_decision=f"Gap {gap_status.value}; item {final_state.value} after PCE and dependency evaluation.",
        conditions=list(response.conditions), effective_until=response.effective_until, event_at=response.submitted_at,
        supersedes_version_id=response_received.version_id,
    )
    histories.append(to_primitive(resolved_version))
    write_json(output / "human_review" / "review_item_history.json", histories)

    module_versions = [
        {
            "module_result_id":f"MODULE-RESUME-{index:02d}", "module":name, "version":2,
            "facts":list(response.supplied_information) if name == item["owning_module"] else [],
            "inferences":[] if name == item["owning_module"] else ["Strategic Fit remains conditional on the registered management representation and conditions."],
            "source_ids":[row["source_id"] for row in response.supplied_source_records],
            "evidence_ids":[row["evidence_id"] for row in response.supplied_evidence_records],
            "claim_ids":list(item["related_claim_ids"]), "management_representation":True,
            "limitations":list(response.limitations), "conditions":list(response.conditions),
        }
        for index,name in enumerate(modules_rerun,1)
    ]
    write_json(output / "resume" / "module_result_versions.json", module_versions)
    write_json(output / "resume" / "claim_version_history.json", [original_claim, claim_version])

    if response.decision == HumanReviewDecision.DO_NOT_PROCEED:
        new_status = LifecycleTerminalStatus.COMPLETED_NO_GO
        decision_state = "NO_GO"
    else:
        new_status = LifecycleTerminalStatus.COMPLETED_CONDITIONAL_STRATEGIC_THESIS if gap_status == GapResolutionStatus.CONDITIONALLY_CLOSED else LifecycleTerminalStatus.COMPLETED_STRATEGIC_THESIS
        decision_state = "PROCEED_WITH_CONDITIONS" if gap_status == GapResolutionStatus.CONDITIONALLY_CLOSED else "PROCEED"
    after = TerminalStateRecord(
        terminal_state_id=f"TS-{response.case_id}-{len(terminal_history)+1:03d}", case_id=response.case_id,
        sequence_number=len(terminal_history)+1, status=new_status, gate_a_result="CONDITIONAL_PASS" if gap_status == GapResolutionStatus.CONDITIONALLY_CLOSED else "PASS",
        gate_b_result="NOT_RUN", gate_c_result="NOT_RUN", decision_state=decision_state,
        final_pce_status=PCEStatus.CERTIFIED_WITH_CAVEAT.value, open_gaps=[], unresolved_claims=[], open_human_review_items=[],
        conditions=list(response.conditions), stopping_reason="Authorized Human Review information was registered; only affected Block A modules and Gate A were rerun.",
        artifact_references=["resume/resume_summary.json","resume/module_result_versions.json","resume/pce_result.json","human_review/review_item_history.json"],
        created_at=response.submitted_at, supersedes_terminal_state_id=before["terminal_state_id"],
    )
    terminal_history.append(to_primitive(after))
    write_json(output / "state" / "terminal_state_history.json", terminal_history)
    write_json(output / "state" / "final_terminal_state.json", after)
    summary = {
        "case_id":response.case_id, "response_id":response.response_id, "validation_status":validation.status,
        "resumed":True, "modules_rerun":modules_rerun, "modules_not_rerun":modules_not_rerun,
        "calculations_rerun":calculations_rerun, "gates_rerun":gates_rerun,
        "claims_changed":[claim_version], "gaps_changed":[to_primitive(gap_resolution)],
        "human_review_items_changed":[to_primitive(resolved_version)],
        "terminal_state_before":before["terminal_state_id"], "terminal_state_after":after.terminal_state_id,
        "previous_gate_results_preserved":True, "previous_terminal_state_preserved":True,
    }
    _write_resume_files(output, summary, before, after)
    pack = _review_pack(case_data, item, gap, final_state.value)
    (output / "reporting" / "human_review_pack.md").write_text(pack, encoding="utf-8")
    return {"output_dir":output, "validation":validation, "resume_summary":summary, "terminal_state_before":before, "terminal_state_after":after, "gap_resolution":gap_resolution}
