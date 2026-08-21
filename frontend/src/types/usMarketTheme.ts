export type UsThemeStockRole = "LEADER" | "CORE" | "RELATED" | "ETF";

export type UsThemeSummary = { theme_groups: number; themes: number; active_themes: number; linked_stocks: number };

export type UsThemeGroup = {
  id: number; name: string; description: string | null; sort_order: number; active: number;
  theme_count: number; active_theme_count: number; linked_stock_count: number; created_at: string; updated_at: string;
};

export type UsTheme = {
  id: number; theme_group_id: number; theme_group_name: string; name: string; description: string | null;
  keywords: string[]; sort_order: number; active: number; linked_stock_count: number;
  representative_symbols: string[]; created_at: string; updated_at: string;
  latest_return_date: string | null; latest_simple_return: number | null; latest_theme_strength: number | null; latest_breadth_ratio: number | null;
};

export type UsThemeStock = {
  mapping_id: number; theme_id: number; us_stock_id: number; symbol: string; name: string | null; name_ko: string | null;
  exchange: string; stock_type: string; naver_code: string | null; role: UsThemeStockRole;
  is_representative: number; sort_order: number; active: number; created_at: string; updated_at: string;
};

export type UsThemeGroupInput = { name: string; description?: string | null; sort_order: number; active: number };
export type UsThemeInput = { theme_group_id: number; name: string; description?: string | null; keywords: string[]; sort_order: number; active: number };
export type UsThemeStockInput = { us_stock_id: number; role: UsThemeStockRole; is_representative: number; sort_order: number };
export type UsStockCharts = { stock_id: number; naver_code: string | null; day: string | null; week: string | null; month: string | null; available: boolean };
export type UsThemeReturnItem = {
  theme_id: number; theme_group_name: string; theme_name: string; trade_date: string | null;
  simple_return: number | null; theme_strength: number | null; trimmed_mean_return: number | null; median_return: number | null;
  breadth_ratio: number | null; valid_stock_count: number; up_count: number; down_count: number; flat_count: number;
};
export type UsThemeReturnList = { latest_date: string | null; items: UsThemeReturnItem[] };
export type UsThemeTrendPoint = { trade_date: string; simple_return: number; theme_strength: number; rolling_30d_simple_return: number; rolling_30d_theme_strength: number; rolling_30d_valid_count: number; breadth_ratio: number; valid_stock_count: number; up_count: number };
export type UsThemeTrendItem = { theme_id: number; theme_group_id: number; theme_group_name: string; theme_name: string; active: number; points: UsThemeTrendPoint[] };
export type UsThemeTrend = { period: 20 | 30 | 60; dates: string[]; items: UsThemeTrendItem[] };
export type UsThemeReturnDetail = {
  theme_id: number; theme_name: string; theme_group_name: string; description: string | null; active: number;
  trade_date: string | null; simple_return: number | null; theme_strength: number | null; breadth_ratio: number | null;
  valid_stock_count: number; eligible_stock_count: number; linked_stock_count: number; up_count: number; down_count: number; flat_count: number;
  aggregate: UsThemeReturnItem | null;
  stocks: Array<{
    us_stock_id: number; symbol: string; name: string | null; name_ko: string | null; exchange: string; stock_type: string;
    naver_code: string | null; role: UsThemeStockRole; is_representative: number; sort_order: number; active: number;
    return_rate: number | null; daily_return: number | null; close_price: number | null; previous_close: number | null;
  }>;
};
export type UsMarketRefreshResponse = { price: import("@/types/usStock").UsPriceCollectionResponse; returns: { processed_theme_count: number; processed_date_count: number; upserted_count: number; skipped_count: number; date_from: string | null; date_to: string | null; message: string }; message: string };
