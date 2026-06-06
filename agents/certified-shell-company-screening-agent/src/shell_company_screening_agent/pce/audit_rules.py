from __future__ import annotations

def normalize_legacy_status(status: str) -> str:
    mapping = {
        'Certified': 'Certified',
        'Certified with DD Issues': 'Certified with Caveat',
        'Needs Human Review': 'Needs Human Review',
        'Rejected': 'Not Certified',
        'Insufficient Evidence': 'Internal Trace Only',
        '': 'Needs Human Review',
    }
    return mapping.get(status or '', 'Needs Human Review')
