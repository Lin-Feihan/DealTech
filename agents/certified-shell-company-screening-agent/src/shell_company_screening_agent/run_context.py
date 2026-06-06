from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

@dataclass(frozen=True)
class RunContext:
    repo_root: Path
    example_dir: Path
    config_path: Path
    run_id: str
    started_at: str

    @classmethod
    def for_example(cls, repo_root: Path, example: str = 'tuntun_hk', config: str | None = None) -> 'RunContext':
        started = datetime.now(timezone.utc).isoformat(timespec='seconds')
        run_id = 'run_current_demo_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        example_dir = repo_root / 'examples' / example
        return cls(
            repo_root=repo_root,
            example_dir=example_dir,
            config_path=repo_root / (config or f'examples/{example}/case_config.yaml'),
            run_id=run_id,
            started_at=started,
        )
