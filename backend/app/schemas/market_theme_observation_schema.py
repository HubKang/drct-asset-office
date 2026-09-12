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
    stage_code: str | None = None
    stage_label: str | None = None
    stage_summary: str | None = None
    flow_acceleration_score: float | None = None
    sustainability_score: float | None = None
    price_flow_gap: float | None = None
    prediction_percentile: float | None = None
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
    calculation_data_cutoff_date: str | None = None
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
    precision_at_10: float | None = None
    ndcg_at_5: float | None = None
    spearman: float | None = None
    mean_rank_error: float | None = None
    brier: float | None = None
    log_loss: float | None = None
    calibration_error: float | None = None
    raw_brier: float | None = None
    raw_log_loss: float | None = None
    raw_calibration_error: float | None = None
    top5_mean_actual_strength: float | None = None
    top5_actual_top10_rate: float | None = None
    top5_bottom_half_rate: float | None = None


class MarketThemeObservationMLFoldResult(BaseModel):
    fold: int
    train_start_date: str
    train_end_date: str
    validation_start_date: str
    validation_end_date: str
    metrics: MarketThemeObservationMLMetrics
    delta_precision_at_5: float | None = None


class MarketThemeObservationFeatureDiagnostic(BaseModel):
    feature_name: str
    feature_group: str
    structural_role: str
    missing_rate: float
    unique_count: int
    near_constant: bool = False


class MarketThemeObservationAblationResult(BaseModel):
    feature_group: str
    metrics: MarketThemeObservationMLMetrics
    delta_precision_at_5: float
    delta_ndcg_at_5: float
    delta_precision_top20: float = 0
    delta_top5_bottom_half_rate: float = 0
    verdict: str


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
    candidate_type: str = "ML"
    feature_version: str = "THEME_OBSERVATION_FEATURE_V2"
    parameters: dict[str, float | int | str] = Field(default_factory=dict)
    delta_precision_at_5: float | None = None
    delta_ndcg_at_5: float | None = None
    fold_results: list[MarketThemeObservationMLFoldResult] = Field(default_factory=list)
    worst_fold_precision_at_5: float | None = None
    fold_precision_at_5_std: float | None = None
    oos_metrics: MarketThemeObservationMLMetrics | None = None
    candidate_status: str = "EXPERIMENTAL"


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
    baseline_fold_results: list[MarketThemeObservationMLFoldResult] = Field(default_factory=list)
    feature_diagnostics: list[MarketThemeObservationFeatureDiagnostic] = Field(default_factory=list)
    ablation_results: list[MarketThemeObservationAblationResult] = Field(default_factory=list)
    oos_start_date: str | None = None
    oos_end_date: str | None = None
    oos_sample_days: int = 0
    gate_metric: str = "precision_top20"
    gate_required_improvement: float = 0.03
    recommended_candidate: str | None = None
    recommendation: str = "현 운영 Rule V2 유지"


class MarketThemePriceFlowStageMetric(BaseModel):
    stage_code: str
    stage_label: str
    sample_count: int
    sample_ratio: float
    top10_rate: float
    top20_rate: float
    mean_actual_percentile: float
    median_actual_percentile: float
    mean_actual_rank: float
    median_actual_rank: float
    bottom_half_rate: float
    top5_rate: float
    fold_win_count: int = 0
    worst_fold_top20_rate: float | None = None
    fold_top20_std: float | None = None


class MarketThemePriceFlowRadarProfile(BaseModel):
    price_strength: float | None = None
    flow_strength: float | None = None
    flow_acceleration: float | None = None
    breadth: float | None = None
    sustainability: float | None = None


class MarketThemePriceFlowRadarAxisResult(BaseModel):
    axis: str
    success_mean: float | None = None
    failure_mean: float | None = None
    difference: float | None = None


class MarketThemePriceFlowResearchResponse(BaseModel):
    status: str
    message: str
    stage_version: str
    feature_version: str
    data_start_date: str | None = None
    data_end_date: str | None = None
    signal_start_date: str | None = None
    signal_end_date: str | None = None
    sample_count: int = 0
    evaluated_dates: int = 0
    stage_metrics: list[MarketThemePriceFlowStageMetric] = Field(default_factory=list)
    first_half_stage_metrics: list[MarketThemePriceFlowStageMetric] = Field(default_factory=list)
    second_half_stage_metrics: list[MarketThemePriceFlowStageMetric] = Field(default_factory=list)
    success_radar: MarketThemePriceFlowRadarProfile = Field(default_factory=MarketThemePriceFlowRadarProfile)
    failure_radar: MarketThemePriceFlowRadarProfile = Field(default_factory=MarketThemePriceFlowRadarProfile)
    radar_axis_results: list[MarketThemePriceFlowRadarAxisResult] = Field(default_factory=list)
    rule_top5_bottom_half_rate: float | None = None
    severe_failure_count: int = 0


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


class MarketThemeObservationDiagnosticStagePerformance(BaseModel):
    stage_code: str
    sample_count: int
    top20_hit_rate: float | None = None
    mean_actual_relative_strength: float | None = None


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
    stage_performance: list[MarketThemeObservationDiagnosticStagePerformance] = Field(default_factory=list)
    score_bucket_performance: list[MarketThemeObservationDiagnosticScoreBucket] = Field(default_factory=list)
    diagnostic_status: str
    messages: list[MarketThemeObservationDiagnosticMessage] = Field(default_factory=list)
    ml_quality_days_since_training: int = 0
