import type { StockDailyFlowSummary } from "@/types/marketTheme";

export type MarketScope = "ALL" | "KOSPI" | "KOSDAQ";
export type ThemeStatus =
  | "unassigned"
  | "manual_assigned"
  | "ai_suggested"
  | "auto_assigned_pending_review"
  | "user_corrected";

export type TrendDetectionSetting = {
  id: number;
  setting_key: string;
  setting_name: string;
  min_market_cap: number;
  min_market_cap_krw_100m: number;
  min_trading_value: number;
  min_trading_value_krw_100m: number;
  min_change_rate: number;
  min_intraday_range_rate: number | null;
  use_market_cap: boolean;
  use_trading_value: boolean;
  use_change_rate: boolean;
  use_intraday_range: boolean;
  market_scope: MarketScope;
  is_active: boolean;
};

export type UpdateTrendDetectionSettingRequest = {
  use_market_cap: boolean;
  min_market_cap_krw_100m: number;
  use_trading_value: boolean;
  min_trading_value_krw_100m: number;
  use_change_rate: boolean;
  min_change_rate: number;
  min_intraday_range_rate: number | null;
  use_intraday_range: boolean;
  market_scope: MarketScope;
  is_active: boolean;
};

export type MarketTrendEvent = {
  event_id: number;
  trade_date: string;
  stock_id: number;
  stock_code: string | null;
  stock_name: string | null;
  market_type: string | null;
  market_cap: number | null;
  trading_value: number | null;
  change_rate: number | null;
  intraday_range_rate: number | null;
  event_type: string;
  detection_source: string | null;
  theme_id: number | null;
  theme_name: string | null;
  theme_status: ThemeStatus;
  reason_summary: string | null;
  user_memo: string | null;
  applied_condition: {
    min_market_cap_krw_100m: number | null;
    min_trading_value_krw_100m: number | null;
    min_change_rate: number | null;
    min_intraday_range_rate: number | null;
    use_intraday_range: boolean;
  };
};

export type ManualSupplyEventCandidateRequest = {
  trade_date: string;
  stock_id?: number | null;
  stock_code?: string | null;
  change_rate?: number | null;
  trading_value?: number | null;
  volume?: number | null;
  theme_id?: number | null;
  memo: string;
};

export type ManualSupplyEventCandidateResponse = {
  success: boolean;
  event_id: number;
  message: string;
};

export type MarketPriceSnapshot = {
  snapshot_date: string;
  snapshot_time: string;
  stock_id: number | null;
  stock_code: string;
  stock_name: string | null;
  market_type: string | null;
  close_price: number | null;
  change_rate: number | null;
  trading_value: number | null;
  market_cap: number | null;
  intraday_range_rate: number | null;
};

export type CollectMarketPriceSnapshotsRequest = {
  snapshot_date?: string | null;
  market_scope?: MarketScope;
  collect_mode?: "stock_loop" | "market_bulk" | "auto";
  limit?: number | null;
};

export type CollectMarketPriceSnapshotsResponse = {
  snapshot_date: string;
  snapshot_time: string;
  source: string;
  market_scope: MarketScope;
  collect_mode: "stock_loop" | "market_bulk" | "auto";
  requested_count: number;
  collected_count: number;
  inserted_count: number;
  failed_count: number;
  skipped_count: number;
  matched_stock_count: number;
  unmatched_stock_count: number;
  failed_markets: string[];
  failed_items: string[];
  message: string;
};

export type DetectEventsFromSnapshotRequest = {
  snapshot_date?: string | null;
};

export type DetectEventsFromSnapshotResponse = {
  snapshot_date: string;
  source_snapshot_count: number;
  filtered_count: number;
  inserted_count: number;
  updated_count: number;
  duplicated_count: number;
  applied_condition: {
    use_market_cap: boolean;
    min_market_cap_krw_100m: number | null;
    use_trading_value: boolean;
    min_trading_value_krw_100m: number | null;
    use_change_rate: boolean;
    min_change_rate: number;
    use_intraday_range: boolean;
    min_intraday_range_rate: number | null;
    market_scope: MarketScope;
  };
  message: string;
};

