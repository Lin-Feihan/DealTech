from __future__ import annotations

from typing import Any


class ResearchPlanValidationError(ValueError):
    pass


def build_research_plan(mandate: dict[str, Any]) -> dict[str, Any]:
    buyer = mandate["buyer"]["name"]
    target = mandate["target"]["name"]
    transaction_type = mandate["transaction_context"]["transaction_type"]
    stage = mandate["transaction_context"]["stage"]
    decision_need = mandate["transaction_context"]["decision_need"].rstrip(".")
    decision_date = mandate["decision_date"]
    source_pack_id = mandate["source_pack_reference"]["reference_id"]

    plan = {
        "case_id": mandate["case_id"],
        "research_objective": (
            f"Create a Milestone 1 buyer-side acquisition research plan for {buyer} evaluating {target}; "
            f"decision need: {decision_need}."
        ),
        "key_questions": _build_key_questions(buyer, target, transaction_type, stage, decision_date),
        "workstreams": _build_workstreams(buyer, target),
        "evidence_requirements": _build_evidence_requirements(source_pack_id),
        "expected_artifacts": ["mandate.json", "research_plan.json"],
        "verification_targets": _build_verification_targets(),
        "open_questions": _build_open_questions(),
    }
    validate_research_plan(plan)
    return plan


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
        "What transaction background, mandate facts, and deal logic must be established before downstream analysis?",
        "What buyer strategic rationale, objectives, and value-creation requirements should drive the acquisition plan?",
        "What acquisition alternatives should be compared against buying the target?",
        "What target business quality, market position, and competitive risks must future diligence test?",
        "What valuation, deal structure, synergy, return, and downside-risk questions must be answered?",
        "What legal, regulatory, operational, integration, and red-line conditions should future diligence verify?",
        "What evidence requirements and human-review boundaries must be satisfied before any final recommendation can be drafted?",
    ]


def _build_workstreams(buyer: str, target: str) -> list[dict[str, Any]]:
    return [
        _workstream(
            "WS-001",
            "Transaction Background and Mandate Clarification",
            f"Plan the source-backed transaction narrative for {buyer} evaluating {target}.",
            [
                "What transaction problem is the buyer trying to solve?",
                "Which mandate facts, dates, parties, and deal terms must be verified before downstream work?",
            ],
        ),
        _workstream(
            "WS-002",
            "Buyer Strategic Rationale and Acquisition Alternatives",
            "Define buyer goals, success criteria, and alternatives to acquisition.",
            [
                "Which buyer objectives are must-have versus optional?",
                "Could build, partner, license, minority investment, or no-deal alternatives satisfy the same goals?",
            ],
        ),
        _workstream(
            "WS-003",
            "Target Business Quality and Competitive Position",
            "Plan diligence on business quality, market position, competitive durability, and management quality.",
            [
                "What evidence is needed to assess target quality?",
                "What market, customer, product, and competitive-position claims require verification?",
            ],
        ),
        _workstream(
            "WS-004",
            "Valuation, Deal Structure, Synergy, and Returns",
            "Define future valuation, purchase-price, deal-structure, synergy, and return-analysis requirements.",
            [
                "What valuation inputs must be source-backed before price guidance?",
                "Which deal terms, synergy assumptions, and financing inputs shift risk between buyer and seller?",
            ],
        ),
        _workstream(
            "WS-005",
            "Financing, Payment Mechanics, and Value Transfer",
            "Plan evidence needs for financing sources, payment mechanics, earnouts, contingent value, seller economics, and allocation of value transfer.",
            [
                "Which financing, payment, and contingent-value mechanics require source-backed analysis?",
                "Which seller economics or value-transfer claims require direct evidence?",
            ],
        ),
        _workstream(
            "WS-006",
            "Operating Model and Integration Planning",
            "Plan diligence on operating model, people, systems, technology, transition needs, and integration execution risk.",
            [
                "What operating or integration assumptions could affect value realization?",
                "Which people, systems, technology, and transition risks require diligence before closing?",
            ],
        ),
        _workstream(
            "WS-007",
            "Diligence Priorities and Risk Review",
            "Plan diligence tracks for legal, regulatory, financial, operational, technology, people, and integration risks.",
            [
                "Which diligence issues could change price, structure, timing, or approval conditions?",
                "Which unresolved issues should become human-review items rather than report assertions?",
            ],
        ),
        _workstream(
            "WS-008",
            "Legal, Regulatory, and Approval Conditions",
            "Plan legal, regulatory, consent, approval, liability, and closing-condition review.",
            [
                "Which legal or regulatory conditions could block or delay the acquisition?",
                "Which approvals, consents, liabilities, or compliance issues must be verified?",
            ],
        ),
        _workstream(
            "WS-009",
            "IC Decision Framework and Red-Line Conditions",
            "Define the investment-committee decision framework without drafting a recommendation in Milestone 1.",
            [
                "What evidence would support Proceed, Proceed with Conditions, Renegotiate, Defer, or Walk Away?",
                "What red-line conditions should block final report generation until verified?",
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


def _build_evidence_requirements(source_pack_id: str) -> list[dict[str, str]]:
    descriptions = [
        "Transaction documents and mandate materials supporting buyer, target, timing, parties, and transaction structure.",
        "Buyer strategy materials supporting strategic rationale, objectives, alternatives, and value-creation requirements.",
        "Target business, market, customer, competitive-position, management, legal, and regulatory materials needed for future diligence.",
        "Financial statements, valuation inputs, purchase-price support, financing assumptions, synergy inputs, and downside-risk evidence needed before any recommendation.",
        "Legal, regulatory, operational, technology, people, integration, and liability diligence materials needed to define red-line conditions.",
        "Evidence needed to prevent unsupported claims from entering future reports or investment-committee materials.",
        "Evidence needed to identify unresolved source gaps, human-review items, and decision-blocking red-line conditions.",
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
        ("Source boundary", "Treat mandate and case seed materials as leads unless they are independently retrieved and logged as sources."),
        ("Numeric verification", "Future valuation, purchase-price, synergy, financing, and return inputs must be source-backed and replayable."),
        ("Citation verification", "Each transaction, market, target-quality, valuation, synergy, and risk claim must link to source evidence before downstream use."),
        ("Claim verification", "Unsupported claims must become caveats or human_review_items rather than final report assertions."),
        ("Human review boundary", "Material unresolved diligence, source conflicts, and red-line issues require human review before recommendation drafting."),
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
        "Which buyer alternatives should be compared against acquisition?",
        "Which valuation method and return framework should future stages use after evidence is available?",
        "Which diligence issues should become human-review items in future Loop Certification?",
        "Which red-line conditions should block recommendation drafting until source-supported?",
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
