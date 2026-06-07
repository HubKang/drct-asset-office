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
