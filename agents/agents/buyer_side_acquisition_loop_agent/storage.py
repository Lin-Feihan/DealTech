from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


def to_primitive(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return to_primitive(asdict(value))
    if isinstance(value, dict):
        return {key: to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    return value


def load_case(path: Path) -> dict[str, Any]:
    """Load the milestone's JSON-compatible YAML fixture using the standard library."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("case input must be a mapping")
    return data


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_primitive(value), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
