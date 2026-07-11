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
  stocks: MarketThemeReturnStock[];
};

export type MarketThemeReturnRefreshRequest = {
  scope: "all_active" | "selected";
  theme_ids?: number[];
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
  items: MarketThemeReturnRefreshItem[];
  message?: string | null;
};

export type MarketThemeMonthlyReturnDailyItem = {
  return_date: string;
  avg_change_rate: number | null;
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
  daily_returns: MarketThemeMonthlyReturnDailyItem[];
};

export type MarketThemeMonthlyReturnSummaryTopItem = {
  theme_id: number;
  theme_name: string;
  monthly_compound_return: number | null;
  period_compound_return?: number | null;
  total_trading_value_100m: number | null;
  continuous_rising_days?: number | null;
};

export type MarketThemeMonthlyReturnResponse = {
  month?: string | null;
  end_date?: string | null;
  days?: number | null;
  active_only: boolean;
  display_start_date: string;
  display_end_date: string;
  themes: MarketThemeMonthlyReturnThemeItem[];
  summary: {
    top_rising_theme: MarketThemeMonthlyReturnSummaryTopItem | null;
    top_falling_theme: MarketThemeMonthlyReturnSummaryTopItem | null;
    top_trading_value_theme: MarketThemeMonthlyReturnSummaryTopItem | null;
    rising_day_theme: MarketThemeMonthlyReturnSummaryTopItem | null;
    top_continuous_rising_theme?: MarketThemeMonthlyReturnSummaryTopItem | null;
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
  created_at: string;
  updated_at: string;
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
