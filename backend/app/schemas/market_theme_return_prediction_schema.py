from __future__ import annotations

from pydantic import BaseModel, Field


class MarketThemeReturnPredictionRequest(BaseModel):
    target_date: str
    theme_group_id: int | None = None


class MarketThemeReturnValidationRequest(BaseModel):
    target_date: str


class MarketThemeReturnPredictionRun(BaseModel):
    id: int
    target_date: str
    data_cutoff_date: str
    data_cutoff_at: str | None = None
    prediction_stage: str
    prediction_horizon: str
    official_method: str
    status: str
    revision_count: int
    rule_version: str
    model_version: str | None = None
    first_predicted_at: str
    last_predicted_at: str
    evaluated_at: str | None = None


class MarketThemeReturnPredictionItem(BaseModel):
    theme_id: int
    theme_name: str
    theme_group_id: int | None = None
    theme_group_name: str | None = None
    prediction_method: str = "RULE"
    is_official: bool = True
    model_version: str | None = None
    base_change_rate: float | None = None
    predicted_change_rate: float | None = None
    prediction_score: float | None = None
    top5_probability: float | None = None
    predicted_rank: int | None = None
    price_score: float | None = None
    flow_score: float | None = None
    breadth_score: float | None = None
    alignment_score: float | None = None
    liquidity_score: float | None = None
    market_environment_score: float | None = None
    penalty_score: float = 0
    data_coverage_rate: float = 0
    actual_change_rate: float | None = None
    actual_rank: int | None = None
    signed_gap: float | None = None
    absolute_gap: float | None = None
    rank_gap: int | None = None
    direction_hit: bool | None = None
    baseline_absolute_error: float | None = None
    prediction_effect: float | None = None
    evaluation_status: str


class MarketThemeReturnPredictionMetrics(BaseModel):
    theme_count: int
    evaluable_theme_count: int
    return_mae: float | None = None
    return_rmse: float | None = None
    mean_signed_gap: float | None = None
    mean_rank_error: float | None = None
    top1_hit: float | None = None
    precision_at_3: float | None = None
    precision_at_5: float | None = None
    precision_at_10: float | None = None
    direction_accuracy: float | None = None
    spearman_rank_correlation: float | None = None
    ndcg_at_5: float | None = None
    baseline_mae: float | None = None
    mae_improvement: float | None = None
    baseline_precision_at_5: float | None = None
    improved_theme_count: int = 0
    evaluation_status: str
    evaluated_at: str


class MarketThemeReturnPredictionAdvice(BaseModel):
    code: str
    diagnosis: str
    impact: str
    evidence: str
    current_setting: str
    suggested_range: str
    expected_effect: str
    parameter_code: str


class MarketThemeReturnMethodMetrics(BaseModel):
    prediction_method: str
    model_version: str = ""
    theme_count: int
    evaluable_theme_count: int
    return_mae: float | None = None
    return_rmse: float | None = None
    mean_signed_gap: float | None = None
    mean_rank_error: float | None = None
    precision_at_5: float | None = None
    direction_accuracy: float | None = None
    ndcg_at_5: float | None = None


class MarketThemeReturnPredictionResponse(BaseModel):
    status: str
    message: str | None = None
    data_cutoff_date: str | None = None
    default_target_date: str | None = None
    run: MarketThemeReturnPredictionRun | None = None
    items: list[MarketThemeReturnPredictionItem] = Field(default_factory=list)
    shadow_items: list[MarketThemeReturnPredictionItem] = Field(default_factory=list)
    metrics: MarketThemeReturnPredictionMetrics | None = None
    recommendations: list[MarketThemeReturnPredictionAdvice] = Field(default_factory=list)
    method_metrics: list[MarketThemeReturnMethodMetrics] = Field(default_factory=list)


class MarketThemeReturnMLRequest(BaseModel):
    target_date: str


class MarketThemeReturnMLMetrics(BaseModel):
    mae: float | None = None
    rmse: float | None = None
    mean_signed_gap: float | None = None
    direction_accuracy: float | None = None
    precision_at_3: float | None = None
    precision_at_5: float | None = None
    precision_at_10: float | None = None
    spearman: float | None = None
    ndcg_at_5: float | None = None
    mean_rank_error: float | None = None


