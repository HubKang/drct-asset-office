export type MarketThemeLatestReturn = {
  return_date: string | null;
  avg_change_rate: number | null;
  last_refreshed_at: string | null;
  stock_count: number;
  success_stock_count: number;
  failed_stock_count: number;
  total_trading_value_100m?: number | null;
};

export type MarketThemeReturnStock = {
  stock_id: number;
  stock_code: string | null;
  stock_name: string;
  stock_memo?: string | null;
  trading_value_100m: number | null;
  change_rate: number | null;
  current_price?: number | null;
  data_status: "success" | "failed" | "missing";
  error_message?: string | null;
  flow_summary?: StockDailyFlowSummary | null;
};

export type StockDailyFlowSummary = {
  individual_net_amount: number | null;
  foreign_net_amount: number | null;
  institution_net_amount: number | null;
  program_net_amount: number | null;
  individual_flow_strength: number | null;
  foreign_flow_strength: number | null;
  institution_flow_strength: number | null;
  program_flow_strength: number | null;
  summary_code: "FOREIGN_INSTITUTION_BUY" | "FOREIGN_LEAD" | "INSTITUTION_LEAD" | "INDIVIDUAL_LEAD" | "FOREIGN_INSTITUTION_SELL" | "MIXED" | "NO_DATA";
  has_investor_data: boolean;
  has_program_data: boolean;
};

export type ThemeActorDailyFlowSummary = {
  net_amount: number | null;
  flow_strength: number | null;
  positive_stock_count: number;
  data_stock_count: number;
};

export type ThemeDailyFlowSummary = {
  base_date: string;
  aggregation_basis: "CURRENT_ACTIVE_LINKS";
  attribution_mode: "FULL";
  connected_stock_count: number;
  investor_data_stock_count: number;
  program_data_stock_count: number;
  complete_stock_count: number;
  completeness_ratio: number;
  quality_status: "ENOUGH" | "PARTIAL" | "INSUFFICIENT" | "EMPTY";
  theme_trading_value: number | null;
  summary_code: string;
  individual: ThemeActorDailyFlowSummary;
  foreign: ThemeActorDailyFlowSummary;
  institution: ThemeActorDailyFlowSummary;
  program: ThemeActorDailyFlowSummary;
};

export type MarketThemeLatestReturnDetail = {
  theme_id: number;
  theme_name: string;
  theme_group_name: string | null;
  return_date: string | null;
  avg_change_rate: number | null;
  snapshot_at: string | null;
  stock_count: number;
  success_stock_count: number;
  failed_stock_count: number;
  rising_stock_count: number;
  falling_stock_count: number;
  flat_stock_count: number;
  total_trading_value_100m: number | null;
  flow_summary?: ThemeDailyFlowSummary | null;
  stocks: MarketThemeReturnStock[];
};

export type MarketThemeFlowChartSeriesItem = {
  trade_date: string;
  theme_daily_return_pct: number | null;
  theme_cumulative_return_pct: number | null;
  theme_trading_value: number | null;
  individual_daily_amount: number | null;
  individual_cumulative_amount: number | null;
  foreign_daily_amount: number | null;
  foreign_cumulative_amount: number | null;
  institution_daily_amount: number | null;
  institution_cumulative_amount: number | null;
  program_daily_amount: number | null;
  program_cumulative_amount: number | null;
  individual_positive_stock_count: number;
  foreign_positive_stock_count: number;
  institution_positive_stock_count: number;
  program_positive_stock_count: number;
  individual_data_stock_count: number;
  foreign_data_stock_count: number;
  institution_data_stock_count: number;
  program_data_stock_count: number;
  investor_data_stock_count: number;
  complete_stock_count: number;
  connected_stock_count: number;
  completeness_ratio: number;
};

export type MarketThemeFlowChartResponse = {
  theme_id: number;
  theme_name: string;
  period: { code: MarketThemePriceFlowPeriod; requested_trading_days: number; actual_trading_days: number; start_date: string | null; end_date: string | null };
  latest_theme_return_date: string | null;
  latest_flow_date: string | null;
  common_latest_date: string | null;
  aggregation_basis: "CURRENT_ACTIVE_LINKS";
  attribution_mode: "FULL";
  data_quality: "ENOUGH" | "PARTIAL" | "INSUFFICIENT" | "EMPTY";
  summary: {
    theme_return_pct: number | null;
    individual: { cumulative_amount: number | null; positive_days: number; positive_stock_count: number; data_stock_count: number };
    foreign: { cumulative_amount: number | null; positive_days: number; positive_stock_count: number; data_stock_count: number };
    institution: { cumulative_amount: number | null; positive_days: number; positive_stock_count: number; data_stock_count: number };
    program: { cumulative_amount: number | null; positive_days: number; positive_stock_count: number; data_stock_count: number };
  };
  series: MarketThemeFlowChartSeriesItem[];
  focus_date: string | null;
  selected: MarketThemeFlowChartSeriesItem | null;
};

