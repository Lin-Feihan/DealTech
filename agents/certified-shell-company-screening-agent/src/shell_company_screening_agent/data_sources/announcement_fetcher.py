from __future__ import annotations
class AnnouncementFetcher:
    """Adapter boundary for market-specific announcement retrieval."""
    def fetch(self, *args, **kwargs):
        raise NotImplementedError('Implement in a market adapter, e.g. data_sources.hk.hkexnews')
