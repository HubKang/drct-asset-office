export type MarketIndicatorCategory = "FX" | "RATE" | "INFLATION" | "ECONOMY" | "COMMODITY" | "GLOBAL_INDEX" | "GLOBAL_RATE" | "CUSTOM";
export type MarketIndicatorFrequency = "DAILY" | "MONTHLY" | "QUARTERLY";
export type MarketIndicatorChartType = "LINE" | "CANDLE" | "BAR" | "LINE_WITH_BASELINE" | "BAR_LINE" | "SPREAD_LINE";

export interface MarketIndicator {
  id?: number | null;
  indicator_code: string;
  indicator_name: string;
  category: MarketIndicatorCategory | string;
  subcategory?: string | null;
  data_frequency: MarketIndicatorFrequency | string;
  chart_type: MarketIndicatorChartType | string;
  unit?: string | null;
  unit_label?: string | null;
  value_label?: string | null;
  base_line_value?: number | null;
  display_order: number;
  priority_rank: number;
  description?: string | null;
  interpretation_note?: string | null;
  higher_value_meaning?: string | null;
  lower_value_meaning?: string | null;
  is_active: boolean;
  collection_status: string;
  latest_value?: number | null;
  latest_value_date?: string | null;
  latest_change_value?: number | null;
  latest_change_pct?: number | null;
  latest_yoy_pct?: number | null;
  latest_mom_pct?: number | null;
}

export interface MarketIndicatorListResponse {
  items: MarketIndicator[];
  category_counts: Record<string, number>;
}

export interface MarketIndicatorValue {
  id?: number | null;
  indicator_code: string;
  value_date: string;
  period_label?: string | null;
  value?: number | null;
  open_value?: number | null;
  high_value?: number | null;
  low_value?: number | null;
  close_value?: number | null;
  change_value?: number | null;
  change_pct?: number | null;
  mom_pct?: number | null;
  yoy_pct?: number | null;
  normalized_value?: number | null;
  source_provider?: string | null;
  source_unit?: string | null;
  is_preliminary?: boolean;
  release_date?: string | null;
}

export interface MarketIndicatorValueResponse {
  indicator_code: string;
  indicator_name?: string | null;
  items: MarketIndicatorValue[];
}

export interface MarketIndicatorProviderMapping {
  id?: number | null;
  indicator_code: string;
  indicator_name?: string | null;
  provider: string;
  api_type?: string | null;
  api_id?: string | null;
  endpoint_url?: string | null;
  provider_symbol?: string | null;
  request_params_json?: string | null;
  is_enabled: boolean;
  is_verified: boolean;
  verified_at?: string | null;
  last_test_status?: string | null;
  last_test_message?: string | null;
  last_tested_at?: string | null;
}

export interface MarketIndicatorProviderMappingListResponse {
  items: MarketIndicatorProviderMapping[];
}

export interface ExternalProviderStatus {
  provider: string;
  display_name: string;
  configured: boolean;
  masked_key?: string | null;
  status: string;
  message: string;
  last_checked_at: string;
}

export interface ExternalProviderStatusListResponse {
  items: ExternalProviderStatus[];
}