export type CollectMarketTrendEventsRequest = {
  trade_date?: string | null;
};

export type CollectMarketTrendEventsResponse = {
  trade_date: string;
  applied_condition: {
    min_market_cap_krw_100m: number;
    min_trading_value_krw_100m: number;
    min_change_rate: number;
    use_intraday_range: boolean;
    min_intraday_range_rate: number | null;
    market_scope: MarketScope;
  };
  collected_count: number;
  inserted_count: number;
  duplicated_count: number;
  message: string;
};

export type AssignThemeToTrendEventRequest = {
  theme_id: number;
  reason_summary?: string | null;
  user_memo?: string | null;
  also_add_to_theme_stocks?: boolean;
  is_primary_for_theme?: boolean;
};

export type AssignThemeToTrendEventResponse = {
  event_id: number;
  theme_id: number;
  theme_name: string;
  theme_status: ThemeStatus;
  added_to_theme_stocks: boolean;
  already_mapped: boolean;
  message: string;
};

export type DailyThemeFlowItem = {
  theme_id: number;
  theme_name: string;
  is_supply_theme: boolean;
  detected_stock_count: number;
  total_trading_value: number;
  total_trading_value_krw_100m: number;
  avg_change_rate: number | null;
  max_change_rate: number | null;
  top_change_stock_name: string | null;
  top_trading_value_stock_name: string | null;
  trend_rank: number;
};

export type DailyThemeFlowResponse = {
  trade_date: string;
  description: string;
  summary: {
    event_count: number;
    assigned_count: number;
    unassigned_count: number;
  };
  items: DailyThemeFlowItem[];
};

export type KiwoomConditionItem = {
  id: number;
  condition_seq: string;
  condition_name: string;
  source: string;
  is_active: number;
  last_synced_at: string | null;
};

export type SyncKiwoomConditionsRequest = {
  source?: string;
  items: Array<{ condition_seq: string; condition_name: string }>;
};

export type SyncKiwoomConditionsResponse = {
  success: boolean;
  inserted_count: number;
  updated_count: number;
  total_count: number;
};

export type RefreshKiwoomConditionsResponse = {
  success: boolean;
  source: string;
  api_id: string;
  return_code?: string | null;
  return_msg?: string | null;
  condition_count: number;
  inserted: number;
  updated: number;
  total: number;
  top_level_keys: string[];
  sample_conditions: Array<{
    condition_no: string;
    condition_name: string;
  }>;
  message?: string | null;
};

export type KiwoomConditionResultItem = {
  id?: number;
  condition_seq?: string;
  condition_name?: string | null;
  stock_code: string;
  stock_code_raw?: string | null;
  stock_name?: string | null;
  current_price?: number | null;
  change_rate?: number | null;
  intraday_change_rate?: number | null;
  trading_value?: number | null;
  volume?: number | null;
  estimated_trading_value?: number | null;
  detected_at?: string;
  source_api?: string | null;
  raw?: Record<string, unknown> | null;
};

export type KiwoomConditionPreviewRequest = {
  condition_name?: string | null;
  header_mode?: "full" | "auth-only" | "none";
  login_mode?: "header" | "message-bearer" | "message-token";
  search_type?: string;
  stex_tp?: string;
};

export type KiwoomConditionPreviewResponse = {
  success: boolean;
  source?: string | null;
  api_id?: string | null;
  condition_seq: string;
  condition_name?: string | null;
  requested_condition_seq?: string | null;
  requested_condition_name?: string | null;
  resolved_condition_seq?: string | null;
  resolved_condition_name?: string | null;
  return_code?: string | null;
  return_msg?: string | null;
  item_count: number;
  items: KiwoomConditionResultItem[];
  parsing_error?: boolean;
  debug?: Record<string, unknown>;
  error_message?: string | null;
};

export type SaveKiwoomConditionResultsRequest = {
  condition_name?: string | null;
  source?: string;
  items: KiwoomConditionResultItem[];
};

export type SaveKiwoomConditionResultsResponse = {
  success: boolean;
  saved_count: number;
  skipped_count: number;
};

