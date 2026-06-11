import type { BacktestStock } from "@/types/backtest";

export type PatternResearchStock = BacktestStock & {
  stock_id?: number;
};

export type PatternGoalParseResponse = {
  parsed_goal: Record<string, any>;
  interpreted_items: Array<Record<string, any>>;
  entry_filters: Array<Record<string, any>>;
  exclude_filters: Array<Record<string, any>>;
  needs_review_items: Array<Record<string, any>>;
  unsupported_items: Array<Record<string, any>>;
  llm_assist?: Record<string, any> | null;
  warnings: string[];
};

export type PatternResearchRunRequest = {
  research_name?: string | null;
  stock_codes: string[];
  start_date: string;
  end_date: string;
  goal_text: string;
  parsed_goal: Record<string, any>;
};

export type PatternResearchRunCreateResponse = {
  run_id: number;
  summary: Record<string, any>;
};

export type PatternResearchRunSimulateResponse = {
  summary: Record<string, any>;
  samples: PatternResearchSample[];
  gpt_package: PatternResearchGptPackage;
  parsed_goal: Record<string, any>;
};

export type PatternResearchRun = {
  id: number;
  research_name?: string | null;
  stock_codes: string[];
  start_date: string;
  end_date: string;
  goal_text?: string | null;
  parsed_goal?: Record<string, any> | null;
  target_return_pct?: number | null;
  target_days?: number | null;
  stop_loss_pct?: number | null;
  max_holding_days?: number | null;
  summary?: Record<string, any> | null;
  gpt_prompt_text?: string | null;
  gpt_response_text?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type PatternResearchSample = {
  id: number;
  run_id: number;
  stock_code: string;
  stock_name?: string | null;
  trade_date: string;
  entry_price?: number | null;
  max_future_return_pct?: number | null;
  min_future_return_pct?: number | null;
  future_return_pct?: number | null;
  target_hit: number;
  stop_hit: number;
  result_label: "SUCCESS" | "FAILURE" | "NEUTRAL" | string;
  features: Record<string, any>;
  pattern_tags: string[];
  created_at: string;
};

export type PatternResearchGptPackage = {
  gpt_prompt_text: string;
  summary: Record<string, any>;
  sample_counts: Record<string, number>;
};

export type PatternResearchStockListResponse = {
  items: PatternResearchStock[];
  keyword?: string | null;
  limit: number;
};

export type PatternGptGoalParsePromptResponse = {
  prompt_text: string;
  sentence_splits: string[];
};

export type PatternValidationMessage = {
  source_text?: string;
  message: string;
};

export type PatternInterpretationConflict = {
  source_text?: string;
  drct_first_pass?: string;
  gpt_correction?: string;
  suggested_indicator_key?: string;
};

export type PatternGptGoalResultValidateResponse = {
  status: string;
  validated_conditions: Array<Record<string, any>>;
  new_indicator_candidates: Array<Record<string, any>>;
  unsupported_items: PatternValidationMessage[];
  warnings: PatternValidationMessage[];
  interpretation_conflicts?: PatternInterpretationConflict[];
  raw_error: string;
  validation_message?: string;
  parsed_json: Record<string, any>;
};

export type ScenarioValidationStatus =
  | "simulation_ready"
  | "needs_review"
  | "unsupported"
  | "risky"
  | "invalid";

export type ScenarioConditionValidationStatus =
  | "valid"
  | "auto_converted"
  | "unsupported_indicator"
  | "unsupported_operator"
  | "unsupported_action"
  | "invalid_value"
  | "invalid_structure"
  | "missing_field"
  | "needs_review";

export type ScenarioValidationRequest = {
  goal: {
    trade_type: string;
    target_return_pct: number;
    holding_days: number;
    stop_loss_pct: number;
    min_sample_count: number;
  };
  risk_plan: {
    add_buy_enabled: boolean;
    max_add_buy_count: number;
    initial_amount: number;
    add_buy_trigger_loss_pct: number;
    final_stop_loss_basis: string;
    final_stop_loss_pct: number;
  };
  candidates: Array<Record<string, any>>;
};

export type ScenarioValidationSummary = {
  total_candidates: number;
  simulation_ready: number;
  needs_review: number;
  unsupported: number;
  risky: number;
  invalid?: number;
  structure_error?: number;
  auto_converted?: number;
};

export type ScenarioConditionValidationResult = {
  section: string;
  indicator_key?: string | null;
  operator?: string | null;
  value?: unknown;
  action?: string | null;
  status: ScenarioConditionValidationStatus | string;
  message: string;
  original?: unknown;
};

export type ValidatedScenarioCandidate = {
  candidate_index: number;
  scenario_name: string;
  status: ScenarioValidationStatus;
  status_label: string;
  is_simulation_ready: boolean;
  condition_results: ScenarioConditionValidationResult[];
  risk_filter_results: ScenarioConditionValidationResult[];
  add_buy_result?: {
    status: string;
    message: string;
    warnings: string[];
    errors?: string[];
  } | null;
  warnings: string[];
  errors: string[];
  normalized_candidate: Record<string, any>;
  auto_converted_count?: number;
  structure_error_count?: number;
};

export type ScenarioValidationResponse = {
  summary: ScenarioValidationSummary;
  validated_candidates: ValidatedScenarioCandidate[];
};

export type ScenarioSimulationRequest = {
  goal: ScenarioValidationRequest["goal"];
  risk_plan: ScenarioValidationRequest["risk_plan"];
  stocks: Array<{
    stock_code: string;
    stock_name?: string | null;
  }>;
  candidates: Array<Record<string, any>>;
};

export type ScenarioSimulationSummary = {
  executed_scenarios: number;
  total_candidates: number;
  best_strategy_success_rate: number;
  best_efficiency_score: number;
  add_buy_effective_count: number;
  overfit_warning_count: number;
};

export type ScenarioSimulationJudgement =
  | "promising"
  | "review"
  | "overfit_warning"
  | "capital_risk"
  | "weak"
  | "no_sample"
  | "error";

export type ScenarioTradeSample = {
  stock_code?: string | null;
  stock_name?: string | null;
  entry_date: string;
  entry_price: number;
  base_result: string;
  strategy_result: string;
  add_buy_count: number;
  add_buy_price?: number | null;
  average_price?: number | null;
  capital_used: number;
  max_return_pct?: number | null;
  max_drawdown_pct?: number | null;
  exit_reason: string;
  warnings?: string[];
};

export type ScenarioSimulationResult = {
  scenario_index: number;
  scenario_name: string;
  scenario_type?: string | null;
  status: string;
  judgement: ScenarioSimulationJudgement;
  judgement_label: string;
  candidate_count: number;
  success_count: number;
  failure_count: number;
  neutral_count: number;
  base_success_rate: number;
  strategy_success_count: number;
  strategy_failure_count: number;
  strategy_neutral_count: number;
  strategy_success_rate: number;
  failure_rate: number;
  recovery_count_after_add_buy: number;
  recovery_rate_after_add_buy: number;
  add_buy_trigger_count: number;
  avg_add_buy_count: number;
  avg_capital_used: number;
  max_capital_used: number;
  avg_max_return_pct: number;
  avg_max_drawdown_pct: number;
  efficiency_score: number;
  warnings: string[];
  errors?: string[];
  success_samples: ScenarioTradeSample[];
  failure_samples: ScenarioTradeSample[];
  add_buy_success_samples?: ScenarioTradeSample[];
  add_buy_failure_samples?: ScenarioTradeSample[];
};

export type ScenarioSimulationResponse = {
  summary: ScenarioSimulationSummary;
  scenario_results: ScenarioSimulationResult[];
};
