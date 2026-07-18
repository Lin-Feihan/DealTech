from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.buyer_side_acquisition_loop_agent.attachment_ingestion import prepare_attachments
from agents.buyer_side_acquisition_loop_agent.block_a_evaluation import (
    dependent_synthesis_modules,
    evaluate_block_a_gate,
)
from agents.buyer_side_acquisition_loop_agent.block_a_models import (
    BLOCK_A_DEPENDENCIES,
    BLOCK_A_MODULE_NAMES,
    BLOCK_A_ORDER,
)
from agents.buyer_side_acquisition_loop_agent.block_a_runtime import (
    MODULE_FILENAMES,
    build_block_a_research_plan,
    check_block_a_configuration,
    run_block_a_case,
)
from agents.buyer_side_acquisition_loop_agent.business_contracts import (
    load_module_contracts,
    load_prompt_registry,
)
from agents.buyer_side_acquisition_loop_agent.live_research_models import (
    ProviderConfigurationError,
    ProviderMode,
)
from agents.buyer_side_acquisition_loop_agent.live_research_provider import (
    block_a_provider_output_schema,
)
from agents.buyer_side_acquisition_loop_agent.provider_validation import validate_provider_output
from agents.buyer_side_acquisition_loop_agent.storage import load_case


AGENT_ROOT = Path(__file__).resolve().parents[1]
RECORDED_CASE = AGENT_ROOT / "06_examples" / "recorded_block_a_provider_case" / "case.yaml"
LIVE_TEMPLATE = AGENT_ROOT / "06_examples" / "live_block_a_provider_case_template" / "case.yaml"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_case(tmp_path: Path) -> Path:
    destination = tmp_path / "case"
    shutil.copytree(RECORDED_CASE.parent, destination, ignore=shutil.ignore_patterns("run_output"))
    return destination / "case.yaml"


@pytest.fixture(scope="module")
def block_a_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("m6-recorded") / "run_output"
    result = run_block_a_case(RECORDED_CASE, output, provider="recorded", module="BLOCK_A")
    return result, output


def _gate_inputs(output: Path):
    case_data = load_case(RECORDED_CASE)
    module_results = {
        module_id: _read(output / "modules" / filename)["final_result"]
        for module_id, filename in MODULE_FILENAMES.items()
    }
    registry = SimpleNamespace(
        claims=_read(output / "research" / "claims.json"),
        counterevidence=_read(output / "research" / "counterevidence.json"),
        conflicts=_read(output / "research" / "conflicts.json"),
        assumptions=_read(output / "research" / "assumptions.json"),
        unknowns=_read(output / "research" / "unknowns.json"),
    )
    certification = {
        "pce_result": _read(output / "verification" / "pce_results.json"),
        "er_brb_results": _read(output / "verification" / "er_brb_results.json"),
    }
    return case_data, module_results, registry, certification


def test_01_all_seven_modules_execute(block_a_run):
    result, output = block_a_run
    summary = _read(output / "run_summary.json")
    assert summary["modules_executed"] == sorted(BLOCK_A_MODULE_NAMES)
    assert result.module_executions == 10


def test_02_no_module_is_an_empty_placeholder(block_a_run):
    _, output = block_a_run
    for module_id, filename in MODULE_FILENAMES.items():
        result = _read(output / "modules" / filename)["final_result"]
        assert result["module_id"] == module_id
        assert result["claim_ids"] and result["evidence_ids"]
        assert result["structured_output"] and result["business_conclusion"]


def test_03_every_module_uses_its_approved_prompt(block_a_run):
    _, output = block_a_run
    contracts = {item.module_id: item for item in load_module_contracts()}
    prompts = load_prompt_registry()
    for module_id in BLOCK_A_MODULE_NAMES:
        request = _read(output / "provider" / module_id / "attempt_01" / "provider_request.json")
        assert request["prompt_reference"] == contracts[module_id].prompt_reference
        assert request["prompt_reference"].rsplit("#", 1)[-1] in prompts


def test_04_research_requests_are_module_specific(block_a_run):
    _, output = block_a_run
    questions = []
    for module_id in BLOCK_A_ORDER:
        request = _read(output / "provider" / module_id / "attempt_01" / "provider_request.json")
        assert request["module_id"] == module_id
        assert request["module_name"] == BLOCK_A_MODULE_NAMES[module_id]
        assert request["business_purpose"]
        assert request["prohibited_conclusions"]
        questions.append(tuple(request["research_questions"]))
    assert len(set(questions)) == 7


