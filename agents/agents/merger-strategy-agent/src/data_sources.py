from dealtech_certification.engine import get_agent_config, resolve_case_paths
from dealtech_certification.data_sources import load_source_registry as _load_source_registry

AGENT_SLUG = 'merger-strategy'


def load_source_registry(case=None, view=None):
    config = get_agent_config(AGENT_SLUG)
    paths = resolve_case_paths(config, case, view)
    return [s.__dict__ for s in _load_source_registry(paths.case_dir, paths.agent_dir)]
