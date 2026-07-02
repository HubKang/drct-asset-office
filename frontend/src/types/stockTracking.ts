export type StockTrackingStatus = "TRACKING" | "SUCCESS" | "FAIL" | "HOLD" | "EXCLUDED";
export type StockTrackingPriceStatus = "NOT_COLLECTED" | "COLLECTING" | "LATEST" | "PARTIAL" | "STOPPED" | "ERROR";

export type StockTrackingGroup = {
  id: number;
  name: string;
  description: string | null;
  success_rule_note: string | null;
  fail_rule_note: string | null;
  observation_note: string | null;
  is_active: number;
  item_count: number;
  tracking_count: number;
  created_at: string;
  updated_at: string;
};

export type CreateStockTrackingGroupPayload = {
  name: string;
  description?: string | null;
  success_rule_note?: string | null;
  fail_rule_note?: string | null;
  observation_note?: string | null;
  is_active?: number;
};

export type UpdateStockTrackingGroupPayload = CreateStockTrackingGroupPayload;

export type StockTrackingItem = {
  id: number;
  group_id: number;
  group_name: string;
  candidate_id: number | null;
  condition_no: string | null;
  condition_name: string | null;
  stock_id: number | null;
  stock_code: string | null;
  stock_name: string | null;
  detected_date: string | null;
  tracking_base_date: string;
  base_price: number | null;
  base_change_rate: number | null;
  base_volume: number | null;
  base_trading_value: number | null;
  entry_close_price: number | null;
  entry_close_date: string | null;
  latest_close_price: number | null;
  latest_close_date: string | null;
  tracking_return_pct: number | null;
  price_updated_at: string | null;
  status: StockTrackingStatus;
  review_date: string | null;
  review_note: string | null;
  price_status: StockTrackingPriceStatus;
  created_at: string;
  updated_at: string;
};

export type StockTrackingItemListResponse = {
  items: StockTrackingItem[];
  total: number;
};

export type RegisterTrackingItemsFromCandidatesPayload = {
  group_id: number;
  candidate_ids: number[];
};

export type StockTrackingRegisterItemResult = {
  candidate_id: number;
  stock_code: string | null;
  stock_name: string | null;
  status: "CREATED" | "SKIPPED";
  message?: string | null;
};

export type RegisterTrackingItemsFromCandidatesResponse = {
  requested_count?: number;
  success: boolean;
  created_count: number;
  skipped_count: number;
  item_ids: number[];
  items?: StockTrackingRegisterItemResult[];
  message: string;
};

export type CreateTrackingFromConditionResultItem = {
  stock_code: string;
  stock_name?: string | null;
  market?: string | null;
  current_price?: number | null;
  change_rate?: number | null;
  volume?: number | null;
  trading_value?: number | null;
};

export type CreateTrackingFromConditionResultsPayload = {
  group_id: number;
  condition_no?: string | null;
  condition_name?: string | null;
  detected_date: string;
  items: CreateTrackingFromConditionResultItem[];
};

export type CreateTrackingFromConditionResultStatus = {
  stock_code: string | null;
  stock_name: string | null;
  status: "CREATED" | "SKIPPED";
  tracking_item_id?: number | null;
  reason?: string | null;
};

export type CreateTrackingFromConditionResultsResponse = {
  requested_count?: number;
  success: boolean;
  created_count: number;
  skipped_count: number;
  item_ids: number[];
  items?: CreateTrackingFromConditionResultStatus[];
  message: string;
};
export type UpdateStockTrackingReviewPayload = {
  status: StockTrackingStatus;
  review_note?: string | null;
};


export type CollectStockTrackingPricesPayload = {
  item_ids: number[];
  source?: string;
};

export type CollectStockTrackingPriceItemResult = {
  item_id: number;
  stock_code: string | null;
  stock_name: string | null;
  status: "SUCCESS" | "PARTIAL" | "FAILED" | "SKIPPED";
  collected_count: number;
  last_collected_date: string | null;
  message: string | null;
};

