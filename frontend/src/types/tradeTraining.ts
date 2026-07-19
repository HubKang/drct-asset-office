import type { TradeMethod } from "@/types/tradeJournal";

export type TrainingStockItem = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  market: string | null;
  price_count: number;
  first_date: string | null;
  last_date: string | null;
  source: string | null;
};

export type TrainingStockListResponse = {
  items: TrainingStockItem[];
  limit: number;
};

export type TrainingSessionCreate = {
  stock_code: string;
  method_id?: number | null;
  initial_cash: number;
  fee_rate: number;
  display_days: number;
  start_date?: string | null;
  end_date?: string | null;
  moving_averages: number[];
  training_account_id?: number | null;
};

export type TrainingLaunchMode = "standalone" | "account-linked";

export type TradeTrainingAccountStatus = "ACTIVE" | "PAUSED" | "COMPLETED" | "ARCHIVED";

export type TradeTrainingAccount = {
  id: number;
  name: string;
  description: string | null;
  status: TradeTrainingAccountStatus | string;
  initial_capital: number;
  cash_balance: number;
  realized_equity: number;
  commission_rate: number;
  risk_per_trade_pct: number;
  max_open_risk_pct: number;
  max_position_count: number;
  display_days_default: number;
  moving_average_periods_default: number[];
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
};

export type TradeTrainingAccountListResponse = {
  items: TradeTrainingAccount[];
};

export type TradeTrainingAccountSaveRequest = {
  name: string;
  description?: string | null;
  status?: TradeTrainingAccountStatus | string;
  initial_capital: number;
  cash_balance?: number | null;
  realized_equity?: number | null;
  commission_rate: number;
  risk_per_trade_pct: number;
  max_open_risk_pct: number;
  max_position_count: number;
  display_days_default: number;
  moving_average_periods_default: number[];
};

export type TradeTrainingAccountSummary = {
  account_id: number;
  initial_capital: number;
  cash_balance: number;
  training_equity: number;
  current_training_equity?: number | null;
  open_position_cost?: number | null;
  open_position_market_value?: number | null;
  realized_pnl: number;
  unrealized_pnl: number;
  cumulative_realized_return_pct?: number | null;
  current_equity_return_pct?: number | null;
  active_session_count: number;
  open_position_count?: number | null;
  closed_trade_count: number;
  winning_ratio: number | null;
  profit_loss_ratio: number | null;
  profit_loss_ratio_status: ProfitLossRatioStatus;
  winning_trade_count: number;
  losing_trade_count: number;
  flat_trade_count: number;
  average_profit: number | null;
  average_loss: number | null;
};

export type TradeTrainingAccountDeleteResponse = {
  deleted: boolean;
  account_id: number;
  session_count: number;
  trade_count: number;
  snapshot_count: number;
  review_count: number;
  message: string;
};

export type TradeTrainingAccountSession = {
  id: number;
  session_id?: number | null;
  training_account_id: number;
  stock_id?: number | null;
  market?: string | null;
  stock_code: string;
  stock_name: string | null;
  status: string;
  status_state?: "READY" | "WATCHING" | "OPEN" | "PAUSED" | "COMPLETED" | string | null;
  status_display?: string | null;
  start_date: string;
  end_date: string;
  chart_start_date?: string | null;
  chart_end_date?: string | null;
  current_date: string | null;
  chart_current_date?: string | null;
  current_index: number;
  current_step?: number | null;
  display_days?: number | null;
  moving_averages?: number[];
  position_qty: number;
  position_quantity?: number | null;
  avg_price: number;
  average_entry_price?: number | null;
  current_price?: number | null;
  market_value?: number | null;
  position_cost?: number | null;
  unrealized_pnl?: number | null;
  unrealized_return_pct?: number | null;
  realized_profit: number;
  trade_count: number;
  buy_count: number;
  sell_count: number;
  created_at: string | null;
  updated_at: string | null;
  last_trained_at?: string | null;
};

export type TradeTrainingAccountSessionListResponse = {
  items: TradeTrainingAccountSession[];
};

