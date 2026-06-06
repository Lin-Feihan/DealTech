from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from shell_company_screening_agent.cli import main

raise SystemExit(main(['--repo-root', str(REPO_ROOT), 'run-tuntun-hk-demo']))
