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
