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
};

export type TrainingOrderRequest = {
  price: number;
  quantity: number;
  reason?: string | null;
};

export type TrainingSession = {
  id: number;
  stock_code: string;
  stock_name: string | null;
  method_id?: number | null;
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
