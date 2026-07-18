from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from agents.buyer_side_acquisition_loop_agent.a5_research_runtime import (
    check_a5_configuration,
    run_a5_research_case,
)
from agents.buyer_side_acquisition_loop_agent.attachment_ingestion import (
    AttachmentValidationError,
    prepare_attachments,
)
from agents.buyer_side_acquisition_loop_agent.business_contracts import (
    load_module_contracts,
    load_prompt_registry,
)
from agents.buyer_side_acquisition_loop_agent.live_research_models import (
    A5Outcome,
    ProviderConfigurationError,
    ProviderExecution,
    ProviderMode,
)
from agents.buyer_side_acquisition_loop_agent.live_research_provider import (
    build_provider_bundle,
)
from agents.buyer_side_acquisition_loop_agent.provider_validation import (
    validate_provider_output,
)
from agents.buyer_side_acquisition_loop_agent.runtime import run_case
from agents.buyer_side_acquisition_loop_agent.storage import load_case


AGENT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "buyer_side_acquisition_loop_agent"
RECORDED_CASE = AGENT_ROOT / "06_examples" / "recorded_a5_provider_case" / "case.yaml"
COMPLETE_CASE = AGENT_ROOT / "06_examples" / "synthetic_complete_acquisition_case" / "case.yaml"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_case(tmp_path: Path) -> Path:
    target = tmp_path / "case"
    shutil.copytree(RECORDED_CASE.parent, target)
    return target / "case.yaml"


@pytest.fixture(scope="module")
def recorded_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("m5_recorded") / "run"
    result = run_a5_research_case(RECORDED_CASE, output, provider="recorded", module="A5")
    return result, output


@pytest.fixture
def initial_payload():
    recording = _read(RECORDED_CASE.parent / "recordings" / "a5_recording.json")
    payload = copy.deepcopy(recording["attempts"][0]["structured_response"])
    case_data = load_case(RECORDED_CASE)
    attachments, _ = prepare_attachments(
        case_dir=RECORDED_CASE.parent,
        manifest=case_data["research"]["attachments"],
        provider_mode=ProviderMode.RECORDED,
    )
    from agents.buyer_side_acquisition_loop_agent.attachment_ingestion import attachment_source

    payload["sources"].append(attachment_source(attachments[0]))
    return payload


def test_01_deterministic_mode_remains_unchanged(tmp_path):
    result = run_case(COMPLETE_CASE, tmp_path / "deterministic")
    assert result["run_summary"]["decision_state"].value == "PROCEED_WITH_CONDITIONS"
    assert result["run_summary"]["schema_version"] == "milestone-4"


def test_02_recorded_and_live_execution_use_same_bundle_contract(recorded_run):
    _, output = recorded_run
    request_data = _read(output / "provider" / "provider_request.json")[0]
    from agents.buyer_side_acquisition_loop_agent.business_models import BusinessBlock, ResearchRequest

    request_data["owning_block"] = BusinessBlock(request_data["owning_block"])
    request = ResearchRequest(**request_data)
    structured = _read(output / "provider" / "attempt_01" / "provider_response_raw.json")["recorded_response"]
    execution = ProviderExecution(
        provider_type=ProviderMode.OPENAI_LIVE,
        model_identifier="contract-test",
        response_id="RESP-CONTRACT-TEST",
        structured_response=structured,
        raw_response={"id": "RESP-CONTRACT-TEST"},
        trace={},
        tool_calls=[],
        search_queries=structured["searched_queries"],
        returned_citations=structured["returned_citations"],
    )
    contract = next(item for item in load_module_contracts() if item.module_id == "A5")
    live_contract_bundle = build_provider_bundle(execution=execution, request=request, contract=contract)
    required = {
        "provider_response_raw", "provider_trace", "tool_calls", "search_queries",
        "returned_citations", "validation_result", "admitted_objects", "rejected_objects",
    }
    assert required.issubset(live_contract_bundle.provider_artifacts)


