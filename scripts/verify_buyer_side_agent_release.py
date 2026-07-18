from __future__ import annotations

import compileall
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "agents" / "agents" / "buyer_side_acquisition_loop_agent"
ASSETS = ROOT / "agents" / "agents" / "buyer-side-acquisition-loop-agent"
DEMO = ASSETS / "06_examples" / "recorded_full_pipeline_case"
SAMPLE = DEMO / "sample_output"
CASE = DEMO / "case.yaml"
PROTECTED = (
    "agents/agents/acquisition-strategy-agent",
    "agents/agents/acquisition_strategy_agent",
    "agents/dealtech_certification",
    "agents/docs/acquisition-loop-upgrade",
    ".codex",
)
SAMPLE_FILES = (
    "final_acquisition_strategy_report.md", "run_summary.json", "gate_a_result.json",
    "gate_b_result.json", "gate_c_result.json", "decision_state.json",
    "final_delivery_verification.json", "run_manifest.json",
    "cross_block_consistency_result.json",
)
REQUIRED = (
    ROOT / "pyproject.toml", ROOT / "README.md", ROOT / "AGENTS.md",
    ASSETS / "QUICKSTART.md", ASSETS / "ARCHITECTURE.md", ASSETS / "CASE_INPUT_GUIDE.md",
    ASSETS / "EVIDENCE_AND_CERTIFICATION.md", ASSETS / "HUMAN_REVIEW_GUIDE.md",
    ASSETS / "KNOWN_LIMITATIONS.md", ASSETS / "RELEASE_CHECKLIST.md",
    ASSETS / "RELEASE_INVENTORY.md", CASE,
)
WINDOWS_ABSOLUTE = re.compile(r"(?i)(?:[A-Z]:\\Users\\|[A-Z]:/Users/)")
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|api[_-]?key\s*[:=]\s*['\"][^'\"]{12,})", re.I)
FORBIDDEN_LEGACY = ("app" + "le", "darwin" + "ai")
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".py"}


def canonical_artifact_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return data
    text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")


def run(command: list[str], *, timeout: int = 240) -> bool:
    print("$", " ".join(command))
    completed = subprocess.run(command, cwd=ROOT, env=source_env(), timeout=timeout)
    return completed.returncode == 0


def source_env() -> dict[str, str]:
    env = os.environ.copy()
    paths = [str(ROOT / "agents"), str(ROOT / "agents" / "agents")]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def validate_sample() -> list[str]:
    errors: list[str] = []
    for name in SAMPLE_FILES:
        path = SAMPLE / name
        if not path.is_file():
            errors.append(f"missing curated sample: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        if WINDOWS_ABSOLUTE.search(text):
            errors.append(f"absolute user path in curated sample: {name}")
        if SECRET.search(text):
            errors.append(f"possible secret in curated sample: {name}")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON {name}: {exc}")
    manifest_path = SAMPLE / "run_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for row in manifest.get("artifacts", []):
            path = SAMPLE / row["path"]
            if not path.is_file():
                errors.append(f"curated manifest mismatch: {row['path']}")
                continue
            data = canonical_artifact_bytes(path)
            if hashlib.sha256(data).hexdigest() != row["sha256"] or len(data) != row["bytes"]:
                errors.append(f"curated manifest mismatch: {row['path']}")
    return errors


def scan_release() -> list[str]:
    errors: list[str] = []
    roots = (
        PACKAGE, ASSETS, ROOT / "scripts", ROOT / ".github" / "workflows",
        ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "pyproject.toml",
    )
    paths: list[Path] = []
    for root in roots:
        paths.extend(root.rglob("*") if root.is_dir() else [root])
    for path in paths:
        if not path.is_file() or "run_output" in path.parts or "__pycache__" in path.parts:
            continue
        if path.stat().st_size > 5 * 1024 * 1024:
            errors.append(f"unexpectedly large release file: {path.relative_to(ROOT)}")
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        if WINDOWS_ABSOLUTE.search(text):
            errors.append(f"absolute user path: {path.relative_to(ROOT)}")
        if SECRET.search(text):
            errors.append(f"possible secret: {path.relative_to(ROOT)}")
        if any(term in text.lower() for term in FORBIDDEN_LEGACY):
            errors.append(f"legacy demonstration content: {path.relative_to(ROOT)}")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")
    return errors


def main() -> int:
    errors = [f"missing required file: {path.relative_to(ROOT)}" for path in REQUIRED if not path.is_file()]
    errors.extend(scan_release())
    errors.extend(validate_sample())
    if not compileall.compile_dir(PACKAGE, quiet=1):
        errors.append("Python compilation failed")
    protected = subprocess.run(
        ["git", "diff", "--name-only", "--", *PROTECTED], cwd=ROOT,
        text=True, capture_output=True, check=False,
    )
    if protected.returncode or protected.stdout.strip():
        errors.append(f"protected-path diff detected: {protected.stdout.strip() or protected.stderr.strip()}")
    if errors:
        for error in errors:
            print("FAIL:", error)
        return 1
    with tempfile.TemporaryDirectory(prefix="buyer-side-agent-rc1-", dir=ROOT) as temp:
        smoke = run([
            sys.executable, "-m", "buyer_side_acquisition_loop_agent", "--case", str(CASE),
            "--module", "FULL_PIPELINE", "--output", str(Path(temp) / "run_output"),
        ])
        if not smoke:
            print("FAIL: recorded full-pipeline smoke test")
            return 1
        test = run([
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--basetemp", str(Path(temp) / "pytest"),
            str(ASSETS / "tests" / "test_release_candidate_1.py"),
        ])
        if not test:
            print("FAIL: focused RC1 tests")
            return 1
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, capture_output=True, check=False)
    print(status.stdout.rstrip())
    print("PASS: buyer-side acquisition loop agent RC1 release verification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
