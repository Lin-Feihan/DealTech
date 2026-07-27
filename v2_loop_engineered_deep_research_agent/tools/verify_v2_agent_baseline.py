#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUYER = ROOT / "agents" / "acquisition_strategy_agent" / "buyer_side"


REQUIRED_FILES = [
    "AGENT_BASELINE_MAP.md",
    "README.md",
    "architecture/system_overview.md",
    "architecture/loop_design.md",
    "architecture/workflow_diagram.md",
    "runtime_workflow/research_loop.md",
    "runtime_workflow/certification_loop.md",
    "runtime_workflow/deal_analysis_loop.md",
    "runtime_workflow/report_generation_loop.md",
    "agents/acquisition_strategy_agent/README.md",
    "agents/acquisition_strategy_agent/agent.manifest.json",
    "agents/acquisition_strategy_agent/buyer_side/agent.config.json",
    "agents/acquisition_strategy_agent/buyer_side/source_mapping.md",
    "agents/acquisition_strategy_agent/buyer_side/prompt.md",
    "agents/acquisition_strategy_agent/buyer_side/workflow.json",
    "agents/acquisition_strategy_agent/buyer_side/loop_policy.json",
    "agents/acquisition_strategy_agent/buyer_side/certification_policy.json",
    "agents/acquisition_strategy_agent/buyer_side/report_writer_policy.json",
    "agents/acquisition_strategy_agent/buyer_side/output_contract.json",
    "agents/acquisition_strategy_agent/buyer_side/runbook.md",
    "schemas/mandate.schema.json",
    "schemas/research_plan.schema.json",
    "schemas/claim.schema.json",
    "schemas/evidence.schema.json",
    "schemas/certification.schema.json",
    "schemas/case_analysis.schema.json",
    "schemas/section_analysis.schema.json",
    "schemas/analysis_package.schema.json",
    "schemas/recommendation_decision.schema.json",
    "schemas/report_manifest.schema.json",
]

JSON_FILES = [path for path in REQUIRED_FILES if path.endswith(".json")]

PROMPT_MARKERS = [
    "Buyer Acquisition Strategy Deep Research Prompt",
    "Deep Research",
    "Analysis-First Contract",
    "case_analysis.json",
    "一、交易基本输入",
    "三、Deep Research 工作流程",
    "买方是否应该收购该标的",
]

PROMPT_SECTION_MARKERS = [
    "## 1. 执行摘要",
    "## 2. 交易概览",
    "## 3. 买方战略目标",
    "## 4. 标的业务质量",
    "## 5. 行业与竞争地位",
    "## 6. 战略匹配",
    "## 7. 独立财务分析",
    "## 8. 估值与收购价格",
    "## 9. 协同效应与价值创造",
    "## 10. 交易结构",
    "## 11. 融资及资本结构影响",
    "## 12. 回报分析",
    "## 13. 尽职调查发现",
    "## 14. 监管、整合与下行风险",
    "## 15. 最终建议",
]

OUTPUT_ARTIFACTS = [
    "final_report.md",
    "case_analysis.json",
    "analysis_package.json",
    "recommendation_decision.json",
    "claim_evidence_graph.json",
    "evidence_repository.json",
    "certification_results.json",
    "report_manifest.json",
    "research_gaps.json",
    "human_review_items.json",
    "analysis_quality_control.json",
]

REPORT_SECTIONS = [
    "1. 执行摘要 / Executive Summary",
    "2. 交易概览 / Transaction Overview",
    "3. 买方战略目标 / Buyer Strategic Objectives",
    "4. 标的业务质量 / Target Business Quality",
    "5. 行业与竞争地位 / Industry and Competitive Position",
    "6. 战略匹配 / Strategic Fit",
    "7. 独立财务分析 / Standalone Financial Analysis",
    "8. 估值与可接受收购价格 / Valuation and Acceptable Purchase Price",
    "9. 协同效应与价值创造 / Synergies and Value Creation",
    "10. 交易结构 / Deal Structure",
    "11. 融资及资本结构影响 / Financing and Capital Structure Impact",
    "12. 回报分析 / Returns Analysis",
    "13. 尽职调查发现 / Due Diligence Findings",
    "14. 监管、整合与下行风险 / Regulatory, Integration, and Downside Risks",
    "15. 最终决策建议 / Final Decision Recommendation",
]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def load_json(rel_path: str) -> object:
    with (ROOT / rel_path).open(encoding="utf-8") as handle:
        return json.load(handle)