def test_05_block_a_dependency_graph_is_explicit():
    case_data = load_case(RECORDED_CASE)
    plan = build_block_a_research_plan(case_data)
    assert plan.module_order == ["A1", "A2", "A4", "A5", "A6", "A3", "A7"]
    assert plan.dependency_graph["A3"] == ["A1", "A2", "A4", "A5", "A6"]
    assert {"A2", "A5", "A6"}.issubset(plan.dependency_graph["A7"])


def test_06_a3_contains_all_required_upstream_claim_dependencies(block_a_run):
    _, output = block_a_run
    result = _read(output / "modules" / MODULE_FILENAMES["A3"])["final_result"]
    claims = {row["claim_id"]: row for row in _read(output / "research" / "claims.json")}
    modules = {claims[item]["owning_module_id"] for item in result["dependency_claim_ids"]}
    assert modules == {"A1", "A2", "A4", "A5", "A6"}


def test_07_a7_links_need_capability_and_industry_claims(block_a_run):
    _, output = block_a_run
    result = _read(output / "modules" / MODULE_FILENAMES["A7"])["final_result"]
    claims = {row["claim_id"]: row for row in _read(output / "research" / "claims.json")}
    modules = {claims[item]["owning_module_id"] for item in result["dependency_claim_ids"]}
    assert {"A2", "A5", "A6"}.issubset(modules)


def test_08_changing_a5_invalidates_only_dependent_synthesis():
    assert dependent_synthesis_modules("A5") == ["A3", "A7"]


def test_09_recorded_a6_change_reruns_only_a6_a3_a7(block_a_run):
    _, output = block_a_run
    iterations = _read(output / "loop" / "iteration_records.json")
    assert iterations[1]["modules_executed"] == ["A6", "A3", "A7"]
    assert all(iterations[1]["module_versions"][item] == 1 for item in ["A1", "A2", "A4", "A5"])


def test_10_a1_prohibits_valuation(block_a_run):
    _, output = block_a_run
    request = _read(output / "provider" / "A1" / "attempt_01" / "provider_request.json")
    assert "valuation" in request["prohibited_conclusions"]


def test_11_a2_does_not_decide_target_attractiveness(block_a_run):
    _, output = block_a_run
    request = _read(output / "provider" / "A2" / "attempt_01" / "provider_request.json")
    assert "target attractiveness" in request["prohibited_conclusions"]


def test_12_a3_excludes_block_b_analysis(block_a_run):
    _, output = block_a_run
    request = _read(output / "provider" / "A3" / "attempt_01" / "provider_request.json")
    assert {"valuation", "pricing", "financing", "returns", "quantified synergy"}.issubset(request["prohibited_conclusions"])


def test_13_a4_preserves_alternative_class_without_target_universe(block_a_run):
    _, output = block_a_run
    result = _read(output / "modules" / MODULE_FILENAMES["A4"])["final_result"]
    assert "Commercial partnership" in result["structured_output"]["alternatives"]
    assert "complete target universe" in _read(output / "provider" / "A4" / "attempt_01" / "provider_request.json")["prohibited_conclusions"]


def test_14_a5_milestone_5_boundaries_remain(block_a_run):
    _, output = block_a_run
    request = _read(output / "provider" / "A5" / "attempt_01" / "provider_request.json")
    assert {"Strategic Thesis Gate", "valuation", "Block B", "Block C", "Go / No-Go"}.issubset(request["prohibited_conclusions"])


def test_15_a6_does_not_issue_legal_conclusion(block_a_run):
    _, output = block_a_run
    request = _read(output / "provider" / "A6" / "attempt_01" / "provider_request.json")
    assert "definitive antitrust legal conclusion" in request["prohibited_conclusions"]


def test_16_a7_does_not_quantify_synergy(block_a_run):
    _, output = block_a_run
    request = _read(output / "provider" / "A7" / "attempt_01" / "provider_request.json")
    assert "quantified synergy" in request["prohibited_conclusions"]


