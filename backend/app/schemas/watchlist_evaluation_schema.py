from __future__ import annotations

from pydantic import BaseModel, ConfigDict



class MaterialNewsItem(BaseModel):
    id: int
    title: str
    published_at: str | None = None
    importance_score: float | None = None
    summary: str | None = None
    source: str | None = None
    sentiment: str | None = None


class MaterialDisclosureItem(BaseModel):
    id: int
    title: str
    disclosed_at: str | None = None
    importance_score: float | None = None
    summary: str | None = None
    disclosure_type: str | None = None
    risk_level: str | None = None


class MaterialThemeItem(BaseModel):
    theme_id: int | None = None
    theme_name: str
    is_primary: bool = False
    return_30d: float | None = None
    return_5d: float | None = None
    source_date: str | None = None


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
    material_status: str | None = None
    material_grade: str | None = None
    material_summary: str | None = None
    material_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_material_data: list[str] = []
    latest_material_date: str | None = None
    material_news_count: int = 0
    material_disclosure_count: int = 0
    material_theme_names: list[str] = []
    material_recent_news: list[MaterialNewsItem] = []
    material_recent_disclosures: list[MaterialDisclosureItem] = []
    material_themes: list[MaterialThemeItem] = []
    supply_score: float | None = None
    supply_status: str | None = None
    supply_grade: str | None = None
    supply_summary: str | None = None
    supply_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_supply_data: list[str] = []
    representative_theme_name: str | None = None
    representative_theme_return_30d: float | None = None
    supply_investor_flow_status: dict[str, str] = {}
    supply_model_version: str | None = None
    investor_flow_summary: dict[str, object] = {}
    chart_score: float | None = None
    chart_status: str | None = None
    chart_grade: str | None = None
    chart_summary: str | None = None
    chart_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_chart_data: list[str] = []
    chart_model_version: str | None = None
    chart_metrics: dict[str, object] = {}
    financial_score: float | None = None
    financial_status: str | None = None
    financial_grade: str | None = None
    financial_summary: str | None = None
    financial_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_financial_data: list[str] = []
    financial_model_version: str | None = None
    financial_snapshot: dict[str, object] = {}
    financial_annual_statements: list[dict[str, object]] = []
    financial_quarterly_statements: list[dict[str, object]] = []
    shareholder_snapshot: dict[str, object] = {}
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
    material_status: str | None = None
    material_grade: str | None = None
    material_summary: str | None = None
    material_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_material_data: list[str] = []
    latest_material_date: str | None = None
    material_news_count: int = 0
    material_disclosure_count: int = 0
    material_theme_names: list[str] = []
    material_recent_news: list[MaterialNewsItem] = []
    material_recent_disclosures: list[MaterialDisclosureItem] = []
    material_themes: list[MaterialThemeItem] = []
    supply_score: float | None
    supply_status: str | None
    supply_grade: str | None = None
    supply_summary: str | None = None
    supply_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_supply_data: list[str] = []
    representative_theme_name: str | None = None
    representative_theme_return_30d: float | None = None
    supply_investor_flow_status: dict[str, str] = {}
    supply_model_version: str | None = None
    investor_flow_summary: dict[str, object] = {}
    chart_score: float | None
    chart_grade: str | None = None
    chart_summary: str | None = None
    chart_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_chart_data: list[str] = []
    chart_model_version: str | None = None
    chart_metrics: dict[str, object] = {}
    financial_score: float | None
    financial_status: str | None = None
    financial_grade: str | None = None
    financial_summary: str | None = None
    financial_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_financial_data: list[str] = []
    financial_model_version: str | None = None
    financial_snapshot: dict[str, object] = {}
    financial_annual_statements: list[dict[str, object]] = []
    financial_quarterly_statements: list[dict[str, object]] = []
    shareholder_snapshot: dict[str, object] = {}
    total_score: float | None
    chart_status: str | None
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
    material_status: str | None = None
    material_grade: str | None = None
    material_summary: str | None = None
    material_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_material_data: list[str] = []
    latest_material_date: str | None = None
    material_news_count: int = 0
    material_disclosure_count: int = 0
    material_theme_names: list[str] = []
    supply_score: float | None = None
    supply_status: str | None = None
    supply_grade: str | None = None
    supply_summary: str | None = None
    supply_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_supply_data: list[str] = []
    representative_theme_name: str | None = None
    representative_theme_return_30d: float | None = None
    supply_investor_flow_status: dict[str, str] = {}
    supply_model_version: str | None = None
    investor_flow_summary: dict[str, object] = {}
    chart_score: float | None = None
    chart_status: str | None = None
    chart_grade: str | None = None
    chart_summary: str | None = None
    chart_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_chart_data: list[str] = []
    chart_model_version: str | None = None
    chart_metrics: dict[str, object] = {}
    financial_score: float | None = None
    financial_status: str | None = None
    financial_grade: str | None = None
    financial_summary: str | None = None
    financial_factors: list[WatchlistEvaluationFactorResponse] = []
    missing_financial_data: list[str] = []
    financial_model_version: str | None = None
    financial_snapshot: dict[str, object] = {}
    financial_annual_statements: list[dict[str, object]] = []
    financial_quarterly_statements: list[dict[str, object]] = []
    shareholder_snapshot: dict[str, object] = {}
    total_score: float | None
    overall_status: str | None
    data_confidence: str
    missing_data: list[str]


class WatchlistGptPromptResponse(BaseModel):
    watchlist_id: int
    prompt: str