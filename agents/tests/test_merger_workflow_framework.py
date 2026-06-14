from dealtech_certification.engine import run_agent_case, REPO_ROOT


def test_merger_workflow_diagram_integrated_without_fake_case():
    diagram = (REPO_ROOT / 'agents' / 'merger-strategy-agent' / '01_business_workflow' / 'workflow_diagram.mmd').read_text(encoding='utf-8')
    assert 'Transaction Overview' in diagram
    assert 'Strategic Rationale' in diagram
    assert 'Valuation and Walkaway Price' in diagram
    assert 'Synergies & Value Creation' in diagram
    assert 'Regulatory & Antitrust Risk' in diagram
    assert 'Final Recommendation' in diagram
    result = run_agent_case('merger-strategy')
    assert result.status == 'Framework only'
    assert result.sources_loaded == 0
    assert result.evidence_records_loaded == 0
    assert result.claims_checked == 0
    assert 'Business workflow integrated from provided flowchart' in result.reason
