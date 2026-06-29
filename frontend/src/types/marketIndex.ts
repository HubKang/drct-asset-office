export type MarketIndexItem = {
  id: number;
  index_code: string;
  index_name: string;
  category: string;
  market: string;
  currency: string;
  provider: string;
  provider_symbol?: string | null;
  description?: string | null;
  is_active: boolean;
  display_order: number;
  last_collected_date?: string | null;
  collection_status: string;
  error_message?: string | null;
  latest_price_date?: string | null;
  latest_close_price?: number | null;
  latest_close?: number | null;
  latest_volume?: number | null;
  latest_trading_value?: number | null;
  recent_5d_return?: number | null;
  recent_20d_return?: number | null;
  recent_5d_return_pct?: number | null;
  recent_20d_return_pct?: number | null;
};

export type MarketIndexListResponse = {
  items: MarketIndexItem[];
};

export type MarketIndexDailyPriceItem = {
  id?: number | null;
  index_code: string;
  price_date: string;
  open_price?: number | null;
  high_price?: number | null;
  low_price?: number | null;
  close_price?: number | null;
  volume?: number | null;
  trading_value?: number | null;
  change_rate?: number | null;
  ma5?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ma120?: number | null;
  source_provider?: string | null;
};

export type MarketIndexDailyPriceListResponse = {
  index_code: string;
  index_name?: string | null;
  items: MarketIndexDailyPriceItem[];
};

export type MarketIndexCollectRequest = {
  index_codes?: string[];
  start_date?: string;
  end_date?: string;
};

export type MarketIndexCollectResponse = {
  requested_count: number;
  success_count: number;
  failed_count: number;
  saved_count: number;
  message: string;
  results: Array<{
    index_code: string;
    index_name?: string | null;
    status: string;
    collected_count: number;
    saved_count: number;
    from_date?: string | null;
    to_date?: string | null;
    message?: string | null;
    last_collected_date?: string | null;
    error_message?: string | null;
  }>;
};

export type MarketIndexComparePoint = {
  date: string;
  value?: number | null;
  close_price?: number | null;
};

export type MarketIndexCompareResponse = {
  normalize: boolean;
  start_date?: string | null;
  end_date?: string | null;
  series: Array<{
    index_code: string;
    index_name?: string | null;
    points: MarketIndexComparePoint[];
  }>;
};

