from __future__ import annotations

import os
import unittest
import urllib.error
from unittest.mock import patch

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.sec_companyfacts_provider import make_sec_companyfacts_provider, normalize_cik
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.xbrl_numeric_check import run_xbrl_numeric_check


class BuyerSideAcquisitionStrategyAgentSecCompanyfactsProviderTest(unittest.TestCase):
    def test_cik_normalize(self) -> None:
        self.assertEqual(normalize_cik("320193"), "0000320193")
        self.assertEqual(normalize_cik("CIK 320193"), "0000320193")
        self.assertEqual(normalize_cik(320193), "0000320193")

    def test_fake_sec_response_value_matched_by_end_period(self) -> None:
        captured = {}

        def fake_fetcher(url: str, user_agent: str, timeout_seconds: float) -> dict:
            captured["url"] = url
            captured["user_agent"] = user_agent
            return self._companyfacts_payload([
                {"end": "2024-09-28", "fy": 2024, "filed": "2024-11-01", "accn": "old", "val": 60800000000},
                {"end": "2024-09-28", "fy": 2024, "filed": "2024-11-02", "accn": "new", "val": 60900000000},
            ])

        provider = make_sec_companyfacts_provider(user_agent="DealTech test@example.com", fetcher=fake_fetcher)
        result = provider("320193", "Revenues", "2024-09-28", "USD")

        self.assertEqual(result, {"status": "ok", "observed_value": 60900000000})
        self.assertIn("CIK0000320193.json", captured["url"])
        self.assertEqual(captured["user_agent"], "DealTech test@example.com")

    def test_fake_sec_response_value_matched_by_fiscal_year(self) -> None:
        provider = make_sec_companyfacts_provider(
            user_agent="DealTech test@example.com",
            fetcher=lambda url, user_agent, timeout: self._companyfacts_payload([
                {"end": "2024-09-28", "fy": 2024, "filed": "2024-11-01", "val": 60900000000}
            ]),
        )

        result = provider("0000320193", "Revenues", "2024", "USD")

        self.assertEqual(result, {"status": "ok", "observed_value": 60900000000})

    def test_sec_provider_can_be_passed_to_xbrl_numeric_check(self) -> None:
        provider = make_sec_companyfacts_provider(
            user_agent="DealTech test@example.com",
            fetcher=lambda url, user_agent, timeout: self._companyfacts_payload([
                {"end": "2024-09-28", "fy": 2024, "filed": "2024-11-01", "val": 60900000000}
            ]),
        )
        repository = {
            "generated_artifact": "evidence_repository.json",
            "evidence_records": [
                {
                    "evidence_record_id": "ER-001",
                    "structured_attributes": {
                        "xbrl": {
                            "cik": "320193",
                            "taxonomy_tag": "Revenues",
                            "period": "2024-09-28",
                            "unit": "USD",
                            "expected_value": 60900000000,
                        }
                    },
                }
            ],
        }

        result = run_xbrl_numeric_check(repository, provider=provider)[0]

        self.assertEqual(result["xbrl_check_status"], "verified")
        self.assertEqual(result["observed_value"], 60900000000)

    def test_fake_sec_response_not_found(self) -> None:
        provider = make_sec_companyfacts_provider(
            user_agent="DealTech test@example.com",
            fetcher=lambda url, user_agent, timeout: self._companyfacts_payload([
                {"end": "2023-09-30", "fy": 2023, "filed": "2023-11-01", "val": 50000000000}
            ]),
        )

        result = provider("320193", "Revenues", "2024-09-28", "USD")

        self.assertEqual(result, {"status": "not_found"})

    def test_missing_sec_user_agent_returns_provider_unavailable(self) -> None:
        with patch.dict(os.environ, {"SEC_USER_AGENT": ""}):
            provider = make_sec_companyfacts_provider(fetcher=lambda url, user_agent, timeout: self.fail("fetcher should not be called"))

            result = provider("320193", "Revenues", "2024", "USD")

        self.assertEqual(result, {"status": "provider_unavailable"})

    def test_network_error_returns_provider_unavailable(self) -> None:
        def failing_fetcher(url: str, user_agent: str, timeout_seconds: float) -> dict:
            raise urllib.error.URLError("network down")

        provider = make_sec_companyfacts_provider(user_agent="DealTech test@example.com", fetcher=failing_fetcher)

        result = provider("320193", "Revenues", "2024", "USD")

        self.assertEqual(result, {"status": "provider_unavailable"})

    def _companyfacts_payload(self, facts: list[dict]) -> dict:
        return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": facts}}}}}


if __name__ == "__main__":
    unittest.main()
