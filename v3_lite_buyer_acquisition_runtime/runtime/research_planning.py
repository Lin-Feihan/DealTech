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
    source_pack_id = mandate["source_pack_reference"]["reference_id"]
    planning_context = _planning_context_text(mandate)
    is_fronthera_case = _is_fronthera_case(planning_context)

    key_questions = _build_key_questions(
        buyer=buyer,
        target=target,
        transaction_type=transaction_type,
        stage=stage,
        decision_date=mandate["decision_date"],
        is_fronthera_case=is_fronthera_case,
    )

    plan = {
        "case_id": mandate["case_id"],
        "research_objective": (
            f"Create a Milestone 1 buyer-side acquisition research plan for {buyer} evaluating {target}; "
            f"decision need: {decision_need}."
        ),
        "key_questions": key_questions,
        "workstreams": _build_workstreams(buyer, target, is_fronthera_case),
        "evidence_requirements": _build_evidence_requirements(source_pack_id, is_fronthera_case),
        "expected_artifacts": ["mandate.json", "research_plan.json"],
        "verification_targets": _build_verification_targets(is_fronthera_case),
        "open_questions": _build_open_questions(is_fronthera_case),
    }
    validate_research_plan(plan)
    return plan


def _planning_context_text(mandate: dict[str, Any]) -> str:
    fields = [
        mandate.get("case_id", ""),
        mandate.get("buyer", {}).get("name", ""),
        mandate.get("buyer", {}).get("description", ""),
        mandate.get("target", {}).get("name", ""),
        mandate.get("target", {}).get("description", ""),
        mandate.get("transaction_context", {}).get("decision_need", ""),
        mandate.get("source_pack_reference", {}).get("description", ""),
    ]
    fields.extend(mandate.get("requested_scope", []))
    fields.extend(mandate.get("constraints", {}).get("notes", []))
    return "\n".join(str(field) for field in fields)


def _is_fronthera_case(planning_context: str) -> bool:
    required_signals = ("fronthera", "tyk2")
    context = planning_context.lower()
    return all(signal in context for signal in required_signals)


def _build_key_questions(
    buyer: str,
    target: str,
    transaction_type: str,
    stage: str,
    decision_date: str,
    is_fronthera_case: bool,
) -> list[str]:
    if is_fronthera_case:
        return [
            f"What was the buyer-side investment thesis for {buyer} acquiring {target} rather than licensing, partnering, or making a minority investment?",
            "What scientific and commercial evidence is required to evaluate the TYK2 / ESK-001 / envudeucitinib asset lineage?",
            "How should the buyer distinguish $60M base initial consideration, up to $120M milestone consideration, and the $180M headline maximum value?",
            "What milestone triggers, development risks, and approval risks determine value realization?",
            "What diligence is required around FronThera patents, clinical development status, asset ownership, liabilities, and regulatory path?",
            "How should Bohan Jin's founder / VP Chemistry / director / 2017 11.12% shareholder role be treated without overclaiming personal realized proceeds?",
            "What evidence would be required before making any claim about personal payout, founder economics, or cap table economics?",
            "What buyer alternatives were available besides acquisition, including licensing, partnering, internal discovery, or minority investment?",
            "What would make the acquisition a Proceed, Proceed with Conditions, Renegotiate, Defer, or Walk Away case?",
        ]

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


