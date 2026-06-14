from dealtech_certification.engine import get_agent_config, resolve_case_paths
from dealtech_certification.data_sources import load_source_registry


def _sources(agent, case, view=None):
    cfg = get_agent_config(agent)
    paths = resolve_case_paths(cfg, case, view)
    return load_source_registry(paths.case_dir, paths.agent_dir)


def test_source_registry_loads_structured_records():
    sources = _sources('shell-company-screening', 'case_001_tonton_shell_company_screening')
    first = sources[0]
    assert first.source_id.startswith('SRC-')
    assert first.source_name
    assert isinstance(first.PCE_eligible, bool)


def test_imported_artifact_not_tier1_primary_source():
    sources = _sources('spac-target-acquisition', 'case_001_soren_spac_target_acquisition')
    imported = next(s for s in sources if s.source_id == 'SRC-SPAC-001')
    assert imported.is_imported_artifact
    assert not imported.PCE_eligible
    assert 'Tier 1' not in imported.reliability_tier


def test_acquisition_source_replay_status_controls_pce_eligibility():
    buyer_sources = _sources('acquisition-strategy', 'case_001_acquisition_strategy', 'buyer_side')
    target_sources = _sources('acquisition-strategy', 'case_001_acquisition_strategy', 'target_side')
    by_id = {s.source_id: s for s in buyer_sources + target_sources}

    for source_id in ['SRC-ACQ-B03', 'SRC-ACQ-T03']:
        source = by_id[source_id]
        assert source.source_replay_completed
        assert source.PCE_eligible
        assert source.has_real_url_or_file

    for source_id in ['SRC-ACQ-B05', 'SRC-ACQ-T05']:
        source = by_id[source_id]
        assert source.replay_pending
        assert not source.PCE_eligible
        assert source.source_replay_status == 'pending'
