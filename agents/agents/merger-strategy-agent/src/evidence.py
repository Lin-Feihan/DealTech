from dealtech_certification.engine import get_agent_config, resolve_case_paths
from dealtech_certification.evidence import load_evidence_table as _load_evidence_table, load_claim_to_evidence_map as _load_claim_to_evidence_map

AGENT_SLUG = 'merger-strategy'


def load_evidence_table(case=None, view=None):
    config = get_agent_config(AGENT_SLUG)
    paths = resolve_case_paths(config, case, view)
    return [e.__dict__ for e in _load_evidence_table(paths.case_dir, paths.agent_dir)]


def load_claim_to_evidence_map(case=None, view=None):
    config = get_agent_config(AGENT_SLUG)
    paths = resolve_case_paths(config, case, view)
    evidence = _load_evidence_table(paths.case_dir, paths.agent_dir) if paths.case_dir else []
    return [c.__dict__ for c in _load_claim_to_evidence_map(paths.case_dir, evidence)]