export type MarketThemeFlowTrendActor = "FOREIGN" | "INSTITUTION" | "FOREIGN_INSTITUTION" | "INDIVIDUAL" | "PROGRAM";
export type MarketThemeFlowTrendMetric = "FLOW_STRENGTH" | "NET_AMOUNT" | "BREADTH";
export type MarketThemeFlowTrendAttribution = "FRACTIONAL" | "FULL";
export type MarketThemeFlowTrendQuality = "ENOUGH" | "PARTIAL" | "INSUFFICIENT" | "EMPTY";

export type MarketThemeFlowTrendContributor = {
  stock_id: number; stock_code: string | null; stock_name: string; net_buy_amount: number;
};
export type MarketThemeFlowTrendCell = {
  trade_date: string; net_buy_amount: number | null; trading_value: number | null;
  flow_strength: number | null; breadth_ratio: number | null;
  positive_stock_count: number; negative_stock_count: number; zero_stock_count: number;
  actor_data_stock_count: number; connected_stock_count: number; missing_stock_count: number;
  completeness_ratio: number; data_quality: MarketThemeFlowTrendQuality;
  theme_return_pct: number | null; top_contributors: MarketThemeFlowTrendContributor[];
};
export type MarketThemeFlowTrendPeriodSummary = {
  cumulative_net_buy_amount: number | null; cumulative_trading_value: number | null;
  flow_strength: number | null; latest_breadth_ratio: number | null;
  positive_stock_count: number; actor_data_stock_count: number; current_streak: number;
  connected_stock_count: number; completeness_ratio: number; data_quality: MarketThemeFlowTrendQuality;
};
export type MarketThemeFlowTrendTheme = {
  theme_id: number; theme_name: string; theme_group_id: number | null; theme_group_name: string | null;
  sort_order: number; connected_stock_count: number; twenty_day_summary: MarketThemeFlowTrendPeriodSummary;
  cells: MarketThemeFlowTrendCell[];
};
export type MarketThemeFlowTrendTopItem = {
  theme_id: number; theme_name: string; flow_strength: number | null; net_buy_amount: number | null;
  breadth_ratio: number | null; positive_stock_count: number; actor_data_stock_count: number;
  current_streak: number; completeness_ratio: number; data_quality: MarketThemeFlowTrendQuality;
};
export type MarketThemeFlowTrendResponse = {
  request: {
    end_date: string; actual_end_date: string | null; recent_days: number; actor: MarketThemeFlowTrendActor;
    metric: MarketThemeFlowTrendMetric; attribution_mode: MarketThemeFlowTrendAttribution;
    aggregation_basis: "CURRENT_ACTIVE_LINKS"; theme_group_id: number | null; search: string | null; limit: number | null;
  };
  dates: string[];
  summary: { top_today: MarketThemeFlowTrendTopItem | null; top_five_day: MarketThemeFlowTrendTopItem | null; top_breadth: MarketThemeFlowTrendTopItem | null; top_streak: MarketThemeFlowTrendTopItem | null };
  themes: MarketThemeFlowTrendTheme[];
  performance: Record<string, number | boolean>;
};
export type MarketThemeFlowTrendParams = {
  end_date: string; recent_days?: number; actor: MarketThemeFlowTrendActor; metric: MarketThemeFlowTrendMetric;
  attribution: MarketThemeFlowTrendAttribution; theme_group_id?: number; search?: string; limit?: number; refresh?: boolean; signal?: AbortSignal;
};

export type MarketThemeReturnRefreshRequest = {
  scope: "all_active" | "selected";
  theme_ids?: number[];
  mode?: "FULL" | "PILOT";
  pilot_stock_ids?: number[];
  pilot_stock_codes?: string[];
  max_stocks?: number;
};

export type MarketThemeReturnRefreshItem = {
  theme_id: number;
  theme_name: string;
  return_date: string;
  avg_change_rate: number | null;
  stock_count: number;
  success_stock_count: number;
  failed_stock_count: number;
  total_trading_value_100m: number | null;
  save_action: string;
};

