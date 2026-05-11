export type StockDailyPrice = {
  id: number;
  stock_id: number;
  trade_date: string;
  open_price: number | null;
  high_price: number | null;
  low_price: number | null;
  close_price: number | null;
  change_price: number | null;
  change_rate: number | null;
  volume: number | null;
  trading_value: number | null;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
  ma120: number | null;
  ma240: number | null;
  source: string | null;
  created_at: string;
  updated_at: string;
};

export type SelectedStockPriceCollectRequest = {
  stock_ids: number[];
  period_years: number;
  source: string;
};

export type SelectedStockPriceUpdateRequest = {
  stock_ids: number[];
  source: string;
};

export type StockPriceCollectItemResult = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  status: string;
  saved_count: number;
  message: string | null;
};

export type StockPriceCollectResult = {
  requested_count: number;
  success_count: number;
  failed_count: number;
  saved_count: number;
  message: string;
  results: StockPriceCollectItemResult[];
};
