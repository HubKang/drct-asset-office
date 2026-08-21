export type UsExchange = "NASDAQ" | "NYSE" | "NYSE_AMERICAN" | "OTHER";
export type UsStockType = "COMMON" | "ETF" | "OTHER";
export type UsHistoricalPriceStatus = "NOT_COLLECTED" | "COMPLETE" | "PARTIAL" | "ERROR";

export type UsStock = {
  id: number;
  symbol: string;
  name: string | null;
  name_ko: string | null;
  exchange: UsExchange;
  stock_type: UsStockType;
  naver_code: string | null;
  is_active: number;
  last_synced_at: string | null;
  latest_price_date: string | null;
  latest_close: number | null;
  latest_change_rate: number | null;
  historical_price_status: UsHistoricalPriceStatus;
  historical_price_completed_at: string | null;
  historical_price_row_count: number;
  price_status: UsHistoricalPriceStatus;
  created_at: string;
  updated_at: string;
};

export type UsStockInput = {
  symbol: string;
  name?: string | null;
  name_ko?: string | null;
  exchange: UsExchange;
  stock_type: UsStockType;
  naver_code?: string | null;
  is_active: number;
};

export type UsStockUpdateInput = Omit<Partial<UsStockInput>, "symbol">;

export type UsStockListResponse = { items: UsStock[]; total: number; page: number; page_size: number };
export type UsStockSummary = {
  total: number;
  active: number;
  common: number;
  etf: number;
  price_complete: number;
  price_not_collected: number;
  price_partial: number;
  price_error: number;
  latest_price_date: string | null;
};
export type UsStockDeleteImpact = { stock_id: number; symbol: string; price_row_count: number; theme_link_count: number; affected_theme_count: number };
export type UsStockDeleteResponse = { deleted: boolean; stock_id: number; symbol: string; deleted_price_count: number; deleted_theme_link_count: number; invalidated_theme_return_count: number; recalculated_theme_count: number; message: string };
export type UsStockBulkInput = { tickers: string[]; exchange: UsExchange; stock_type: UsStockType; is_active: number };
export type UsStockBulkPreviewItem = { symbol: string; exchange: string; stock_type: string; status: "NEW" | "EXISTING" | "DUPLICATE" | "INVALID"; reason: string | null };
export type UsStockBulkPreviewResponse = { items: UsStockBulkPreviewItem[]; new_count: number; existing_count: number; invalid_count: number };
export type UsStockBulkCreateResponse = { created_count: number; skipped_count: number; items: UsStock[] };
export type UsHistoricalCollectionMode = "MISSING" | "SELECTED" | "ALL_ACTIVE";
export type UsPriceCollectionMode = "INCREMENTAL" | UsHistoricalCollectionMode;
export type UsPriceCollectionResponse = {
  mode: UsPriceCollectionMode; requested_stock_count: number; success_stock_count: number; failed_stock_count: number;
  inserted_count: number; updated_count: number; affected_date_from: string | null; affected_date_to: string | null;
  recalculated_theme_count: number; latest_price_date: string | null;
  failures: Array<{ stock_id: number; symbol: string; reason: string }>; message: string;
};
