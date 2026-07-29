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
  waiting_count?: number;
  excluded_count?: number;
  custom_index_required_count?: number;
  saved_count: number;
  message: string;
  results: Array<{
    index_code: string;
    index_name?: string | null;
    status: string;
    collected_count: number;
    saved_count: number;
    inserted_count?: number;
    updated_count?: number;
    unchanged_count?: number;
    from_date?: string | null;
    to_date?: string | null;
    message?: string | null;
    last_collected_date?: string | null;
    error_message?: string | null;
  }>;
};

export type MarketIndexComparePoint = {
  date: string;
  plotDate?: string | null;
  value?: number | null;
  close_price?: number | null;
  periodLabel?: string | null;
  isCarryForward?: boolean;
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


export type MarketIndexProviderMapping = {
  id?: number | null;
  index_code: string;
  index_name?: string | null;
  provider: string;
  api_type?: string | null;
  provider_symbol?: string | null;
  market_type?: string | null;
  indicator_type?: string | null;
  request_params_json?: string | null;
  api_id?: string | null;
  endpoint_url?: string | null;
  is_enabled: boolean;
  is_verified: boolean;
  verified_at?: string | null;
  last_test_status?: string | null;
  last_test_message?: string | null;
  last_tested_at?: string | null;
};

export type MarketIndexProviderMappingListResponse = {
  items: MarketIndexProviderMapping[];
};

export type ProviderMappingUpsertRequest = {
  provider?: string;
  api_type?: string | null;
  provider_symbol?: string | null;
  market_type?: string | null;
  indicator_type?: string | null;
  request_params_json?: string | null;
  api_id?: string | null;
  endpoint_url?: string | null;
  is_enabled?: boolean;
};

export type ProviderMappingTestRequest = {
  provider?: string;
  api_type?: string | null;
  provider_symbol?: string | null;
  market_type?: string | null;
  request_params_json?: string | null;
  api_id?: string | null;
  endpoint_url?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  save_result?: boolean;
};

export type ProviderMappingTestResult = {
  index_code: string;
  status: string;
  sample_count: number;
  first_date?: string | null;
  last_date?: string | null;
  message: string;
  sample: Array<Record<string, unknown>>;
};

export type MarketIndexProviderCode = {
  id?: number | null;
  provider: string;
  market_type: string;
  market_code?: string | null;
  code: string;
  name: string;
  group_name?: string | null;
  source_api_id?: string | null;
  is_active: boolean;
  matched_index_code?: string | null;
  matched_index_name?: string | null;
};

export type ProviderCodeCollectRequest = {
  provider?: string;
  market_types?: string[];
};

export type ProviderCodeCollectResponse = {
  requested_count: number;
  success_count: number;
  failed_count: number;
  results: Array<{ market_type: string; count: number; status: string; error_message?: string | null }>;
};

export type MarketIndexProviderCodeListResponse = {
  items: MarketIndexProviderCode[];
};

export type SectorCodeAutoMatchResponse = {
  matched_count: number;
  waiting_count: number;
  results: Array<{ index_code: string; index_name?: string | null; matched_code?: string | null; matched_name?: string | null; status: string; message?: string | null }>;
};