export type MarketThemeReturnRefreshResponse = {
  success: boolean;
  return_date: string;
  refreshed_at: string;
  theme_count: number;
  stock_count: number;
  success_stock_count: number;
  failed_stock_count: number;
  inserted_count: number;
  updated_count: number;
  theme_stock_link_count?: number;
  unique_stock_count?: number;
  price_api_call_count?: number;
  rest_post_calls?: number;
  auth_token_issue_count?: number;
  ka10001_calls?: number;
  ka10015_calls?: number;
  price_fetch_ms?: number;
  calc_ms?: number;
  db_upsert_ms?: number;
  total_ms?: number;
  run_id?: number | null;
  job_status?: "COMPLETED" | "PARTIAL" | "FAILED";
  price_success_count?: number;
  price_failed_count?: number;
  price_inserted_count?: number;
  price_updated_count?: number;
  technical_success_count?: number;
  technical_failed_count?: number;
  technical_saved_count?: number;
  investor_success_count?: number;
  investor_failed_count?: number;
  program_success_count?: number;
  program_failed_count?: number;
  flow_inserted_count?: number;
  flow_updated_count?: number;
  latest_price_date?: string | null;
  latest_investor_flow_date?: string | null;
  latest_program_flow_date?: string | null;
  collection_mode?: "FULL" | "PILOT";
  processed_stock_codes?: string[];
  failure_items?: Array<{
    stock_id?: number | null;
    stock_code?: string | null;
    stock_name?: string | null;
    stage: string;
    message: string;
    error_code?: string;
    user_message?: string | null;
    internal_summary?: string | null;
    retryable?: boolean;
  }>;
  price_stage?: MarketThemePriceFlowStageResult;
  technical_stage?: MarketThemePriceFlowStageResult;
  investor_stage?: MarketThemePriceFlowStageResult;
  program_stage?: MarketThemePriceFlowStageResult;
  theme_return_stage?: MarketThemePriceFlowStageResult;
  target_results?: Array<{
    stock_id: number;
    stock_code: string;
    stock_name: string;
    market?: string | null;
    price_status: string;
    technical_status: string;
    investor_status: string;
    program_status: string;
    error_code?: string | null;
    error_message?: string | null;
  }>;
  items: MarketThemeReturnRefreshItem[];
  message?: string | null;
};

export type MarketThemeReturnRecalculationPreview = {
  theme_id: number;
  theme_name: string;
  connected_stock_count: number;
  period_from: string | null;
  period_to: string | null;
  data_source: "STORED_STOCK_DAILY_PRICES";
};

export type MarketThemeReturnRecalculationResponse = MarketThemeReturnRecalculationPreview & {
  success: boolean;
  processed_date_count: number;
  inserted_count: number;
  updated_count: number;
  skipped_date_count: number;
  recalculated_at: string;
};

export type MarketThemePriceFlowJobStartResponse = {
  job_id: string;
  status: string;
  message: string;
  requested_at: string;
};

export type MarketThemePriceFlowStageResult = {
  target_count: number;
  attempted_count: number;
  success_count: number;
  up_to_date_count: number;
  no_data_count: number;
  skipped_count: number;
  failed_count: number;
  inserted_rows: number;
  updated_rows: number;
};

export type MarketThemePriceFlowJobStatusResponse = {
  job_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED";
  stage: string;
  completed_count: number;
  total_count: number;
  current_stage: string;
  current_stage_label: string;
  completed_stock_count: number;
  total_stock_count: number;
  failed_stock_count: number;
  price_result: MarketThemePriceFlowStageResult;
  technical_indicator_result: MarketThemePriceFlowStageResult;
  investor_flow_result: MarketThemePriceFlowStageResult;
  program_flow_result: MarketThemePriceFlowStageResult;
  theme_return_result: MarketThemePriceFlowStageResult;
  requested_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  failures?: NonNullable<MarketThemeReturnRefreshResponse["failure_items"]>;
  message?: string | null;
  result?: MarketThemeReturnRefreshResponse | null;
};

export type MarketThemePriceFlowPeriod = "1M" | "3M" | "6M";
export type MarketThemePriceFlowUnit = "QUANTITY" | "AMOUNT";
export type MarketThemePriceFlowView = "ACTUAL" | "NORMALIZED";

export type MarketThemePriceFlowChartParams = {
  period: MarketThemePriceFlowPeriod;
  unit: MarketThemePriceFlowUnit;
  view: MarketThemePriceFlowView;
  theme_id?: number;
};

export type MarketThemePriceFlowSeriesItem = {
  trade_date: string;
  close_price: number | null;
  daily_return_pct: number | null;
  price_return_pct: number | null;
  individual_daily: number | null;
  individual_cumulative: number | null;
  foreign_daily: number | null;
  foreign_cumulative: number | null;
  institution_daily: number | null;
  institution_cumulative: number | null;
  program_daily: number | null;
  program_cumulative: number | null;
  normalized_price: number | null;
  normalized_individual: number | null;
  normalized_foreign: number | null;
  normalized_institution: number | null;
  normalized_program: number | null;
};

export type MarketThemePriceFlowEvent = {
  event_date: string;
  event_count: number;
  is_current_theme: boolean;
  items: Array<{
    theme_id: number | null;
    theme_name: string | null;
    memo: string | null;
    is_current_theme: boolean;
  }>;
};