def test_17_provider_output_cannot_choose_gate_a(tmp_path):
    recording = _read(RECORDED_CASE.parent / "recordings" / "block_a_recording.json")
    payload = recording["modules"]["A1"]["attempts"][0]["structured_response"]
    payload["gate_a_result"] = "PASS"
    result = validate_provider_output(
        payload, expected_module_id="A1", expected_module_name="Transaction Context",
        require_counterevidence=True,
    )
    assert result.status.value == "REJECTED"
    assert any(row["type"] == "PROVIDER_GATE_AUTHORITY_VIOLATION" for row in result.errors)


def test_18_duplicate_source_candidate_is_rejected_not_admitted(block_a_run):
    _, output = block_a_run
    rejected = _read(output / "provider" / "A3" / "attempt_01" / "rejected_objects.json")
    admitted = _read(output / "provider" / "A3" / "attempt_01" / "admitted_objects.json")
    assert any(row["object_type"] == "DUPLICATE_SOURCE_CANDIDATE" for row in rejected)
    assert admitted["sources"] == []


def test_19_duplicate_source_does_not_inflate_diversity(block_a_run):
    _, output = block_a_run
    sources = _read(output / "research" / "sources.json")
    identities = [tuple(row["source_identity"]) for row in sources]
    assert len(identities) == len(set(identities))
    assert not any(row["source_id"].startswith("SRC-A3-DUP") for row in sources)


def test_20_source_versions_remain_distinct(block_a_run):
    _, output = block_a_run
    sources = _read(output / "research" / "sources.json")
    versions = {row.get("version") for row in sources if row.get("document_identity") == "regulated-workflow-industry-series"}
    assert versions == {"2026-Q1", "2026-Q2"}


def test_21_shared_source_records_every_module_use(block_a_run):
    _, output = block_a_run
    sources = {row["source_id"]: row for row in _read(output / "research" / "sources.json")}
    uses = {row["owning_module"] for row in sources["SRC-A2-OFFICIAL-001"]["module_uses"]}
    assert uses == {"A2", "A3"}


def test_22_attachment_provenance_is_preserved(block_a_run):
    _, output = block_a_run
    source = next(row for row in _read(output / "research" / "sources.json") if row["source_id"] == "SRC-BA-ATT-001")
    assert source["file_hash_sha256"] and source["original_filename"] == "target_capability_brief.md"
    assert {row["owning_module"] for row in source["module_uses"]} == {"A5"}


def test_23_each_module_preserves_counterevidence(block_a_run):
    _, output = block_a_run
    rows = _read(output / "research" / "counterevidence.json")
    assert set(BLOCK_A_MODULE_NAMES) == {row["owning_module_id"] for row in rows}


def test_24_material_conflict_remains_visible(block_a_run):
    _, output = block_a_run
    conflicts = _read(output / "research" / "conflicts.json")
    assert any(row["materiality"] == "material" and row["resolution_status"] == "CONDITION_OPEN" for row in conflicts)
    gate = _read(output / "gate_a" / "gate_a_result.json")["final_result"]
    conflict_criterion = next(row for row in gate["criterion_results"] if row["criterion_id"] == "GA-CONFLICTS")
    assert conflict_criterion["outcome"] == "CONDITION"


def test_25_conflicting_estimates_keep_scope_date_and_versions(block_a_run):
    _, output = block_a_run
    sources = _read(output / "research" / "sources.json")
    rows = [row for row in sources if row.get("document_identity") == "regulated-workflow-industry-series"]
    assert {(row["publication_date"], row["version"]) for row in rows} == {("2026-04-01", "2026-Q1"), ("2026-06-25", "2026-Q2")}


def test_26_initial_failure_maps_to_smallest_module(block_a_run):
    _, output = block_a_run
    gap = _read(output / "loop" / "gaps.json")[0]
    assert gap["originating_module"] == "A6"
    assert gap["gap_type"] == "SOURCE_DIVERSITY_GAP"


def test_27_repair_question_is_narrower_and_not_repeated(block_a_run):
    _, output = block_a_run
    replan = _read(output / "loop" / "replans.json")[0]
    attempts = [row for row in _read(output / "loop" / "research_attempts.json") if row["module_id"] == "A6"]
    assert replan["target_module"] == "A6"
    assert replan["narrower_follow_up_question"] == attempts[1]["question"]
    assert attempts[0]["question"].lower() != attempts[1]["question"].lower()