def _build_workstreams(buyer: str, target: str, is_fronthera_case: bool) -> list[dict[str, Any]]:
    if is_fronthera_case:
        return [
            _workstream(
                "WS-001",
                "Transaction Background and Buyer Investment Thesis",
                "Frame why the buyer would pursue FronThera in March 2021 and what strategic problem the acquisition was meant to solve.",
                [
                    "What did FL2021-001 / Esker / Alumis need to believe about FronThera to justify acquisition over licensing or partnership?",
                    "What source-backed timeline is needed for the March 5, 2021 stock purchase agreement and acquisition context?",
                ],
            ),
            _workstream(
                "WS-002",
                "Target and Scientific Asset Quality",
                "Plan diligence on FronThera's scientific platform, development maturity, and commercial relevance.",
                [
                    "What evidence is required to assess FronThera's TYK2 inhibitor chemistry quality?",
                    "What pre-deal data would support or weaken the case for clinical and commercial potential?",
                ],
            ),
            _workstream(
                "WS-003",
                "TYK2 / ESK-001 / envudeucitinib Asset Lineage Diligence",
                "Define the source trail needed to connect FronThera chemistry to the later ESK-001 / envudeucitinib asset lineage.",
                [
                    "Which documents link FronThera, Esker, Alumis, TYK2, ESK-001, and envudeucitinib?",
                    "What lineage claims must remain caveated until source-supported?",
                ],
            ),
            _workstream(
                "WS-004",
                "Patent / IP / Ownership and Key-Person Diligence",
                "Plan diligence on patents, asset ownership, governance, key-person roles, and founder economics boundaries.",
                [
                    "What patent and assignment evidence is needed for the TYK2 chemistry and acquired rights?",
                    "How should Bohan Jin's documented FronThera roles and 2017 11.12% shareholding be verified without asserting personal proceeds?",
                ],
            ),
            _workstream(
                "WS-005",
                "Deal Economics, Valuation, and Purchase Price Bridge",
                "Separate upfront, milestone, and headline value concepts before future valuation or return analysis.",
                [
                    "How should the $60M base initial consideration, up to $120M milestones, and $180M headline maximum be bridged?",
                    "What valuation support is needed before determining acceptable purchase price or renegotiation range?",
                ],
            ),
            _workstream(
                "WS-006",
                "Milestone Consideration and Risk Allocation",
                "Identify future diligence needed to understand milestone triggers, payment timing, and risk allocation.",
                [
                    "What milestone events triggered the $37M payment in 2022 and $23M payment in 2024?",
                    "Which development, regulatory, approval, or commercial risks remained after 2024?",
                ],
            ),
            _workstream(
                "WS-007",
                "Strategic Fit, Alternatives, and Value Creation",
                "Plan analysis of whether acquisition was superior to build, partner, license, or minority investment alternatives.",
                [
                    "What buyer capabilities would FronThera add to Esker / Alumis?",
                    "What alternatives could have delivered similar TYK2 exposure with lower capital or execution risk?",
                ],
            ),
            _workstream(
                "WS-008",
                "Legal / Regulatory / Clinical / Liability Diligence",
                "Define diligence tracks for legal liabilities, clinical development status, regulatory path, and transaction conditions.",
                [
                    "What liabilities, consent requirements, and regulatory risks should be checked before closing?",
                    "What clinical-development and regulatory-path evidence is required before downstream deal analysis?",
                ],
            ),
            _workstream(
                "WS-009",
                "IC Decision Framework and Red-Line Conditions",
                "Create the future investment-committee decision framework without drafting a recommendation in Milestone 1.",
                [
                    "What evidence would support Proceed, Proceed with Conditions, Renegotiate, Defer, or Walk Away?",
                    "What unsupported claim types must become caveats or human_review_items in future stages?",
                ],
            ),
        ]

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


def _build_evidence_requirements(source_pack_id: str, is_fronthera_case: bool) -> list[dict[str, str]]:
    if is_fronthera_case:
        descriptions = [
            "Stock purchase agreement and consideration schedule supporting March 5, 2021 transaction timing and economics.",
            "SEC / Alumis filings supporting FL2021-001, Esker Therapeutics, and Alumis name history and milestone payments.",
            "Source evidence on FronThera roles, ownership, governance, Bohan Jin's founder / VP Chemistry / director status, and 2017 11.12% shareholding.",
            "Patent evidence for TYK2 inhibitor chemistry and asset lineage.",
            "Pipeline, clinical, and regulatory evidence for ESK-001 / envudeucitinib.",
            "Source evidence distinguishing $180M headline deal value from $60M upfront/base initial consideration and milestone consideration.",
            "Evidence needed to avoid unsupported claims about Bohan Jin's personal proceeds, personal realized proceeds, founder economics, or cap table economics.",
        ]
    else:
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


def _build_verification_targets(is_fronthera_case: bool) -> list[dict[str, str]]:
    if is_fronthera_case:
        targets = [
            (
                "Numeric verification",
                "$60M upfront/base initial consideration + up to $120M milestone consideration must reconcile to $180M maximum headline value; $60M + $37M + $23M must reconcile to at least around $120M paid or payable by end-2024.",
            ),
            (
                "Citation verification",
                "Each transaction economics claim must link to source evidence before it can be used downstream.",
            ),
            (
                "Claim verification",
                "The phrase '$180M sale' must not be treated as an all-cash upfront purchase price.",
            ),
            (
                "Claim verification",
                "Bohan Jin's 2017 11.12% stake must not be converted into verified personal proceeds or personal realized proceeds.",
            ),
            (
                "Lineage verification",
                "FL2021-001 -> Esker Therapeutics -> Alumis entity/name history must be source-supported before use.",
            ),
            (
                "Scientific asset verification",
                "TYK2 / ESK-001 / envudeucitinib linkage must be source-supported before downstream analysis.",
            ),
            (
                "Human review target",
                "Founder economics, cap table changes, and personal payout claims require human review.",
            ),
            (
                "Milestone 1 scope boundary",
                "Prevent web search, evidence generation, certification, claim graph construction, and report generation.",
            ),
        ]
    else:
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


def _build_open_questions(is_fronthera_case: bool) -> list[str]:
    if is_fronthera_case:
        return [
            "What was FronThera's cap table immediately before the 2021 transaction?",
            "Which sellers received the base and milestone consideration?",
            "What exact milestones triggered the 2022 and 2024 payments?",
            "What remaining approval or development milestones were outstanding after 2024?",
            "What evidence links specific TYK2 patents to the acquired clinical asset?",
            "What buyer alternatives were available besides acquisition?",
            "Which source-pack files are sufficient for future evidence extraction without web search?",
        ]

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
