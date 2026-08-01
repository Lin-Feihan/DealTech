from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def write_json_artifact(output_dir: Path, filename: str, payload: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / filename
    with NamedTemporaryFile("w", encoding="utf-8", dir=output_dir, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(target)
    return target


def write_run_artifacts(output_dir: Path, mandate: dict[str, Any], research_plan: dict[str, Any]) -> dict[str, Path]:
    mandate_path = write_json_artifact(output_dir, "mandate.json", mandate)
    research_plan_path = write_json_artifact(output_dir, "research_plan.json", research_plan)
    return {
        "mandate": mandate_path,
        "research_plan": research_plan_path,
    }