export type SaveKiwoomMarketEventsRequest = {
  condition_seq: string;
  condition_name?: string | null;
  detected_date?: string | null;
  source?: string;
  items: KiwoomConditionResultItem[];
};

export type SaveKiwoomMarketEventsResponse = {
  success: boolean;
  saved_count: number;
  updated_count: number;
  unmatched_count: number;
  unmatched_items: string[];
};

export type ExistingMarketEventTheme = {
  theme_id: number;
  theme_name: string;
  theme_group_id?: number | null;
  theme_group_name?: string | null;
  is_active: number | boolean;
};

export type KiwoomMarketEventItem = {
  event_id: number;
  trade_date: string;
  stock_code: string | null;
  stock_name: string | null;
  market_type: string | null;
  change_rate: number | null;
  theme_status: string | null;
  condition_seq: string | null;
  condition_name: string | null;
  detection_source?: string | null;
  user_memo: string | null;
  detected_at: string | null;
  updated_at: string | null;
  existing_themes?: ExistingMarketEventTheme[];
};

export type KiwoomMarketEventListResponse = {
  items: KiwoomMarketEventItem[];
};

export type UpdateKiwoomMarketEventRequest = {
  theme_status?: string | null;
  user_memo?: string | null;
};

export type UpdateKiwoomMarketEventResponse = {
  success: boolean;
  item: KiwoomMarketEventItem;
};

export type ThemeStockSyncSummary = {
  created: number;
  reactivated: number;
  deactivated: number;
  skipped: number;
  failed: number;
};

export type DeleteKiwoomMarketEventResponse = {
  success: boolean;
  event_id: number;
  theme_stock_sync?: ThemeStockSyncSummary | null;
};

export type MarketEventThemeLink = {
  link_id: number;
  event_id: number;
  market_theme_id: number;
  theme_name: string;
  link_reason: string | null;
  user_memo: string | null;
  is_primary: number;
  created_at: string | null;
  updated_at: string | null;
};

export type MarketEventThemeLinkListResponse = {
  items: MarketEventThemeLink[];
};

export type AddMarketEventThemeLinkRequest = {
  market_theme_id: number;
  link_reason?: string | null;
  user_memo?: string | null;
  is_primary?: number;
};

export type ThemeStockSyncResult = {
  status: string;
  reason: string | null;
  mapping_id: number | null;
};

export type AddMarketEventThemeLinkResponse = {
  success: boolean;
  item: MarketEventThemeLink;
  theme_stock_sync?: ThemeStockSyncResult | null;
};

export type RemoveMarketEventThemeLinkResponse = {
  success: boolean;
  link_id: number;
  theme_stock_sync?: ThemeStockSyncResult | null;
};

export type DailyThemeFlowSummary = {
  market_theme_id: number;
  theme_name: string;
  event_count: number;
  stock_count: number;
  avg_change_rate: number | null;
  max_change_rate: number | null;
  estimated_trading_value_sum: number;
  representative_stocks: string[];
  auto_rank: number | null;
  manual_rank: number | null;
  final_rank: number | null;
  theme_strength_score?: number;
  return_score?: number;
  trading_value_score?: number;
  breadth_score?: number;
  rank_score: number;
  rank_basis: "auto" | "manual";
};

export type DailyThemeFlowStock = {
  event_id: number;
  market_theme_id: number;
  theme_name: string;
  stock_code: string;
  stock_name: string;
  change_rate: number | null;
  current_price: number | null;
  volume: number | null;
  estimated_trading_value: number | null;
  condition_seq: string | null;
  condition_name: string | null;
  user_memo?: string | null;
};

export type DailyThemeFlowSummaryResponse = {
  success: boolean;
  trade_date: string;
  items: DailyThemeFlowSummary[];
};

export type DailyThemeFlowStocksResponse = {
  success: boolean;
  trade_date: string;
  market_theme_id: number;
  theme_name: string | null;
  items: DailyThemeFlowStock[];
};

export type MonthlyThemeFlowStock = {
  stock_id?: number | null;
  stock_code?: string | null;
  stock_name: string;
  change_rate?: number | null;
};