def test_03_live_provider_is_not_used_without_explicit_selection(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("live provider was selected implicitly")

    monkeypatch.setattr(
        "agents.buyer_side_acquisition_loop_agent.live_research_provider.OpenAIResearchProvider.research",
        forbidden,
    )
    assert run_case(COMPLETE_CASE, tmp_path / "deterministic")["run_summary"]["schema_version"] == "milestone-4"


def test_04_openai_live_never_falls_back_to_recorded(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    result = run_a5_research_case(
        RECORDED_CASE, tmp_path / "no-fallback", provider="openai_live", module="A5"
    )
    assert result.outcome == A5Outcome.FAILED_TECHNICAL
    trace = _read(Path(result.output_dir) / "provider" / "provider_trace.json")[0]
    assert trace["provider_type"] == "openai_live"


def test_05_api_key_is_not_serialized(monkeypatch):
    secret = "test-secret-that-must-not-appear"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    check = check_a5_configuration(RECORDED_CASE, provider="openai_live", module="A5")
    assert secret not in json.dumps(check)
    assert check["api_key_value_serialized"] is False


def test_06_case_plaintext_credentials_are_rejected(tmp_path):
    case_path = _copy_case(tmp_path)
    case_data = _read(case_path)
    case_data["provider"]["api_key"] = "prohibited"
    case_path.write_text(json.dumps(case_data), encoding="utf-8")
    check = check_a5_configuration(case_path, provider="recorded", module="A5")
    assert check["ready"] is False
    assert any("credential" in item.lower() for item in check["issues"])


def test_07_confidential_file_is_not_sent_without_permission(tmp_path):
    case_path = _copy_case(tmp_path)
    case_data = _read(case_path)
    case_data["research"]["attachments"][0]["confidentiality"] = "confidential"
    case_data["research"]["attachments"][0]["allow_provider_upload"] = False
    case_path.write_text(json.dumps(case_data), encoding="utf-8")
    result = run_a5_research_case(case_path, tmp_path / "blocked", provider="openai_live", module="A5")
    assert result.outcome == A5Outcome.AWAITING_HUMAN_REVIEW
    assert result.attempts == 0
    assert _read(Path(result.output_dir) / "provider" / "tool_calls.json") == [[]]


def test_08_orphan_evidence_is_rejected(initial_payload):
    payload = copy.deepcopy(initial_payload)
    payload["evidence"][0]["source_id"] = "SRC-NOT-REGISTERED"
    result = validate_provider_output(payload)
    assert result.status.value == "REJECTED"
    assert any(item["type"] == "ORPHAN_EVIDENCE" for item in result.errors)


def test_09_orphan_claim_is_rejected(initial_payload):
    payload = copy.deepcopy(initial_payload)
    payload["claims"][0]["supporting_evidence_ids"] = ["EV-NOT-REGISTERED"]
    result = validate_provider_output(payload)
    assert any(item["type"] == "ORPHAN_CLAIM" for item in result.errors)


def test_10_duplicate_ids_are_rejected(initial_payload):
    payload = copy.deepcopy(initial_payload)
    payload["evidence"][1]["evidence_id"] = payload["evidence"][0]["evidence_id"]
    result = validate_provider_output(payload)
    assert any(item["type"] == "DUPLICATE_ID" for item in result.errors)


def test_11_unsupported_citation_is_rejected(initial_payload):
    payload = copy.deepcopy(initial_payload)
    payload["returned_citations"].append(
        {"url": "https://unsupported.example.invalid", "title": "unsupported", "start_index": 0, "end_index": 1}
    )
    result = validate_provider_output(payload)
    assert any(item["type"] == "UNSUPPORTED_CITATION" for item in result.errors)


def test_12_malformed_output_does_not_enter_memory(tmp_path):
    case_path = _copy_case(tmp_path)
    recording_path = case_path.parent / "recordings" / "a5_recording.json"
    recording = _read(recording_path)
    del recording["attempts"][0]["structured_response"]["claims"]
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    result = run_a5_research_case(case_path, tmp_path / "malformed", provider="recorded", module="A5")
    assert result.outcome == A5Outcome.FAILED_TECHNICAL
    assert all(not values for values in result.admitted_objects.values())
    assert _read(Path(result.output_dir) / "provider" / "provider_response_raw.json")


def test_13_raw_response_and_admitted_objects_are_separate(recorded_run):
    _, output = recorded_run
    raw = _read(output / "provider" / "provider_response_raw.json")
    admitted = _read(output / "provider" / "admitted_objects.json")
    assert raw != admitted
    assert len(raw) == len(admitted) == 2


def test_14_search_snippet_cannot_satisfy_claim(initial_payload):
    payload = copy.deepcopy(initial_payload)
    payload["evidence"][0]["evidence_type"] = "search-result snippet only"
    result = validate_provider_output(payload)
    assert any(item["type"] == "SEARCH_SNIPPET_ONLY" for item in result.errors)


def test_15_model_prose_is_not_evidence(initial_payload):
    payload = copy.deepcopy(initial_payload)
    payload["evidence"][0]["source_id"] = "model"
    result = validate_provider_output(payload)
    assert any(item["type"] in {"MODEL_PROSE_IS_NOT_EVIDENCE", "ORPHAN_EVIDENCE"} for item in result.errors)


def test_16_counterevidence_is_preserved(recorded_run):
    result, output = recorded_run
    counter = _read(output / "research" / "counterevidence.json")
    assert counter and counter[0]["counterevidence_id"] == "CE-A5-001"
    assert "CE-A5-001" in result.gate_dependency_result["counterevidence_ids"]


def test_17_unknowns_remain_explicit(recorded_run):
    _, output = recorded_run
    unknowns = _read(output / "research" / "unknowns.json")
    assert unknowns and "unavailable" in unknowns[0]["description"]


def test_18_management_source_requires_limitation(initial_payload):
    payload = copy.deepcopy(initial_payload)
    payload["sources"][0]["source_type"] = "management representation"
    payload["sources"][0]["limitations"] = ""
    result = validate_provider_output(payload)
    assert any(item["type"] == "MANAGEMENT_LIMITATION_MISSING" for item in result.errors)


def test_19_first_result_creates_precise_gap(recorded_run):
    _, output = recorded_run
    gaps = _read(output / "loop" / "gaps.json")
    assert gaps[0]["gap_type"] == "SOURCE_DIVERSITY_GAP"
    assert gaps[0]["created_iteration"] == 1


def test_20_repair_question_is_narrower_and_nonidentical(recorded_run):
    _, output = recorded_run
    replan = _read(output / "loop" / "replan.json")[0]
    assert replan["narrower_follow_up_question"] != replan["prior_question"]
    assert "two additional independent records" in replan["narrower_follow_up_question"]


def test_21_identical_question_repetition_is_prevented(tmp_path):
    case_path = _copy_case(tmp_path)
    recording_path = case_path.parent / "recordings" / "a5_recording.json"
    recording = _read(recording_path)
    original = _read(case_path)["research"]["research_question"]
    recording["attempts"][0]["structured_response"]["suggested_follow_up_questions"] = [original]
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    result = run_a5_research_case(case_path, tmp_path / "repeat", provider="recorded", module="A5")
    assert result.outcome == A5Outcome.STOPPED_NO_PROGRESS
    assert result.attempts == 1


def test_22_second_iteration_improves_a5(recorded_run):
    result, output = recorded_run
    attempts = _read(output / "loop" / "research_attempts.json")
    assert result.outcome == A5Outcome.CONDITIONAL_PASS
    assert len(attempts) == 2
    assert attempts[1]["material_progress"] is True


def test_23_private_information_routes_to_human_review(tmp_path):
    case_path = _copy_case(tmp_path)
    recording_path = case_path.parent / "recordings" / "a5_recording.json"
    recording = _read(recording_path)
    unknown = recording["attempts"][0]["structured_response"]["unknowns"][0]
    unknown["materiality"] = "material"
    unknown["human_review_required"] = True
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    result = run_a5_research_case(case_path, tmp_path / "human", provider="recorded", module="A5")
    assert result.outcome == A5Outcome.AWAITING_HUMAN_REVIEW
    assert result.attempts == 1


def test_24_attachment_provenance_and_hash_are_retained(recorded_run):
    _, output = recorded_run
    manifest = _read(output / "provider" / "attachment_manifest.json")[0]
    source = next(row for row in _read(output / "research" / "sources.json") if row["source_id"] == "SRC-A5-ATT-001")
    assert len(manifest["file_hash_sha256"]) == 64
    assert source["file_hash_sha256"] == manifest["file_hash_sha256"]
    assert source["original_filename"] == "target_capability_brief.md"


def test_25_pdf_permission_is_enforced(tmp_path):
    (tmp_path / "document.pdf").write_bytes(b"%PDF-1.4\nrecorded test")
    manifest = [{
        "attachment_id": "PDF-1", "path": "document.pdf", "original_filename": "document.pdf",
        "file_type": "pdf", "confidentiality": "confidential", "supplied_by": "case owner",
        "document_date": "2026-06-30", "allow_provider_upload": False,
    }]
    records, blocked = prepare_attachments(case_dir=tmp_path, manifest=manifest, provider_mode=ProviderMode.OPENAI_LIVE)
    assert records[0].file_type == "pdf"
    assert blocked[0]["route"] == "HUMAN_REVIEW"


@pytest.mark.parametrize("extension,locator_fragment", [("txt", "line"), ("md", "line"), ("html", "HTML"), ("csv", "rows")])
def test_26_plain_text_attachment_locators_are_preserved(tmp_path, extension, locator_fragment):
    filename = f"document.{extension}"
    content = "a,b\n1,2\n" if extension == "csv" else "section\ncontent\n"
    (tmp_path / filename).write_text(content, encoding="utf-8")
    manifest = [{
        "attachment_id": f"ATT-{extension}", "path": filename, "original_filename": filename,
        "file_type": extension, "confidentiality": "public", "supplied_by": "case owner",
        "document_date": "2026-06-30", "allow_provider_upload": True,
    }]
    records, blocked = prepare_attachments(case_dir=tmp_path, manifest=manifest, provider_mode=ProviderMode.RECORDED)
    assert not blocked
    assert locator_fragment.lower() in records[0].locator.lower()


def test_27_unsupported_attachment_type_has_clear_error(tmp_path):
    (tmp_path / "document.xlsx").write_bytes(b"not supported")
    manifest = [{
        "attachment_id": "XLSX-1", "path": "document.xlsx", "original_filename": "document.xlsx",
        "file_type": "xlsx", "confidentiality": "public", "supplied_by": "case owner",
        "document_date": "2026-06-30", "allow_provider_upload": True,
    }]
    with pytest.raises(AttachmentValidationError, match="Unsupported attachment type"):
        prepare_attachments(case_dir=tmp_path, manifest=manifest, provider_mode=ProviderMode.RECORDED)


def test_28_all_required_output_groups_exist(recorded_run):
    _, output = recorded_run
    required = [
        "provider/provider_request.json", "provider/provider_response_raw.json",
        "provider/provider_trace.json", "provider/tool_calls.json", "provider/search_queries.json",
        "provider/returned_citations.json", "provider/validation_result.json",
        "provider/admitted_objects.json", "provider/rejected_objects.json",
        "research/sources.json", "research/evidence.json", "research/claims.json",
        "research/assumptions.json", "research/unknowns.json", "research/counterevidence.json",
        "research/follow_up_questions.json", "module/target_capability_business_quality_result.json",
        "module/pce_results.json", "module/er_brb_results.json", "module/gate_dependency_result.json",
        "loop/research_attempts.json", "loop/gaps.json", "loop/replan.json",
        "loop/controller_decisions.json", "loop/iteration_records.json", "loop/loop_state.json",
        "state/terminal_state_history.json", "state/final_terminal_state.json",
    ]
    assert all((output / item).is_file() for item in required)


def test_29_provider_attempts_are_append_only(recorded_run):
    _, output = recorded_run
    assert (output / "provider" / "attempt_01" / "provider_response_raw.json").is_file()
    assert (output / "provider" / "attempt_02" / "provider_response_raw.json").is_file()
    assert len(_read(output / "provider" / "provider_trace.json")) == 2


def test_30_a5_does_not_exercise_gate_or_later_blocks(recorded_run):
    result, output = recorded_run
    summary = _read(output / "run_summary.json")
    assert result.gate_dependency_result["gate_a_evaluated"] is False
    assert summary["block_b_or_c_executed"] is False
    assert summary["final_recommendation_generated"] is False


def test_31_approved_a5_prompt_is_loaded_from_registry():
    contract = next(item for item in load_module_contracts() if item.module_id == "A5")
    prompt_id = contract.prompt_reference.rsplit("#", 1)[-1]
    prompt = load_prompt_registry()[prompt_id]
    assert prompt["prompt_id"] == "A5_TARGET_CAPABILITY_BUSINESS_QUALITY"
    assert "Gate A" in prompt["role_boundary"]


def test_32_live_dry_run_never_makes_paid_request(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    check = check_a5_configuration(RECORDED_CASE, provider="openai_live", module="A5")
    assert check["paid_request_made"] is False
    assert check["ready"] is False


def test_33_no_secret_appears_in_recorded_artifacts(recorded_run):
    _, output = recorded_run
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in output.rglob("*") if path.is_file())
    assert "OPENAI_API_KEY" not in text
    assert "Bearer " not in text


def test_34_no_legacy_case_content_appears_in_milestone_5():
    forbidden = ("app" + "le", "darwin" + "ai")
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for root in (AGENT_ROOT, PACKAGE_ROOT)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    assert all(value not in text for value in forbidden)