export type TradeTrainingClosedTrade = {
  id: string;
  closed_trade_id?: string | null;
  trade_sequence: number;
  training_account_id: number;
  training_session_id: number;
  simulation_session_id?: number | null;
  stock_id: number | null;
  stock_code: string;
  stock_name: string | null;
  opened_chart_date: string;
  closed_chart_date: string;
  chart_entry_date?: string | null;
  chart_exit_date?: string | null;
  completed_at: string | null;
  gross_buy_amount: number;
  gross_sell_amount: number;
  gross_pnl?: number | null;
  commission_amount: number;
  tax_amount: number;
  net_pnl: number;
  return_pct: number;
  holding_bars: number;
  result_type: "WIN" | "LOSS" | "FLAT" | string;
  quantity: number;
  actual_quantity?: number | null;
  avg_buy_price: number;
  avg_sell_price: number;
  average_entry_price?: number | null;
  average_exit_price?: number | null;
  planned_risk_pct?: number | null;
  planned_risk_amount?: number | null;
  realized_r?: number | null;
  atr_value?: number | null;
  atr_pct?: number | null;
  recommended_quantity?: number | null;
};

export type TradeTrainingClosedTradeListResponse = {
  items: TradeTrainingClosedTrade[];
};

export type ProfitLossRatioStatus = "NO_CLOSED_TRADES" | "NO_WIN_TRADES" | "NO_LOSS_TRADES" | "AVAILABLE" | string;

export type TradeTrainingPerformancePoint = {
  closed_trade_id: string | null;
  trade_sequence: number;
  simulation_session_id: number | null;
  training_session_id: number | null;
  training_account_id: number | null;
  stock_id: number | null;
  stock_code: string;
  stock_name: string | null;
  chart_entry_date: string | null;
  chart_exit_date: string | null;
  completed_at: string | null;
  quantity: number | null;
  average_entry_price: number | null;
  average_exit_price: number | null;
  gross_buy_amount?: number | null;
  gross_sell_amount?: number | null;
  gross_pnl: number | null;
  commission_amount: number | null;
  tax_amount: number | null;
  net_pnl: number;
  return_pct: number;
  holding_bars: number | null;
  equity_before: number | null;
  equity_after: number;
  cumulative_return_pct: number | null;
  planned_risk_pct: number | null;
  planned_risk_amount: number | null;
  realized_r: number | null;
  atr_value: number | null;
  atr_pct: number | null;
  recommended_quantity: number | null;
  actual_quantity: number | null;
};

export type TradeTrainingAccountPerformance = {
  account_id: number | null;
  initial_capital: number;
  current_realized_equity: number | null;
  cumulative_return_pct: number | null;
  closed_trade_count: number;
  winning_ratio: number | null;
  profit_loss_ratio: number | null;
  profit_loss_ratio_status: ProfitLossRatioStatus;
  winning_trade_count: number;
  losing_trade_count: number;
  flat_trade_count: number;
  average_profit: number | null;
  average_loss: number | null;
  items: TradeTrainingPerformancePoint[];
};

export type TrainingOrderRequest = {
  price: number;
  quantity: number;
  reason?: string | null;
  method_review?: TrainingMethodReview | null;
  client_order_id?: string | null;
};

export type TrainingSession = {
  id: number;
  stock_code: string;
  stock_name: string | null;
  method_id?: number | null;
  training_account_id?: number | null;
  start_date: string;
  end_date: string;
  current_date: string | null;
  current_index: number;
  initial_cash: number;
  cash: number;
  position_qty: number;
  avg_price: number;
  realized_profit: number;
  status: string;
  options: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
};

export type TrainingCandle = {
  trade_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  trading_value: number | null;
  moving_averages: Record<string, number | null>;
};

export type TrainingAccount = {
  current_price: number;
  evaluation_amount: number;
  cash_balance?: number | null;
  open_position_cost?: number | null;
  open_position_market_value?: number | null;
  current_training_equity?: number | null;
  unrealized_profit: number;
  unrealized_return_rate: number;
  position_profit: number;
  position_return_rate: number;
  realized_profit: number;
  total_asset: number;
  total_profit: number;
  total_return_rate: number;
};

export type TrainingTrade = {
  id: number;
  session_id: number;
  trade_date: string;
  side: "BUY" | "SELL" | string;
  price: number;
  quantity: number;
  fee: number;
  amount: number;
  realized_profit: number;
  reason: string | null;
  method_review?: TrainingMethodReview | null;
  created_at: string | null;
};

export type TrainingSessionDetail = {
  session: TrainingSession;
  trade_method?: TradeMethod | null;
  candles: TrainingCandle[];
  current_candle: TrainingCandle | null;
  account: TrainingAccount;
  trades: TrainingTrade[];
};

export type TrainingFinishResponse = {
  session: TrainingSession;
  account: TrainingAccount;
  message: string;
};