export type MarketThemePriceFlowChartResponse = {
  stock: { stock_id: number; stock_code: string; stock_name: string; market: string | null };
  requested_unit: MarketThemePriceFlowUnit;
  requested_view: MarketThemePriceFlowView;
  period: {
    code: MarketThemePriceFlowPeriod;
    requested_trading_days: number;
    actual_trading_days: number;
    start_date: string | null;
    end_date: string | null;
  };
  latest_dates: {
    price: string | null;
    investor: string | null;
    program: string | null;
    common: string | null;
  };
  data_quality: {
    status: "ENOUGH" | "PERIOD_SHORT" | "PARTIAL" | "LATEST_MISMATCH" | "EMPTY";
    valid_days: number;
    missing_price_days: number;
    missing_investor_days: number;
    missing_program_days: number;
    completeness_ratio: number;
  };
  summary: {
    price_return_pct: number | null;
    individual_cumulative: number | null;
    foreign_cumulative: number | null;
    institution_cumulative: number | null;
    program_cumulative: number | null;
    individual_positive_days: number;
    foreign_positive_days: number;
    institution_positive_days: number;
    program_positive_days: number;
    individual_streak: number;
    foreign_streak: number;
    institution_streak: number;
    program_streak: number;
  };
  series: MarketThemePriceFlowSeriesItem[];
  events: MarketThemePriceFlowEvent[];
};

export type MarketThemeMonthlyReturnDailyItem = {
  return_date: string;
  avg_change_rate: number | null;
  rolling_30d_change_rate?: number | null;
  total_trading_value_100m: number | null;
  rising_stock_count: number;
  falling_stock_count: number;
  flat_stock_count: number;
};

export type MarketThemeMonthlyReturnThemeItem = {
  theme_id: number;
  theme_name: string;
  theme_group_id: number | null;
  theme_group_name: string | null;
  monthly_compound_return: number | null;
  monthly_sum_return: number | null;
  period_compound_return?: number | null;
  period_sum_return?: number | null;
  total_trading_value_100m: number | null;
  rising_days: number;
  falling_days: number;
  flat_days: number;
  data_days: number;
  rolling_30d_change_rate?: number | null;
  weighted_return_10d?: number | null;
  weighted_return_score?: number | null;
  positive_days_10d?: number;
  observed_days_10d?: number;
  persistence_10d?: number | null;
  recent_5d_return?: number | null;
  previous_5d_return?: number | null;
  momentum_delta?: number | null;
  momentum_score?: number | null;
  last_positive_impulse_date?: string | null;
  days_since_positive_impulse?: number | null;
  freshness_score?: number | null;
  rolling_30d_peak?: number | null;
  rolling_30d_peak_gap?: number | null;
  stale_penalty?: number;
  theme_strength_score?: number | null;
  strength_status_code?: "IGNITION" | "PERSISTENT" | "SLOWDOWN" | "FADING" | "NEUTRAL" | "INSUFFICIENT";
  strength_status_name?: string;
  persistence_rank?: number | null;
  current_strength_rank?: number | null;
  rolling_30d_rank?: number | null;
  daily_returns: MarketThemeMonthlyReturnDailyItem[];
};

export type MarketThemeMonthlyReturnSummaryTopItem = {
  theme_id: number;
  theme_name: string;
  monthly_compound_return: number | null;
  period_compound_return?: number | null;
  total_trading_value_100m: number | null;
  continuous_rising_days?: number | null;
  rolling_30d_change_rate?: number | null;
  theme_strength_score?: number | null;
  persistence_10d?: number | null;
  strength_status_code?: string | null;
  strength_status_name?: string | null;
};

export type MarketThemeMonthlyReturnResponse = {
  month?: string | null;
  end_date?: string | null;
  days?: number | null;
  active_only: boolean;
  display_start_date: string;
  display_end_date: string;
  sort_by?: "CURRENT_STRENGTH" | "ROLLING_30D_RETURN" | null;
  themes: MarketThemeMonthlyReturnThemeItem[];
  summary: {
    top_rising_theme: MarketThemeMonthlyReturnSummaryTopItem | null;
    top_falling_theme: MarketThemeMonthlyReturnSummaryTopItem | null;
    top_trading_value_theme: MarketThemeMonthlyReturnSummaryTopItem | null;
    rising_day_theme: MarketThemeMonthlyReturnSummaryTopItem | null;
    top_continuous_rising_theme?: MarketThemeMonthlyReturnSummaryTopItem | null;
    current_strength_top?: MarketThemeMonthlyReturnSummaryTopItem | null;
    rolling_30d_top?: MarketThemeMonthlyReturnSummaryTopItem | null;
    trading_value_top?: MarketThemeMonthlyReturnSummaryTopItem | null;
    persistence_top?: MarketThemeMonthlyReturnSummaryTopItem | null;
  };
  prediction?: MarketThemeReturnTrendPrediction | null;
};

