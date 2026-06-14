from dealtech_certification.engine import get_agent_config, resolve_case_paths
from dealtech_certification.evidence import load_evidence_table, load_claim_to_evidence_map


def test_evidence_table_loads_non_empty_records():
    cfg = get_agent_config('shell-company-screening')
    paths = resolve_case_paths(cfg, 'case_001_tonton_shell_company_screening', None)
    evidence = load_evidence_table(paths.case_dir, paths.agent_dir)
    assert evidence
    assert evidence[0].evidence_id
    assert evidence[0].claim_id
    assert evidence[0].source_id


def test_claim_to_evidence_map_loads_case_file():
    cfg = get_agent_config('acquisition-strategy')
    paths = resolve_case_paths(cfg, 'case_001_acquisition_strategy', 'buyer_side')
    evidence = load_evidence_table(paths.case_dir, paths.agent_dir)
    claims = load_claim_to_evidence_map(paths.case_dir, evidence)
    assert claims
    assert all(c.claim_id.startswith('CLM-ACQ-B') for c in claims)


def test_llm_summary_is_not_evidence_property():
    from dealtech_certification.models import EvidenceRecord
    ev = EvidenceRecord(evidence_id='E', claim_id='C', source_id='S', evidence_type='LLM summary')
    assert ev.is_llm_summary