export type MonthlyThemeFlowMemoItem = {
  theme_id?: number | null;
  theme_name: string;
  stock_code?: string | null;
  stock_name: string;
  memo: string;
};

export type MonthlyThemeFlowCalendarTheme = {
  rank: number;
  theme_group_id: number | null;
  theme_group_name: string;
  market_theme_id: number;
  theme_name: string;
  stock_count: number;
  event_count: number;
  avg_change_rate: number | null;
  max_change_rate: number | null;
  estimated_trading_value_sum: number;
  auto_rank: number | null;
  manual_rank: number | null;
  final_rank: number | null;
  theme_strength_score?: number;
  return_score?: number;
  trading_value_score?: number;
  breadth_score?: number;
  rank_score: number;
  rank_basis: "auto" | "manual";
  stocks: MonthlyThemeFlowStock[];
};

export type MonthlyThemeFlowCalendarDay = {
  trade_date: string;
  event_count: number;
  related_stock_count: number;
  themes: MonthlyThemeFlowCalendarTheme[];
  memo_items?: MonthlyThemeFlowMemoItem[];
};

export type MonthlySupplySummaryStock = {
  rank: number;
  stock_id: number | null;
  stock_code: string | null;
  stock_name: string;
  appearance_count: number;
  latest_detected_date: string | null;
};

export type MonthlySupplySummaryTheme = {
  theme_id: number;
  theme_name: string;
  appearance_count: number;
  latest_appearance_date: string | null;
  unique_stock_count: number;
};

export type MonthlySupplySummary30d = {
  period_start_date: string;
  period_end_date: string;
  appeared_theme_count: number;
  top_theme: MonthlySupplySummaryTheme | null;
  top_stocks: MonthlySupplySummaryStock[];
};
export type SupplyTopStockReturnPoint = {
  trade_date: string;
  close: number | null;
  daily_return: number | null;
  cumulative_return: number | null;
  is_supply_date: boolean;
};

export type SupplyTopStockPriceStatus = "READY" | "READY_WITH_FALLBACK" | "NO_PRICE_DATA" | "NO_BASE_PRICE" | "INSUFFICIENT_OBSERVATIONS" | "PARTIAL";

export type SupplyTopStockPriceReadiness = {
  total_stock_count: number;
  ready_stock_count: number;
  fallback_ready_stock_count: number;
  partial_stock_count: number;
  missing_stock_count: number;
  readiness_rate: number;
  missing_stock_ids: number[];
  missing_stock_codes: string[];
  no_price_data_count: number;
  no_base_price_count: number;
  insufficient_observation_count: number;
};

export type SupplyTopStockReturnTrendItem = {
  rank: number;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  appearance_count: number;
  appearance_dates: string[];
  latest_detected_date: string | null;
  price_data_status: SupplyTopStockPriceStatus;
  price_data_status_name: string;
  price_data_reason: string;
  price_observation_count: number;
  expected_trade_date_count: number;
  price_coverage_rate: number;
  base_price_date: string | null;
  base_close: number | null;
  latest_price_date: string | null;
  latest_close: number | null;
  latest_daily_return: number | null;
  latest_cumulative_return: number | null;
  has_sufficient_price_data: boolean;
  points: SupplyTopStockReturnPoint[];
};

export type SupplyTopStockReturnTrendResponse = {
  period_start_date: string;
  period_end_date: string;
  price_data_end_date: string | null;
  last_price_collection_date: string | null;
  ranking_basis: "UNIQUE_STOCK_SUPPLY_DAYS";
  limit: number;
  trade_dates: string[];
  price_readiness: SupplyTopStockPriceReadiness;
  stocks: SupplyTopStockReturnTrendItem[];
};

export type SupplyTopStockPriceCollectRequest = {
  period_start_date: string;
  period_end_date: string;
  limit?: number;
};