export type MarketThemeReturnPredictionRun = {
  id: number;
  target_date: string;
  data_cutoff_date: string;
  data_cutoff_at: string | null;
  prediction_stage: string;
  prediction_horizon: string;
  official_method: string;
  status: "DRAFT" | "PREDICTED" | "WAITING_ACTUAL" | "EVALUATED" | "CANCELLED";
  revision_count: number;
  rule_version: string;
  model_version: string | null;
  first_predicted_at: string;
  last_predicted_at: string;
  evaluated_at: string | null;
};

export type MarketThemeReturnPredictionItem = {
  theme_id: number; theme_name: string; theme_group_id: number | null; theme_group_name: string | null;
  prediction_method: string; is_official: boolean; model_version: string | null; base_change_rate: number | null;
  predicted_change_rate: number | null; prediction_score: number | null; predicted_rank: number | null;
  top5_probability: number | null;
  price_score: number | null; flow_score: number | null; breadth_score: number | null;
  alignment_score: number | null; liquidity_score: number | null; market_environment_score: number | null;
  penalty_score: number; data_coverage_rate: number; actual_change_rate: number | null; actual_rank: number | null;
  signed_gap: number | null; absolute_gap: number | null; rank_gap: number | null; direction_hit: boolean | null;
  baseline_absolute_error: number | null; prediction_effect: number | null; evaluation_status: string;
};

export type MarketThemeReturnPredictionMetrics = {
  theme_count: number; evaluable_theme_count: number; return_mae: number | null; return_rmse: number | null;
  mean_signed_gap: number | null; mean_rank_error: number | null; top1_hit: number | null;
  precision_at_3: number | null; precision_at_5: number | null; precision_at_10: number | null;
  direction_accuracy: number | null; spearman_rank_correlation: number | null; ndcg_at_5: number | null;
  baseline_mae: number | null; mae_improvement: number | null; baseline_precision_at_5: number | null;
  improved_theme_count: number; evaluation_status: string; evaluated_at: string;
};

export type MarketThemeReturnPredictionAdvice = {
  code: string; diagnosis: string; impact: string; evidence: string; current_setting: string;
  suggested_range: string; expected_effect: string; parameter_code: string;
};

export type MarketThemeReturnPredictionResponse = {
  status: string; message: string | null; data_cutoff_date: string | null; default_target_date: string | null;
  run: MarketThemeReturnPredictionRun | null; items: MarketThemeReturnPredictionItem[];
  shadow_items: MarketThemeReturnPredictionItem[];
  metrics: MarketThemeReturnPredictionMetrics | null; recommendations: MarketThemeReturnPredictionAdvice[];
  method_metrics: MarketThemeReturnMethodMetrics[];
};

export type MarketThemeObservationRun = {
  id: number; target_date: string; data_cutoff_date: string; status: string; method: string;
  model_version: string | null; feature_version: string; display_mode: "PROBABILITY" | "SCORE";
  calculated_at: string; evaluated_at: string | null;
  calculation_mode: "CURRENT_MARKET_DATA" | "REFRESHED_MARKET_DATA";
  market_refresh_requested: boolean; market_refresh_status: "NOT_REQUESTED" | "SUCCESS" | "PARTIAL" | "FAILED";
  market_indicator_refreshed_at: string | null; market_indicator_data_asof_at: string | null;
  market_indicator_updated_count: number | null; market_indicator_failed_count: number | null;
  market_collection_run_id: number | null; revision_count: number;
};

export type MarketThemeObservationItem = {
  theme_id: number; theme_name: string; theme_group_id: number | null; theme_group_name: string | null;
  observation_rank: number | null; relative_strength_probability: number | null; relative_strength_score: number | null;
  top20_probability: number | null; status_code: "FLOW_LEADING" | "STRONG_CONTINUATION" | "REVERSAL_WATCH" | "NEUTRAL" | "OVERHEAT_RISK" | "FLOW_EXIT";
  confidence_level: "HIGH" | "MEDIUM" | "LOW"; data_coverage_rate: number; base_change_rate: number | null;
  price_score: number | null; flow_score: number | null; breadth_score: number | null; liquidity_score: number | null;
  technical_score: number | null; market_environment_score: number | null; penalty_score: number;
  actual_change_rate: number | null; actual_rank: number | null; actual_top20: boolean | null;
  actual_relative_strength: number | null; relative_strength_gap: number | null;
  current_score: number | null; refreshed_score: number | null;
  rank_gap: number | null; probability_error: number | null; evaluation_status: string;
};

export type MarketThemeObservationMetrics = {
  theme_count: number; evaluable_theme_count: number; precision_top20: number | null; recall_top20: number | null;
  f1_top20: number | null; precision_at_5: number | null; ndcg_at_5: number | null;
  spearman_rank_correlation: number | null; mean_rank_error: number | null; brier_score: number | null;
  log_loss: number | null; calibration_error: number | null; evaluation_status: string; evaluated_at: string;
};

