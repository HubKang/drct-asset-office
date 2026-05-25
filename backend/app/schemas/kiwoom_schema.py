from __future__ import annotations

from pydantic import BaseModel, Field


class KiwoomPocDailyPriceRequest(BaseModel):
    ticker: str
    mode: str = "recent"  # recent | backfill
    years: int = 2
    start_date: str | None = None
    end_date: str | None = None
    max_pages: int | None = None
    repeat_calls: int = 1
    api_id: str | None = None
    endpoint: str | None = None
    save: bool = False
    calculate_technical: bool = False


class KiwoomPocDailyPriceItem(BaseModel):
    trade_date: str
    open_price: int | None = None
    high_price: int | None = None
    low_price: int | None = None
    close_price: int | None = None
    change_price: int | None = None
    change_rate: float | None = None
    volume: int | None = None
    trading_value: int | None = None


class KiwoomPocDailyPriceResponse(BaseModel):
    success: bool
    provider: str = "kiwoom_rest"
    enabled: bool
    use_mock: bool
    base_url: str
    ticker: str
    normalized_stock_code: str
    requested_start_date: str | None = None
    requested_end_date: str | None = None
    actual_min_trade_date: str | None = None
    actual_max_trade_date: str | None = None
    api_id: str | None = None
    api_call_count: int = 0
    raw_count: int = 0
    mapped_count: int = 0
    cont_yn_used: bool = False
    next_key_used: bool = False
    elapsed_ms: int = 0
    sample_items: list[KiwoomPocDailyPriceItem] = Field(default_factory=list)
    first_row: KiwoomPocDailyPriceItem | None = None
    last_row: KiwoomPocDailyPriceItem | None = None
    repeat_calls: int = 1
    repeat_success: int = 0
    repeat_failed: int = 0
    avg_elapsed_ms: float | None = None
    estimated_50_symbols_seconds: float | None = None
    estimated_100_symbols_seconds: float | None = None
    save: bool = False
    calculate_technical: bool = False
    stock_id: int | None = None
    stock_name: str | None = None
    source: str = "kiwoom_rest"
    existing_price_count_by_source: list[dict] = Field(default_factory=list)
    unique_policy: str | None = None
    unique_indexes: list[dict] = Field(default_factory=list)
    would_save_count: int = 0
    save_blocked_reason: str | None = None
    saved_count: int = 0
    skipped_count: int = 0
    technical_saved_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    raw_response_preview: dict | None = None
