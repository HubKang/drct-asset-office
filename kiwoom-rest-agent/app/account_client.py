from __future__ import annotations

from .kiwoom_rest_client import KiwoomRestClient, RestApiResult


class AccountClient:
    def __init__(self, rest_client: KiwoomRestClient) -> None:
        self.rest_client = rest_client

    def get_account_no(self, token: str) -> RestApiResult:
        return self.rest_client.post(api_id="ka00001", path="/api/dostk/acnt", body={}, token=token)
