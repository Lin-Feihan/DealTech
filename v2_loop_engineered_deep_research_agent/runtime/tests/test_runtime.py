from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from v2_loop_engineered_deep_research_agent.runtime.acquisition_analysis import (
    REPORT_SECTION_TITLES,
    render_acquisition_report,
)
from v2_loop_engineered_deep_research_agent.runtime.runner import run_case


class BuyerAnalysisRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.case_dir = self.root / "case"
        self.supporting = self.case_dir / "supporting_files"
        self.supporting.mkdir(parents=True)
        self.case_id = "synthetic_biopharma_case"
        self.analysis = self._analysis_input()
        self._write_analysis()
        (self.case_dir / "certification_results.json").write_text(
            json.dumps({"case_id": self.case_id, "overall_status": "Needs Human Review"}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _analysis_input(self) -> dict:
        chapters = [
            {
                "number": number,
                "title": title,
                "judgment": f"Case-specific judgment for {title}.",
                "paragraphs": [
                    f"This chapter evaluates {title.lower()} from the supplied analysis, not from renderer policy."
                ],
                "basis_ids": ["FACT-001", "ASM-001"],
            }
            for number, title in enumerate(REPORT_SECTION_TITLES, start=1)
        ]
        chapters[5]["dynamic_tables"] = ["strategic_alternatives"]
        chapters[7]["dynamic_tables"] = ["model:rnpv"]
        return {
            "report_metadata": {
                "case_id": self.case_id,
                "title": "Northstar / Meridian Buyer-side Acquisition Strategy Report",
                "as_of_date": "2025-06-30",
                "transaction_state": "Pre-signing decision",
                "decision_mandate": "Evaluate acquisition",
                "evidence_boundary": "Later outcomes are excluded from the decision-date case."
            },
            "recommendation": {
                "disposition": "Defer",
                "decision": "Defer final approval until the rNPV inputs are evidenced.",
                "price_position": "No defensible price ceiling.",
                "structure_position": "Use contingent consideration if diligence supports ownership.",
                "financing_position": "Financing evidence is incomplete.",
                "conditions": ["Complete clinical diligence."],
                "red_lines": ["Unresolved chain of title."],
                "next_actions": ["Build a source-mapped rNPV."]
            },
            "facts": [
                {
                    "id": "FACT-001",
                    "statement": "The target is a single development-stage asset.",
                    "evidence_class": "Source-backed fact"
                }
            ],
            "assumptions": [
                {
                    "id": "ASM-001",
                    "statement": "Scenario inputs are illustrative.",
                    "evidence_class": "Analyst assumption"
                }
            ],
            "method_selection": [
                {
                    "analysis_area": "Valuation and buyer returns",
                    "model_id": "rnpv",
                    "method": "Risk-adjusted net present value",
                    "rationale": "The supplied case describes a development-stage asset without operating cash flow.",
                    "scenario_policy": "downside_base_upside",
                    "basis_ids": ["FACT-001", "ASM-001"],
                }
            ],
            "models": {
                "rnpv": {
                    "model_type": "rnpv",
                    "valuation_date": "2025-06-30",
                    "currency": "USD millions",
                    "discount_rate": 0.1,
                    "method": "Probability-adjusted commercial cash flow less survival-weighted development cost.",
                    "model_limitations": ["Synthetic unit-test inputs."],
                    "scenarios": [
                        self._scenario("Downside", 0.05, 10),
                        self._scenario("Base", 0.1, 20),
                        self._scenario("Upside", 0.2, 40),
                    ]
                }
            },
            "alternatives": [
                {
                    "option": option,
                    "control": "Varies",
                    "capital_at_risk": "Varies",
                    "advantage": f"{option} advantage",
                    "drawback": f"{option} drawback",
                    "current_view": "Requires analysis"
                }
                for option in ("build", "buy", "license", "partner", "wait")
            ],
            "chapters": chapters,
            "research_gaps": [
                {"question": "What is the development stage?", "decision_effect": "Changes PTRS and rNPV."}
            ],
            "human_review_items": ["Clinical diligence"]
        }

    @staticmethod
    def _scenario(name: str, ptrs: float, sales: float) -> dict:
        return {
            "name": name,
            "evidence_class": "Analyst scenario",
            "ptrs": ptrs,
            "launch_after_years": 2,
            "commercial_cash_margin": 0.5,
            "annual_net_sales_usd_m": [sales, sales],
            "development_costs_usd_m": [10, 10],
            "development_active_probability": [1.0, 0.5],
            "upfront_consideration_usd_m": 5,
            "headline_consideration_usd_m": 15,
            "limitations": ["Illustrative only."]
        }

    def _write_analysis(self) -> None:
        (self.supporting / "case_analysis.json").write_text(
            json.dumps(self.analysis, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_runtime_serializes_authoritative_analysis(self) -> None:
        output_dir = self.root / "output"
        result = run_case(self.case_dir, output_dir)
        package = json.loads((output_dir / "analysis_package.json").read_text(encoding="utf-8"))
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")

        self.assertEqual(result["recommendation"], "Defer")
        self.assertEqual(package["analysis_engine_version"], "3.1.0-general-method-routing")
        self.assertEqual(len(package["sections"]), 15)
        self.assertTrue(package["quality_control"]["passed"])
        self.assertIn("Case-specific judgment for Executive Summary.", report)
        self.assertIn("### Illustrative rNPV Sensitivity", report)
        self.assertIn("### Build / Buy / License / Partner / Wait", report)
        for number, title in enumerate(REPORT_SECTION_TITLES, start=1):
            self.assertIn(f"## {number}. {title}", report)

    def test_missing_authoritative_analysis_fails_closed(self) -> None:
        (self.supporting / "case_analysis.json").unlink()
        with self.assertRaisesRegex(ValueError, "case_analysis.json"):
            run_case(self.case_dir, self.root / "missing-analysis-output")

    def test_file_presence_cannot_promote_recommendation(self) -> None:
        (self.supporting / "valuation_model.csv").write_text(
            "method,value\nrNPV,999\n", encoding="utf-8"
        )
        (self.supporting / "sources_and_uses.csv").write_text(
            "source,amount\nCash,999\n", encoding="utf-8"
        )
        result = run_case(self.case_dir, self.root / "heuristic-output")
        self.assertEqual(result["recommendation"], "Defer")

    def test_renderer_rejects_internal_marker_leakage(self) -> None:
        output_dir = self.root / "leak-output"
        run_case(self.case_dir, output_dir)
        package = json.loads((output_dir / "analysis_package.json").read_text(encoding="utf-8"))
        package["sections"][0]["paragraphs"][0] += " CLM-LEAK"
        with self.assertRaisesRegex(ValueError, "audit markers leaked"):
            render_acquisition_report(package)

    def test_rnpv_is_replayed_from_typed_inputs(self) -> None:
        output_dir = self.root / "model-output"
        run_case(self.case_dir, output_dir)
        package = json.loads((output_dir / "analysis_package.json").read_text(encoding="utf-8"))
        downside = package["models"]["rnpv"]["scenarios"][0]

        self.assertEqual(downside["pv_expected_development_cost_usd_m"], 13.2)
        self.assertEqual(downside["pv_risk_adjusted_commercial_cash_flow_usd_m"], 0.4)
        self.assertEqual(downside["asset_rnpv_before_acquisition_consideration_usd_m"], -12.8)
        self.assertEqual(downside["buyer_npv_at_upfront_consideration_usd_m"], -17.8)

    def test_operating_company_uses_dcf_without_rnpv(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["report_metadata"].update(
            {
                "case_id": "synthetic_operating_company_case",
                "title": "Orion / Harbor Buyer-side Acquisition Strategy Report",
                "as_of_date": "2026-01-31",
                "transaction_state": "Pre-indication decision",
            }
        )
        analysis["facts"] = [
            {
                "id": "FACT-001",
                "statement": "The user supplied a cash-generative operating-company target.",
                "evidence_class": "User-provided input",
            }
        ]
        analysis["assumptions"] = [
            {
                "id": "ASM-001",
                "statement": "Forecast cash flows are synthetic test assumptions.",
                "evidence_class": "Analyst assumption",
            }
        ]
        analysis["method_selection"] = [
            {
                "analysis_area": "Standalone valuation",
                "model_id": "dcf",
                "method": "Discounted cash flow",
                "rationale": "The user-supplied target has forecastable free cash flow and net debt.",
                "scenario_policy": "downside_base_upside",
                "basis_ids": ["FACT-001", "ASM-001"],
            }
        ]
        analysis["models"] = {
            "dcf": {
                "model_type": "dcf",
                "valuation_date": "2026-01-31",
                "currency": "USD millions",
                "discount_rate": 0.1,
                "terminal_growth_rate": 0.025,
                "method": "Present value of forecast free cash flow and terminal value less net debt.",
                "model_limitations": ["Synthetic unit-test inputs."],
                "scenarios": [
                    {
                        "name": name,
                        "evidence_class": "Analyst scenario",
                        "free_cash_flows": cash_flows,
                        "net_debt": 20,
                        "acquisition_consideration": 100,
                        "limitations": ["Synthetic only."],
                    }
                    for name, cash_flows in (
                        ("Downside", [8, 8, 8]),
                        ("Base", [10, 11, 12]),
                        ("Upside", [12, 14, 16]),
                    )
                ],
            }
        }
        analysis["chapters"][7]["dynamic_tables"] = ["model:dcf"]
        analysis["chapters"][7]["model_refs"] = ["dcf"]
        self.case_id = "synthetic_operating_company_case"
        self.analysis = analysis
        self._write_analysis()
        (self.case_dir / "certification_results.json").write_text(
            json.dumps({"case_id": self.case_id, "overall_status": "Needs Human Review"}),
            encoding="utf-8",
        )

        output_dir = self.root / "operating-company-output"
        run_case(self.case_dir, output_dir)
        package = json.loads((output_dir / "analysis_package.json").read_text(encoding="utf-8"))
        report = (output_dir / "final_report.md").read_text(encoding="utf-8")

        self.assertEqual(set(package["models"]), {"dcf"})
        self.assertEqual(package["models"]["dcf"]["model_type"], "dcf")
        self.assertNotIn("rnpv", package["models"])
        self.assertIn("### Discounted Cash Flow Sensitivity", report)
        self.assertNotIn("rNPV", report)

    def test_output_shapes_cover_v2_schemas(self) -> None:
        output_dir = self.root / "schema-output"
        run_case(self.case_dir, output_dir)
        schema_dir = Path(__file__).resolve().parents[2] / "schemas"
        checks = (
            ("analysis_package.schema.json", "analysis_package.json"),
            ("recommendation_decision.schema.json", "recommendation_decision.json"),
            ("report_manifest.schema.json", "report_manifest.json"),
        )
        for schema_name, output_name in checks:
            schema = json.loads((schema_dir / schema_name).read_text(encoding="utf-8"))
            payload = json.loads((output_dir / output_name).read_text(encoding="utf-8"))
            self.assertTrue(set(schema["required"]).issubset(payload), schema_name)


if __name__ == "__main__":
    unittest.main()
