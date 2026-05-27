export type TradeMethod = {
  id: number;
  method_name: string;
  description?: string | null;
  entry_rule?: string | null;
  exit_rule?: string | null;
  stop_loss_rule?: string | null;
  take_profit_rule?: string | null;
  is_active: number;
  sort_order: number;
  created_at?: string;
  updated_at?: string | null;
};

export type TradeMethodSaveRequest = {
  method_name: string;
  description?: string;
  entry_rule?: string;
  exit_rule?: string;
  stop_loss_rule?: string;
  take_profit_rule?: string;
  is_active: boolean;
  sort_order: number;
};

export type TradeJournal = {
  id: number;
  buy_date: string;
  sell_date?: string | null;
  stock_code?: string | null;
  stock_name: string;
  stock_theme?: string | null;
  trade_method_id?: number | null;
  trade_method_name?: string | null;
  result_type?: "profit" | "loss" | "holding" | "break_even" | string | null;
  profit_rate?: number | null;
  realized_profit?: number | null;
  buy_price?: number | null;
  buy_quantity?: number | null;
  buy_amount?: number | null;
  sell_price?: number | null;
  sell_quantity?: number | null;
  sell_amount?: number | null;
  trade_reason?: string | null;
  success_reason?: string | null;
  failure_reason?: string | null;
  review_memo?: string | null;
  remark?: string | null;
  image_count?: number;
  created_at?: string;
  updated_at?: string | null;
};

export type TradeJournalSaveRequest = {
  buy_date: string;
  sell_date?: string | null;
  stock_code?: string;
  stock_name: string;
  stock_theme?: string;
  trade_method_id?: number | null;
  trade_method_name?: string;
  result_type?: string;
  profit_rate?: number | null;
  realized_profit?: number | null;
  buy_price?: number | null;
  buy_quantity?: number | null;
  buy_amount?: number | null;
  sell_price?: number | null;
  sell_quantity?: number | null;
  sell_amount?: number | null;
  trade_reason?: string;
  success_reason?: string;
  failure_reason?: string;
  review_memo?: string;
  remark?: string;
};

export type TradeJournalListResponse = {
  items: TradeJournal[];
  total_count: number;
};

export type TradeJournalImage = {
  id: number;
  trade_journal_id: number;
  image_type: string;
  image_path: string;
  image_url?: string | null;
  image_memo?: string | null;
  original_filename?: string | null;
  created_at?: string;
};

export type TradeCalendarDaySummary = {
  trade_date: string;
  trade_count: number;
  realized_profit_sum: number;
};

export type TradeMonthlyStatistics = {
  trade_month: string;
  trade_count: number;
  profit_count: number;
  loss_count: number;
  win_rate: number;
  realized_profit_sum: number;
  avg_profit_rate: number;
};

export type TradeMonthlyStatisticsResponse = {
  items: TradeMonthlyStatistics[];
  total: number;
  page: number;
  page_size: number;
};

export type TradeJournalGptReviewPackage = {
  package_type: "single_trade_review";
  trade_journal_id: number;
  prompt_key: string;
  prompt_text: string;
  markdown: string;
  json_data: Record<string, unknown>;
};
