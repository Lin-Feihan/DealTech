import json
from pathlib import Path
p=Path('examples/tuntun_hk/delivery/readiness_result.json')
print(p.read_text() if p.exists() else json.dumps({'ready': False, 'reason': 'run demo first'}, indent=2))
