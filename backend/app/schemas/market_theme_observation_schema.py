from __future__ import annotations

from pydantic import BaseModel, Field


class MarketThemeObservationRequest(BaseModel):
    target_date: str
    refresh_market_indicators: bool = False


class MarketThemeObservationRun(BaseModel):
    id: int
    target_date: str
    data_cutoff_date: str
    status: str
    method: str
    model_version: str | None = None
    feature_version: str
    display_mode: str
    calculated_at: str
    evaluated_at: str | None = None
    calculation_mode: str = "CURRENT_MARKET_DATA"
    market_refresh_requested: bool = False
    market_refresh_status: str = "NOT_REQUESTED"
    market_indicator_refreshed_at: str | None = None
    market_indicator_data_asof_at: str | None = None
    market_indicator_updated_count: int | None = None
    market_indicator_failed_count: int | None = None
    market_collection_run_id: int | None = None
    revision_count: int = 0


class MarketThemeObservationItem(BaseModel):
    theme_id: int
    theme_name: str
    theme_group_id: int | None = None
    theme_group_name: str | None = None
    observation_rank: int | None = None
    relative_strength_probability: float | None = None
    relative_strength_score: float | None = None
    top20_probability: float | None = None
    status_code: str
    confidence_level: str
    data_coverage_rate: float
    base_change_rate: float | None = None
    price_score: float | None = None
    flow_score: float | None = None
    breadth_score: float | None = None
    liquidity_score: float | None = None
    technical_score: float | None = None
    market_environment_score: float | None = None
    penalty_score: float = 0
    actual_change_rate: float | None = None
    actual_rank: int | None = None
    actual_relative_strength: float | None = None
    relative_strength_gap: float | None = None
    current_score: float | None = None
    refreshed_score: float | None = None
    actual_top20: bool | None = None
    rank_gap: int | None = None
    probability_error: float | None = None
    evaluation_status: str


class MarketThemeObservationMetrics(BaseModel):
    theme_count: int
    evaluable_theme_count: int
    precision_top20: float | None = None
    recall_top20: float | None = None
    f1_top20: float | None = None
    precision_at_5: float | None = None
    ndcg_at_5: float | None = None
    spearman_rank_correlation: float | None = None
    mean_rank_error: float | None = None
    brier_score: float | None = None
    log_loss: float | None = None
    calibration_error: float | None = None
    evaluation_status: str
    evaluated_at: str


class MarketThemeObservationResponse(BaseModel):
    status: str
    message: str | None = None
    data_cutoff_date: str | None = None
    default_target_date: str | None = None
    run: MarketThemeObservationRun | None = None
    items: list[MarketThemeObservationItem] = Field(default_factory=list)
    metrics: MarketThemeObservationMetrics | None = None
    actual_universe_count: int | None = None
    market_indicator_latest_refreshed_at: str | None = None
    pre_validation_status: str | None = None
    pre_validation_target_date: str | None = None
    pre_validation_modes: list[str] = Field(default_factory=list)
    pre_validation_quality_status: str | None = None
    pre_validation_message: str | None = None
    diagnostic_status: str | None = None


class MarketThemeObservationMLMetrics(BaseModel):
    precision_top20: float | None = None
    recall_top20: float | None = None
    f1_top20: float | None = None
    precision_at_5: float | None = None
    ndcg_at_5: float | None = None
    spearman: float | None = None
    mean_rank_error: float | None = None
    brier: float | None = None
    log_loss: float | None = None
    calibration_error: float | None = None
    raw_brier: float | None = None
    raw_log_loss: float | None = None
    raw_calibration_error: float | None = None


class MarketThemeObservationMLCandidate(BaseModel):
    model_type: str
    model_version: str | None = None
    target_type: str
    selection_gate_status: str
    calibration_status: str
    probability_display_mode: str
    improving_fold_count: int = 0
    validation_fold_count: int = 0
    metrics: MarketThemeObservationMLMetrics


class MarketThemeObservationMLTrainResponse(BaseModel):
    status: str
    message: str
    feature_version: str
    train_start_date: str | None = None
    train_end_date: str | None = None
    distinct_base_dates: int = 0
    train_row_count: int = 0
    qualified_date_count: int = 0
    excluded_universe_dates: int = 0
    validation_fold_count: int = 0
    candidates: list[MarketThemeObservationMLCandidate] = Field(default_factory=list)
    baseline_metrics: dict[str, MarketThemeObservationMLMetrics] = Field(default_factory=dict)


class MarketThemeObservationDiagnosticMetricSummary(BaseModel):
    evaluated_days: int = 0
    precision_top20: float | None = None
    precision_at_5: float | None = None
    ndcg_at_5: float | None = None
    spearman: float | None = None
    mean_rank_error: float | None = None


class MarketThemeObservationDiagnosticPeriod(BaseModel):
    quality_days: int = 0
    current: MarketThemeObservationDiagnosticMetricSummary
    refreshed: MarketThemeObservationDiagnosticMetricSummary


class MarketThemeObservationDiagnosticPairedSummary(BaseModel):
    paired_days: int = 0
    mean_rank_error_current: float | None = None
    mean_rank_error_refreshed: float | None = None
    mean_refresh_effect: float | None = None
    improved_theme_count: int = 0
    worsened_theme_count: int = 0
    unchanged_theme_count: int = 0


class MarketThemeObservationDiagnosticStatusPerformance(BaseModel):
    status_code: str | None = None
    sample_count: int
    top20_hit_rate: float | None = None
    mean_actual_rank: float | None = None
    mean_rank_error: float | None = None


class MarketThemeObservationDiagnosticScoreBucket(BaseModel):
    score_bucket: str
    sample_count: int
    top20_entry_rate: float | None = None
    mean_actual_rank_percentile: float | None = None


class MarketThemeObservationDiagnosticMessage(BaseModel):
    code: str
    severity: str
    title: str
    message: str


class MarketThemeObservationDiagnosticsResponse(BaseModel):
    quality_evaluated_days: int = 0
    recent_5: MarketThemeObservationDiagnosticPeriod
    recent_20: MarketThemeObservationDiagnosticPeriod
    all: MarketThemeObservationDiagnosticPeriod
    paired_correction: MarketThemeObservationDiagnosticPairedSummary
    status_performance: list[MarketThemeObservationDiagnosticStatusPerformance] = Field(default_factory=list)
    score_bucket_performance: list[MarketThemeObservationDiagnosticScoreBucket] = Field(default_factory=list)
    diagnostic_status: str
    messages: list[MarketThemeObservationDiagnosticMessage] = Field(default_factory=list)
    ml_quality_days_since_training: int = 0
