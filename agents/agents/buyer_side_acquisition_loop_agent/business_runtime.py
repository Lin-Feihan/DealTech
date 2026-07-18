from __future__ import annotations

from pathlib import Path
from typing import Any

from .business_certification import run_business_certification
from .business_contracts import load_module_contracts, load_prompt_registry, validate_contract_prompt_links
from .business_gates import evaluate_business_gate
from .business_loop import enter_unified_loop
from .business_models import (
    BusinessBlock, BusinessGateStatus, BusinessMandate, BusinessResearchContract,
    BusinessTerminalState, CalculationInput, DecisionState, DecisionStateValue, ResearchRequest,
)
from .calculations import run_calculation
from .models import Claim, PCEStatus
from .research_provider import DeterministicResearchProvider
from .storage import to_primitive, write_json


ADVANCING = {BusinessGateStatus.PASS, BusinessGateStatus.CONDITIONAL_PASS}
BLOCK_MODULES = {
    BusinessBlock.BLOCK_A: [f"A{i}" for i in range(1, 8)],
    BusinessBlock.BLOCK_B: [f"B{i}" for i in range(1, 6)],
    BusinessBlock.BLOCK_C: [f"C{i}" for i in range(1, 6)],
}


def _unique(items: list[Any], field: str) -> list[Any]:
    result: dict[str, Any] = {}
    for item in items:
        key = getattr(item, field)
        if key in result and to_primitive(result[key]) != to_primitive(item):
            raise ValueError(f"conflicting duplicate {field}: {key}")
        result[key] = item
    return list(result.values())


def _research(block, mandate, contract, contracts, provider):
    bundles = []
    for module_id in BLOCK_MODULES[block]:
        module = contracts[module_id]
        request = ResearchRequest(
            request_id=f"REQ-{mandate.case_id}-{module_id}", case_id=mandate.case_id,
            module_id=module_id, module_name=module.professional_name, owning_block=block,
            prompt_reference=module.prompt_reference,
            research_questions=list(module.required_research_questions),
            mandate_id=mandate.mandate_id, contract_id=contract.contract_id,
            provenance_boundary="deterministic fixture only; no LLM or web execution",
        )
        bundles.append(provider.research(request, module))
    return bundles


def _attach_controls(bundles, certification):
    er_by_claim: dict[str, list[dict[str, Any]]] = {}
    for row in certification["er_brb_results"]:
        er_by_claim.setdefault(row["claim_id"], []).append(row)
    for bundle in bundles:
        statuses = [claim.pce_status for claim in bundle.claims]
        if PCEStatus.NOT_CERTIFIED in statuses: aggregate = PCEStatus.NOT_CERTIFIED
        elif PCEStatus.NEEDS_HUMAN_REVIEW in statuses: aggregate = PCEStatus.NEEDS_HUMAN_REVIEW
        elif PCEStatus.CERTIFIED_WITH_CAVEAT in statuses: aggregate = PCEStatus.CERTIFIED_WITH_CAVEAT
        else: aggregate = PCEStatus.CERTIFIED
        bundle.module_result.pce_status = aggregate
        bundle.module_result.er_brb_result = {claim.claim_id: er_by_claim.get(claim.claim_id, []) for claim in bundle.claims}


def _write_block(output, directory, bundles):
    for bundle in bundles:
        write_json(output / directory / f"{bundle.module_result.module_id.lower()}_result.json", bundle.module_result)
    write_json(output / directory / "block_summary.json", [item.module_result for item in bundles])


def _loop_return(output, gate, common):
    event = enter_unified_loop(gate, 1)
    write_json(output / "08_controls" / "unified_loop_events.json", [event])
    write_json(output / "09_loop" / "loop_state.json", {
        "status": "REPLAN_REQUIRED", "current_gate": gate.gate_id,
        "return_block": event["loop_controller"]["return_block"],
        "return_modules": event["loop_controller"]["return_modules"],
    })
    write_json(output / "09_loop" / "terminal_state.json", {
        "status": "NOT_TERMINAL_REPLAN_REQUIRED", "gate_status": gate.status,
        "reason": "Gate failure entered Gap Diagnosis, Memory Update, Loop Controller and targeted Re-plan.",
    })
    summary = {"schema_version":"milestone-3", "status":"REPLAN_REQUIRED", "failed_gate":gate.gate_id, "gate_status":gate.status, "output_directory":str(output)}
    write_json(output / "run_summary.json", summary)
    return {**common, "run_summary":summary, "output_dir":output, "loop_event":event}


