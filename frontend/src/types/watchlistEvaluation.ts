export type DataConfidence = "NOT_EVALUATED" | "LIMITED" | "PARTIAL" | "ENOUGH";
export type EvaluationStatus = "EVALUATED" | "PARTIAL" | "DATA_MISSING" | "NOT_EVALUATED" | "ERROR";
export type EvaluationCategory = "MARKET" | "MATERIAL" | "SUPPLY" | "CHART" | "FINANCIAL" | "OVERALL";
export type StockType = "common_stock" | "preferred_stock" | "etf" | "etn" | "spac" | "reit" | "other" | "UNCLASSIFIED";


export type MaterialNewsItem = {
  id: number;
  title: string;
  published_at?: string | null;
  importance_score?: number | null;
  summary?: string | null;
  source?: string | null;
  sentiment?: string | null;
};

export type MaterialDisclosureItem = {
  id: number;
  title: string;
  disclosed_at?: string | null;
  importance_score?: number | null;
  summary?: string | null;
  disclosure_type?: string | null;
  risk_level?: string | null;
};

export type MaterialThemeItem = {
  theme_id?: number | null;
  theme_name: string;
  is_primary?: boolean;
  return_30d?: number | null;
  return_5d?: number | null;
  source_date?: string | null;
};

export type WatchlistEvaluationFactor = {
  id?: number;
  score_id?: number;
  category: EvaluationCategory | string;
  factor_code: string;
  factor_name: string;
  raw_value?: string | null;
  normalized_score?: number | null;
  weight?: number | null;
  contribution_score?: number | null;
  reason?: string | null;
  source_table?: string | null;
  source_date?: string | null;
  created_at?: string;
};

export type ChartMetrics = {
  trade_date?: string | null;
  close_price?: number | null;
  ma5?: number | null;
  ma10?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ma120?: number | null;
  close_vs_ma20_pct?: number | null;
  close_vs_ma60_pct?: number | null;
  ma60_slope_5d?: number | null;
  recent_5d_return?: number | null;
  trading_value_ratio_20?: number | null;
};

export type FinancialStatementItem = {
  period_label?: string | null;
  period_end_date?: string | null;
  revenue?: number | null;
  operating_profit?: number | null;
  net_income?: number | null;
};

export type FinancialSnapshot = Record<string, string | number | null | undefined>;
export type FinancialCollectResponse = {
  status: string;
  target_count: number;
  success_count: number;
  partial_count: number;
  failed_count: number;
  skipped_count: number;
};

export type WatchlistEvaluationListItem = {
  watchlist_id: number;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  market: string | null;
  is_active: boolean;
  watch_reason: string | null;
  stock_type: StockType | string;
  market_score: number | null;
  market_status?: EvaluationStatus | string | null;
  market_grade?: string | null;
  market_summary?: string | null;
  market_factors?: WatchlistEvaluationFactor[];
  missing_market_data?: string[];
  material_score: number | null;
  material_status?: EvaluationStatus | string | null;
  material_grade?: string | null;
  material_summary?: string | null;
  material_factors?: WatchlistEvaluationFactor[];
  missing_material_data?: string[];
  latest_material_date?: string | null;
  material_news_count?: number;
  material_disclosure_count?: number;
  material_theme_names?: string[];
  material_recent_news?: MaterialNewsItem[];
  material_recent_disclosures?: MaterialDisclosureItem[];
  material_themes?: MaterialThemeItem[];
  supply_score: number | null;
  supply_status?: EvaluationStatus | string | null;
  supply_grade?: string | null;
  supply_summary?: string | null;
  supply_factors?: WatchlistEvaluationFactor[];
  missing_supply_data?: string[];
  representative_theme_name?: string | null;
  representative_theme_return_30d?: number | null;
  supply_investor_flow_status?: Record<string, string>;
  supply_model_version?: string | null;
  investor_flow_summary?: Record<string, unknown>;
  chart_score: number | null;
  chart_status?: EvaluationStatus | string | null;
  chart_grade?: string | null;
  chart_summary?: string | null;
  chart_factors?: WatchlistEvaluationFactor[];
  missing_chart_data?: string[];
  chart_model_version?: string | null;
  chart_metrics?: ChartMetrics;
  financial_score: number | null;
  financial_status?: EvaluationStatus | string | null;
  financial_grade?: string | null;
  financial_summary?: string | null;
  financial_factors?: WatchlistEvaluationFactor[];
  missing_financial_data?: string[];
  financial_model_version?: string | null;
  financial_snapshot?: FinancialSnapshot;
  financial_annual_statements?: FinancialStatementItem[];
  financial_quarterly_statements?: FinancialStatementItem[];
  shareholder_snapshot?: FinancialSnapshot;
  total_score: number | null;
  data_confidence: DataConfidence | string;
  last_evaluated_at: string | null;
  missing_data: string[];
};

