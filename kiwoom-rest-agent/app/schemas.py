from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    token: str = ""
    token_type: str = ""
    expires_dt: str = ""
    return_code: int | str | None = None
    return_msg: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)

    def is_success(self) -> bool:
        return str(self.return_code) in ("0", "000000") and bool(self.token)

    def safe_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        if data.get("token"):
            data["token"] = "***MASKED***"
        raw = data.get("raw")
        if isinstance(raw, dict):
            safe_raw = dict(raw)
            if "token" in safe_raw:
                safe_raw["token"] = "***MASKED***"
            if "access_token" in safe_raw:
                safe_raw["access_token"] = "***MASKED***"
            data["raw"] = safe_raw
        return data


class KiwoomApiResponse(BaseModel):
    status_code: int
    headers: dict[str, Any]
    body: dict[str, Any]
    cont_yn: str | None = None
    next_key: str | None = None


class MarketCandidateItem(BaseModel):
    stock_code: str
    stock_name: str
    current_price: int | None = None
    open_price: int | None = None
    high_price: int | None = None
    low_price: int | None = None
    volume: int | None = None
    trading_value: int | None = None
    intraday_change_rate: float | None = None
    day_change_rate: float | None = None
    strength: float | None = None
    source_api: str


class MarketEventPayload(BaseModel):
    source: str
    count: int
    items: list[MarketCandidateItem]
