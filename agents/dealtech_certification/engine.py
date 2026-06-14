from __future__ import annotations

from pathlib import Path
from .models import AgentConfig, CasePaths, RunResult
from .data_sources import load_source_registry
from .evidence import load_evidence_table, load_claim_to_evidence_map
from .er_brb import run_er_brb
from .pce import run_pce
from .output import write_outputs, write_framework_only
from .business_metrics import load_business_metrics
from .shell_scope import build_shell_scoped_claim_sample, scoped_rows_as_pce_results, scoped_rows_as_er_brb_results

REPO_ROOT = Path(__file__).resolve().parents[1]

AGENTS: dict[str, AgentConfig] = {
    'shell-company-screening': AgentConfig(
        slug='shell-company-screening',
        package='shell_company_screening_agent',
        display_name='Shell Company Screening',
        doc_dir=REPO_ROOT / 'agents' / 'shell-company-screening-agent',
        default_case='case_001_tonton_shell_company_screening',
    ),
    'spac-target-acquisition': AgentConfig(
        slug='spac-target-acquisition',
        package='spac_target_acquisition_agent',
        display_name='SPAC Target Acquisition',
        doc_dir=REPO_ROOT / 'agents' / 'spac-target-acquisition-agent',
        default_case='case_001_soren_spac_target_acquisition',
    ),
    'acquisition-strategy': AgentConfig(
        slug='acquisition-strategy',
        package='acquisition_strategy_agent',
        display_name='Acquisition Strategy',
        doc_dir=REPO_ROOT / 'agents' / 'acquisition-strategy-agent',
        default_case='case_001_acquisition_strategy',
        allowed_views=('buyer_side', 'target_side'),
    ),
    'merger-strategy': AgentConfig(
        slug='merger-strategy',
        package='merger_strategy_agent',
        display_name='Merger Strategy',
        doc_dir=REPO_ROOT / 'agents' / 'merger-strategy-agent',
        framework_only=True,
        framework_reason='Business workflow integrated from provided flowchart; ER/BRB and PCE framework ready; real case input pending.',
    ),
}
ALIASES = {cfg.package: slug for slug, cfg in AGENTS.items()}
ALIASES.update({slug.replace('-', '_'): slug for slug in AGENTS})


def _run_reason_from_pce(pce_result: dict) -> str:
    status = pce_result.get('overall_status', '')
    summary = pce_result.get('summary', {})
    if status == 'Needs Human Review':
        return 'PCE audit completed; not all claims are certified. Final delivery remains constrained by unresolved source replay, calculation replay, and human review requirements.'
    if status == 'Not Certified':
        return 'PCE audit completed; one or more material claims are not certified under the registered evidence and calculation boundary.'
    if status == 'Certified with Caveat':
        return 'PCE executed; final certification is caveated and requires visible delivery limitations.'
    if summary.get('human_review_required_claims') or summary.get('calculation_replay_required_claims'):
        return 'PCE executed; final certification remains limited by human-review, source, and calculation constraints.'
    return 'PCE executed; all certified claims remain within the current registered evidence boundary.'


def get_agent_config(agent: str) -> AgentConfig:
    key = agent.strip()
    key = ALIASES.get(key, key)
    if key not in AGENTS:
        raise KeyError(f"Unknown agent {agent!r}. Available: {', '.join(sorted(AGENTS))}")
    return AGENTS[key]


def resolve_case_paths(config: AgentConfig, case: str | None, view: str | None) -> CasePaths:
    if config.framework_only:
        out = config.doc_dir / '07_case_studies' / '_framework_only_run'
        return CasePaths(agent_dir=config.doc_dir, case_dir=None, output_dir=out, view=view)
    case_id = case or config.default_case
    if not case_id:
        raise ValueError(f'{config.slug} requires --case')
    case_root = config.doc_dir / '07_case_studies' / case_id
    if config.allowed_views:
        if view not in config.allowed_views:
            raise ValueError(f'{config.slug} requires --view one of {config.allowed_views}')
        case_dir = case_root / view
    else:
        case_dir = case_root
    if not case_dir.exists():
        raise FileNotFoundError(f'Case directory not found: {case_dir}')
    return CasePaths(agent_dir=config.doc_dir, case_dir=case_dir, output_dir=case_dir, view=view)


