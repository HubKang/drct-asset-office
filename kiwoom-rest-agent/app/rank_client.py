from __future__ import annotations

from .kiwoom_rest_client import KiwoomRestClient, RestApiResult


class RankClient:
    def __init__(self, rest_client: KiwoomRestClient) -> None:
        self.rest_client = rest_client

    def get_intraday_change_rank(self, token: str, market_type: str = "000", trading_value_condition: str = "0") -> RestApiResult:
        body = {
            "sort_tp": "1",
            "trde_qty_cnd": "0000",
            "mrkt_tp": market_type,
            "updown_incls": "1",
            "stk_cnd": "1",
            "crd_cnd": "0",
            "trde_prica_cnd": trading_value_condition,
            "flu_cnd": "1",
            "stex_tp": "3",
        }
        return self.rest_client.post(api_id="ka10028", path="/api/dostk/stkinfo", body=body, token=token)
