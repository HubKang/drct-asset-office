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
  use_intraday_range: boolean;
  market_scope: MarketScope;
  is_active: boolean;
};

export type UpdateTrendDetectionSettingRequest = {
  min_market_cap_krw_100m: number;
  min_trading_value_krw_100m: number;
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