export type MarketThemeObservationResponse = {
  status: string; message: string | null; data_cutoff_date: string | null; default_target_date: string | null;
  calculation_data_cutoff_date: string | null;
  run: MarketThemeObservationRun | null; items: MarketThemeObservationItem[]; metrics: MarketThemeObservationMetrics | null;
  actual_universe_count: number | null;
  market_indicator_latest_refreshed_at: string | null;
  pre_validation_status?: string | null; pre_validation_target_date?: string | null;
  pre_validation_modes?: string[]; pre_validation_quality_status?: string | null;
  pre_validation_message?: string | null; diagnostic_status?: string | null;
};

export type MarketThemeObservationDiagnosticMetricSummary = {
  evaluated_days: number; precision_top20: number | null; precision_at_5: number | null;
  ndcg_at_5: number | null; spearman: number | null; mean_rank_error: number | null;
};
export type MarketThemeObservationDiagnosticPeriod = {
  quality_days: number; current: MarketThemeObservationDiagnosticMetricSummary; refreshed: MarketThemeObservationDiagnosticMetricSummary;
};
export type MarketThemeObservationDiagnosticsResponse = {
  quality_evaluated_days: number;
  recent_5: MarketThemeObservationDiagnosticPeriod;
  recent_20: MarketThemeObservationDiagnosticPeriod;
  all: MarketThemeObservationDiagnosticPeriod;
  paired_correction: {
    paired_days: number; mean_rank_error_current: number | null; mean_rank_error_refreshed: number | null;
    mean_refresh_effect: number | null; improved_theme_count: number; worsened_theme_count: number; unchanged_theme_count: number;
  };
  status_performance: Array<{ status_code: string | null; sample_count: number; top20_hit_rate: number | null; mean_actual_rank: number | null; mean_rank_error: number | null; }>;
  score_bucket_performance: Array<{ score_bucket: string; sample_count: number; top20_entry_rate: number | null; mean_actual_rank_percentile: number | null; }>;
  diagnostic_status: string;
  messages: Array<{ code: string; severity: string; title: string; message: string; }>;
  ml_quality_days_since_training: number;
};

export type MarketThemeObservationMLTrainResponse = {
  status: string; message: string; feature_version: string; train_start_date: string | null; train_end_date: string | null;
  distinct_base_dates: number; train_row_count: number; qualified_date_count: number; excluded_universe_dates: number;
  validation_fold_count: number; candidates: Array<{ model_type: string; model_version: string | null; target_type: string;
    selection_gate_status: string; calibration_status: string; probability_display_mode: string; improving_fold_count: number;
    validation_fold_count: number; metrics: { precision_top20: number | null; recall_top20: number | null; f1_top20: number | null;
      precision_at_5: number | null; ndcg_at_5: number | null; spearman: number | null; mean_rank_error: number | null;
      brier: number | null; log_loss: number | null; calibration_error: number | null; raw_brier: number | null;
      raw_log_loss: number | null; raw_calibration_error: number | null; }; }>;
};

export type MarketThemeReturnMethodMetrics = {
  prediction_method: string; model_version: string; theme_count: number; evaluable_theme_count: number;
  return_mae: number | null; return_rmse: number | null; mean_signed_gap: number | null;
  mean_rank_error: number | null; precision_at_5: number | null; direction_accuracy: number | null; ndcg_at_5: number | null;
};

export type MarketThemeReturnMLMetrics = {
  mae: number | null; rmse: number | null; mean_signed_gap: number | null; direction_accuracy: number | null;
  precision_at_3: number | null; precision_at_5: number | null; precision_at_10: number | null;
  spearman: number | null; ndcg_at_5: number | null; mean_rank_error: number | null;
};

export type MarketThemeReturnMLStatus = {
  status: string; available: boolean; model_version: string | null; model_type: string | null; feature_version: string | null;
  trained_at: string | null; train_start_date: string | null; train_end_date: string | null; distinct_train_dates: number;
  train_row_count: number; validation_fold_count: number; validation_metrics: MarketThemeReturnMLMetrics | null;
  rule_metrics: MarketThemeReturnMLMetrics | null; baseline_metrics: MarketThemeReturnMLMetrics | null; artifact_path: string | null;
  common_evaluated_runs: number; cumulative_rule_mae: number | null; cumulative_ml_mae: number | null;
  cumulative_rule_precision_at_5: number | null; cumulative_ml_precision_at_5: number | null;
  cumulative_rule_ndcg_at_5: number | null; cumulative_ml_ndcg_at_5: number | null; promotion_readiness: string;
  target_type: string | null; selection_gate_status: string; selection_reason: string | null;
  readiness: "NOT_READY" | "OBSERVE" | "ELIGIBLE_FOR_REVIEW"; drift_status: "STABLE" | "WATCH" | "DEGRADED";
  recent_5: MarketThemeReturnMLPerformanceWindow | null; recent_20: MarketThemeReturnMLPerformanceWindow | null;
  all_common: MarketThemeReturnMLPerformanceWindow | null; remaining_runs_for_review: number;
  advice_code: string; advice_message: string;
};

