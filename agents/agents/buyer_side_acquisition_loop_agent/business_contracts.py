from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .business_models import BusinessBlock, BusinessModuleContract


AGENT_ASSET_ROOT = Path(__file__).resolve().parent.parent / "buyer-side-acquisition-loop-agent"
MODULE_CONTRACT_PATH = AGENT_ASSET_ROOT / "04_schemas" / "business_module_contracts.json"
PROMPT_ROOT = AGENT_ASSET_ROOT / "03_prompts"
REPORTING_PROMPT_PATH = PROMPT_ROOT / "reporting_prompt_registry.json"


def load_module_contracts(path: Path = MODULE_CONTRACT_PATH) -> list[BusinessModuleContract]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "milestone-3":
        raise ValueError("business module contract schema_version must be milestone-3")
    contracts: list[BusinessModuleContract] = []
    for item in payload.get("modules", []):
        values = dict(item)
        values["owning_block"] = BusinessBlock(values["owning_block"])
        contracts.append(BusinessModuleContract(**values))
    module_ids = [item.module_id for item in contracts]
    if len(contracts) != 17 or len(set(module_ids)) != 17:
        raise ValueError("exactly 17 unique acquisition business modules are required")
    return contracts


def load_prompt_registry(root: Path = PROMPT_ROOT) -> dict[str, dict[str, Any]]:
    prompts: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*_prompts.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for prompt in payload.get("prompts", []):
            prompt_id = prompt.get("prompt_id", "")
            required = {
                "prompt_id",
                "role",
                "authority_limits",
                "input_contract",
                "required_analysis",
                "output_contract",
                "evidence_rules",
                "counterevidence_rules",
                "invention_prohibition",
                "human_review_triggers",
                "role_boundary",
            }
            missing = sorted(required - set(prompt))
            if missing:
                raise ValueError(f"prompt {prompt_id or path.name} misses {missing}")
            if not prompt_id or prompt_id in prompts:
                raise ValueError(f"duplicate or empty prompt id: {prompt_id!r}")
            prompts[prompt_id] = {**prompt, "source_file": str(path)}
    if len(prompts) != 35:
        raise ValueError(f"exactly 35 prompts are required; loaded {len(prompts)}")
    return prompts


def validate_contract_prompt_links(
    contracts: list[BusinessModuleContract], prompts: dict[str, dict[str, Any]]
) -> None:
    for contract in contracts:
        prompt_id = contract.prompt_reference.rsplit("#", 1)[-1]
        if prompt_id not in prompts:
            raise ValueError(f"{contract.module_id} references missing prompt {prompt_id}")


def load_reporting_prompts(path: Path = REPORTING_PROMPT_PATH) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "prompt_id", "role", "authority_limits", "required_input_objects",
        "required_output_schema", "citation_requirements", "caveat_preservation",
        "counterevidence_preservation", "blocked_claim_handling",
        "human_review_boundary", "invention_prohibition", "decision_authority_boundary",
    }
    prompts: dict[str, dict[str, Any]] = {}
    for item in payload.get("prompts", []):
        missing = sorted(required - set(item))
        if missing:
            raise ValueError(f"reporting prompt {item.get('prompt_id','')} misses {missing}")
        if item["prompt_id"] in prompts:
            raise ValueError(f"duplicate reporting prompt {item['prompt_id']}")
        prompts[item["prompt_id"]] = item
    if len(prompts) != 7:
        raise ValueError(f"exactly 7 reporting prompts are required; loaded {len(prompts)}")
    return prompts
