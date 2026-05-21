from __future__ import annotations

import requests

from .config import Settings
from .logger import get_logger


class DrctApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        self.session.trust_env = settings.use_proxy

    def sync_conditions(self, items: list[dict]) -> tuple[int, dict]:
        url = f"{self.settings.drct_api_base_url}/external/kiwoom/conditions/sync"
        resp = self.session.post(url, json={"source": "kiwoom_rest", "items": items}, timeout=self.settings.timeout_seconds)
        return resp.status_code, resp.json()

    def save_condition_results(self, condition_seq: str, condition_name: str | None, items: list[dict]) -> tuple[int, dict]:
        url = f"{self.settings.drct_api_base_url}/external/kiwoom/conditions/{condition_seq}/results"
        payload = {"source": "kiwoom_rest", "condition_name": condition_name, "items": items}
        resp = self.session.post(url, json=payload, timeout=self.settings.timeout_seconds)
        return resp.status_code, resp.json()

    def save_market_events(self, condition_seq: str, condition_name: str | None, items: list[dict]) -> tuple[int, dict]:
        url = f"{self.settings.drct_api_base_url}/external/kiwoom/market-events"
        payload = {"source": "kiwoom_rest", "condition_seq": condition_seq, "condition_name": condition_name, "items": items}
        resp = self.session.post(url, json=payload, timeout=self.settings.timeout_seconds)
        return resp.status_code, resp.json()