export type SupplyTopStockPriceCollectItem = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  status: "SUCCESS" | "FAILED";
  pages_fetched: number;
  collected_count: number;
  saved_count: number;
  collection_mode: "INITIAL" | "INCREMENTAL";
  collect_start_date: string;
  collect_end_date: string;
  price_data_status_before: SupplyTopStockPriceStatus;
  price_data_status_after: SupplyTopStockPriceStatus;
  error_message: string | null;
};

export type SupplyTopStockPriceCollectResponse = {
  period_start_date: string;
  period_end_date: string;
  collect_start_date: string;
  collect_end_date: string;
  last_price_collection_date: string | null;
  top_stock_count: number;
  target_stock_count: number;
  success_count: number;
  partial_count: number;
  failed_count: number;
  skipped_count: number;
  saved_price_count: number;
  total_api_calls: number;
  total_pages: number;
  total_ms: number;
  before_readiness: SupplyTopStockPriceReadiness;
  after_readiness: SupplyTopStockPriceReadiness;
  results: SupplyTopStockPriceCollectItem[];
};
export type MonthlySupplyClassificationDiagnostics = {
  classification_basis: "CURRENT_ACTIVE_THEME_MAPPING";
  event_count: number;
  unique_stock_count: number;
  active_theme_count: number;
  reclassified_event_stock_count: number;
  unclassified_stock_count: number;
  period_start_date: string;
  period_end_date: string;
};
export type MonthlyThemeFlowCalendarResponse = {
  success: boolean;
  month: string;
  start_date: string;
  end_date: string;
  summary_30d: MonthlySupplySummary30d;
  diagnostics: MonthlySupplyClassificationDiagnostics;
  days: MonthlyThemeFlowCalendarDay[];
};

export type MonthlyThemeFlowTrendPoint = {
  trade_date: string;
  value: number;
  daily_score: number;
  final_rank: number | null;
  rank_basis: "auto" | "manual";
  stock_count: number;
  event_count: number;
  avg_change_rate: number | null;
  max_change_rate: number | null;
  estimated_trading_value_sum: number;
};

export type MonthlyThemeFlowTrendTheme = {
  market_theme_id: number;
  theme_name: string;
  view_mode?: "THEME_GROUP" | "THEME";
  theme_group_id?: number | null;
  theme_group_name?: string | null;
  child_theme_count?: number;
  top_child_themes?: string[];
  related_stocks?: string[];
  series: MonthlyThemeFlowTrendPoint[];
};

export type MonthlyThemeFlowTrendResponse = {
  success: boolean;
  month: string;
  start_date: string;
  end_date: string;
  diagnostics: MonthlySupplyClassificationDiagnostics;
  themes: MonthlyThemeFlowTrendTheme[];
};

export type MonthlyThemeCellDetailStock = {
  stock_id: number;
  stock_code: string | null;
  stock_name: string;
  trading_value_100m: number | null;
  change_rate: number | null;
  current_price: number | null;
  data_status: "success" | "failed" | "missing";
  error_message?: string | null;
  flow_summary?: StockDailyFlowSummary | null;
};

export type MonthlyThemeCellDetailResponse = {
  theme: { id: number; name: string; group_name: string | null };
  selected_date: string;
  period: { from_date: string; to_date: string };
  summary: {
    appearance_days: number;
    unique_stock_count: number;
    selected_stock_count: number;
    selected_avg_change_rate: number | null;
    selected_trading_value_100m: number | null;
    rise_count: number;
    fall_count: number;
    flat_count: number;
    missing_change_count: number;
    flow_ready_count: number;
    flow_total_count: number;
    first_appearance_date: string | null;
    latest_appearance_date: string | null;
    recent_appearance_dates: string[];
    monthly_avg_change_rate: number | null;
  };
  stocks: MonthlyThemeCellDetailStock[];
  chart_reference: "CURRENT";
  queried_at: string;
};
export type UpdateDailyThemeRanksRequest = {
  trade_date: string;
  items: Array<{
    market_theme_id: number;
    manual_rank: number | null;
    user_memo?: string | null;
  }>;
};

export type UpdateDailyThemeRanksResponse = {
  success: boolean;
  trade_date: string;
  updated_count: number;
  items: DailyThemeFlowSummary[];
};