def run_end_to_end_case(case_data: dict[str, Any], case_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    mandate = BusinessMandate.from_dict(case_data["mandate"])
    research_contract = BusinessResearchContract(**case_data["research_contract"])
    if mandate.case_id != research_contract.case_id:
        raise ValueError("Mandate and Research Contract case_id must match")
    module_contracts = load_module_contracts()
    prompts = load_prompt_registry()
    validate_contract_prompt_links(module_contracts, prompts)
    if research_contract.module_ids != [item.module_id for item in module_contracts]:
        raise ValueError("Research Contract must contain the ordered 17-module registry")
    output = output_dir or case_path.parent / "run_output"
    output.mkdir(parents=True, exist_ok=True)
    contracts = {item.module_id:item for item in module_contracts}
    provider = DeterministicResearchProvider(
        case_data["module_fixtures"],
        source_registry=case_data.get("source_registry"),
        evidence_registry=case_data.get("evidence_registry"),
        claim_registry=case_data.get("claim_registry"),
    )
    bundles: list[Any] = []; sources: list[Any] = []; evidence: list[Any] = []; claims: list[Claim] = []
    assumptions: list[Any] = []; unknowns: list[Any] = []; counterevidence: list[Any] = []; responses: list[Any] = []; gates: list[Any] = []

    write_json(output/"00_input"/"mandate.json", mandate)
    write_json(output/"00_input"/"research_contract.json", research_contract)
    write_json(output/"00_input"/"business_module_contracts.json", module_contracts)
    write_json(output/"00_input"/"research_plan.json", [{"sequence":i,"module_id":m.module_id,"professional_name":m.professional_name,"block":m.owning_block,"dependencies":m.dependencies} for i,m in enumerate(module_contracts,1)])
    write_json(output/"00_input"/"research_questions.json", [{"question_id":f"RQ-{m.module_id}-{i:02d}","module_id":m.module_id,"question":q} for m in module_contracts for i,q in enumerate(m.required_research_questions,1)])

    def append(new_bundles):
        bundles.extend(new_bundles)
        sources.extend(x for b in new_bundles for x in b.sources); evidence.extend(x for b in new_bundles for x in b.evidence); claims.extend(x for b in new_bundles for x in b.claims)
        assumptions.extend(x for b in new_bundles for x in b.assumptions); unknowns.extend(x for b in new_bundles for x in b.unknowns); counterevidence.extend(x for b in new_bundles for x in b.counterevidence); responses.extend(b.response for b in new_bundles)

    block_a = _research(BusinessBlock.BLOCK_A, mandate, research_contract, contracts, provider); append(block_a)
    sources[:] = _unique(sources,"source_id"); evidence[:] = _unique(evidence,"evidence_id"); claims[:] = _unique(claims,"claim_id")
    certification = run_business_certification(case_id=mandate.case_id,sources=sources,evidence=evidence,claims=claims); _attach_controls(block_a,certification)
    gate_a = evaluate_business_gate(gate_id="GATE_A",module_results=[b.module_result for b in block_a],claims=claims,mandate=mandate); gates.append(gate_a)
    _write_block(output,"02_block_a",block_a); write_json(output/"03_gate_a"/"gate_a_result.json",gate_a)
    common={"mandate":mandate,"research_contract":research_contract,"module_contracts":module_contracts,"prompts":prompts,"gates":gates}
    if gate_a.status not in ADVANCING: return _loop_return(output,gate_a,common)

    block_b = _research(BusinessBlock.BLOCK_B, mandate, research_contract, contracts, provider); append(block_b)
    sources[:] = _unique(sources,"source_id"); evidence[:] = _unique(evidence,"evidence_id"); claims[:] = _unique(claims,"claim_id")
    calculations=[]; replays=[]; calculation_gaps=[]; claim_by_id={c.claim_id:c for c in claims}
    for spec in case_data["calculations"]:
        raw_inputs = spec.get("inputs") or [
            case_data["calculation_input_registry"][name] for name in spec["input_names"]
        ]
        record,replay,gap=run_calculation(
            calculation_id=spec["calculation_id"],calculation_type=spec["calculation_type"],owning_module=spec["owning_module"],scenario=spec["scenario"],
            inputs=[CalculationInput(**x) for x in raw_inputs],output_unit=spec["output_unit"],linked_claim_ids=spec["linked_claim_ids"],required_reviewer=spec["required_reviewer"],unsupported_assumptions=spec.get("unsupported_assumptions",[]))
        calculations.append(record); replays.append(replay)
        if gap: calculation_gaps.append(gap)
        for claim_id in record.linked_claim_ids:
            claim=claim_by_id[claim_id]; claim.calculation_required=True; claim.calculation_ids.append(record.calculation_id)
    for claim in claims:
        related = [record for record in calculations if claim.claim_id in record.linked_claim_ids]
        if related:
            claim.calculation_replayed = all(record.replay_status.value == "PASS" for record in related)
    certification=run_business_certification(case_id=mandate.case_id,sources=sources,evidence=evidence,claims=claims); _attach_controls(bundles,certification)
    gate_b=evaluate_business_gate(gate_id="GATE_B",module_results=[b.module_result for b in block_b],claims=claims,mandate=mandate,calculations=calculations,calculation_gaps=calculation_gaps,prior_gates=[gate_a]); gates.append(gate_b)
    _write_block(output,"04_block_b",block_b); write_json(output/"04_block_b"/"calculations.json",calculations); write_json(output/"04_block_b"/"calculation_replays.json",replays); write_json(output/"04_block_b"/"calculation_gaps.json",calculation_gaps); write_json(output/"05_gate_b"/"gate_b_result.json",gate_b)
    common["gates"]=gates
    if gate_b.status not in ADVANCING: return _loop_return(output,gate_b,common)

    block_c = _research(BusinessBlock.BLOCK_C, mandate, research_contract, contracts, provider); append(block_c)
    sources[:] = _unique(sources,"source_id"); evidence[:] = _unique(evidence,"evidence_id"); claims[:] = _unique(claims,"claim_id")
    certification=run_business_certification(case_id=mandate.case_id,sources=sources,evidence=evidence,claims=claims); _attach_controls(bundles,certification)
    gate_c=evaluate_business_gate(gate_id="GATE_C",module_results=[b.module_result for b in block_c],claims=claims,mandate=mandate,prior_gates=[gate_a,gate_b]); gates.append(gate_c)
    _write_block(output,"06_block_c",block_c); write_json(output/"07_gate_c"/"gate_c_result.json",gate_c); common["gates"]=gates
    if gate_c.status not in ADVANCING: return _loop_return(output,gate_c,common)

    c5=next(b.module_result for b in block_c if b.module_result.module_id=="C5"); decision_value=DecisionStateValue(c5.structured_output["decision_state"])
    conditions=sorted(set(gate_a.conditions+gate_b.conditions+gate_c.conditions+list(c5.structured_output.get("conditions",[])))); review_ids=[x["review_id"] for x in case_data.get("human_review_items",[])]
    decision=DecisionState(decision_id=f"DECISION-{mandate.case_id}",case_id=mandate.case_id,state=decision_value,gate_a_status=gate_a.status,gate_b_status=gate_b.status,gate_c_status=gate_c.status,rationale=list(c5.structured_output.get("rationale",[])),conditions=conditions,walk_away_triggers=list(c5.structured_output.get("walk_away_triggers",[])),unresolved_gap_ids=[],human_review_items=review_ids,authority_boundary=mandate.authority_limit)
    write_json(output/"07_gate_c"/"decision_state.json",decision)
    for name,value in [("sources",sources),("evidence",evidence),("claims",claims),("assumptions",assumptions),("unknowns",unknowns),("counterevidence",counterevidence),("research_responses",responses)]: write_json(output/"01_research"/f"{name}.json",value)
    write_json(output/"08_controls"/"er_brb_results.json",certification["er_brb_results"]); write_json(output/"08_controls"/"pce_results.json",certification["pce_result"]); write_json(output/"08_controls"/"certification_adapter_boundary.json",certification["adapter_boundary"])
    write_json(output/"08_controls"/"prompt_manifest.json",[{"prompt_id":k,"role":v["role"],"source_file":v["source_file"]} for k,v in prompts.items()]); write_json(output/"08_controls"/"human_review_items.json",case_data.get("human_review_items",[])); write_json(output/"08_controls"/"unified_loop_events.json",[])
    iteration={"iteration":1,"modules_executed":[m.module_id for m in module_contracts],"gate_results":[{"gate_id":g.gate_id,"status":g.status} for g in gates],"calculation_replay_passes":sum(r.status.value=="PASS" for r in replays),"decision_state":decision.state,"note":"No gate failed; unified failure loop was not entered."}
    write_json(output/"09_loop"/"iteration_records.json",[iteration]); write_json(output/"09_loop"/"loop_state.json",{"status":"COMPLETED_ACQUISITION_BUSINESS_LAYER","completed_iterations":1,"gate_history":[{"gate_id":g.gate_id,"status":g.status} for g in gates],"unified_loop_available_for_all_gates":True})
    artifacts=[str(p.relative_to(output)).replace("\\","/") for p in sorted(output.rglob("*.json"))]
    terminal=BusinessTerminalState(status="COMPLETED_ACQUISITION_BUSINESS_LAYER",case_id=mandate.case_id,gate_a_status=gate_a.status,gate_b_status=gate_b.status,gate_c_status=gate_c.status,decision_state=decision.state,modules_executed=[m.module_id for m in module_contracts],calculations_replayed=sum(r.status.value=="PASS" for r in replays),open_gap_ids=[],human_review_items=review_ids,stopping_reason="All three business gates advanced; conditional items remain visible for human review.",generated_artifact_references=artifacts+["09_loop/terminal_state.json","run_summary.json"])
    write_json(output/"09_loop"/"terminal_state.json",terminal)
    from .reporting import generate_reporting_package

    reporting_package=generate_reporting_package(
        output_dir=output,case_data=case_data,mandate=mandate,
        module_results=[bundle.module_result for bundle in bundles],sources=sources,
        evidence=evidence,claims=claims,assumptions=assumptions,unknowns=unknowns,
        counterevidence=counterevidence,calculations=calculations,replays=replays,
        calculation_gaps=calculation_gaps,gates=gates,decision=decision,
        certification=certification,
    )
    summary={"schema_version":"milestone-4","case_id":mandate.case_id,"status":reporting_package["terminal_state"].status,"modules_executed":len(terminal.modules_executed),"prompts_loaded":len(prompts),"reporting_prompts_loaded":len(reporting_package["prompts"]),"calculations_replayed":terminal.calculations_replayed,"gate_a":gate_a.status,"gate_b":gate_b.status,"gate_c":gate_c.status,"decision_state":decision.state,"final_narrative_report_generated":True,"delivery_outcome":reporting_package["verification"]["delivery_outcome"],"output_directory":str(output)}
    write_json(output/"run_summary.json",summary)
    return {**common,"run_summary":summary,"output_dir":output,"bundles":bundles,"sources":sources,"evidence":evidence,"claims":claims,"assumptions":assumptions,"unknowns":unknowns,"counterevidence":counterevidence,"calculations":calculations,"calculation_replays":replays,"calculation_gaps":calculation_gaps,"certification":certification,"decision_state":decision,"terminal_state":terminal,"lifecycle_terminal_state":reporting_package["terminal_state"],"reporting_package":reporting_package}
