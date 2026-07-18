from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "agents" / "agents" / "buyer-side-acquisition-loop-agent" / "06_examples" / "recorded_full_pipeline_case"
RUN = CASE / "run_output"
SAMPLE = CASE / "sample_output"
FILES = (
    "final_acquisition_strategy_report.md",
    "run_summary.json",
    "gate_a_result.json",
    "gate_b_result.json",
    "gate_c_result.json",
    "decision_state.json",
    "final_delivery_verification.json",
    "cross_block_consistency_result.json",
)
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".py"}


def canonical_artifact_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return data
    text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")


def artifact_entry(name: str) -> dict[str, str | int]:
    data = canonical_artifact_bytes(SAMPLE / name)
    return {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def write_manifest() -> None:
    summary = json.loads((SAMPLE / "run_summary.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "release-candidate-1",
        "case_id": summary["case_id"],
        "run_id": summary["run_id"],
        "sample_scope": "Sanitized GitHub subset; full provider, evidence, calculation, loop and Human Review traces are intentionally excluded and are reproducible with the documented recorded demo command.",
        "unpublished_internal_references": ["stages/block_a/", "stages/block_b/", "stages/block_c/"],
        "artifacts": [artifact_entry(name) for name in FILES],
        "contains_local_absolute_paths": False,
        "contains_credentials": False,
    }
    (SAMPLE / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    missing = [name for name in FILES if not (RUN / name).is_file()]
    if missing:
        raise SystemExit(f"Run the recorded FULL_PIPELINE first; missing: {missing}")
    SAMPLE.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(RUN / name, SAMPLE / name)
    write_manifest()
    print(SAMPLE.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