class MarketThemeReturnMLCandidate(BaseModel):
    model_type: str
    model_version: str | None = None
    target_type: str = "RAW_RETURN"
    selection_gate_status: str = "NOT_EVALUATED"
    selection_reason: str | None = None
    improving_fold_count: int = 0
    validation_fold_count: int = 0
    metrics: MarketThemeReturnMLMetrics


class MarketThemeReturnMLTrainResponse(BaseModel):
    status: str
    message: str
    feature_version: str
    train_start_date: str | None = None
    train_end_date: str | None = None
    distinct_base_dates: int = 0
    train_row_count: int = 0
    theme_count: int = 0
    excluded_missing_label: int = 0
    excluded_low_coverage: int = 0
    validation_fold_count: int = 0
    candidates: list[MarketThemeReturnMLCandidate] = Field(default_factory=list)
    baseline_metrics: MarketThemeReturnMLMetrics | None = None
    rule_metrics: MarketThemeReturnMLMetrics | None = None
    selected_model_type: str | None = None
    model_version: str | None = None
    artifact_path: str | None = None
    sklearn_version: str | None = None
    proposed_shadow_model_version: str | None = None
    metric_version: str = "THEME_RETURN_METRIC_V2"


class MarketThemeReturnMLSelectRequest(BaseModel):
    model_version: str


class MarketThemeReturnMLPerformanceWindow(BaseModel):
    sample_size: int = 0
    sufficient: bool = False
    rule_metrics: MarketThemeReturnMLMetrics | None = None
    ml_metrics: MarketThemeReturnMLMetrics | None = None
    ndcg_difference: float | None = None
    precision_at_5_difference: float | None = None
    mean_rank_error_difference: float | None = None


class MarketThemeReturnMLStatusResponse(BaseModel):
    status: str
    available: bool
    model_version: str | None = None
    model_type: str | None = None
    feature_version: str | None = None
    trained_at: str | None = None
    train_start_date: str | None = None
    train_end_date: str | None = None
    distinct_train_dates: int = 0
    train_row_count: int = 0
    validation_fold_count: int = 0
    validation_metrics: MarketThemeReturnMLMetrics | None = None
    rule_metrics: MarketThemeReturnMLMetrics | None = None
    baseline_metrics: MarketThemeReturnMLMetrics | None = None
    artifact_path: str | None = None
    common_evaluated_runs: int = 0
    cumulative_rule_mae: float | None = None
    cumulative_ml_mae: float | None = None
    cumulative_rule_precision_at_5: float | None = None
    cumulative_ml_precision_at_5: float | None = None
    cumulative_rule_ndcg_at_5: float | None = None
    cumulative_ml_ndcg_at_5: float | None = None
    promotion_readiness: str = "실전 비교 데이터 부족"
    target_type: str | None = None
    selection_gate_status: str = "NOT_EVALUATED"
    selection_reason: str | None = None
    readiness: str = "NOT_READY"
    drift_status: str = "WATCH"
    recent_5: MarketThemeReturnMLPerformanceWindow | None = None
    recent_20: MarketThemeReturnMLPerformanceWindow | None = None
    all_common: MarketThemeReturnMLPerformanceWindow | None = None
    remaining_runs_for_review: int = 20
    advice_code: str = "ML_SAMPLE_INSUFFICIENT"
    advice_message: str = "실전 공통 검증 데이터가 부족합니다."


class MarketThemeObservationTrendRun(BaseModel):
    id: int
    target_date: str
    data_cutoff_date: str
    method: str
    feature_version: str
    display_mode: str
    calculated_at: str
    calculation_mode: str = "CURRENT_MARKET_DATA"
    market_refresh_status: str = "NOT_REQUESTED"
    market_indicator_refreshed_at: str | None = None
    market_indicator_data_asof_at: str | None = None


class MarketThemeReturnTrendPrediction(BaseModel):
    run: MarketThemeObservationTrendRun | None = None
    values: dict[int, float | None] = Field(default_factory=dict)
    ranks: dict[int, int | None] = Field(default_factory=dict)
    mode: str | None = None
    method: str | None = None
    feature_version: str | None = None
    calculated_at: str | None = None
