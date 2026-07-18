from __future__ import annotations

from typing import Any

from .block_a_models import BLOCK_A_DEPENDENCIES, BLOCK_A_MODULE_NAMES, BLOCK_A_ORDER


def latest_claims(rows: list[dict[str, Any]], module_id: str | None = None) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if module_id and row.get("owning_module_id") != module_id:
            continue
        family = str(row.get("claim_family_id") or row.get("claim_id"))
        if family not in latest or int(row.get("claim_version", 1)) > int(
            latest[family].get("claim_version", 1)
        ):
            latest[family] = row
    return list(latest.values())


def assess_block_a_module(
    *,
    request: Any,
    bundle: Any,
    registry: Any,
    contract: Any,
    threshold: dict[str, Any],
    iteration: int,
    version: int,
) -> dict[str, Any]:
    admitted = bundle.provider_artifacts["admitted_objects"]
    claim_ids = set(bundle.response.claim_ids)
    claims = [row for row in registry.claims if row["claim_id"] in claim_ids]
    evidence_by_id = {row["evidence_id"]: row for row in registry.evidence}
    minimum_sources = int(threshold.get("minimum_independent_sources_per_material_claim", 1))
    failures: list[dict[str, Any]] = []
    conditions = list(
        bundle.provider_artifacts["provider_response_structured"]["module_assessment"].get(
            "conditions", []
        )
    )
    source_diversity: dict[str, int] = {}
    source_by_id = {row["source_id"]: row for row in registry.sources}
    for claim in claims:
        supporting = [
            evidence_by_id[evidence_id]
            for evidence_id in claim.get("supporting_evidence_ids", [])
            if evidence_id in evidence_by_id
            and evidence_by_id[evidence_id].get("direction") == "support"
        ]
        independent_source_keys = {
            (
                source_by_id.get(row["source_id"], {}).get("source_kind", ""),
                source_by_id.get(row["source_id"], {}).get("file_hash_sha256", "")
                if source_by_id.get(row["source_id"], {}).get("source_kind") == "attachment"
                else (
                    source_by_id.get(row["source_id"], {}).get("publication_identity")
                    or source_by_id.get(row["source_id"], {}).get("publisher_or_owner")
                    or row["source_id"]
                ),
            )
            for row in supporting
        }
        source_count = len(independent_source_keys)
        source_diversity[claim["claim_id"]] = source_count
        if claim.get("materiality", "").lower() == "material" and source_count < minimum_sources:
            failures.append(
                {
                    "type": "SOURCE_DIVERSITY_GAP",
                    "claim_id": claim["claim_id"],
                    "reason": (
                        f"{contract.module_id} material Claim has {source_count} independent "
                        f"Sources; {minimum_sources} required."
                    ),
                }
            )
        if claim.get("pce_status") == "Not Certified":
            failures.append(
                {
                    "type": "PCE_LINEAGE_GAP",
                    "claim_id": claim["claim_id"],
                    "reason": "Claim remains Not Certified after the independent PCE control.",
                }
            )
    if not admitted.get("counterevidence"):
        failures.append(
            {
                "type": "COUNTEREVIDENCE_GAP",
                "claim_id": contract.module_id,
                "reason": "The module did not return the required counterevidence record.",
            }
        )
    if not claims or not bundle.module_result.supporting_evidence_ids:
        failures.append(
            {
                "type": "EMPTY_MODULE_RESULT",
                "claim_id": contract.module_id,
                "reason": "A Block A module cannot be an empty placeholder.",
            }
        )
    assessment = bundle.provider_artifacts["provider_response_structured"]["module_assessment"]
    if assessment["criterion_outcome"] == "FAIL":
        failures.append(
            {
                "type": "MODULE_CONTRACT_INSUFFICIENT",
                "claim_id": contract.module_id,
                "reason": assessment["business_conclusion"],
            }
        )
    required_dependencies = BLOCK_A_DEPENDENCIES[contract.module_id]
    dependency_claim_ids = {
        item for claim in claims for item in claim.get("dependency_claim_ids", [])
    }
    dependency_claims = {
        row["claim_id"]: row for row in registry.claims if row["claim_id"] in dependency_claim_ids
    }
    dependency_modules = {
        row.get("owning_module_id", "") for row in dependency_claims.values()
    }
    if contract.module_id in {"A3", "A7"}:
        required = set(required_dependencies)
        if contract.module_id == "A7":
            required = {"A2", "A5", "A6"}
        missing = sorted(required - dependency_modules)
        if missing:
            failures.append(
                {
                    "type": "SYNTHESIS_DEPENDENCY_GAP",
                    "claim_id": contract.module_id,
                    "reason": f"Evidence-based synthesis is missing upstream Claims from {missing}.",
                }
            )
    conflicts = list(bundle.provider_artifacts.get("conflicts", []))
    material_conflicts = [
        row
        for row in conflicts
        if row.get("materiality", "").lower() == "material"
        and row.get("resolution_status") not in {"RESOLVED", "CLOSED"}
    ]
    if material_conflicts:
        conditions.append("Material cross-source conflict remains visible and requires resolution.")
    human_unknowns = [
        row for row in admitted.get("unknowns", []) if row.get("human_review_required")
    ]
    if human_unknowns:
        conditions.append("Human Review is required for information unavailable to public research.")
    if failures:
        status = "FAIL_RESEARCH_GAP"
    elif assessment["criterion_outcome"] == "CONDITION" or conditions or material_conflicts:
        status = "CONDITIONAL_PASS"
    else:
        status = "PASS"
    pce_statuses = {row["claim_id"]: row.get("pce_status", "Not Certified") for row in claims}
    er_statuses = {row["claim_id"]: row.get("er_brb_status", []) for row in claims}
    return {
        "module_result_id": f"MODULE-{contract.module_id}-V{version:02d}",
        "module_id": contract.module_id,
        "module_name": contract.professional_name,
        "iteration": iteration,
        "version": version,
        "prompt_reference": contract.prompt_reference,
        "research_request_id": request.request_id,
        "dependency_claim_ids": sorted(dependency_claim_ids),
        "status": status,
        "business_conclusion": assessment["business_conclusion"],
        "structured_output": assessment["structured_output"],
        "facts": list(bundle.module_result.facts),
        "inferences": list(bundle.module_result.inferences),
        "assumption_ids": list(bundle.response.assumption_ids),
        "unknown_ids": list(bundle.response.unknown_ids),
        "counterevidence_ids": list(bundle.response.counterevidence_ids),
        "conflict_ids": [row["conflict_id"] for row in conflicts],
        "source_ids": list(bundle.response.source_ids),
        "evidence_ids": list(bundle.response.evidence_ids),
        "claim_ids": list(bundle.response.claim_ids),
        "source_diversity": source_diversity,
        "pce_statuses": pce_statuses,
        "er_brb_statuses": er_statuses,
        "failures": failures,
        "conditions": sorted(set(conditions)),
        "limitations": list(assessment["limitations"]),
        "provider_has_gate_authority": False,
    }