def assert_required_files() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))


def assert_json_parses() -> None:
    for path in JSON_FILES:
        try:
            load_json(path)
        except Exception as exc:  # pragma: no cover - script diagnostics
            fail(f"invalid JSON in {path}: {exc}")


def assert_prompt_baseline() -> None:
    prompt = read_text("agents/acquisition_strategy_agent/buyer_side/prompt.md")
    missing = [marker for marker in PROMPT_MARKERS if marker not in prompt]
    if missing:
        fail("prompt baseline markers missing: " + ", ".join(missing))

    missing_sections = [section for section in PROMPT_SECTION_MARKERS if section not in prompt]
    if missing_sections:
        fail("prompt no longer preserves the buyer-side report section framework: " + ", ".join(missing_sections))


def assert_output_contract() -> None:
    contract = load_json("agents/acquisition_strategy_agent/buyer_side/output_contract.json")
    required_outputs = set(contract.get("required_final_outputs", []))
    missing_outputs = [name for name in OUTPUT_ARTIFACTS if name not in required_outputs]
    if missing_outputs:
        fail("output contract missing artifacts: " + ", ".join(missing_outputs))

    required_sections = contract.get("required_report_sections", [])
    if required_sections != REPORT_SECTIONS:
        fail("output contract no longer preserves the exact 15-section buyer-side report contract")

    minimums = "\n".join(contract.get("decision_grade_minimum_requirements", []))
    for marker in [
        "prior-case content is forbidden",
        "case_analysis.json is authoritative",
        "later disclosures of historical facts",
        "explicit proceed / proceed with conditions / renegotiate / defer / walk away recommendation",
    ]:
        if marker not in minimums:
            fail(f"output contract lost decision-grade requirement: {marker}")


def assert_runtime_boundary() -> None:
    config = load_json("agents/acquisition_strategy_agent/buyer_side/agent.config.json")
    if config.get("system_type") != "loop_engineered_certified_deep_research_agent":
        fail("agent.config.json lost loop-engineered system_type")

    implemented = set(config.get("runtime", {}).get("implemented_sequence", []))
    expected_implemented = {
        "load_certified_case_inputs",
        "load_authoritative_case_analysis",
        "validate_current_case_input_sovereignty",
        "route_case_applicable_methods",
        "replay_typed_models",
        "run_analysis_provenance_gate",
        "generate_professional_report",
        "run_report_leakage_gate",
        "emit_analysis_and_report_outputs",
    }
    if not expected_implemented.issubset(implemented):
        fail("agent.config.json lost implemented runtime sequence items")

    upstream = set(config.get("runtime", {}).get("upstream_not_implemented", []))
    expected_upstream = {
        "automated_source_retrieval",
        "research_planning_execution",
        "claim_evidence_graph_construction",
        "claim_certification",
    }
    if not expected_upstream.issubset(upstream):
        fail("agent.config.json no longer states the upstream unimplemented boundary")


def assert_source_mapping() -> None:
    mapping = read_text("agents/acquisition_strategy_agent/buyer_side/source_mapping.md")
    for marker in [
        "V2 does not replace V1",
        "Human-readable prompt baseline",
        "Structured workflow baseline",
        "prompt.md",
        "workflow.json",
        "loop-engineered runtime-ready structure",
    ]:
        if marker not in mapping:
            fail(f"source mapping lost marker: {marker}")


def main() -> None:
    assert_required_files()
    assert_json_parses()
    assert_prompt_baseline()
    assert_output_contract()
    assert_runtime_boundary()
    assert_source_mapping()
    print("OK: V2 acquisition strategy agent baseline is intact.")


if __name__ == "__main__":
    main()
