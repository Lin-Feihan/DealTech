from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v3_lite_buyer_acquisition_runtime.runtime.claim_evidence_graph_builder import validate_claim_evidence_graph
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m4 import M4FailClosed, run_m4_pipeline


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


class V3LiteM4ClaimEvidenceGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.evidence_repository_path = RUNTIME_ROOT / "outputs" / "fronthera_esker_alumis_m3" / "evidence_repository.json"

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
        forbidden_markers = ("FronThera", "Bohan", "TYK2", "Alumis", "Esker", "11.12", "$60M", "$120M", "$180M")
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
        forbidden_markers = ("FronThera", "Bohan", "TYK2", "Alumis", "Esker", "11.12", "$60M", "$120M", "$180M")

        self.assertTrue(source_supported_claims)
        self.assertTrue(all(claim["canonical_fact_type"] for claim in source_supported_claims))
        self.assertTrue(all(claim["claim_type"] in {claim["canonical_fact_type"], "generic_fact"} for claim in source_supported_claims))
        self.assertTrue(all(claim["supporting_source_ids"] for claim in source_supported_claims))
        self.assertTrue(all(claim["supporting_raw_evidence_ids"] for claim in source_supported_claims))
        self.assertFalse(any(marker in json.dumps(graph["claim_nodes"]) for marker in forbidden_markers))

    def test_post_decision_and_retrospective_claims_are_not_ex_ante(self) -> None:
        graph = self._run_graph("m4_temporal")

        for claim in graph["claim_nodes"]:
            if claim["temporal_scope"] in {"post_decision", "retrospective"}:
                self.assertNotEqual(claim["permitted_use"], "ex_ante_deal_evaluation")
                self.assertTrue(claim["hindsight_leakage_warning"])

    def _run_graph(self, label: str) -> dict:
        artifacts = run_m4_pipeline(evidence_repository_path=self.evidence_repository_path, output_dir=self.root / label)
        return json.loads(artifacts["claim_evidence_graph"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
