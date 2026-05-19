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
    date_gap_days: int | None = None
    date_gap_label: str | None = None
    freshness_status: str | None = None
    freshness_label: str | None = None
    freshness_message: str | None = None
    is_stale: bool
    stale_days: int | None = None
    staleness_level: str
    market: str | None = None
    trading_value: int | None = None
    trading_value_display: str | None = None
    market_cap: int | None = None
    market_cap_display: str | None = None
    listed_shares: int | None = None
    trading_volume: int | None = None
    trading_value_rank: int | None = None
    market_trading_value_rank: int | None = None
    trading_value_percentile: float | None = None
    market_trading_value_percentile: float | None = None
    source: str
    unit_notes: dict[str, str] | None = None
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


class EvidenceSimilarPatternCaseItem(BaseModel):
    rank: int
    start_date: str
    end_date: str
    trading_days: int
    overall_similarity_score: float
    price_similarity_score: float
    ma_position_similarity_score: float
    volume_similarity_score: float
    start_close: float | None = None
    end_close: float | None = None
    return_rate: float | None = None
    max_return_after_pattern: float | None = None
    min_return_after_pattern: float | None = None
    after_5d_return: float | None = None
    after_10d_return: float | None = None
    after_20d_return: float | None = None
    gpt_note_ko: str


class EvidenceSimilarPatternCasesBlock(BaseModel):
    included: bool
    method: str
    search_trading_days: int
    pattern_window: int
    pattern_ma: int
    requested_limit: int
    returned_count: int
    weight: dict
    base_pattern: dict | None = None
    cases: list[EvidenceSimilarPatternCaseItem] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)


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
    similar_pattern_cases: EvidenceSimilarPatternCasesBlock | None = None
    caution_note: str | None = None


class EvidenceStrategyHorizonContextBlock(BaseModel):
    selected_horizon: str
    horizon_notes: list[str] = Field(default_factory=list)


class EvidenceAnalysisHorizonWeightsBlock(BaseModel):
    swing_weight: float
    long_term_weight: float


class EvidenceNewsSummaryItem(BaseModel):
    news_id: int
    title: str | None = None
    published_at: str | None = None
    source: str | None = None
    url: str | None = None
    summary: str | None = None
    ai_summary: str | None = None
    tag: str | None = None
    score: int | None = None
    sentiment: str | None = None
    risk_level: str | None = None
    event_type: str | None = None
    gpt_note_ko: str | None = None


class EvidenceNewsSummaryBlock(BaseModel):
    included: bool
    lookback_days: int
    max_items: int
    total_found: int
    items: list[EvidenceNewsSummaryItem] = Field(default_factory=list)


class EvidenceDisclosureSummaryItem(BaseModel):
    disclosure_id: int
    title: str | None = None
    disclosed_at: str | None = None
    report_name: str | None = None
    disclosure_url: str | None = None
    ai_summary: str | None = None
    tag: str | None = None
    score: int | None = None
    sentiment: str | None = None
    risk_level: str | None = None
    event_type: str | None = None
    gpt_note_ko: str | None = None


class EvidenceDisclosureSummaryBlock(BaseModel):
    included: bool
    lookback_days: int
    max_items: int
    total_found: int
    items: list[EvidenceDisclosureSummaryItem] = Field(default_factory=list)


class EvidenceRiskCounts(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    unknown: int = 0


class EvidenceRiskSummaryBlock(BaseModel):
    included: bool
    lookback_days: int
    news_risk_counts: EvidenceRiskCounts
    disclosure_risk_counts: EvidenceRiskCounts
    combined_risk_counts: EvidenceRiskCounts
    highest_risk_level: str
    risk_summary_ko: str
    caution_notes_ko: list[str] = Field(default_factory=list)


class EvidenceRecentEventTimelineItem(BaseModel):
    event_date: str | None = None
    source_type: str
    title: str | None = None
    summary: str | None = None
    risk_level: str | None = None
    sentiment: str | None = None
    event_type: str | None = None
    score: int | None = None
    gpt_note_ko: str | None = None


class AdvisoryEvidencePackageResponse(BaseModel):
    stock: EvidenceStockBlock
    price_summary: EvidencePriceSummaryBlock
    market_metrics_summary: EvidenceMarketMetricsSummaryBlock | None = None
    price_candle_reference: EvidencePriceCandleReferenceBlock | None = None
    strategy_horizon_context: EvidenceStrategyHorizonContextBlock | None = None
    analysis_horizon_weights: EvidenceAnalysisHorizonWeightsBlock | None = None
    scenario_questions_for_gpt: list[str] = Field(default_factory=list)
    news_summary_block: EvidenceNewsSummaryBlock | None = None
    disclosure_summary_block: EvidenceDisclosureSummaryBlock | None = None
    risk_summary_block: EvidenceRiskSummaryBlock | None = None
    recent_event_timeline: list[EvidenceRecentEventTimelineItem] = Field(default_factory=list)
    technical_indicators_block: dict | None = None
    data_freshness_block: dict | None = None
    executive_summary_for_gpt: dict | None = None
    news_summary: dict | None = None
    disclosure_summary: dict | None = None
    risk_summary: dict | None = None
    theme_summary: dict | None = None
    telegram_theme_summary: dict | None = None
    data_quality_notes: list[str] = Field(default_factory=list)
    instruction_guardrails: list[str] = Field(default_factory=list)
    generated_at: str
