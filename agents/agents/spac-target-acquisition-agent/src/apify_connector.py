from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ApifyConnectorStatus:
    configured: bool
    authenticated_run_executed: bool
    status: str
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


class ApifyConnector:
    """Design stub for future authenticated Apify target-discovery runs.

    This connector intentionally does not pretend that live scraping has happened.
    The Soren case remains Needs Human Review until an authenticated Apify run is
    executed and its dataset is mapped into source/evidence/claim tables.
    """

    def status(self) -> ApifyConnectorStatus:
        return ApifyConnectorStatus(
            configured=False,
            authenticated_run_executed=False,
            status='not_authenticated',
            note='No authenticated Apify run was executed in this version.',
        )

    def run(self):
        raise RuntimeError('No authenticated Apify run was executed in this version.')