export type MarketThemeReturnMLPerformanceWindow = {
  sample_size: number; sufficient: boolean; rule_metrics: MarketThemeReturnMLMetrics | null;
  ml_metrics: MarketThemeReturnMLMetrics | null; ndcg_difference: number | null;
  precision_at_5_difference: number | null; mean_rank_error_difference: number | null;
};

export type MarketThemeReturnMLTrainResponse = {
  status: string; message: string; feature_version: string; train_start_date: string | null; train_end_date: string | null;
  distinct_base_dates: number; train_row_count: number; theme_count: number; excluded_missing_label: number;
  excluded_low_coverage: number; validation_fold_count: number; candidates: Array<{
    model_type: string; model_version: string | null; target_type: string; selection_gate_status: string;
    selection_reason: string | null; improving_fold_count: number; validation_fold_count: number;
    metrics: MarketThemeReturnMLMetrics;
  }>;
  baseline_metrics: MarketThemeReturnMLMetrics | null; rule_metrics: MarketThemeReturnMLMetrics | null;
  selected_model_type: string | null; model_version: string | null; artifact_path: string | null; sklearn_version: string | null;
  proposed_shadow_model_version: string | null; metric_version: string;
};

export type MarketThemeReturnTrendPrediction = {
  run: { id: number; target_date: string; data_cutoff_date: string; method: string; feature_version: string;
    display_mode: "PROBABILITY" | "SCORE"; calculated_at: string; calculation_mode: "CURRENT_MARKET_DATA" | "REFRESHED_MARKET_DATA";
    market_refresh_status: string; market_indicator_refreshed_at: string | null; market_indicator_data_asof_at: string | null } | null;
  values: Record<number, number | null>;
  ranks: Record<number, number | null>;
  mode: "PROBABILITY" | "SCORE" | null;
  method: string | null;
  feature_version: string | null;
  calculated_at: string | null;
};

export type MarketThemeMonthlyReturnParams = {
  month: string;
  active_only?: boolean;
  theme_group_id?: number;
  keyword?: string;
  limit?: number;
  lookback_days?: number;
};

export type MarketThemeRangeReturnParams = {
  end_date: string;
  days?: number;
  active_only?: boolean;
  theme_group_id?: number;
  keyword?: string;
  limit?: number;
  sort_by?: "CURRENT_STRENGTH" | "ROLLING_30D_RETURN";
};
export type MarketThemeType = "industry" | "theme" | "custom" | "telegram";
export type MarketThemeLevel = "THEME_GROUP" | "THEME";

export type MarketTheme = {
  id: number;
  theme_name: string;
  theme_code: string;
  theme_type: MarketThemeType;
  theme_level: MarketThemeLevel;
  description: string | null;
  keywords: string[];
  parent_theme_id: number | null;
  parent_theme_name?: string | null;
  is_supply_theme: number;
  is_active: number;
  sort_order: number;
  stock_count: number;
  linked_stock_count?: number;
  keyword_count?: number;
  child_theme_count?: number;
  supply_child_theme_count?: number;
  latest_return?: MarketThemeLatestReturn | null;
  created_at: string;
  updated_at: string;
};

export type MarketThemeDeleteResponse = {
  deleted_theme_id: number;
  deleted_theme_name: string;
  deleted_theme_count: number;
  deleted_related_row_count: number;
  detached_event_reference_count: number;
};

export type MarketThemeCreateInput = {
  theme_name: string;
  theme_code?: string;
  theme_type: MarketThemeType;
  theme_level?: MarketThemeLevel;
  description?: string | null;
  keywords: string[];
  parent_theme_id?: number | null;
  is_supply_theme?: number;
  sort_order?: number;
  is_active?: number;
};

export type MarketThemeUpdateInput = {
  theme_name: string;
  theme_type: MarketThemeType;
  theme_level?: MarketThemeLevel;
  description?: string | null;
  keywords: string[];
  parent_theme_id?: number | null;
  is_supply_theme?: number;
  sort_order?: number;
  is_active?: number;
};

export type MarketThemeListParams = {
  is_active?: number;
  theme_type?: string;
  theme_level?: MarketThemeLevel;
  parent_theme_id?: number;
  is_supply_theme?: number;
  keyword?: string;
  limit?: number;
  offset?: number;
};

export type MarketThemeStock = {
  mapping_id: number;
  theme_id: number;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  market: string | null;
  mapping_source: string;
  confidence_score: number | null;
  is_primary: number;
  is_active: number;
  stock_memo: string | null;
  supply_day_count: number;
  recent_30d_supply_day_count: number;
  first_supply_date: string | null;
  last_supply_date: string | null;
  created_at: string;
  updated_at: string;
};

