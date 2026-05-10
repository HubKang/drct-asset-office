from __future__ import annotations

from abc import abstractmethod

from backend.app.collectors.base_collector import BaseCollector


class BaseDisclosureCollector(BaseCollector):
    @abstractmethod
    def collect_by_corp_code(self, corp_code: str, bgn_de: str, end_de: str, page_count: int = 100) -> dict:
        raise NotImplementedError
