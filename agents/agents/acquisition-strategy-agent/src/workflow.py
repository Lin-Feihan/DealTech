from dealtech_certification.engine import run_agent_case

AGENT_SLUG = 'acquisition-strategy'

VIEW_WORKFLOW_STEPS = {
    'buyer_side': [
        'Strategic rationale',
        'Target attractiveness',
        'Synergy assessment',
        'Valuation / pricing',
        'Integration risk',
        'Go / no-go recommendation',
    ],
    'target_side': [
        'Offer attractiveness',
        'Standalone case',
        'Strategic alternatives',
        'Fairness assessment',
        'Deal certainty',
        'Accept / reject / negotiate recommendation',
    ],
}


def describe_workflow(view=None):
    if view:
        return {'agent': AGENT_SLUG, 'view': view, 'workflow_steps': VIEW_WORKFLOW_STEPS[view]}
    return {'agent': AGENT_SLUG, 'views': VIEW_WORKFLOW_STEPS}


def run_workflow(case=None, view=None):
    result = run_agent_case(AGENT_SLUG, case=case, view=view).to_dict()
    result['workflow_steps_executed'] = VIEW_WORKFLOW_STEPS.get(view, [])
    return result
