from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WatchlistEvaluationFactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    score_id: int
    category: str
    factor_code: str
    factor_name: str
    raw_value: str | None
    normalized_score: float | None
    weight: float | None
    contribution_score: float | None
    reason: str | None
    source_table: str | None
    source_date: str | None
    created_at: str


class WatchlistEvaluationListItem(BaseModel):
    watchlist_id: int
    stock_id: int
    stock_code: str
    stock_name: str
    market: str | None
    is_active: bool
    watch_reason: str | None
    stock_type: str
    market_score: float | None = None
    market_status: str | None = None
    market_grade: str | None = None
    market_summary: str | None = None
    market_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_market_data: list[str] = []
    material_score: float | None = None
    supply_score: float | None = None
    chart_score: float | None = None
    financial_score: float | None = None
    total_score: float | None = None
    data_confidence: str
    last_evaluated_at: str | None = None
    missing_data: list[str]


class WatchlistEvaluationSummary(BaseModel):
    watchlist_count: int
    active_count: int
    inactive_count: int
    evaluated_count: int
    not_evaluated_count: int
    missing_data_count: int
    last_evaluated_at: str | None = None


class WatchlistEvaluationListResponse(BaseModel):
    items: list[WatchlistEvaluationListItem]
    summary: WatchlistEvaluationSummary


class WatchlistEvaluateRequest(BaseModel):
    watchlist_ids: list[int] = []
    run_type: str = "MANUAL"


class WatchlistEvaluateAllRequest(BaseModel):
    include_inactive: bool = True
    run_type: str = "MANUAL"


class WatchlistEvaluateResponse(BaseModel):
    run_id: int
    evaluated_count: int
    status: str


class WatchlistEvaluationScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    watchlist_stock_id: int
    stock_id: int
    evaluated_at: str
    market_score: float | None
    market_status: str | None
    market_grade: str | None = None
    market_summary: str | None = None
    market_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_market_data: list[str] = []
    material_score: float | None
    supply_score: float | None
    chart_score: float | None
    financial_score: float | None
    total_score: float | None
    material_status: str | None
    supply_status: str | None
    chart_status: str | None
    financial_status: str | None
    overall_status: str | None
    data_confidence: str
    risk_flags: list[str]
    missing_data: list[str]
    summary_text: str | None
    created_at: str
    updated_at: str
    factors: list[WatchlistEvaluationFactorResponse] = []


class WatchlistEvaluationHistoryItem(BaseModel):
    score_id: int
    run_id: int
    run_date: str
    run_type: str
    status: str
    evaluated_at: str
    market_score: float | None = None
    market_status: str | None = None
    market_grade: str | None = None
    material_score: float | None = None
    supply_score: float | None = None
    chart_score: float | None = None
    financial_score: float | None = None
    total_score: float | None
    overall_status: str | None
    data_confidence: str
    missing_data: list[str]


class WatchlistGptPromptResponse(BaseModel):
    watchlist_id: int
    prompt: str