from __future__ import annotations

from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.case_profile_loader import load_case_profile_for_case_id


class ResearchPlanValidationError(ValueError):
    pass


def build_research_plan(mandate: dict[str, Any]) -> dict[str, Any]:
    buyer = mandate["buyer"]["name"]
    target = mandate["target"]["name"]
    transaction_type = mandate["transaction_context"]["transaction_type"]
    stage = mandate["transaction_context"]["stage"]
    decision_need = mandate["transaction_context"]["decision_need"].rstrip(".")
    source_pack_id = mandate["source_pack_reference"]["reference_id"]
    case_profile = load_case_profile_for_case_id(mandate["case_id"])
    planning_profile = case_profile.get("planning_profile") if case_profile else None

    plan = {
        "case_id": mandate["case_id"],
        "research_objective": (
            f"Create a Milestone 1 buyer-side acquisition research plan for {buyer} evaluating {target}; "
            f"decision need: {decision_need}."
        ),
        "key_questions": _profile_or_generic(
            planning_profile,
            "key_questions",
            lambda: _build_key_questions(buyer, target, transaction_type, stage, mandate["decision_date"]),
        ),
        "workstreams": _profile_or_generic(planning_profile, "workstreams", lambda: _build_workstreams(buyer, target)),
        "evidence_requirements": _build_evidence_requirements(source_pack_id, planning_profile),
        "expected_artifacts": ["mandate.json", "research_plan.json"],
        "verification_targets": _profile_or_generic(planning_profile, "verification_targets", _build_verification_targets),
        "open_questions": _profile_or_generic(planning_profile, "open_questions", _build_open_questions),
    }
    validate_research_plan(plan)
    return plan


def _profile_or_generic(profile: dict[str, Any] | None, field: str, generic_builder: Any) -> list[Any]:
    if profile:
        return profile[field]
    return generic_builder()


def _build_key_questions(
    buyer: str,
    target: str,
    transaction_type: str,
    stage: str,
    decision_date: str,
) -> list[str]:
    return [
        f"What decision must {buyer} make about {target} by {decision_date}?",
        f"What buyer-side acquisition issues are in scope for the {transaction_type} at {stage}?",
        "What transaction background and deal logic must be established before downstream analysis?",
        "What buyer strategic objectives, alternatives, and value-creation requirements should drive the acquisition plan?",
        "What target business quality, industry position, and competitive risks must future diligence test?",
        "What valuation, acceptable purchase price, deal structure, returns, and downside-risk questions must be answered?",
        "What legal, regulatory, integration, and red-line conditions should future diligence verify?",
        "What evidence requirements must be satisfied before any final recommendation can be drafted?",
    ]


def _build_workstreams(buyer: str, target: str) -> list[dict[str, Any]]:
    return [
        _workstream(
            "WS-001",
            "Transaction Background and Deal Logic",
            f"Plan the source-backed transaction narrative for {buyer} evaluating {target}.",
            [
                "What transaction problem is the buyer trying to solve?",
                "What facts are needed to separate deal context from analyst judgment?",
            ],
        ),
        _workstream(
            "WS-002",
            "Buyer Strategic Objectives and Alternatives",
            "Define buyer goals, success criteria, and alternatives to acquisition.",
            [
                "Which buyer objectives are must-have versus optional?",
                "Could build, partner, license, or minority investment satisfy the same goals?",
            ],
        ),
        _workstream(
            "WS-003",
            "Target Business Quality and Competitive Position",
            "Plan diligence on business quality, market position, and competitive durability.",
            [
                "What evidence is needed to assess target quality?",
                "What market and competitive-position claims require verification?",
            ],
        ),
        _workstream(
            "WS-004",
            "Valuation, Deal Structure, and Returns",
            "Define future valuation, purchase-price, structure, and return-analysis requirements.",
            [
                "What valuation inputs must be source-backed before price guidance?",
                "What deal-structure terms shift risk between buyer and seller?",
            ],
        ),
        _workstream(
            "WS-005",
            "Diligence, Risks, and IC Decision Framework",
            "Plan diligence priorities, red flags, and decision states for future analysis.",
            [
                "Which legal, regulatory, integration, and downside risks require diligence?",
                "What would support Proceed, Conditional Proceed, Renegotiate, Defer, or Walk Away?",
            ],
        ),
    ]