export type TrainingTradePair = {
  buy_date: string;
  sell_date: string;
  buy_price: number;
  sell_price: number;
  quantity: number;
  holding_days: number;
  profit_amount: number;
  profit_rate: number;
  buy_reason: string | null;
  sell_reason: string | null;
  buy_reason_quality?: string | null;
  sell_reason_quality?: string | null;
  buy_reason_quality_guide?: string | null;
  sell_reason_quality_guide?: string | null;
  buy_method_review?: TrainingMethodReview | null;
  sell_method_review?: TrainingMethodReview | null;
};

export type TrainingMethodReview = {
  selected_template?: string;
  entry_type_tags?: string[];
  method_fit?: string;
  matched_entry_rules?: string;
  risk_or_violation_notes?: string;
  failure_criteria?: string;
  stop_loss_rule?: string;
  target_exit_rule?: string;
  add_buy_plan_type?: string;
  add_buy_condition?: string;
  max_position_plan?: string;
  add_buy_stop_loss_rule?: string;
  exit_type_tags?: string[];
  method_exit_fit?: string;
  matched_exit_rules?: string;
  plan_alignment?: string;
  exit_reason_detail?: string;
  after_review_memo?: string;
};

export type TrainingOpenPosition = {
  position_qty: number;
  avg_price: number;
  evaluation_amount: number;
  unrealized_profit: number;
  unrealized_return_rate: number;
};

export type TrainingEquityCurvePoint = {
  trade_date: string;
  total_asset: number;
  cash: number;
  evaluation_amount: number;
};

export type TrainingResult = {
  session_id: number;
  stock_code: string;
  stock_name: string | null;
  start_date: string;
  end_date: string;
  current_date: string | null;
  status: string;
  initial_cash: number;
  final_cash: number;
  final_evaluation_amount: number;
  final_total_asset: number;
  total_profit: number;
  total_return_rate: number;
  trade_count: number;
  buy_count: number;
  sell_count: number;
  round_trip_count: number;
  winning_trade_count: number;
  losing_trade_count: number;
  break_even_trade_count: number;
  win_rate: number | null;
  average_profit_rate: number | null;
  average_loss_rate: number | null;
  max_profit_amount: number | null;
  max_loss_amount: number | null;
  average_holding_days: number | null;
  total_fees: number;
  buy_reason_fill_rate: number | null;
  sell_reason_fill_rate: number | null;
  buy_reason_quality_summary?: Record<string, number>;
  sell_reason_quality_summary?: Record<string, number>;
  weak_buy_reason_count?: number;
  weak_sell_reason_count?: number;
  method_review_stats?: Record<string, number>;
  trade_pairs: TrainingTradePair[];
  open_position: TrainingOpenPosition;
  equity_curve: TrainingEquityCurvePoint[];
};

export type TrainingGptPackage = {
  session_id: number;
  stock_code: string;
  stock_name: string | null;
  package_title: string;
  generated_prompt: string;
  sections: Record<string, string>;
};

export type SimulationReview = {
  session_id: number;
  review_status: string;
  self_review_text: string;
  gpt_prompt_text: string;
  gpt_review_text: string;
  improvement_point: string;
  next_training_goal: string;
  main_mistake: string;
  discipline_score: number | null;
  reviewed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type SimulationReviewSaveRequest = {
  review_status: string;
  self_review_text?: string | null;
  gpt_prompt_text?: string | null;
  gpt_review_text?: string | null;
  improvement_point?: string | null;
  next_training_goal?: string | null;
  main_mistake?: string | null;
  discipline_score?: number | null;
};

export type TrainingCalendarStock = {
  stock_code?: string | null;
  stock_name: string;
  training_count: number;
  total_return_rate: number;
  avg_return_rate: number;
  review_saved_count: number;
};

export type TrainingCalendarMethodGroup = {
  trade_method_id?: number | null;
  trade_method_name: string;
  training_count: number;
  total_return_rate: number;
  avg_return_rate: number;
  review_saved_count: number;
  stocks: TrainingCalendarStock[];
};

export type TrainingCalendarDay = {
  date: string;
  training_count: number;
  total_return_rate: number;
  avg_return_rate: number;
  training_score: number;
  review_saved_count: number;
  review_required_count: number;
  method_groups: TrainingCalendarMethodGroup[];
};

export type TrainingCalendarSummary = {
  total_sessions: number;
  training_days: number;
  avg_training_score: number;
  avg_return_rate: number;
  review_completion_rate: number;
};

export type TrainingCalendarResponse = {
  month: string;
  summary: TrainingCalendarSummary;
  days: TrainingCalendarDay[];
};