def test_28_module_history_is_append_only(block_a_run):
    _, output = block_a_run
    assert len(_read(output / "modules" / MODULE_FILENAMES["A6"])["history"]) == 2
    assert len(_read(output / "modules" / MODULE_FILENAMES["A3"])["history"]) == 2
    assert len(_read(output / "modules" / MODULE_FILENAMES["A7"])["history"]) == 2
    assert _read(output / "loop" / "loop_state.json")["history_is_append_only"] is True


def test_29_budget_and_no_progress_controls_are_recorded(block_a_run):
    _, output = block_a_run
    state = _read(output / "loop" / "loop_state.json")
    assert state["provider_request_count"] == 10
    assert state["provider_request_count"] <= state["maximum_provider_requests"]
    assert _read(output / "loop" / "replans.json")[0]["prior_queries_repeated"] is False


def test_30_gate_a_executes_all_seventeen_criteria(block_a_run):
    _, output = block_a_run
    gate = _read(output / "gate_a" / "gate_a_result.json")["final_result"]
    assert len(gate["criterion_results"]) == 17
    assert gate["certification_summary"]["provider_selected_gate_result"] is False


def test_31_certified_claims_cannot_hide_missing_a4(block_a_run):
    _, output = block_a_run
    case_data, modules, registry, certification = _gate_inputs(output)
    modules.pop("A4")
    gate = evaluate_block_a_gate(
        case_data=case_data, module_results=modules, registry=registry,
        certification=certification, iteration=9, open_gaps=[],
    )
    assert gate["status"] == "FAIL_RESEARCH_GAP"
    assert "GA-A4" in gate["failed_criteria"]


def test_32_strategic_fit_prose_cannot_hide_missing_a6(block_a_run):
    _, output = block_a_run
    case_data, modules, registry, certification = _gate_inputs(output)
    modules.pop("A6")
    gate = evaluate_block_a_gate(
        case_data=case_data, module_results=modules, registry=registry,
        certification=certification, iteration=9, open_gaps=[],
    )
    assert gate["status"] == "FAIL_RESEARCH_GAP"
    assert "GA-A6" in gate["failed_criteria"]


def test_33_human_review_boundary_remains_visible(block_a_run):
    _, output = block_a_run
    gate = _read(output / "gate_a" / "gate_a_result.json")["final_result"]
    assert gate["human_review_items"]
    assert any(row["originating_module"] == "A5" for row in gate["human_review_items"])


def test_34_recorded_case_ends_conditional_pass(block_a_run):
    result, output = block_a_run
    assert result.outcome.value == "CONDITIONAL_PASS"
    assert _read(output / "run_summary.json")["gate_a_result"] == "CONDITIONAL_PASS"
    assert _read(output / "loop" / "iteration_records.json")[0]["gate_a_result"] == "FAIL_RESEARCH_GAP"


def test_35_deterministic_block_a_uses_same_contract_path(tmp_path):
    result = run_block_a_case(
        RECORDED_CASE, tmp_path / "deterministic", provider="deterministic", module="BLOCK_A"
    )
    assert result.provider_mode == ProviderMode.DETERMINISTIC
    trace = _read(Path(result.output_dir) / "provider" / "A1" / "attempt_01" / "provider_trace.json")
    assert trace["provider_type"] == "deterministic"
    assert trace["validation_outcome"] == "ACCEPTED"


def test_36_recorded_and_live_use_the_same_research_contract_schema():
    contract = next(item for item in load_module_contracts() if item.module_id == "A6")
    schema = block_a_provider_output_schema(contract)
    assert set(schema["properties"]) >= {"sources", "evidence", "claims", "counterevidence", "conflicts", "module_assessment"}
    assert set(schema["properties"]["module_assessment"]["properties"]["structured_output"]["properties"]) == set(contract.structured_output_fields)


