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


export interface MarketIndicatorProviderMappingUpsertRequest {
  provider?: string;
  api_type?: string | null;
  api_id?: string | null;
  endpoint_url?: string | null;
  provider_symbol?: string | null;
  request_params_json?: Record<string, unknown> | string | null;
  is_enabled?: boolean;
}

export interface MarketIndicatorProviderMappingTestRequest {
  start_date?: string | null;
  end_date?: string | null;
  save_result?: boolean;
}

export interface MarketIndicatorProviderMappingTestResponse {
  indicator_code: string;
  provider: string;
  status: string;
  message: string;
  sample_count: number;
  sample_rows: Record<string, unknown>[];
}

export interface EcosItemListResponse {
  stat_code: string;
  status: string;
  message: string;
  list_total_count: number;
  items: Record<string, unknown>[];
}

export interface MarketIndicatorCollectRequest {
  indicator_codes?: string[] | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface MarketIndicatorCollectResult {
  indicator_code: string;
  status: string;
  message: string;
  saved_count: number;
  latest_value?: number | null;
  latest_value_date?: string | null;
}

export interface MarketIndicatorCollectResponse {
  requested_count: number;
  success_count: number;
  waiting_count: number;
  failed_count: number;
  message: string;
  results: MarketIndicatorCollectResult[];
}


export interface EcosTableItem {
  p_stat_code?: string | null;
  stat_code?: string | null;
  stat_name?: string | null;
  cycle?: string | null;
  srch_yn?: string | null;
  org_name?: string | null;
}

export interface EcosTableListResponse {
  status: string;
  message: string;
  total_count: number;
  items: EcosTableItem[];
}

export interface EcosTableSearchResponse {
  keyword: string;
  status: string;
  message: string;
  searched_count: number;
  items: EcosTableItem[];
}

export interface EcosDiscoverCandidatesRequest {
  indicator_codes?: string[] | null;
  max_depth?: number;
  cycle?: string | null;
}

export interface EcosCandidate extends EcosTableItem {
  score: number;
  reason?: string | null;
}

export interface EcosIndicatorCandidates {
  indicator_code: string;
  indicator_name?: string | null;
  keywords: string[];
  candidates: EcosCandidate[];
}

export interface EcosDiscoverCandidatesResponse {
  status: string;
  message: string;
  searched_count: number;
  items: EcosIndicatorCandidates[];
}


export interface EcosMappingCandidate {
  indicator_code: string;
  indicator_name?: string | null;
  stat_code: string;
  stat_name?: string | null;
  cycle?: string | null;
  item_code1: string;
  item_name1?: string | null;
  provider_symbol: string;
  score: number;
  reason?: string | null;
  source_unit?: string | null;
  request_params_json: Record<string, unknown>;
}

export interface EcosIndicatorMappingCandidates {
  indicator_code: string;
  indicator_name?: string | null;
  candidates: EcosMappingCandidate[];
}

export interface EcosDiscoverMappingCandidatesRequest {
  indicator_codes?: string[] | null;
  top_table_count?: number;
  max_item_count?: number;
}

export interface EcosDiscoverMappingCandidatesResponse {
  status: string;
  message: string;
  items: EcosIndicatorMappingCandidates[];
}

export interface EcosMappingCandidateTestRequest {
  provider?: string;
  stat_code: string;
  cycle?: string;
  item_code1: string;
  item_name1?: string | null;
  scale?: number;
  source_unit?: string | null;
}