export type WatchlistEvaluationSummary = {
  watchlist_count: number;
  active_count: number;
  inactive_count: number;
  evaluated_count: number;
  not_evaluated_count: number;
  missing_data_count: number;
  last_evaluated_at: string | null;
};

export type WatchlistEvaluationListResponse = {
  items: WatchlistEvaluationListItem[];
  summary: WatchlistEvaluationSummary;
};

export type WatchlistEvaluateResponse = {
  run_id: number;
  evaluated_count: number;
  status: string;
};

export type WatchlistEvaluationHistoryItem = {
  score_id: number;
  run_id: number;
  run_date: string;
  run_type: string;
  status: string;
  evaluated_at: string;
  market_score?: number | null;
  market_status?: string | null;
  market_grade?: string | null;
  material_score?: number | null;
  material_status?: string | null;
  material_grade?: string | null;
  material_summary?: string | null;
  material_factors?: WatchlistEvaluationFactor[];
  missing_material_data?: string[];
  latest_material_date?: string | null;
  material_news_count?: number;
  material_disclosure_count?: number;
  material_theme_names?: string[];
  supply_score?: number | null;
  supply_status?: string | null;
  supply_grade?: string | null;
  supply_summary?: string | null;
  supply_factors?: WatchlistEvaluationFactor[];
  missing_supply_data?: string[];
  representative_theme_name?: string | null;
  representative_theme_return_30d?: number | null;
  supply_investor_flow_status?: Record<string, string>;
  supply_model_version?: string | null;
  investor_flow_summary?: Record<string, unknown>;
  chart_score?: number | null;
  chart_status?: string | null;
  chart_grade?: string | null;
  chart_summary?: string | null;
  chart_factors?: WatchlistEvaluationFactor[];
  missing_chart_data?: string[];
  chart_model_version?: string | null;
  chart_metrics?: ChartMetrics;
  financial_score?: number | null;
  financial_status?: string | null;
  financial_grade?: string | null;
  financial_summary?: string | null;
  financial_factors?: WatchlistEvaluationFactor[];
  missing_financial_data?: string[];
  financial_model_version?: string | null;
  financial_snapshot?: FinancialSnapshot;
  financial_annual_statements?: FinancialStatementItem[];
  financial_quarterly_statements?: FinancialStatementItem[];
  shareholder_snapshot?: FinancialSnapshot;
  total_score: number | null;
  overall_status: string | null;
  data_confidence: string;
  missing_data: string[];
};

export type WatchlistGptPromptResponse = {
  watchlist_id: number;
  prompt: string;
};

export type InvestorFlowMetricMode = "qty" | "amount";

export type InvestorFlowChartItem = {
  date: string;
  source?: string | null;
  data_source_type?: string | null;
  source_method?: string | null;
  is_real_investor_flow?: boolean;
  collection_status?: string | null;
  foreign_net_qty?: number | null;
  institution_net_qty?: number | null;
  program_net_qty?: number | null;
  foreign_net_amount?: number | null;
  foreign_holding_qty?: number | null;
  foreign_holding_ratio?: number | null;
  institution_net_amount?: number | null;
  program_net_amount?: number | null;
};

export type InvestorFlowChartResponse = {
  watchlist_id: number;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  latest_date?: string | null;
  selected_source_type?: string | null;
  fallback_source_type?: string | null;
  is_real_investor_flow?: boolean;
  source_method?: string | null;
  source_methods?: string[];
  has_real_data?: boolean;
  amount_available?: boolean;
  available_subjects?: Record<"foreign" | "institution" | "program", boolean>;
  available_metrics?: { foreign_holding_ratio?: boolean };
  data_notice?: string | null;
  items: InvestorFlowChartItem[];
};

export type InvestorFlowCollectRequest = {
  watchlist_ids?: number[];
  stock_ids?: number[];
  period?: "RECENT_7D" | "RECENT_30D" | "RECENT_90D" | "CUSTOM";
  start_date?: string | null;
  end_date?: string | null;
  source?: string;
  prefer_real_source?: boolean;
  fallback_to_derived?: boolean;
};

export type InvestorFlowCollectResponse = {
  status: string;
  requested_count: number;
  success_count: number;
  failed_count: number;
  saved_count: number;
  items: Array<{ stock_id: number; stock_code: string; stock_name: string; status: string; message?: string | null; saved_count: number; data_source_type?: string | null; foreign_status?: string | null; institution_status?: string | null; program_status?: string | null; foreign_holding_status?: string | null }>; 
};
