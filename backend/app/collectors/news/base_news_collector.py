from __future__ import annotations

from abc import abstractmethod

from backend.app.collectors.base_collector import BaseCollector


class BaseNewsCollector(BaseCollector):
    @abstractmethod
    def collect_by_keyword(self, keyword: str, display: int = 20, start: int = 1, sort: str = "date") -> dict:
        raise NotImplementedError
