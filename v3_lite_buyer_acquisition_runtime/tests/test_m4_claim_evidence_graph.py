from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.case_seed_loader import load_case_seed
from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.claim_evidence_graph_builder import validate_claim_evidence_graph
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m2 import run_m2_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m3 import run_m3_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m4 import M4FailClosed, run_m4_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM4ClaimEvidenceGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        mandate_path = RUNTIME_ROOT / "examples" / "synthetic_acquisition_mandate.json"
        case_seed_path = RUNTIME_ROOT / "case_seeds" / "synthetic_acquisition_case_seed.json"
        research_plan_path = self.root / "research_plan.json"
        research_plan = build_research_plan(load_mandate(mandate_path))
        research_plan_path.write_text(json.dumps(research_plan, indent=2), encoding="utf-8")
        m2_artifacts = run_m2_pipeline(
            mandate_path=mandate_path,
            research_plan_path=research_plan_path,
            case_seed_path=case_seed_path,
            output_dir=self.root / "m2",
            retrieval_mode="manual_retrieved_sources",
            retrieved_sources_manifest_path=RUNTIME_ROOT / "retrieved_sources" / "synthetic_acquisition" / "retrieved_sources_manifest.json",
        )
        m3_artifacts = run_m3_pipeline(
            raw_evidence_path=m2_artifacts["raw_evidence"],
            retrieved_sources_manifest_path=m2_artifacts["retrieved_sources_manifest"],
            output_dir=self.root / "m3",
        )
        self.evidence_repository_path = m3_artifacts["evidence_repository"]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_evidence_repository_produces_claim_evidence_graph(self) -> None:
        output_dir = self.root / "m4_valid"

        artifacts = run_m4_pipeline(evidence_repository_path=self.evidence_repository_path, output_dir=output_dir)

        self.assertTrue(artifacts["claim_evidence_graph"].exists())
        graph = json.loads(artifacts["claim_evidence_graph"].read_text(encoding="utf-8"))
        validate_claim_evidence_graph(graph)
        self.assertEqual(graph["generated_artifact"], "claim_evidence_graph.json")
        self.assertEqual(graph["stage"], "M4_claim_evidence_graph")
        self.assertTrue(graph["source_bounded"])
        self.assertFalse((output_dir / "certification_result.json").exists())
        self.assertFalse((output_dir / "final_report.md").exists())

    def test_invalid_evidence_repository_fails_closed(self) -> None:
        evidence_repository = json.loads(self.evidence_repository_path.read_text(encoding="utf-8"))
        del evidence_repository["evidence_records"][0]["permitted_use"]
        broken_path = self.root / "broken_evidence_repository.json"
        broken_path.write_text(json.dumps(evidence_repository, indent=2), encoding="utf-8")

        with self.assertRaises(M4FailClosed):
            run_m4_pipeline(evidence_repository_path=broken_path, output_dir=self.root / "m4_invalid")

    def test_every_claim_is_not_certified(self) -> None:
        graph = self._run_graph("m4_certification")

        self.assertTrue(graph["claim_nodes"])
        self.assertTrue(all(claim["certification_status"] != "certified" for claim in graph["claim_nodes"]))
        self.assertTrue(all(claim["certification_status"] in {"uncertified", "pending_verification", "failed_precheck", "not_applicable"} for claim in graph["claim_nodes"]))

    def test_source_gaps_become_gap_nodes(self) -> None:
        graph = self._run_graph("m4_gap_nodes")
        gap_statements = {gap["gap_statement"] for gap in graph["gap_nodes"]}

        self.assertTrue(graph["gap_nodes"])
        self.assertTrue(all("Unresolved source gap" in statement for statement in gap_statements))
        self.assertTrue(all("affected generic claim area" in statement for statement in gap_statements))
        forbidden_markers = ("ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenAmount", "ForbiddenAmount", "ForbiddenTarget")
        self.assertFalse(any(marker in json.dumps(graph["gap_nodes"]) for marker in forbidden_markers))

    def test_gap_only_claims_do_not_get_supporting_evidence(self) -> None:
        graph = self._run_graph("m4_gap_claims")
        gap_claims = [claim for claim in graph["claim_nodes"] if claim["support_level"] in {"gap_only", "unsupported"}]

        self.assertTrue(gap_claims)
        self.assertTrue(all(not claim["supporting_evidence_record_ids"] for claim in gap_claims))
        self.assertTrue(all(claim["related_source_gap_ids"] for claim in gap_claims))

    def test_evidence_edges_only_cite_existing_records(self) -> None:
        graph = self._run_graph("m4_edges")
        evidence_repository = json.loads(self.evidence_repository_path.read_text(encoding="utf-8"))
        evidence_record_ids = {record["evidence_record_id"] for record in evidence_repository["evidence_records"]}
        claim_ids = {claim["claim_id"] for claim in graph["claim_nodes"]}

        self.assertTrue(graph["evidence_edges"])
        for edge in graph["evidence_edges"]:
            self.assertIn(edge["claim_id"], claim_ids)
            self.assertIn(edge["evidence_record_id"], evidence_record_ids)

    def test_numeric_claims_are_not_inferred_without_explicit_formula(self) -> None:
        graph = self._run_graph("m4_numeric_not_inferred")
        derived_claims = [claim for claim in graph["claim_nodes"] if claim["claim_type"] == "derived_numeric_candidate"]

        self.assertEqual(derived_claims, [])
        self.assertTrue(all(not claim["requires_numeric_verification"] for claim in graph["claim_nodes"]))

    def test_source_gap_claims_are_generic_and_unsupported_by_evidence(self) -> None:
        graph = self._run_graph("m4_generic_gap_claims")
        gap_claims = [claim for claim in graph["claim_nodes"] if claim["related_source_gap_ids"]]

        self.assertTrue(gap_claims)
        self.assertTrue(all(claim["support_level"] == "gap_only" for claim in gap_claims))
        self.assertTrue(all(not claim["supporting_evidence_record_ids"] for claim in gap_claims))
        self.assertTrue(all("Source gap blocks support" in claim["claim_statement"] for claim in gap_claims))

    def test_claim_text_is_generic_and_lineage_is_preserved(self) -> None:
        graph = self._run_graph("m4_generic_claim_text")
        source_supported_claims = [claim for claim in graph["claim_nodes"] if claim["supporting_evidence_record_ids"]]
        forbidden_markers = ("ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenTarget", "ForbiddenAmount", "ForbiddenAmount", "ForbiddenTarget")

        self.assertTrue(source_supported_claims)
        self.assertTrue(all(claim["canonical_fact_type"] for claim in source_supported_claims))
        self.assertTrue(all(claim["claim_type"] in {claim["canonical_fact_type"], "generic_fact"} for claim in source_supported_claims))
        self.assertTrue(all(claim["supporting_source_ids"] for claim in source_supported_claims))
        self.assertTrue(all(claim["supporting_raw_evidence_ids"] for claim in source_supported_claims))
        self.assertTrue(all("Generic fallback claim:" in claim["claim_statement"] for claim in source_supported_claims))
        self.assertFalse(any(marker in json.dumps(graph["claim_nodes"]) for marker in forbidden_markers))

    def test_m4_builds_claim_nodes_from_candidate_claims_when_available(self) -> None:
        graph = self._run_candidate_graph("m4_candidate_claim_nodes")
        candidate_claims = [claim for claim in graph["claim_nodes"] if claim.get("created_from_candidate_claim_id")]

        self.assertTrue(candidate_claims)
        self.assertEqual(candidate_claims[0]["created_from_candidate_claim_id"], "CC-M4-001")
        self.assertEqual(
            candidate_claims[0]["claim_statement"],
            "The signed source states the buyer agreed to a $100 million closing payment plus contingent milestones.",
        )
        self.assertNotIn("Source-bounded evidence supports", candidate_claims[0]["claim_statement"])

    def test_m4_creates_evidence_edges_from_claim_evidence_links(self) -> None:
        graph = self._run_candidate_graph("m4_candidate_edges")
        candidate_claim = next(claim for claim in graph["claim_nodes"] if claim.get("created_from_candidate_claim_id") == "CC-M4-001")
        edges = [edge for edge in graph["evidence_edges"] if edge["claim_id"] == candidate_claim["claim_id"]]

        self.assertTrue(edges)
        self.assertEqual(edges[0]["edge_type"], "supports")
        self.assertIn("External candidate link rationale", edges[0]["notes"])

    def test_m4_does_not_certify_candidate_claims(self) -> None:
        graph = self._run_candidate_graph("m4_candidate_uncertified")
        candidate_claims = [claim for claim in graph["claim_nodes"] if claim.get("created_from_candidate_claim_id")]

        self.assertTrue(candidate_claims)
        self.assertTrue(all(claim["certification_status"] in {"pending_verification", "failed_precheck", "not_applicable"} for claim in candidate_claims))
        self.assertFalse(any(claim["certification_status"] == "certified" for claim in candidate_claims))

    def test_gap_only_candidate_claims_remain_blocked(self) -> None:
        graph = self._run_candidate_graph("m4_gap_only_candidate")
        gap_claim = next(claim for claim in graph["claim_nodes"] if claim.get("created_from_candidate_claim_id") == "CC-M4-GAP")

        self.assertEqual(gap_claim["support_level"], "gap_only")
        self.assertEqual(gap_claim["certification_status"], "failed_precheck")
        self.assertEqual(gap_claim["permitted_use"], "gap_tracking")
        self.assertEqual(gap_claim["supporting_evidence_record_ids"], [])
        self.assertIn("blocked from report use", gap_claim["downstream_use_warning"].lower())

    def test_post_decision_and_retrospective_claims_are_not_ex_ante(self) -> None:
        graph = self._run_graph("m4_temporal")

        for claim in graph["claim_nodes"]:
            if claim["temporal_scope"] in {"post_decision", "retrospective"}:
                self.assertNotEqual(claim["permitted_use"], "ex_ante_deal_evaluation")
                self.assertTrue(claim["hindsight_leakage_warning"])

    def _run_graph(self, label: str) -> dict:
        artifacts = run_m4_pipeline(evidence_repository_path=self.evidence_repository_path, output_dir=self.root / label)
        return json.loads(artifacts["claim_evidence_graph"].read_text(encoding="utf-8"))

    def _run_candidate_graph(self, label: str) -> dict:
        evidence_repository = json.loads(self.evidence_repository_path.read_text(encoding="utf-8"))
        evidence_record = evidence_repository["evidence_records"][0]
        evidence_repository["candidate_claims_from_research"] = [
            {
                "candidate_claim_id": "CC-M4-001",
                "claim_statement": "The signed source states the buyer agreed to a $100 million closing payment plus contingent milestones.",
                "claim_type": "transaction_consideration",
                "claim_scope": "Transaction terms only; not valuation or recommendation.",
                "temporal_scope": evidence_record["evidence_time_relation_to_decision_date"],
                "permitted_use": evidence_record["permitted_use"],
                "supporting_evidence_item_ids": ["PE-M4-001"],
                "contradicting_evidence_item_ids": [],
                "related_source_gap_ids": [],
                "confidence_preliminary": "medium",
                "requires_numeric_verification": False,
                "requires_human_review": True,
                "downstream_use_warning": "Candidate claim only. M5 decides certification and report eligibility.",
                "source_bounded_precheck_status": "pending_m4_mapping",
            },
            {
                "candidate_claim_id": "CC-M4-GAP",
                "claim_statement": "Seller realized proceeds remain unresolved because direct authoritative support is missing.",
                "claim_type": "source_gap_claim",
                "claim_scope": "Source gap tracking only.",
                "temporal_scope": "source_gap",
                "permitted_use": "gap_tracking",
                "supporting_evidence_item_ids": [],
                "contradicting_evidence_item_ids": [],
                "related_source_gap_ids": [evidence_repository["source_gaps"][0]["source_gap_id"]],
                "confidence_preliminary": "low",
                "requires_numeric_verification": False,
                "requires_human_review": True,
                "downstream_use_warning": "Gap-only candidate claim. Block from report assertions until source repair.",
                "source_bounded_precheck_status": "pending_m4_mapping",
            },
        ]
        evidence_repository["candidate_claim_evidence_links_from_research"] = [
            {
                "candidate_claim_id": "CC-M4-001",
                "evidence_item_id": "PE-M4-001",
                "link_type": "supports",
                "rationale": "External candidate link rationale maps the claim to a source-bounded repository record.",
                "mapped_evidence_record_ids": [evidence_record["evidence_record_id"]],
                "mapping_status": "mapped_to_evidence_record",
            }
        ]
        candidate_repository_path = self.root / f"{label}_evidence_repository.json"
        candidate_repository_path.write_text(json.dumps(evidence_repository, indent=2), encoding="utf-8")
        artifacts = run_m4_pipeline(evidence_repository_path=candidate_repository_path, output_dir=self.root / label)
        return json.loads(artifacts["claim_evidence_graph"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
