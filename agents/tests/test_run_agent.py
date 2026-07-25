from dealtech_certification.engine import run_agent_case
from dealtech_certification.engine import format_cli_result
from pathlib import Path


def test_shell_tonton_runs_certified_with_caveat():
    result = run_agent_case('shell-company-screening', 'case_001_tonton_shell_company_screening')
    assert result.sources_loaded > 0
    assert result.evidence_records_loaded > 0
    assert result.claims_checked > 0
    assert result.er_brb_completed and result.pce_completed
    assert result.status == 'Certified with Caveat'


def test_spac_soren_runs_needs_human_review():
    result = run_agent_case('spac-target-acquisition', 'case_001_soren_spac_target_acquisition')
    assert result.sources_loaded > 0
    assert result.evidence_records_loaded > 0
    assert result.status == 'Needs Human Review'
    assert 'not all claims are certified' in result.reason
    assert 'source replay' in result.reason and 'calculation replay' in result.reason


def test_acquisition_views_run_separately():
    buyer = run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'buyer_side')
    target = run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'target_side')
    assert buyer.status == 'Needs Human Review'
    assert target.status == 'Needs Human Review'
    assert buyer.view == 'buyer_side'
    assert target.view == 'target_side'
    assert {e['claim_id'] for e in buyer.evidence_records}.isdisjoint({e['claim_id'] for e in target.evidence_records})


def test_acquisition_buyer_output_uses_professional_report_layer():
    result = run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'buyer_side')
    final_text = Path(result.output_written_to, 'final_output.md').read_text(encoding='utf-8')
    assert final_text.startswith('# Buyer-side Acquisition Strategy Report')
    assert '## 4. Deal Structure and Economics' in final_text
    assert '## 6. Key Risks and Mitigants' in final_text
    assert '## 8. Buyer-side Conclusion' in final_text
    assert 'target_profile.md' in final_text
    assert 'transaction_context.md' in final_text
    assert 'CLM-' not in final_text
    assert 'EVI-' not in final_text
    assert 'SRC-' not in final_text
    assert 'PCE' not in final_text
    assert 'Apple factual background can be delivered only where source-backed' not in final_text
    assert 'DarwinAI transaction occurrence/context can be delivered only with caveats' not in final_text


def test_merger_framework_only_does_not_fake_case_run():
    result = run_agent_case('merger-strategy')
    assert result.status == 'Framework only'
    assert result.sources_loaded == 0
    assert result.evidence_records_loaded == 0
    assert result.claims_checked == 0
    assert not result.er_brb_completed
    assert not result.pce_completed


def test_cli_output_uses_repo_relative_output_path():
    result = run_agent_case('shell-company-screening', 'case_001_tonton_shell_company_screening')
    text = format_cli_result(result)
    assert '/Users/zsj/.openclaw/workspace-gf/' not in text
    assert 'agents/shell-company-screening-agent/07_case_studies/' in text


def test_acquisition_cli_output_includes_business_metrics():
    buyer = format_cli_result(run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'buyer_side'))
    target = format_cli_result(run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'target_side'))
    for label in [
        'Evidence count',
        'Calculation count',
        'ER/BRB rows count',
        'PCE claims checked',
        'Human review required count',
        'Blocked claim count',
        'Final delivery allowed count',
        'Overall status',
    ]:
        assert label in buyer
        assert label in target
    assert 'Strategic rationale count' in buyer
    assert 'Integration risk count' in buyer
    assert 'Strategic alternative count' in target
    assert 'Offer-attractiveness criteria count' in target


def test_spac_retained_candidates_are_review_slots_not_recommendations():
    result = run_agent_case('spac-target-acquisition', 'case_001_soren_spac_target_acquisition')
    text = format_cli_result(result)
    assert 'Retained candidate count' in text
    assert 'Final delivery allowed count' in text
    final_text = Path(result.output_written_to, 'final_output.md').read_text(encoding='utf-8')
    assert 'partially source-replayed screening structure' in final_text
    assert 'retained for further review only' in final_text
    assert 'not final recommended SPAC targets' in final_text