def _criterion(
    criterion_id: str,
    name: str,
    outcome: str,
    reason: str,
    *,
    module_ids: list[str] | None = None,
    claim_ids: list[str] | None = None,
    counterevidence_ids: list[str] | None = None,
    conditions: list[str] | None = None,
    human_review_items: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "criterion_name": name,
        "outcome": outcome,
        "reason": reason,
        "affected_module_ids": module_ids or [],
        "supporting_claim_ids": claim_ids or [],
        "counterevidence_ids": counterevidence_ids or [],
        "conditions": conditions or [],
        "human_review_items": human_review_items or [],
    }


def evaluate_block_a_gate(
    *,
    case_data: dict[str, Any],
    module_results: dict[str, dict[str, Any]],
    registry: Any,
    certification: dict[str, Any],
    iteration: int,
    open_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    mandate = case_data.get("mandate", {})
    required_mandate = (
        "buyer_name", "target_name", "transaction_type", "transaction_stage",
        "decision_question", "buyer_strategic_need", "jurisdictions",
    )
    missing_mandate = [name for name in required_mandate if not mandate.get(name)]
    criteria: list[dict[str, Any]] = []
    criteria.append(
        _criterion(
            "GA-MANDATE",
            "Mandate clarity",
            "FAIL" if missing_mandate else "PASS",
            f"Missing Mandate fields: {missing_mandate}" if missing_mandate else "Mandate fields required for Block A are explicit.",
            module_ids=["A1"],
        )
    )
    natural_order = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    for module_id in natural_order:
        result = module_results.get(module_id)
        if result is None:
            criteria.append(
                _criterion(
                    f"GA-{module_id}", BLOCK_A_MODULE_NAMES[module_id], "FAIL",
                    "Required Block A module result is missing; Gate A does not substitute another module.",
                    module_ids=[module_id],
                )
            )
            continue
        outcome = "FAIL" if result["status"] == "FAIL_RESEARCH_GAP" else (
            "CONDITION" if result["status"] == "CONDITIONAL_PASS" else "PASS"
        )
        criteria.append(
            _criterion(
                f"GA-{module_id}", BLOCK_A_MODULE_NAMES[module_id], outcome,
                result["business_conclusion"], module_ids=[module_id],
                claim_ids=result["claim_ids"],
                counterevidence_ids=result["counterevidence_ids"],
                conditions=result["conditions"],
            )
        )
    latest = latest_claims(registry.claims)
    not_certified = [row["claim_id"] for row in latest if row.get("pce_status") == "Not Certified"]
    module_failures = [
        module_id for module_id, result in module_results.items()
        if result["status"] == "FAIL_RESEARCH_GAP"
    ]
    criteria.append(
        _criterion(
            "GA-EVIDENCE", "Evidence sufficiency",
            "FAIL" if module_failures or not_certified else "PASS",
            "Module evidence or PCE requirements remain unsatisfied."
            if module_failures or not_certified else "Every current module Claim has admitted evidence and independent PCE status.",
            module_ids=sorted(module_failures), claim_ids=[row["claim_id"] for row in latest],
        )
    )
    diversity_failures = [
        module_id for module_id, result in module_results.items()
        if any(item["type"] == "SOURCE_DIVERSITY_GAP" for item in result["failures"])
    ]
    criteria.append(
        _criterion(
            "GA-SOURCE-DIVERSITY", "Source diversity",
            "FAIL" if diversity_failures else "PASS",
            "Duplicate or insufficient Sources cannot satisfy diversity."
            if diversity_failures else "Module-specific independent Source thresholds are satisfied.",
            module_ids=sorted(diversity_failures),
        )
    )
    counter_modules = {row.get("owning_module_id") for row in registry.counterevidence}
    missing_counter = sorted(set(BLOCK_A_MODULE_NAMES) - counter_modules)
    criteria.append(
        _criterion(
            "GA-COUNTEREVIDENCE", "Counterevidence",
            "FAIL" if missing_counter else "PASS",
            f"Missing counterevidence search for {missing_counter}." if missing_counter else "Every Block A module preserved counterevidence.",
            module_ids=missing_counter,
            counterevidence_ids=[row["counterevidence_id"] for row in registry.counterevidence],
        )
    )
    material_conflicts = [
        row for row in registry.conflicts
        if row.get("materiality", "").lower() == "material"
        and row.get("resolution_status") not in {"RESOLVED", "CLOSED"}
    ]
    criteria.append(
        _criterion(
            "GA-CONFLICTS", "Conflicts",
            "CONDITION" if material_conflicts else "PASS",
            "Material conflicts remain visible and cannot be hidden to pass Gate A."
            if material_conflicts else "No unresolved material cross-source conflict remains.",
            claim_ids=[item for row in material_conflicts for item in row.get("related_claim_ids", [])],
            conditions=["Resolve or formally accept each material conflict before transaction approval."] if material_conflicts else [],
        )
    )
    material_assumptions = [row for row in registry.assumptions if row.get("materiality", "").lower() == "material"]
    criteria.append(
        _criterion(
            "GA-ASSUMPTIONS", "Material assumptions",
            "CONDITION" if material_assumptions else "PASS",
            "Material assumptions remain explicitly conditional." if material_assumptions else "No material analytical assumption remains open.",
            conditions=[row["statement"] for row in material_assumptions],
        )
    )
    material_unknowns = [row for row in registry.unknowns if row.get("materiality", "").lower() == "material"]
    criteria.append(
        _criterion(
            "GA-UNKNOWNS", "Material unknowns",
            "CONDITION" if material_unknowns else "PASS",
            "Material unknowns remain explicit." if material_unknowns else "No material research unknown remains open.",
            conditions=[row["closure_requirement"] for row in material_unknowns],
        )
    )
    human_items = [
        {
            "human_review_item_id": f"HR-{row['unknown_id']}",
            "originating_module": row.get("owning_module_id") or row.get("owning_module"),
            "description": row["description"],
            "required_role": (mandate.get("human_review_roles") or ["Authorized deal-team reviewer"])[0],
            "blocking": bool(row.get("blocking", False)),
            "status": "OPEN",
        }
        for row in registry.unknowns if row.get("human_review_required")
    ]
    criteria.append(
        _criterion(
            "GA-HUMAN-REVIEW", "Human Review requirements",
            "FAIL" if any(row["blocking"] for row in human_items) else ("CONDITION" if human_items else "PASS"),
            "Human Review boundaries remain visible." if human_items else "No unresolved Human Review item blocks this Gate.",
            human_review_items=[row["human_review_item_id"] for row in human_items],
        )
    )
    criteria.append(
        _criterion(
            "GA-PCE", "PCE status", "FAIL" if not_certified else "PASS",
            f"Not Certified Claims: {not_certified}" if not_certified else "All current Claims passed the independent PCE delivery control.",
            claim_ids=[row["claim_id"] for row in latest],
        )
    )
    er_rows = certification.get("er_brb_results", [])
    criteria.append(
        _criterion(
            "GA-ER-BRB", "ER/BRB status", "PASS" if er_rows else "FAIL",
            "Independent ER/BRB evidence-row assessment completed." if er_rows else "ER/BRB did not produce evidence-row results.",
        )
    )
    failed = [row["criterion_id"] for row in criteria if row["outcome"] == "FAIL"]
    conditions = sorted(
        set(item for row in criteria for item in row.get("conditions", []))
    )
    blocking_human = any(row["blocking"] for row in human_items)
    fatal = any(result.get("fatal_mismatch") for result in module_results.values())
    if fatal:
        status = "FATAL_STRATEGIC_MISMATCH"
    elif missing_mandate:
        status = "FAIL_MANDATE_GAP"
    elif blocking_human:
        status = "HUMAN_REVIEW_REQUIRED"
    elif failed:
        status = "FAIL_RESEARCH_GAP"
    elif any(row["outcome"] == "CONDITION" for row in criteria) or conditions:
        status = "CONDITIONAL_PASS"
    else:
        status = "PASS"
    unresolved_gaps = [row for row in open_gaps if row.get("status") == "OPEN"]
    return {
        "gate_result_id": f"GATE-A-{iteration:02d}",
        "gate_id": "GATE_A",
        "gate_name": "Strategic Thesis Gate",
        "iteration": iteration,
        "status": status,
        "criterion_results": criteria,
        "failed_criteria": failed,
        "supporting_claims": [row["claim_id"] for row in latest],
        "counterevidence": [row["counterevidence_id"] for row in registry.counterevidence],
        "conditions": conditions,
        "open_gaps": [row["gap_id"] for row in unresolved_gaps],
        "human_review_items": human_items,
        "downstream_permission": (
            "BLOCK_B_MAY_START_WITH_CONDITIONS" if status == "CONDITIONAL_PASS"
            else "BLOCK_B_MAY_START" if status == "PASS" else "BLOCK_B_NOT_PERMITTED"
        ),
        "business_outcome": status,
        "certification_summary": {
            "pce_statuses": {row["claim_id"]: row.get("pce_status", "Not Certified") for row in latest},
            "er_brb_record_count": len(er_rows),
            "provider_selected_gate_result": False,
            "certification_does_not_replace_business_gate": True,
        },
        "authority_boundary": "Gate A is evaluated by deterministic business criteria after admission, PCE and ER/BRB; no provider selects this result.",
    }


def smallest_responsible_gap(
    gate_result: dict[str, Any], module_results: dict[str, dict[str, Any]], iteration: int
) -> dict[str, Any]:
    for module_id in BLOCK_A_ORDER:
        result = module_results.get(module_id)
        if result and result["status"] == "FAIL_RESEARCH_GAP":
            failure = result["failures"][0]
            return {
                "gap_id": f"GAP-{module_id}-{iteration:02d}",
                "gap_type": failure["type"],
                "originating_module": module_id,
                "originating_gate": "GATE_A",
                "failed_criterion": f"GA-{module_id}",
                "affected_claim_id": failure.get("claim_id", module_id),
                "missing_evidence": failure["reason"],
                "required_action": f"Run a narrower {module_id} question and preserve all prior attempts.",
                "status": "OPEN",
                "created_iteration": iteration,
                "technical_failure": False,
            }
    return {
        "gap_id": f"GAP-GATE-A-{iteration:02d}",
        "gap_type": "GATE_CRITERION_GAP",
        "originating_module": "A1",
        "originating_gate": "GATE_A",
        "failed_criterion": (gate_result.get("failed_criteria") or ["GA-MANDATE"])[0],
        "affected_claim_id": "",
        "missing_evidence": "A Gate A criterion remains unresolved.",
        "required_action": "Resolve the exact failed Gate A criterion.",
        "status": "OPEN",
        "created_iteration": iteration,
        "technical_failure": False,
    }


def dependent_synthesis_modules(changed_module: str) -> list[str]:
    if changed_module in {"A1", "A2", "A3", "A4", "A5", "A6"}:
        return [module for module in ("A3", "A7") if module != changed_module]
    return []
