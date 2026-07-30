from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.case_seed_loader import load_case_seed
from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan, validate_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.source_discovery import build_source_discovery_plan, validate_source_discovery_plan


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
MARKER_PATTERN = re.compile(
    r"FronThera|Bohan|Stan Jin|FL2021|Esker|Alumis|TYK2|ESK-001|envudeucitinib|Haisco|Haisstain|"
    r"11\.12|60M|60_000_000|120M|120_000_000|180M|180_000_000|37M|37_000_000|23M|23_000_000|"
    r"2021-03-05|March 5, 2021"
)


class Step2BCaseProfileExtractionTest(unittest.TestCase):
    def test_case_profile_drives_named_case_planning_and_source_discovery(self) -> None:
        mandate = load_mandate(RUNTIME_ROOT / "examples" / "fronthera_esker_alumis_mandate.json")
        case_seed = load_case_seed(RUNTIME_ROOT / "case_seeds" / "fronthera_esker_alumis_case_seed.json")
        profile = json.loads(
            (RUNTIME_ROOT / "case_profiles" / "fronthera_esker_alumis_2021_acquisition_m1.json").read_text(
                encoding="utf-8",
            )
        )

        research_plan = build_research_plan(mandate)
        source_discovery_plan = build_source_discovery_plan(case_seed, research_plan)

        validate_research_plan(research_plan)
        validate_source_discovery_plan(source_discovery_plan)
        self.assertEqual(research_plan["key_questions"], profile["planning_profile"]["key_questions"])
        self.assertEqual(research_plan["workstreams"], profile["planning_profile"]["workstreams"])
        self.assertEqual(source_discovery_plan["source_needs"], profile["source_discovery_profile"]["source_needs"])
        self.assertEqual(source_discovery_plan["search_queries"], profile["source_discovery_profile"]["search_queries"])

        planning_text = json.dumps(research_plan)
        discovery_text = json.dumps(source_discovery_plan)
        for term in ("FronThera", "TYK2", "Bohan Jin", "ESK-001", "Alumis", "$60M", "$120M", "$180M"):
            self.assertIn(term, planning_text + discovery_text)

    def test_generic_case_uses_generic_fallback_without_named_case_markers(self) -> None:
        mandate = _generic_mandate()
        case_seed = _generic_case_seed()

        research_plan = build_research_plan(mandate)
        source_discovery_plan = build_source_discovery_plan(case_seed, research_plan)

        validate_research_plan(research_plan)
        validate_source_discovery_plan(source_discovery_plan)
        self.assertTrue(source_discovery_plan["source_needs"])
        self.assertEqual(source_discovery_plan["source_needs"][0]["source_need_id"], "SN-001")
        self.assertIn("ExampleTarget Ltd.", json.dumps(source_discovery_plan["search_queries"]))
        self.assertIsNone(MARKER_PATTERN.search(json.dumps(research_plan)))
        self.assertIsNone(MARKER_PATTERN.search(json.dumps(source_discovery_plan)))

    def test_runtime_planning_and_source_discovery_files_have_no_named_case_markers(self) -> None:
        for path in (
            RUNTIME_ROOT / "runtime" / "research_planning.py",
            RUNTIME_ROOT / "runtime" / "source_discovery.py",
        ):
            with self.subTest(path=path):
                self.assertIsNone(MARKER_PATTERN.search(path.read_text(encoding="utf-8")))


def _generic_mandate() -> dict:
    return {
        "case_id": "example_buyer_example_target_2024_acquisition_m1",
        "buyer": {"name": "ExampleBuyer Inc."},
        "target": {"name": "ExampleTarget Ltd."},
        "transaction_context": {
            "transaction_type": "acquisition",
            "stage": "pre-diligence planning",
            "decision_need": "Define a buyer-side acquisition research plan before downstream diligence.",
        },
        "decision_date": "2024-06-30",
        "requested_scope": [
            "buyer strategic objectives",
            "target business quality",
            "valuation and acceptable purchase price",
        ],
        "source_pack_reference": {
            "reference_id": "SOURCE-PACK-EXAMPLE-001",
            "description": "Synthetic source pack placeholder for generic fallback testing.",
        },
        "constraints": {
            "no_web_search": True,
            "no_evidence_generation": True,
            "no_report_generation": True,
        },
        "output_requirements": {
            "expected_artifacts": ["mandate.json", "research_plan.json"],
            "language": "English",
        },
    }


def _generic_case_seed() -> dict:
    return {
        "case_id": "example_buyer_example_target_2024_acquisition_m1",
        "seed_id": "CASE-SEED-EXAMPLE-001",
        "seed_type": "case_brief_lead_document",
        "source_description": "Synthetic case seed for generic buyer-side acquisition testing.",
        "case_parties": {
            "buyer_or_acquiring_vehicle": ["ExampleBuyer Inc."],
            "target": ["ExampleTarget Ltd."],
            "people": [],
        },
        "transaction_leads": [
            "ExampleBuyer Inc. acquisition evaluation of ExampleTarget Ltd.",
            "Decision date 2024-06-30",
        ],
        "key_assets_or_topics": [
            "target business quality",
            "deal structure",
            "buyer-side diligence",
        ],
        "known_dates": ["2024-06-30"],
        "known_amounts": ["illustrative purchase price lead unavailable"],
        "source_leads": [
            "official transaction announcement",
            "target company financial disclosures",
            "buyer strategy materials",
        ],
        "uncertainty_warnings": [
            "Case seed is not authoritative evidence and cannot directly support high-confidence claims.",
            "Use retrieved authoritative sources before extracting raw evidence.",
        ],
    }


if __name__ == "__main__":
    unittest.main()
