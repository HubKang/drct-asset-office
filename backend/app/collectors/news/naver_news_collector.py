from __future__ import annotations

import logging

import requests

from backend.app.collectors.news.base_news_collector import BaseNewsCollector
from backend.app.core.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET


class NaverNewsCollector(BaseNewsCollector):
    api_url = "https://openapi.naver.com/v1/search/news.json"
    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self.client_id = NAVER_CLIENT_ID or ""
        self.client_secret = NAVER_CLIENT_SECRET or ""

    @property
    def name(self) -> str:
        return "naver_news_collector"

    def _validate_credentials(self) -> None:
        if not self.client_id or not self.client_secret:
            raise ValueError("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required")

    def collect_by_keyword(self, keyword: str, display: int = 20, start: int = 1, sort: str = "date") -> dict:
        self._validate_credentials()
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {
            "query": keyword,
            "display": display,
            "start": start,
            "sort": sort,
        }
        response = requests.get(self.api_url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        self.logger.info(
            "Naver news fetched keyword=%s status_code=%s total=%s item_count=%s",
            keyword,
            response.status_code,
            data.get("total", 0),
            len(items),
        )
        return {
            "provider": "naver_news",
            "keyword": keyword,
            "total": data.get("total"),
            "start": data.get("start"),
            "display": data.get("display"),
            "items": items,
        }
