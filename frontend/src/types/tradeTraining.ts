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

export type TradeTrainingPriceCollectionMode = "RECENT_7D" | "FULL";

export type TradeTrainingPriceCollectionResult = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  action: "selected_recent_7d" | "selected_full";
  mode: string;
  target_count: number;
  requested_start_date: string;
  requested_end_date: string;
  pages_fetched: number;
  collected_count: number;
  saved_count: number;
  technical_indicator_saved_count: number;
  price_count: number;
  first_trade_date: string | null;
  latest_trade_date: string | null;
  success: boolean;
  partial: boolean;
  error_message: string | null;
  technical_indicator_error: string | null;
  total_ms: number;
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
  training_account_name?: string | null;
  is_account_linked?: boolean;
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

export type RiskScenarioStatus = "DRAFT" | "ACTIVE" | "CLOSED" | "CANCELLED" | string;

export type RiskPlanStepBase = {
  plan_group: "BUY" | "SELL" | string;
  plan_type: string;
  step_no: number;
  status?: string;
  trigger_type?: string;
  trigger_price?: number | null;
  trigger_text?: string;
  planned_ratio_pct?: number | null;
  planned_quantity?: number | null;
  planned_amount?: number | null;
  memo?: string | null;
};

export type RiskPlanStepRequest = RiskPlanStepBase;