export type CollectStockTrackingPricesResponse = {
  requested_count: number;
  success_count: number;
  partial_count: number;
  failed_count: number;
  items: CollectStockTrackingPriceItemResult[];
  message: string;
};

export type StockTrackingChartPrice = {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  trading_value: number | null;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
  ma120: number | null;
};

export type StockTrackingChartResponse = {
  item_id: number;
  stock_code: string | null;
  stock_name: string | null;
  tracking_base_date: string;
  review_date: string | null;
  prices: StockTrackingChartPrice[];
};


export type StockTrackingImageType = "BASE_DATE" | "SUCCESS" | "FAIL" | "PULLBACK" | "OVERHEAT" | "ENTRY_POINT" | "ETC";

export type StockTrackingImage = {
  id: number;
  tracking_item_id: number;
  image_url: string;
  image_path?: string | null;
  original_filename?: string | null;
  image_type: StockTrackingImageType;
  image_type_label?: string | null;
  caption?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type StockTrackingImageListResponse = {
  items: StockTrackingImage[];
};


export type StockTrackingBaseMetricSummary = {
  close_vs_ma20_pct?: number | null;
  close_vs_ma60_pct?: number | null;
  recent_5d_return_pct?: number | null;
  trading_value_ratio_20?: number | null;
  ma60_slope_5d_pct?: number | null;
  high_vs_close_pct?: number | null;
  close_position_pct?: number | null;
};

export type StockTrackingGroupBaseMetricComparison = {
  avg?: StockTrackingBaseMetricSummary;
  success_avg?: StockTrackingBaseMetricSummary;
  fail_avg?: StockTrackingBaseMetricSummary;
  diff?: StockTrackingBaseMetricSummary;
};

export type StockTrackingGroupAnalysisSample = {
  item_id: number;
  stock_code: string | null;
  stock_name: string | null;
  tracking_base_date: string;
  review_date: string | null;
  review_note: string | null;
  current_return_pct: number | null;
  max_return_pct: number | null;
  max_drawdown_pct: number | null;
  elapsed_trading_days: number | null;
  close_vs_ma20_pct?: number | null;
  close_vs_ma60_pct?: number | null;
  recent_5d_return_pct?: number | null;
  trading_value_ratio_20?: number | null;
  ma60_slope_5d_pct?: number | null;
  high_vs_close_pct?: number | null;
  close_position_pct?: number | null;
};

export type StockTrackingGroupAnalysis = {
  group_id: number;
  group_name: string;
  total_count: number;
  tracking_count: number;
  hold_count: number;
  success_count: number;
  fail_count: number;
  excluded_count: number;
  completed_count: number;
  success_rate: number | null;
  return_calculated_count: number;
  base_metric_calculated_count?: number;
  base_metric_summary?: StockTrackingGroupBaseMetricComparison;
  avg_current_return_pct: number | null;
  avg_max_return_pct: number | null;
  avg_max_drawdown_pct: number | null;
  avg_elapsed_trading_days: number | null;
  success_avg_current_return_pct: number | null;
  success_avg_max_return_pct: number | null;
  success_avg_max_drawdown_pct: number | null;
  success_avg_elapsed_trading_days: number | null;
  fail_avg_current_return_pct: number | null;
  fail_avg_max_return_pct: number | null;
  fail_avg_max_drawdown_pct: number | null;
  fail_avg_elapsed_trading_days: number | null;
  diff_avg_current_return_pct: number | null;
  diff_avg_max_return_pct: number | null;
  diff_avg_max_drawdown_pct: number | null;
  success_samples: StockTrackingGroupAnalysisSample[];
  fail_samples: StockTrackingGroupAnalysisSample[];
};

export type StockTrackingGroupAnalysisListResponse = {
  items: StockTrackingGroupAnalysis[];
};
