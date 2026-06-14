from dealtech_certification.engine import get_agent_config, resolve_case_paths
from dealtech_certification.data_sources import load_source_registry
from dealtech_certification.evidence import load_evidence_table, load_claim_to_evidence_map
from dealtech_certification.er_brb import run_er_brb as _run_er_brb

AGENT_SLUG = 'acquisition-strategy'


def run_er_brb(case=None, view=None):
    config = get_agent_config(AGENT_SLUG)
    paths = resolve_case_paths(config, case, view)
    if paths.case_dir is None:
        return list()
    sources = load_source_registry(paths.case_dir, paths.agent_dir)
    evidence = load_evidence_table(paths.case_dir, paths.agent_dir)
    claims = load_claim_to_evidence_map(paths.case_dir, evidence)
    return _run_er_brb(evidence, sources, claims)