export type TradeTrainingRiskPlanStep = RiskPlanStepBase & {
  id: number;
  risk_scenario_id: number;
  is_removed?: boolean;
  executed_trade_id?: number | null;
  executed_at?: string | null;
  actual_price?: number | null;
  actual_quantity?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type RiskScenarioPreview = {
  risk_basis_equity?: number | null;
  account_risk_pct?: number | null;
  risk_budget_amount?: number | null;
  estimated_planned_loss?: number | null;
  estimated_risk_usage_pct?: number | null;
  warnings: string[];
};

export type TradeTrainingRiskScenarioDraftRequest = {
  buy_plan_mode: string;
  sell_plan_mode: string;
  profit_scenario_text: string;
  stop_scenario_text: string;
  stop_price?: number | null;
  primary_target_price?: number | null;
  memo?: string | null;
  buy_steps: RiskPlanStepRequest[];
  sell_steps: RiskPlanStepRequest[];
  change_reason?: string | null;
};

export type TradeTrainingRiskScenario = {
  id: number;
  training_account_id: number;
  simulation_session_id: number;
  cycle_no: number;
  status: RiskScenarioStatus;
  buy_plan_mode: string;
  sell_plan_mode: string;
  risk_basis_equity?: number | null;
  account_risk_pct?: number | null;
  risk_budget_amount?: number | null;
  profit_scenario_text: string;
  stop_scenario_text: string;
  stop_price?: number | null;
  primary_target_price?: number | null;
  estimated_planned_loss?: number | null;
  estimated_risk_usage_pct?: number | null;
  activated_at?: string | null;
  closed_at?: string | null;
  cancelled_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  closed_trade_id?: string | null;
  final_trade_id?: number | null;
  final_net_pnl?: number | null;
  final_return_pct?: number | null;
  memo?: string | null;
};

export type TradeTrainingRiskScenarioRevision = {
  id: number;
  risk_scenario_id: number;
  revision_no: number;
  revision_type: string;
  snapshot_json: string;
  snapshot: Record<string, unknown>;
  change_reason?: string | null;
  effective_from: string;
  created_at: string;
};

export type TradeTrainingRiskScenarioDetail = {
  scenario?: TradeTrainingRiskScenario | null;
  buy_steps: TradeTrainingRiskPlanStep[];
  sell_steps: TradeTrainingRiskPlanStep[];
  latest_revision?: TradeTrainingRiskScenarioRevision | null;
  preview?: RiskScenarioPreview | null;
  requires_plan_before_buy: boolean;
  holding_risk?: ActiveRiskSummary | null;
  events?: Array<Record<string, unknown>>;
  pending_responses?: RiskPendingResponse[];
};

export type RiskPendingResponse = {
  reach_event_id: number;
  event_type: string;
  chart_date?: string | null;
  created_at?: string | null;
  risk_scenario_id?: number | null;
  risk_scenario_revision_id?: number | null;
  risk_plan_step_id?: number | null;
  step_no?: number | null;
  plan_type?: string | null;
  trigger_price?: number | null;
  day_high?: number | null;
  day_low?: number | null;
  position_quantity?: number | null;
  sequence_unknown?: boolean;
};

export type RiskLevelReachCheckResponse = {
  events: Array<Record<string, unknown>>;
  pending_responses: RiskPendingResponse[];
};

export type ScenarioCategoryScore = {
  key: string;
  label: string;
  applicable?: boolean;
  score?: number | null;
  rate?: number | null;
  eligible_count: number;
  applicable_trade_count?: number;
  applicable_item_count?: number;
  earned_score?: number;
  max_score?: number;
  full_count?: number;
  partial_count?: number;
  miss_count?: number;
  excluded_count?: number;
};

export type ScenarioHabitTrade = TradeTrainingClosedTrade & {
  has_scenario_data: boolean;
  scenario_id?: number | null;
  scenario_execution_rate?: number | null;
  category_scores: ScenarioCategoryScore[];
  max_risk_pct?: number | null;
  unplanned_action_count: number;
  target_response?: Record<string, unknown>;
  stop_response?: Record<string, unknown>;
};

export type ScenarioHabitsResponse = {
  account_id: number;
  filters: Record<string, unknown>;
  coverage: { trade_count: number; closed_trade_count?: number; scenario_trade_count: number; legacy_trade_count: number; scored_trade_count: number; evaluable_trade_count?: number };
  summary: {
    average_execution_rate?: number | null;
    scenario_created_count?: number;
    scenario_creation_denominator?: number;
    scenario_creation_rate?: number | null;
    plan_creation_rate?: number | null;
    unplanned_order_count?: number;
    evaluated_order_count?: number;
    unplanned_order_rate?: number | null;
  };
  execution_trend: Array<{ trade_sequence: number; stock_name: string; result_type: string; score?: number | null; scenario_id?: number | null }>;
  category_scores: ScenarioCategoryScore[];
  target_response_distribution: ScenarioResponseDistribution;
  stop_response_distribution: ScenarioResponseDistribution;
  plan_change_distribution: ScenarioReasonDistribution;
  unplanned_action_distribution: ScenarioReasonDistribution;
  asymmetry: {
    average_profit?: number | null;
    average_loss?: number | null;
    average_win_pnl?: number | null;
    average_loss_pnl_abs?: number | null;
    average_win_holding_bars?: number | null;
    average_loss_holding_bars?: number | null;
    win_count?: number;
    loss_count?: number;
    flat_count?: number;
    winning_ratio?: number | null;
    profit_loss_ratio?: number | null;
  };
  account_risk: { max_open_risk_pct?: number | null; current_open_risk_pct?: number | null; thresholds: number[]; positions: Array<{ session_id: number; stock_name: string; risk_amount?: number | null; risk_usage_pct?: number | null }> };
  volatility_positioning: null;
  trades: ScenarioHabitTrade[];
};

export type ScenarioResponseDistribution = {
  unit?: "EPISODE";
  episode_count?: number;
  total: number;
  same_day_count?: number;
  within_1_2_count?: number;
  over_3_count?: number;
  unresolved_count?: number;
  max_unresolved_bars?: number;
  counts: { same_day: number; one_to_two: number; three_plus: number; held_or_unanswered: number };
  percentages: { same_day: number; one_to_two: number; three_plus: number; held_or_unanswered: number };
};

export type ScenarioReasonDistribution = { total: number; reason_recorded: number; reason_recording_rate?: number | null };

export type ScenarioExecutionReview = {
  scenario_id: number;
  has_scenario_data: boolean;
  overall_execution_rate?: number | null;
  category_scores: ScenarioCategoryScore[];
  timeline: Array<Record<string, unknown>>;
  reach_events: Array<Record<string, unknown>>;
  response_events: Array<Record<string, unknown>>;
  warning_events: Array<Record<string, unknown>>;
  revision_events: Array<Record<string, unknown>>;
  rule_based_summary: string;
};
export type RiskOrderPreviewRequest = {
  side: "BUY" | "SELL";
  price: number;
  quantity: number;
  risk_plan_step_id?: number | null;
};

export type RiskOrderWarning = {
  code: string;
  severity: "INFO" | "CAUTION" | "WARNING" | string;
  message: string;
};

export type RiskOrderPreview = {
  scenario_id: number;
  revision_id?: number | null;
  selected_step?: TradeTrainingRiskPlanStep | null;
  current_position: { quantity: number; average_price: number };
  projected_position: { quantity: number; average_price: number };
  stop_price?: number | null;
  risk_budget_amount?: number | null;
  current_estimated_risk?: number | null;
  projected_estimated_risk?: number | null;
  risk_usage_pct?: number | null;
  severity: "INFO" | "CAUTION" | "WARNING" | "UNAVAILABLE" | string;
  price_deviation_pct?: number | null;
  warnings: RiskOrderWarning[];
};

export type ActiveRiskSummary = {
  current_estimated_risk?: number | null;
  risk_usage_pct?: number | null;
  severity: "INFO" | "CAUTION" | "WARNING" | "UNAVAILABLE" | string;
  stop_price?: number | null;
};
export type TradeTrainingRiskScenarioRevisionListResponse = {
  items: TradeTrainingRiskScenarioRevision[];
};
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
  risk_plan_step_id?: number | null;
  unplanned_reason?: string | null;
  risk_warning_acknowledged?: boolean;
  risk_warning_acknowledgement_note?: string | null;
};