export type MarketThemeStockSupplyCurrentTheme = {
  theme_id: number;
  theme_name: string;
  color: string;
};

export type MarketThemeStockLinkedThemeSupplySummary = {
  theme_id: number;
  theme_name: string;
  supply_count: number;
  supply_dates: string[];
  is_current_theme: boolean;
};

export type MarketThemeStockSupplyMemo = {
  detected_date: string;
  memo: string;
  source?: string | null;
  is_current_theme_supply_date: boolean;
};
export type MarketThemeStockSupplySummary = {
  theme_id: number;
  theme_name: string;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  supply_day_count: number;
  recent_30d_supply_day_count: number;
  first_supply_date: string | null;
  last_supply_date: string | null;
  all_theme_supply_day_count: number;
  recent_supply_dates: string[];
  current_theme: MarketThemeStockSupplyCurrentTheme;
  linked_theme_supply_summaries: MarketThemeStockLinkedThemeSupplySummary[];
  period_start_date: string;
  period_end_date: string;
  recent_30d_theme_supply_count: number;
  current_theme_supply_count: number;
  overall_stock_supply_count: number;
  latest_current_theme_supply_date: string | null;
  first_current_theme_supply_date: string | null;
  current_theme_supply_dates: string[];
  overall_stock_supply_dates: string[];
  stock_memos: MarketThemeStockSupplyMemo[];
};

export type MarketThemeStockMemo = {
  memo_date: string;
  memo: string;
  source?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type MarketThemeStockMemoResponse = {
  stock_code: string;
  stock_name: string | null;
  items: MarketThemeStockMemo[];
};

export type MarketThemeStockCreateInput = {
  stock_id: number;
  is_primary?: boolean;
};

export type MarketThemeStockUpdateInput = {
  is_primary?: boolean;
  is_active?: number;
  confidence_score?: number | null;
};

export type MarketThemeStockMemoUpdateInput = {
  stock_memo: string | null;
};

export type MarketThemeByStockItem = {
  theme_id: number;
  theme_name: string;
  is_primary: boolean;
};

export type MarketThemeByStockResponse = {
  stock_code: string;
  stock_name: string | null;
  themes: MarketThemeByStockItem[];
};

export type MarketThemeCandidateStatus = "pending" | "approved" | "rejected" | "ignored";
export type MarketThemeCandidateSource = "news" | "disclosure" | "keyword" | "telegram" | "system";

export type MarketThemeCandidate = {
  id: number;
  theme_id: number;
  theme_name: string;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  candidate_source: MarketThemeCandidateSource;
  confidence_score: number | null;
  matched_keywords: string[];
  evidence_count: number;
  evidence_summary: string | null;
  status: MarketThemeCandidateStatus;
  review_memo: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MarketThemeCandidateGenerateInput = {
  lookback_days?: number;
  source?: "all" | "news" | "disclosure";
  limit?: number;
  force?: boolean;
};

export type MarketThemeCandidateGenerateResult = {
  generated_count: number;
  updated_count: number;
  skipped_existing_mapping_count: number;
  skipped_rejected_count: number;
  source: string;
  lookback_days: number;
};

export type MarketThemeCandidateApproveResult = {
  candidate: MarketThemeCandidate;
  mapping_id: number;
  message: string;
};

export type MarketThemeCandidateReviewInput = {
  review_memo?: string | null;
};

export type RealtimeThemeTreemapItem = {
  theme_id: number;
  theme_name: string;
  rank: number;
  avg_change_rate: number | null;
  theme_strength: number | null;
  linked_stock_count: number;
  valid_stock_count: number;
};

export type RealtimeThemeTreemapResponse = {
  trade_date: string;
  snapshot_at: string | null;
  theme_count: number;
  linked_stock_count: number;
  unique_stock_count: number;
  valid_stock_count: number;
  failed_stock_count: number;
  themes: RealtimeThemeTreemapItem[];
};

export type RealtimeThemeRefreshResponse = RealtimeThemeTreemapResponse & {
  success: boolean;
  price_api_call_count: number;
  kiwoom_fetch_ms: number;
  db_upsert_ms: number;
  theme_aggregation_ms: number;
  snapshot_response_ms: number;
  stock_fetch_min_ms: number | null;
  stock_fetch_avg_ms: number | null;
  stock_fetch_max_ms: number | null;
  duration_ms: number;
  message: string;
};

export type RealtimeThemeStockItem = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  memo: string | null;
  change_rate: number | null;
  collected_at: string | null;
};

export type RealtimeThemeStocksResponse = {
  theme_id: number;
  theme_name: string;
  theme_rank: number;
  theme_change_rate: number | null;
  trade_date: string;
  snapshot_at: string | null;
  linked_stock_count: number;
  valid_stock_count: number;
  stocks: RealtimeThemeStockItem[];
};
