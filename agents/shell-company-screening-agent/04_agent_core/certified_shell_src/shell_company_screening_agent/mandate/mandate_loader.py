from __future__ import annotations
from pathlib import Path

def load_mandate(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f'Mandate file not found: {path}')
    return path.read_text(encoding='utf-8', errors='replace')