export type TrainingSession = {
  id: number;
  stock_code: string;
  stock_name: string | null;
  method_id?: number | null;
  training_account_id?: number | null;
  training_account_name?: string | null;
  is_account_linked?: boolean;
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
  risk_scenario_id?: number | null;
  risk_scenario_revision_id?: number | null;
  risk_plan_step_id?: number | null;
  created_at: string | null;
};

export type TrainingSessionDetail = {
  session: TrainingSession;
  trade_method?: TradeMethod | null;
  candles: TrainingCandle[];
  current_candle: TrainingCandle | null;
  account: TrainingAccount;
  trades: TrainingTrade[];
  risk_scenario?: TradeTrainingRiskScenarioDetail | null;
};

export type TechnicalAnalysisPeriod = "1M" | "3M" | "6M" | "1Y" | "ALL";

export type TechnicalAnalysisConfiguration = {
  short_window: number;
  medium_window: number;
  trend_window: number;
  channel_multiplier: number;
  minimum_break_persistence: number;
  reversal_persistence: number;
  swing_confirmation_width: number;
  minimum_trend_strength?: number;
  minimum_r_squared?: number;
};

export type TechnicalAnalysisPoint = { date: string; value: number };

export type TechnicalAnalysisPreview = {
  as_of_date: string;
  display_period: TechnicalAnalysisPeriod;
  display_start_date: string | null;
  display_end_date: string | null;
  display_observation_count: number;
  analysis_start_date: string | null;
  analysis_end_date: string | null;
  analysis_observation_count: number;
  applied_configuration: TechnicalAnalysisConfiguration;
  trend: Record<string, any>;
  moving_averages: {
    values?: Record<string, { value?: number | null; distance_pct?: number | null; slope_pct?: number | null }>;
    arrangement?: string;
    arrangement_label?: string;
    latest_cross?: { type: string; label: string; date: string } | null;
  };
  volume: Record<string, any>;
  price_position: Record<string, any>;
  current_candle: Record<string, any>;
  volatility: Record<string, any>;
  summary: {
    status_label?: string;
    compact_items?: string[];
    easy_explanation?: string;
    next_checks?: string[];
    current_candle_label?: string;
    volatility_label?: string;
  };
  overlay: {
    regression_points: TechnicalAnalysisPoint[];
    upper_channel_points: TechnicalAnalysisPoint[];
    lower_channel_points: TechnicalAnalysisPoint[];
    analysis_start_date?: string | null;
    current_point?: TechnicalAnalysisPoint | null;
  };
  performance: {
    cache_hit?: boolean;
    queried_row_count?: number;
    query_ms?: number;
    calculation_ms?: number;
    total_ms?: number;
  };
};

export type TechnicalAnalysisPreviewRequest = {
  training_session_id: number;
  stock_code?: string | null;
  as_of_date?: string | null;
  display_period: TechnicalAnalysisPeriod;
  configuration?: Partial<TechnicalAnalysisConfiguration>;
};

export type TrainingFinishResponse = {
  session: TrainingSession;
  account: TrainingAccount;
  message: string;
};

export type TrainingTradePair = {
  trade_sequence?: number | null;
  buy_date: string;
  sell_date: string;
  buy_price: number;
  sell_price: number;
  quantity: number;
  holding_days: number;
  profit_amount: number;
  profit_rate: number;
  gross_buy_amount?: number | null;
  equity_before?: number | null;
  equity_after?: number | null;
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

export type TrainingCalendarType = "ACCOUNT" | "STANDALONE";

export type TrainingCalendarItem = {
  calendar_item_id: string;
  training_type: TrainingCalendarType;
  completed_date: string;
  completed_at?: string | null;
  session_id: number;
  closed_trade_id?: string | null;
  training_account_id?: number | null;
  training_account_name?: string | null;
  stock_code?: string | null;
  stock_name: string;
  chart_entry_date?: string | null;
  chart_exit_date?: string | null;
  net_pnl: number;
  return_rate: number;
  result_type: "WIN" | "LOSS" | "FLAT";
  scenario_execution_rate?: number | null;
  review_status: string;
  review_done: boolean;
};

export type TrainingCalendarDay = {
  date: string;
  training_count: number;
  unique_stock_count: number;
  total_return_rate: number;
  avg_return_rate: number;
  win_count: number;
  loss_count: number;
  flat_count: number;
  review_saved_count: number;
  review_required_count: number;
  items: TrainingCalendarItem[];
};

export type TrainingCalendarGrowthPoint = {
  date: string;
  training_count: number;
  daily_return_rate: number;
  cumulative_return_rate: number;
};

export type TrainingCalendarSummary = {
  total_trainings: number;
  training_days: number;
  unique_stock_count: number;
  total_return_rate: number;
  avg_return_rate: number;
  review_completion_rate: number;
};

export type TrainingCalendarResponse = {
  month: string;
  summary: TrainingCalendarSummary;
  days: TrainingCalendarDay[];
  growth: TrainingCalendarGrowthPoint[];
};
