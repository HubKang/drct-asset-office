export type BacktestBuyCondition =
  | { type: "close_above_ma"; period: number }
  | { type: "close_below_ma"; period: number }
  | { type: "volume_above_average"; period: number; multiplier: number }
  | { type: "bullish_candle" }
  | { type: "close_above_previous_high" }
  | { type: "close_above_recent_high"; period: number };

export type BacktestConditionField = {
  field_key: string;
  label: string;
  source_table: string;
  source_column: string;
  data_type: string;
  category: string;
  is_active: boolean;
  sort_order: number;
};

export type BacktestConditionFieldListResponse = {
  items: BacktestConditionField[];
};

export type BacktestOperator = ">" | ">=" | "<" | "<=" | "==" | "=";

export type BuyConditionRow = {
  id: string;
  condition_type:
    | "field_value_compare"
    | "field_vs_field"
    | "field_vs_indicator"
    | "field_vs_average_multiplier"
    | "candle_pattern";
  left?: { type: "field"; field: string; label?: string };
  operator?: BacktestOperator;
  right?: {
    type: "field" | "moving_average" | "average_multiplier";
    field?: string;
    period?: number;
    multiplier?: number;
    label?: string;
  };
  value?: number;
  pattern?: "bullish_candle" | "bearish_candle" | "close_above_previous_high" | "close_above_recent_high" | "close_below_recent_low";
  period?: number;
  label?: string;
};

export type SellConditionRow = {
  id: string;
  condition_type: "take_profit_pct" | "stop_loss_pct" | "close_below_ma" | "max_holding_days";
  value?: number;
  field?: string;
  period?: number;
  label?: string;
};

export type BacktestBuyConditions = {
  operator: "AND";
  conditions: Array<BacktestBuyCondition | BuyConditionRow>;
};

export type BacktestSellConditions = {
  operator?: "OR";
  conditions?: SellConditionRow[];
  take_profit_pct?: number;
  stop_loss_pct?: number;
  exit_on_close_below_ma?: { enabled: boolean; period: number };
  max_holding_days?: number;
};

export type BacktestPositionRule = {
  basis: "cash" | "total_asset" | "fixed_amount" | "fixed_quantity";
  percent: number;
};

export type BacktestRule = {
  id: number;
  rule_name: string;
  description?: string | null;
  trade_method_id?: number | null;
  buy_conditions_json: BacktestBuyConditions;
  sell_conditions_json: BacktestSellConditions;
  position_rule_json: BacktestPositionRule;
  fee_rate: number;
  slippage_rate: number;
  is_active: number;
  created_at: string;
  updated_at: string;
};

export type BacktestRuleInput = {
  rule_name: string;
  description?: string | null;
  trade_method_id?: number | null;
  buy_conditions_json: BacktestBuyConditions;
  sell_conditions_json: BacktestSellConditions;
  position_rule_json: BacktestPositionRule;
  fee_rate: number;
  slippage_rate: number;
};

export type BacktestRuleListResponse = {
  items: BacktestRule[];
};

export type BacktestStock = {
  stock_code: string;
  stock_name: string;
  market?: string | null;
  first_price_date?: string | null;
  last_price_date?: string | null;
  price_count: number;
  source?: string | null;
};

export type BacktestStockListResponse = {
  items: BacktestStock[];
  keyword?: string | null;
  limit: number;
};

export type BacktestRunSummary = {
  initial_cash: number;
  final_asset: number;
  total_profit: number;
  total_return_rate: number;
  max_drawdown: number;
  trade_count: number;
  win_count: number;
  loss_count: number;
  breakeven_count: number;
  win_rate?: number | null;
  avg_profit_rate?: number | null;
  avg_loss_rate?: number | null;
  profit_factor?: number | null;
  avg_holding_days?: number | null;
  total_fee: number;
};

export type BacktestRunRequest = {
  rule_id: number;
  stock_code: string;
  start_date?: string | null;
  end_date?: string | null;
  initial_cash: number;
};

export type BacktestRunCreateResponse = {
  run_id: number;
  summary: BacktestRunSummary;
};

export type BacktestRun = {
  id: number;
  rule_id: number;
  rule_name?: string | null;
  stock_code: string;
  stock_name?: string | null;
  start_date: string;
  end_date: string;
  initial_cash: number;
  final_asset?: number | null;
  total_profit?: number | null;
  total_return_rate?: number | null;
  max_drawdown?: number | null;
  trade_count: number;
  win_rate?: number | null;
  status: string;
  message?: string | null;
  created_at: string;
};

export type BacktestRunListResponse = {
  items: BacktestRun[];
};

export type BacktestTrade = {
  id: number;
  run_id: number;
  buy_date: string;
  sell_date?: string | null;
  buy_price: number;
  sell_price?: number | null;
  quantity: number;
  buy_amount: number;
  sell_amount?: number | null;
  fee: number;
  profit?: number | null;
  profit_rate?: number | null;
  holding_days?: number | null;
  exit_reason?: string | null;
};

export type BacktestEquityPoint = {
  id: number;
  run_id: number;
  trade_date: string;
  cash: number;
  position_qty: number;
  position_value: number;
  total_asset: number;
  drawdown_rate: number;
  created_at: string;
};

export type BacktestRunDetail = {
  run: BacktestRun;
  summary: BacktestRunSummary;
  rule?: BacktestRule | null;
  trades: BacktestTrade[];
  equity_curve: BacktestEquityPoint[];
};
