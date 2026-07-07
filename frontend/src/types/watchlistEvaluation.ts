export type DataConfidence = "NOT_EVALUATED" | "LIMITED" | "PARTIAL" | "ENOUGH";
export type EvaluationStatus = "EVALUATED" | "PARTIAL" | "DATA_MISSING" | "NOT_EVALUATED" | "ERROR";
export type EvaluationCategory = "MARKET" | "MATERIAL" | "SUPPLY" | "CHART" | "FINANCIAL" | "OVERALL";
export type StockType = "common_stock" | "preferred_stock" | "etf" | "etn" | "spac" | "reit" | "other" | "UNCLASSIFIED";

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
  supply_score: number | null;
  chart_score: number | null;
  financial_score: number | null;
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
  supply_score?: number | null;
  chart_score?: number | null;
  financial_score?: number | null;
  total_score: number | null;
  overall_status: string | null;
  data_confidence: string;
  missing_data: string[];
};

export type WatchlistGptPromptResponse = {
  watchlist_id: number;
  prompt: string;
};