def _workstream(id_: str, name: str, objective: str, questions: list[str]) -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "objective": objective,
        "questions": questions,
        "planned_artifacts": ["research_plan.json"],
    }


def _build_evidence_requirements(source_pack_id: str, profile: dict[str, Any] | None) -> list[dict[str, str]]:
    if profile:
        return [
            {
                "id": requirement["id"],
                "description": requirement["description"],
                "source_pack_reference": requirement.get("source_pack_reference", source_pack_id),
            }
            for requirement in profile["evidence_requirements"]
        ]

    descriptions = [
        "Transaction documents and mandate materials supporting buyer, target, timing, and transaction structure.",
        "Buyer strategy materials supporting objectives, alternatives, and value-creation requirements.",
        "Target business, market, competitive-position, management, legal, and regulatory materials needed for future diligence.",
        "Valuation, purchase-price, financing, return-analysis, synergy, and downside-risk inputs needed before any recommendation.",
        "Evidence needed to prevent unsupported claims from entering future reports or investment-committee materials.",
    ]

    return [
        {
            "id": f"ER-{index:03d}",
            "description": description,
            "source_pack_reference": source_pack_id,
        }
        for index, description in enumerate(descriptions, start=1)
    ]


def _build_verification_targets() -> list[dict[str, str]]:
    targets = [
        ("Mandate completeness", "Fail closed before planning if required buyer-side acquisition inputs are missing."),
        ("Numeric verification", "Future valuation, purchase-price, synergy, and return inputs must be source-backed and replayable."),
        ("Citation verification", "Each transaction, market, target-quality, and risk claim must link to source evidence before downstream use."),
        ("Claim verification", "Unsupported claims must become caveats or human_review_items rather than final report assertions."),
        ("Milestone 1 scope boundary", "Prevent web search, evidence generation, certification, claim graph construction, and report generation."),
    ]

    return [
        {
            "id": f"VT-{index:03d}",
            "target": target,
            "reason": reason,
        }
        for index, (target, reason) in enumerate(targets, start=1)
    ]


def _build_open_questions() -> list[str]:
    return [
        "Which source-pack files will be available for future evidence extraction?",
        "Which valuation method should future stages use after evidence is available?",
        "Which buyer alternatives should be compared against acquisition?",
        "Which claims should require human review in future Loop Certification?",
    ]


def validate_research_plan(plan: dict[str, Any]) -> None:
    required = (
        "case_id",
        "research_objective",
        "key_questions",
        "workstreams",
        "evidence_requirements",
        "expected_artifacts",
        "verification_targets",
        "open_questions",
    )
    missing = [field for field in required if field not in plan]
    if missing:
        raise ResearchPlanValidationError(f"Missing research plan field(s): {', '.join(missing)}")
    _require_non_empty_string(plan["case_id"], "case_id")
    _require_non_empty_string(plan["research_objective"], "research_objective")
    _require_non_empty_list(plan["key_questions"], "key_questions")
    _require_non_empty_list(plan["workstreams"], "workstreams")
    _require_non_empty_list(plan["evidence_requirements"], "evidence_requirements")
    _require_non_empty_list(plan["expected_artifacts"], "expected_artifacts")
    _require_non_empty_list(plan["verification_targets"], "verification_targets")
    if not isinstance(plan["open_questions"], list):
        raise ResearchPlanValidationError("open_questions must be an array.")


def _require_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ResearchPlanValidationError(f"{field} must be a non-empty string.")


def _require_non_empty_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise ResearchPlanValidationError(f"{field} must be a non-empty array.")
