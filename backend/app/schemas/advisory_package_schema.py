from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AdvisoryPackageGenerateRequest(BaseModel):
    stock_id: int
    news_ids: list[int] = Field(default_factory=list)
    disclosure_ids: list[int] = Field(default_factory=list)
    title: str
    purpose: str
    package_type: Literal["swing", "long_term"]


class AdvisoryPackageGenerateResponse(BaseModel):
    id: int
    stock_id: int
    title: str
    report_type: str
    package_type: Literal["swing", "long_term"]
    markdown_content: str
    created_at: str


class EvidenceStockBlock(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str


class EvidencePriceSummaryBlock(BaseModel):
    latest_trade_date: str | None = None
    latest_close_price: float | None = None
    latest_ma5: float | None = None
    latest_ma20: float | None = None
    latest_ma60: float | None = None
    recent_5d_change_rate: float | None = None
    avg_volume_20d: float | None = None
    high_52w: float | None = None
    high_52w_date: str | None = None
    price_position_vs_52w_high: float | None = None
    price_count: int
    source: str


class EvidenceMarketMetricsSummaryBlock(BaseModel):
    latest_market_metrics_date: str
    latest_price_trade_date: str | None = None
    is_stale: bool
    stale_days: int | None = None
    staleness_level: str
    market: str | None = None
    trading_value: int | None = None
    market_cap: int | None = None
    listed_shares: int | None = None
    trading_volume: int | None = None
    trading_value_rank: int | None = None
    market_trading_value_rank: int | None = None
    trading_value_percentile: float | None = None
    market_trading_value_percentile: float | None = None
    source: str
    data_note: str


class EvidenceTimeframeSummaryBlock(BaseModel):
    label: str
    start_trade_date: str | None = None
    end_trade_date: str | None = None
    change_rate: float | None = None
    highest_price: float | None = None
    lowest_price: float | None = None


class EvidenceRecentCandleItem(BaseModel):
    trade_date: str
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    change_rate: float | None = None
    volume: int | None = None


class EvidenceSimilarPatternCase(BaseModel):
    case_id: str
    reference_end_trade_date: str
    comparison_start_trade_date: str
    comparison_end_trade_date: str
    similarity_score: float
    historical_next_5d_change_rate: float | None = None
    historical_next_20d_change_rate: float | None = None
    note: str


class EvidencePriceCandleReferenceBlock(BaseModel):
    included: bool
    lookback_days: int
    recent_candle_limit: int
    include_raw_candles: bool
    pattern_window: int
    similar_case_limit: int
    row_count: int
    start_trade_date: str | None = None
    end_trade_date: str | None = None
    timeframe_summaries: list[EvidenceTimeframeSummaryBlock] = Field(default_factory=list)
    recent_candles: list[EvidenceRecentCandleItem] = Field(default_factory=list)
    similar_pattern_cases: list[EvidenceSimilarPatternCase] = Field(default_factory=list)
    caution_note: str | None = None


class EvidenceStrategyHorizonContextBlock(BaseModel):
    selected_horizon: str
    horizon_notes: list[str] = Field(default_factory=list)


class EvidenceAnalysisHorizonWeightsBlock(BaseModel):
    swing_weight: float
    long_term_weight: float


class AdvisoryEvidencePackageResponse(BaseModel):
    stock: EvidenceStockBlock
    price_summary: EvidencePriceSummaryBlock
    market_metrics_summary: EvidenceMarketMetricsSummaryBlock | None = None
    price_candle_reference: EvidencePriceCandleReferenceBlock | None = None
    strategy_horizon_context: EvidenceStrategyHorizonContextBlock | None = None
    analysis_horizon_weights: EvidenceAnalysisHorizonWeightsBlock | None = None
    scenario_questions_for_gpt: list[str] = Field(default_factory=list)
    news_summary: dict | None = None
    disclosure_summary: dict | None = None
    risk_summary: dict | None = None
    theme_summary: dict | None = None
    telegram_theme_summary: dict | None = None
    data_quality_notes: list[str] = Field(default_factory=list)
    instruction_guardrails: list[str] = Field(default_factory=list)
    generated_at: str
