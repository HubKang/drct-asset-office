export type StockDailyPrice = {
  id: number;
  stock_id: number;
  stock_code?: string;
  stock_name?: string;
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
  rsi14?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  macd_histogram?: number | null;
  bb_upper?: number | null;
  bb_middle?: number | null;
  bb_lower?: number | null;
  bb_width?: number | null;
  bb_close_position?: string | null;
  atr14?: number | null;
  atr14_ratio_to_close?: number | null;
  ma20_gap_pct?: number | null;
  volume_5_20_ratio?: number | null;
  technical_indicator_source?: string | null;
  technical_indicator_calculation_version?: string | null;
  source: string | null;
  created_at: string;
  updated_at: string;
};

export type SelectedStockPriceCollectRequest = {
  stock_ids: number[];
  period_years: number;
  source: string;
  overlap_days?: number;
  force_full_refresh?: boolean;
  start_date?: string | null;
  end_date?: string | null;
};

export type StockPriceCollectItemResult = {
  stock_id: number;
  stock_code: string;
  normalized_stock_code?: string | null;
  stock_name: string;
  status: string;
  mode?: string | null;
  from_date?: string | null;
  to_date?: string | null;
  collected_count?: number;
  saved_count: number;
  technical_indicator_saved_count?: number;
  technical_indicator_latest_trade_date?: string | null;
  source?: string | null;
  message: string | null;
};

export type StockPriceCollectResult = {
  requested_count: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  saved_count: number;
  technical_indicator_saved_count?: number;
  source?: string | null;
  message: string;
  results: StockPriceCollectItemResult[];
};

export type SelectedMarketMetricsCollectRequest = {
  stock_ids: number[];
  source?: string;
};

export type SelectedMarketMetricsCollectItem = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  trade_date?: string | null;
  source: string;
  status: string;
  error_type?: string | null;
  message?: string | null;
  saved_count: number;
};

export type SelectedMarketMetricsCollectResult = {
  success: boolean;
  source: string;
  requested_count: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  saved_count: number;
  message: string;
  results: SelectedMarketMetricsCollectItem[];
};

export type TechnicalIndicatorCalculationResult = {
  stock_id: number;
  calculated_count: number;
  saved_count: number;
  latest_trade_date: string | null;
  message: string;
};

export type TechnicalIndicatorBatchCalculationItem = TechnicalIndicatorCalculationResult & {
  status: string;
};

export type TechnicalIndicatorBatchCalculationResult = {
  total_requested: number;
  success_count: number;
  failed_count: number;
  saved_count: number;
  items: TechnicalIndicatorBatchCalculationItem[];
  message: string;
};

export type StockDailyPriceListResponse = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  items: StockDailyPrice[];
  limit: number;
  offset: number;
};

export type StockPriceSummaryItem = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  market: string | null;
  security_type: string | null;
  price_count: number;
  min_trade_date: string | null;
  max_trade_date: string | null;
  latest_close_price: number | null;
  latest_volume: number | null;
  latest_trading_value: number | null;
  latest_ma5: number | null;
  latest_ma20: number | null;
  latest_ma60: number | null;
  latest_ma120: number | null;
  latest_ma240: number | null;
  source: string | null;
};

export type StockPriceSummaryResponse = {
  items: StockPriceSummaryItem[];
  limit: number;
  offset: number;
};

export type StockPriceFactSummaryResponse = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  source: string;
  price_count: number;
  min_trade_date: string | null;
  max_trade_date: string | null;
  latest_trade_date: string | null;
  latest_close_price: number | null;
  latest_ma5: number | null;
  latest_ma20: number | null;
  latest_ma60: number | null;
  recent_5d_change_rate: number | null;
  avg_volume_20d: number | null;
  high_52w: number | null;
  high_52w_date: string | null;
  price_position_vs_52w_high: number | null;
};

export type MarketMetricsSummaryResponse = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  source: string;
  latest_market_metrics_date: string;
  latest_price_trade_date: string | null;
  date_gap_days?: number | null;
  date_gap_label?: string | null;
  freshness_status?: string | null;
  freshness_label?: string | null;
  freshness_message?: string | null;
  is_stale: boolean;
  stale_days: number | null;
  staleness_level: string;
  market: string | null;
  trading_value: number | null;
  trading_value_display?: string | null;
  market_cap: number | null;
  market_cap_display?: string | null;
  listed_shares: number | null;
  trading_volume: number | null;
  market_cap_rank: number | null;
  trading_value_rank: number | null;
  market_trading_value_rank: number | null;
  trading_value_percentile: number | null;
  market_trading_value_percentile: number | null;
  foreign_ownership_ratio?: number | null;
  used_api_ids?: string[] | null;
  source_label?: string | null;
  unit_notes?: Record<string, string> | null;
  data_note: string;
};

export type MarketIndexSnapshot = {
  market: string;
  index_value: number | null;
  change_value: number | null;
  change_rate: number | null;
  volume: number | null;
  trading_value: number | null;
  base_date: string | null;
};

