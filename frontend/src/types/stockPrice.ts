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
  source: string | null;
  created_at: string;
  updated_at: string;
};

export type SelectedStockPriceCollectRequest = {
  stock_ids: number[];
  period_years: number;
  source: string;
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
  source?: string | null;
  message: string | null;
};

export type StockPriceCollectResult = {
  requested_count: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  saved_count: number;
  source?: string | null;
  message: string;
  results: StockPriceCollectItemResult[];
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
  is_stale: boolean;
  stale_days: number | null;
  staleness_level: string;
  market: string | null;
  trading_value: number | null;
  market_cap: number | null;
  listed_shares: number | null;
  trading_volume: number | null;
  market_cap_rank: number | null;
  trading_value_rank: number | null;
  market_trading_value_rank: number | null;
  trading_value_percentile: number | null;
  market_trading_value_percentile: number | null;
  data_note: string;
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
  is_stale: boolean;
  stale_days: number | null;
  staleness_level: string;
  market: string | null;
  trading_value: number | null;
  market_cap: number | null;
  listed_shares: number | null;
  trading_volume: number | null;
  trading_value_rank: number | null;
  market_trading_value_rank: number | null;
  trading_value_percentile: number | null;
  market_trading_value_percentile: number | null;
  source: string;
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
  case_id: string;
  reference_end_trade_date: string;
  comparison_start_trade_date: string;
  comparison_end_trade_date: string;
  similarity_score: number;
  historical_next_5d_change_rate: number | null;
  historical_next_20d_change_rate: number | null;
  note: string;
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
  similar_pattern_cases: EvidenceSimilarPatternCase[];
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
  news_summary: Record<string, unknown> | null;
  disclosure_summary: Record<string, unknown> | null;
  risk_summary: Record<string, unknown> | null;
  theme_summary: Record<string, unknown> | null;
  telegram_theme_summary: Record<string, unknown> | null;
  data_quality_notes: string[];
  instruction_guardrails: string[];
  generated_at: string;
};