def test_37_openai_live_never_silently_falls_back(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(ProviderConfigurationError):
        run_block_a_case(
            RECORDED_CASE, tmp_path / "live", provider="openai_live",
            module="BLOCK_A", enable_live=True,
        )


def test_38_provider_validation_error_is_technical_not_business_gap(tmp_path):
    case_path = _copy_case(tmp_path)
    recording_path = case_path.parent / "recordings" / "block_a_recording.json"
    recording = _read(recording_path)
    recording["modules"]["A1"]["attempts"][0]["structured_response"]["gate_a_result"] = "PASS"
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    result = run_block_a_case(case_path, tmp_path / "invalid", provider="recorded", module="BLOCK_A")
    assert result.outcome.value == "FAILED_TECHNICAL"
    assert _read(Path(result.output_dir) / "loop" / "gaps.json") == []
    assert _read(Path(result.output_dir) / "loop" / "controller_decisions.json")[-1]["business_gap_created"] is False


def test_39_raw_output_remains_separate_from_admitted_objects(block_a_run):
    _, output = block_a_run
    raw = _read(output / "provider" / "A3" / "attempt_01" / "provider_response_raw.json")
    admitted = _read(output / "provider" / "A3" / "attempt_01" / "admitted_objects.json")
    assert raw["recorded_response"]["sources"][0]["source_id"] == "SRC-A3-DUP-A2"
    assert admitted["sources"] == []


def test_40_required_output_structure_exists(block_a_run):
    _, output = block_a_run
    required = [
        "planning/block_a_research_plan.json", "planning/dependency_graph.json",
        "planning/research_questions.json", "planning/prompt_manifest.json",
        "research/sources.json", "research/evidence.json", "research/claims.json",
        "research/assumptions.json", "research/unknowns.json",
        "research/counterevidence.json", "research/conflicts.json",
        "verification/evidence_quality_results.json", "verification/pce_results.json",
        "verification/er_brb_results.json", "gate_a/criterion_results.json",
        "gate_a/gate_a_result.json", "loop/gaps.json", "loop/research_attempts.json",
        "loop/replans.json", "loop/controller_decisions.json",
        "loop/iteration_records.json", "loop/dependency_invalidations.json",
        "loop/loop_state.json", "state/terminal_state_history.json",
        "state/final_terminal_state.json",
    ]
    required.extend(f"modules/{value}" for value in MODULE_FILENAMES.values())
    assert all((output / value).is_file() for value in required)


def test_41_recorded_configuration_check_makes_no_paid_request():
    check = check_block_a_configuration(RECORDED_CASE, provider="recorded", module="BLOCK_A")
    assert check["ready"] is True
    assert check["paid_request_made"] is False


def test_42_live_configuration_dry_run_makes_no_paid_request(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    check = check_block_a_configuration(RECORDED_CASE, provider="openai_live", module="BLOCK_A")
    assert check["ready"] is False
    assert check["paid_request_made"] is False
    assert "NOT_CHECKED" in check["network_available"]


def test_43_confidential_attachment_permission_is_enforced(tmp_path):
    case_path = _copy_case(tmp_path)
    case_data = _read(case_path)
    case_data["research"]["attachments"][0]["confidentiality"] = "confidential"
    case_data["research"]["attachments"][0]["allow_provider_upload"] = False
    case_path.write_text(json.dumps(case_data), encoding="utf-8")
    check = check_block_a_configuration(case_path, provider="openai_live", module="BLOCK_A")
    assert check["blocked_attachments"]
    assert check["paid_request_made"] is False


def test_44_plaintext_credentials_in_case_are_rejected(tmp_path):
    case_path = _copy_case(tmp_path)
    case_data = _read(case_path)
    case_data["provider"]["api_key"] = "prohibited"
    case_path.write_text(json.dumps(case_data), encoding="utf-8")
    check = check_block_a_configuration(case_path, provider="recorded", module="BLOCK_A")
    assert check["ready"] is False
    assert any("credential" in row.lower() for row in check["issues"])


def test_45_no_credentials_or_banned_case_content_in_outputs(block_a_run):
    _, output = block_a_run
    text = "\n".join(path.read_text(encoding="utf-8") for path in output.rglob("*.json")).lower()
    assert "sk-" not in text
    forbidden = ("app" + "le", "dar" + "win" + "ai")
    assert all(value not in text for value in forbidden)


def test_46_live_template_has_no_credentials_or_fake_party_facts():
    template = _read(LIVE_TEMPLATE)
    assert "api_key" not in json.dumps(template).lower()
    assert template["mandate"]["buyer_name"] == ""
    assert template["mandate"]["target_name"] == ""
    assert template["mandate"]["unknown_terms"]