export type MarketIndicatorsOverviewResponse = {
  source: string;
  base_date: string | null;
  fetched_at: string;
  kospi: MarketIndexSnapshot;
  kosdaq: MarketIndexSnapshot;
  message: string | null;
};

export type EvidenceStockBlock = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
};

export type EvidencePriceSummaryBlock = {
  latest_trade_date: string | null;
  latest_close_price: number | null;
  latest_ma5: number | null;
  latest_ma20: number | null;
  latest_ma60: number | null;
  recent_5d_change_rate: number | null;
  avg_volume_20d: number | null;
  high_52w: number | null;
  high_52w_date: string | null;
  price_position_vs_52w_high: number | null;
  price_count: number;
  source: string;
};

export type EvidenceMarketMetricsSummaryBlock = {
  latest_market_metrics_date: string;
  latest_price_trade_date: string | null;
  date_gap_days?: number | null;
  date_gap_label?: string | null;
  freshness_status?: string | null;
  freshness_label?: string | null;
  freshness_message?: string | null;
  is_stale: boolean;
  stale_days: number | null;
  staleness_level: string;
  market: string | null;
  trading_value: number | null;
  trading_value_display?: string | null;
  market_cap: number | null;
  market_cap_display?: string | null;
  listed_shares: number | null;
  trading_volume: number | null;
  trading_value_rank: number | null;
  market_trading_value_rank: number | null;
  trading_value_percentile: number | null;
  market_trading_value_percentile: number | null;
  foreign_ownership_ratio?: number | null;
  used_api_ids?: string[] | null;
  source_label?: string | null;
  source: string;
  unit_notes?: Record<string, string> | null;
  data_note: string;
};

export type EvidenceTimeframeSummaryBlock = {
  label: string;
  start_trade_date: string | null;
  end_trade_date: string | null;
  change_rate: number | null;
  highest_price: number | null;
  lowest_price: number | null;
};

export type EvidenceRecentCandleItem = {
  trade_date: string;
  open_price: number | null;
  high_price: number | null;
  low_price: number | null;
  close_price: number | null;
  change_rate: number | null;
  volume: number | null;
};

export type EvidenceSimilarPatternCase = {
  rank: number;
  start_date: string;
  end_date: string;
  trading_days: number;
  overall_similarity_score: number;
  price_similarity_score: number;
  ma_position_similarity_score: number;
  volume_similarity_score: number;
  start_close: number | null;
  end_close: number | null;
  return_rate: number | null;
  max_return_after_pattern: number | null;
  min_return_after_pattern: number | null;
  after_5d_return: number | null;
  after_10d_return: number | null;
  after_20d_return: number | null;
  gpt_note_ko: string;
};

export type EvidenceSimilarPatternCasesBlock = {
  included: boolean;
  method: string;
  search_trading_days: number;
  pattern_window: number;
  pattern_ma: number;
  requested_limit: number;
  returned_count: number;
  weight: Record<string, number>;
  base_pattern: Record<string, unknown> | null;
  cases: EvidenceSimilarPatternCase[];
  data_quality_notes: string[];
};

export type EvidencePriceCandleReferenceBlock = {
  included: boolean;
  lookback_days: number;
  recent_candle_limit: number;
  include_raw_candles: boolean;
  pattern_window: number;
  similar_case_limit: number;
  row_count: number;
  start_trade_date: string | null;
  end_trade_date: string | null;
  timeframe_summaries: EvidenceTimeframeSummaryBlock[];
  recent_candles: EvidenceRecentCandleItem[];
  similar_pattern_cases: EvidenceSimilarPatternCasesBlock | null;
  caution_note: string | null;
};

export type EvidenceStrategyHorizonContextBlock = {
  selected_horizon: "swing" | "long_term" | "both" | string;
  horizon_notes: string[];
};

export type EvidenceAnalysisHorizonWeightsBlock = {
  swing_weight: number;
  long_term_weight: number;
};

export type AdvisoryEvidencePackageResponse = {
  stock: EvidenceStockBlock;
  price_summary: EvidencePriceSummaryBlock;
  market_metrics_summary: EvidenceMarketMetricsSummaryBlock | null;
  price_candle_reference: EvidencePriceCandleReferenceBlock | null;
  strategy_horizon_context: EvidenceStrategyHorizonContextBlock | null;
  analysis_horizon_weights: EvidenceAnalysisHorizonWeightsBlock | null;
  scenario_questions_for_gpt: string[];
  news_summary_block: Record<string, unknown> | null;
  disclosure_summary_block: Record<string, unknown> | null;
  risk_summary_block: Record<string, unknown> | null;
  recent_event_timeline: Record<string, unknown>[];
  technical_indicators_block: Record<string, unknown> | null;
  data_freshness_block: Record<string, unknown> | null;
  executive_summary_for_gpt: Record<string, unknown> | null;
  news_summary: Record<string, unknown> | null;
  disclosure_summary: Record<string, unknown> | null;
  risk_summary: Record<string, unknown> | null;
  theme_summary: Record<string, unknown> | null;
  telegram_theme_summary: Record<string, unknown> | null;
  data_quality_notes: string[];
  instruction_guardrails: string[];
  generated_at: string;
};
