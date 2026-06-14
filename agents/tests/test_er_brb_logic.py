from dealtech_certification.engine import run_agent_case


def test_er_brb_outputs_claim_level_results():
    result = run_agent_case('shell-company-screening', 'case_001_tonton_shell_company_screening')
    assert result.er_brb_results
    row = result.er_brb_results[0]
    assert {'claim_id', 'evidence_id', 'source_id', 'evidence_reliability', 'business_risk', 'regulatory_risk', 'certification_status', 'human_review_required'} <= set(row)


def test_imported_artifact_requires_review_in_er_brb():
    result = run_agent_case('spac-target-acquisition', 'case_001_soren_spac_target_acquisition')
    imported = [r for r in result.er_brb_results if r['source_id'] == 'SRC-SPAC-001']
    assert imported
    assert all(r['human_review_required'] for r in imported)
    assert all(r['certification_status'] in {'Needs Human Review', 'Certified with Caveat'} for r in imported)
