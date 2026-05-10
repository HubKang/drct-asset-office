from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class WatchlistStatus(str, Enum):
    관심 = "관심"
    관망 = "관망"
    매수후보 = "매수후보"
    보유중 = "보유중"
    제외 = "제외"


class WatchlistCreate(BaseModel):
    stock_id: int
    status: WatchlistStatus
    interest_reason: str | None = None
    entry_condition: str | None = None
    exit_condition: str | None = None
    risk_note: str | None = None


class WatchlistUpdate(BaseModel):
    status: WatchlistStatus | None = None
    interest_reason: str | None = None
    entry_condition: str | None = None
    exit_condition: str | None = None
    risk_note: str | None = None


class WatchlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    status: str
    interest_reason: str | None
    entry_condition: str | None
    exit_condition: str | None
    risk_note: str | None
    registered_at: str
    updated_at: str


class WatchlistListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    stock_code: str
    stock_name: str
    status: str
    interest_reason: str | None
    entry_condition: str | None
    exit_condition: str | None
    risk_note: str | None
    registered_at: str
    updated_at: str
