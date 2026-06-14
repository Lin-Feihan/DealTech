from dealtech_certification.engine import run_agent_case

AGENT_SLUG = 'merger-strategy'

WORKFLOW_STEPS = [
    'User intent capture',
    'LLM clarification',
    'Planning intent',
    'Transaction Overview',
    'Strategic Rationale',
    'Stakeholder Assessment',
    'Industry & Market',
    'Valuation and Walkaway Price',
    'Synergies & Value Creation',
    'Deal Structure & Financing',
    'Pro Forma Financial Impact',
    'Governance & Control',
    'Deal Diligence Findings',
    'Regulatory & Antitrust Risk',
    'Integration Plan',
    'Risk Analysis',
    'Scenario & Sensitivity Analysis',
    'Final Recommendation',
    'ER/BRB framework gate',
    'PCE framework gate',
]


def describe_workflow():
    return {
        'agent': AGENT_SLUG,
        'status': 'Business workflow integrated from provided flowchart; real case input pending.',
        'workflow_steps': WORKFLOW_STEPS,
    }


def run_workflow(case=None, view=None):
    result = run_agent_case(AGENT_SLUG, case=case, view=view).to_dict()
    result['workflow_steps_integrated'] = WORKFLOW_STEPS
    return result
