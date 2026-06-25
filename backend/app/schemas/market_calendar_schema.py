from __future__ import annotations

from pydantic import BaseModel, Field


class MarketCalendarStockResponse(BaseModel):
    stock_id: int
    stock_code: str | None = None
    stock_name: str | None = None


class MarketCalendarEventBase(BaseModel):
    start_date: str = Field(min_length=10, max_length=10)
    end_date: str = Field(min_length=10, max_length=10)
    theme_id: int
    title: str = Field(min_length=1)
    summary: str | None = None
    news_url: str | None = None
    event_type: str = "news"
    importance: str = "medium"
    memo: str | None = None
    stock_ids: list[int] = Field(default_factory=list)


class MarketCalendarEventCreateRequest(MarketCalendarEventBase):
    pass


class MarketCalendarEventUpdateRequest(MarketCalendarEventBase):
    pass


class MarketCalendarEventResponse(BaseModel):
    id: int
    start_date: str
    end_date: str
    theme_id: int
    theme_name: str
    theme_group_id: int | None = None
    theme_group_name: str | None = None
    title: str
    summary: str | None = None
    news_url: str | None = None
    event_type: str
    importance: str
    memo: str | None = None
    is_active: int
    stocks: list[MarketCalendarStockResponse] = Field(default_factory=list)
    created_at: str
    updated_at: str


class MarketCalendarMonthlyResponse(BaseModel):
    month: str
    start_date: str
    end_date: str
    events: list[MarketCalendarEventResponse]


class MarketCalendarDailyResponse(BaseModel):
    date: str
    events: list[MarketCalendarEventResponse]