def run_agent_case(agent: str, case: str | None = None, view: str | None = None) -> RunResult:
    config = get_agent_config(agent)
    paths = resolve_case_paths(config, case, view)
    if config.framework_only:
        files = write_framework_only(paths.output_dir, config.display_name, config.framework_reason)
        return RunResult(
            agent=config.display_name,
            agent_slug=config.slug,
            case_id=case,
            view=view,
            status='Framework only',
            reason=config.framework_reason,
            output_written_to=str(paths.output_dir),
            output_files=[str(p) for p in files],
        )

    assert paths.case_dir is not None
    sources = load_source_registry(paths.case_dir, paths.agent_dir)
    evidence = load_evidence_table(paths.case_dir, paths.agent_dir)
    claims = load_claim_to_evidence_map(paths.case_dir, evidence)
    er_results = run_er_brb(evidence, sources, claims)
    pce_result = run_pce(case or config.default_case or paths.case_dir.name, config.slug, paths.case_dir, evidence, sources, claims, er_results)
    if config.slug == 'shell-company-screening':
        scoped_sample = build_shell_scoped_claim_sample(paths.case_dir)
        if scoped_sample.get('rows'):
            er_results.extend(scoped_rows_as_er_brb_results(scoped_sample))
            pce_result['claim_results'].extend(scoped_rows_as_pce_results(scoped_sample))
            pce_result['scoped_claim_sample'] = scoped_sample
            pce_result['summary'] = {
                'claims_checked': len(pce_result['claim_results']),
                'human_review_required_claims': sum(1 for r in pce_result['claim_results'] if r['checks']['human_review_required']),
                'imported_artifact_claims': sum(1 for r in pce_result['claim_results'] if r['checks']['is_imported_artifact']),
                'calculation_replay_required_claims': sum(1 for r in pce_result['claim_results'] if r['checks']['calculation_replay_required']),
            }
    business_metrics = load_business_metrics(config.slug, paths.case_dir, pce_result)
    files = write_outputs(paths.output_dir, config.display_name, case or config.default_case or paths.case_dir.name, view, sources, evidence, er_results, pce_result, business_metrics)
    return RunResult(
        agent=config.display_name,
        agent_slug=config.slug,
        case_id=case or config.default_case,
        view=view,
        status=pce_result['overall_status'],
        reason=_run_reason_from_pce(pce_result),
        sources_loaded=len(sources),
        evidence_records_loaded=len(evidence),
        claims_checked=len(pce_result['claim_results']),
        er_brb_completed=True,
        pce_completed=True,
        output_written_to=str(paths.output_dir),
        output_files=[str(p) for p in files],
        business_metrics=business_metrics,
        source_registry=[s.__dict__ for s in sources],
        evidence_records=[e.__dict__ for e in evidence],
        er_brb_results=er_results,
        pce_result=pce_result,
    )


def format_cli_result(result: RunResult) -> str:
    def _display_path(path_str: str | None) -> str:
        if not path_str:
            return ''
        path = Path(path_str)
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    lines = [f'Agent: {result.agent}']
    if result.case_id:
        lines.append(f'Case: {result.case_id}')
    if result.view:
        lines.append(f'View: {result.view}')
    lines.extend([
        f'Sources loaded: {result.sources_loaded}',
        f'Evidence records loaded: {result.evidence_records_loaded}',
        f'Claims checked: {result.claims_checked}',
        f'ER/BRB completed: {"Yes" if result.er_brb_completed else "No"}',
        f'PCE completed: {"Yes" if result.pce_completed else "No"}',
        f'Overall status: {result.status}',
        f'Reason: {result.reason}',
        f'Output written to: {_display_path(result.output_written_to)}',
    ])
    if result.business_metrics:
        metric_labels = [
            ('candidate_universe_count', 'Candidate universe count'),
            ('hard_filter_pass_count', 'Hard filter pass count'),
            ('hard_filter_fail_count', 'Hard filter fail count'),
            ('retained_candidate_count', 'Retained candidate count'),
            ('excluded_candidate_count', 'Excluded candidate count'),
            ('DD_evidence_count', 'DD evidence count'),
            ('DD_evidence_record_count', 'DD evidence record count'),
            ('risk_count', 'Risk count'),
            ('risk_matrix_item_count', 'Risk matrix item count'),
            ('calculation_count', 'Calculation count'),
            ('calculation_sheet_row_count', 'Calculation sheet row count'),
            ('ER_BRB_rows_count', 'ER/BRB rows count'),
            ('PCE_claims_checked', 'PCE claims checked'),
            ('PCE_audit_row_count', 'PCE audit row count'),
            ('human_review_required_count', 'Human review required count'),
            ('human_review_count', 'Human review count'),
            ('blocked_claim_count', 'Blocked claim count'),
            ('final_delivery_allowed_count', 'Final delivery allowed count'),
            ('final_certification_status', 'Final certification status'),
            ('overall_status', 'Overall status'),
            ('evidence_count', 'Evidence count'),
            ('strategic_rationale_count', 'Strategic rationale count'),
            ('integration_risk_count', 'Integration risk count'),
            ('strategic_alternative_count', 'Strategic alternative count'),
            ('offer_attractiveness_criteria_count', 'Offer-attractiveness criteria count'),
        ]
        lines.append('Business workflow metrics:')
        for key, label in metric_labels:
            if key in result.business_metrics:
                lines.append(f'- {label}: {result.business_metrics[key]}')
    if result.agent_slug == 'spac-target-acquisition':
        lines.extend([
            'SPAC / Apify provenance:',
            '- No authenticated Apify run was executed in this version.',
            '- Imported artifact is not primary evidence by itself.',
            '- Overall status: Needs Human Review.',
        ])
    return '\n'.join(lines)
