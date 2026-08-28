export type MarketSignalCondition = {
  id?: number | null;
  signal_definition_id?: number | null;
  condition_group: string;
  condition_role: "REQUIRED" | "TRIGGER" | "CONFIRM" | "CONTEXT" | "OPPOSING" | "INVALIDATION";
  display_role?: string;
  item_type: "INDEX" | "INDICATOR";
  item_code: string;
  transform_type: string;
  window_size: number;
  comparison_operator: string;
  threshold_type: string;
  threshold_value?: number | null;
  threshold_secondary?: number | null;
  weight: number;
  is_required: boolean;
  sort_order: number;
};

export type MarketSignalDefinition = {
  id: number;
  signal_code: string;
  signal_name: string;
  description?: string | null;
  category?: string | null;
  signal_type: "ATOMIC" | "SINGLE_INDICATOR" | "COMPOSITE" | "COMPOSITE_INDICATOR" | "PHENOMENON";
  horizon: "SHORT" | "MEDIUM" | "LONG";
  status: "DRAFT" | "ACTIVE" | "INACTIVE" | "ARCHIVED";
  interpretation_direction: string;
  phenomenon_template?: string | null;
  process_template?: string | null;
  result_template?: string | null;
  persistence_periods: number;
  cooldown_periods: number;
  minimum_data_quality: number;
  current_version: number;
  display_signal_level?: string | null;
  phenomenon_code?: string | null;
  relation_type?: string | null;
  confirmation_window?: number;
  minimum_confirm_count?: number;
  conditions: MarketSignalCondition[];
};

export type MarketSignalEvaluation = {
  id?: number | null;
  signal_definition_id: number;
  signal_code?: string | null;
  signal_name?: string | null;
  evaluated_at?: string | null;
  observation_date: string;
  state: string;
  score: number;
  previous_score?: number | null;
  data_quality_score: number;
  required_pass_count: number;
  required_total_count: number;
  confirm_pass_count: number;
  opposing_pass_count: number;
  phenomenon_text?: string | null;
  process_text?: string | null;
  result_text?: string | null;
  evidence: Record<string, unknown>[];
  opposing_evidence: Record<string, unknown>[];
  missing_data: Record<string, unknown>[];
};

export type MarketSignalOperationEvaluation = MarketSignalEvaluation & {
  trend_model_id?: number | null;
  evaluation_type: "BASELINE" | "PERIODIC" | "MANUAL" | "REPAIR_BASELINE" | "LEGACY";
  evaluation_type_display_name: string;
  rule_version: number;
  previous_state?: string | null;
  current_state: string;
  display_name: string;
  previous_display_name?: string | null;
  direction_state?: string | null;
  current_value?: number | null;
  trend_strength?: number | null;
  channel_position?: number | null;
  duration_count?: number | null;
  normalized_slope?: number | null;
  r_squared?: number | null;
  data_quality?: string | null;
  easy_explanation?: string | null;
  evaluation_reason?: string | null;
  collection_run_id?: number | null;
  is_state_transition: boolean;
  is_live: boolean;
  error_message?: string | null;
  event_id?: number | null;
  event_type?: string | null;
  event_summary?: string | null;
};

export type MarketSignalEvaluationHistory = {
  signal: { id: number; signal_code: string; signal_name: string; status: string; rule_version: number; display_name: string };
  operation_summary: { activated_at?: string | null; last_evaluated_at?: string | null; current_rule_version: number };
  live_statistics: {
    total_evaluation_count: number;
    transition_count: number;
    break_candidate_count: number;
    break_confirmed_count: number;
    false_break_count: number;
    reversal_confirmed_count: number;
    error_count: number;
  };
  validation_statistics: { period_years?: number | null; false_break_count: number; state_counts: Record<string, number> };
  baseline_status: { exists: boolean; evaluation_type?: string | null; observation_date?: string | null; repair_available: boolean };
  evaluations: MarketSignalOperationEvaluation[];
  chart: Record<string, unknown>[];
  pagination: { page: number; page_size: number; total: number; has_more: boolean };
};

export type MarketSignalEvent = {
  id: number;
  signal_definition_id: number;
  signal_code?: string | null;
  signal_name?: string | null;
  event_date: string;
  previous_state?: string | null;
  new_state: string;
  previous_score?: number | null;
  new_score: number;
  event_type: string;
  summary?: string | null;
  created_at?: string | null;
};

export type MarketSignalGptDraftResponse = {
  mode: string;
  prompt: string;
  validation_status: string;
  validation_messages: string[];
  candidate?: Record<string, unknown> | null;
};

export type MarketSignalIndicatorCatalogItem = {
  code: string;
  name?: string | null;
  category?: string | null;
  frequency?: string | null;
  provider?: string | null;
  provider_symbol?: string | null;
  data_count: number;
  first_value_date?: string | null;
  latest_value_date?: string | null;
  latest_value?: number | null;
  readiness: string;
  classification: string;
  recommended_minimum_count: number;
  insufficient_count: number;
  available_simulation_years?: number | null;
  currently_used_signal_count: number;
  supported_transforms: string[];
  readiness_reason?: string | null;
};

export type MarketSignalSimulationResponse = {
  signal_id: number;
  sample_count: number;
  triggered_count: number;
  occurrence_count: number;
  average_persistence?: number | null;
  median_persistence?: number | null;
  max_persistence: number;
  average_score?: number | null;
  median_score?: number | null;
  active_ratio?: number | null;
  data_insufficient_count: number;
  condition_pass_counts: Record<string, number>;
  required_satisfaction_count: number;
  confirm_contribution_count: number;
  opposing_penalty_count: number;
  condition_contributions: Record<string, unknown>[];
  variant_summaries: Record<string, unknown>[];
  transition_points: Record<string, unknown>[];
  warnings: string[];
  recent_samples: MarketSignalEvaluation[];
};

export type MarketSignalConditionPreviewResponse = {
  observation_date: string;
  preview: Record<string, unknown>;
  series: { date: string; value: number }[];
};

export type MarketSignalListResponse = { items: MarketSignalDefinition[] };
export type MarketSignalEvaluationResponse = { items: MarketSignalEvaluation[] };
export type MarketSignalEventListResponse = { items: MarketSignalEvent[] };
export type MarketSignalIndicatorCatalogResponse = { items: MarketSignalIndicatorCatalogItem[] };

export type MarketSignalGenericListResponse<T = Record<string, unknown>> = { items: T[] };
export type MarketSignalGenericItemResponse<T = Record<string, unknown>> = { item: T };

export type MarketSignalModelProfile = {
  profile_code: string;
  profile_name: string;
  description?: string | null;
  applicable_categories: string[];
  applicable_frequencies: string[];
  default_configuration: Record<string, unknown>;
  supported_transforms: string[];
  status: string;
};

export type MarketSignalCatalogItem = {
  item_type: "INDEX" | "INDICATOR";
  source_kind: "MARKET_INDEX" | "MARKET_INDICATOR" | "DERIVED_INDICATOR";
  item_code: string;
  item_name?: string | null;
  category?: string | null;
  category_group?: string | null;
  country?: string | null;
  provider?: string | null;
  frequency?: string | null;
  unit?: string | null;
  data_count: number;
  first_observation_date?: string | null;
  latest_observation_date?: string | null;
  latest_value?: number | null;
  readiness: string;
  signal_readiness: string;
  registered_signal_count: number;
  active_signal_count: number;
  trend_model_count: number;
  recommended_profile_code: string;
  recommended_profile_reason?: string | null;
  supported_transforms: string[];
  exclusion_reason?: string | null;
  sparkline?: Record<string, unknown>[];
};

export type MarketSignalCatalogResponse = {
  items: MarketSignalCatalogItem[];
  summary: Record<string, number>;
  total_count: number;
};

export type SingleIndicatorSignal = {
  id: number;
  signal_definition_id?: number | null;
  signal_level: "SINGLE_INDICATOR";
  model_profile_code?: string | null;
  user_label: string;
  item_type: "INDEX" | "INDICATOR";
  item_code: string;
  item_name?: string | null;
  category?: string | null;
  frequency?: string | null;
  unit_label?: string | null;
  provider?: string | null;
  rule_status: string;
  evaluation_status: string;
  trend_state: string;
  trend_strength?: number | null;
  latest_value?: number | null;
  latest_value_date?: string | null;
  diagnostic: Record<string, unknown>;
  series?: Record<string, unknown>[];
};

export type CompositeSignalItem = MarketSignalDefinition & {
  signal_level?: string;
  user_label?: string;
  evaluation?: MarketSignalEvaluation;
  relation_diagnostic?: Record<string, unknown>;
};

export type ObjectivePhenomenonItem = {
  id: number;
  phenomenon_code: string;
  source_composite_signal_id: number;
  source_rule_version: number;
  source_title: string;
  display_title: string;
  phenomenon_name: string;
  category?: string | null;
  tags: string[];
  description?: string | null;
  operation_grade: "OFFICIAL" | "REFERENCE";
  operation_grade_label: string;
  source_operation_status: string;
  source_operation_status_label: string;
  current_state: string;
  current_state_label: string;
  evaluation_status: string;
  phenomenon_score: number;
  easy_explanation: string;
  observation_date?: string | null;
  observed_evidence: Record<string, unknown>[];
  trigger_evidence: Record<string, unknown>[];
  confirm_evidence: Record<string, unknown>[];
  opposing_evidence: Record<string, unknown>[];
  missing_conditions: Record<string, unknown>[];
  invalidation_evidence: Record<string, unknown>[];
  next_checks: string[];
  evidence_count: number;
  opposing_count: number;
  missing_count: number;
  next_check_count: number;
  recent_change: string;
  is_flow_candidate: boolean;
  flow_candidate_status?: string | null;
  can_add_flow_candidate: boolean;
  user_note?: string | null;
  importance: string;
  user_confirmed_title: boolean;
  source_evaluation_id?: number | null;
};
export type MarketSignalRuleTemplate = {
  id: number;
  template_code: string;
  template_name: string;
  signal_level: string;
  category?: string | null;
  description?: string | null;
  difficulty: string;
  configuration: Record<string, unknown>;
  required_indicator_codes: string[];
  recommended_horizon: string;
  evidence_summary?: string | null;
  status: string;
  usage_count: number;
  copied_count: number;
  readiness_label: string;
  recent_3y_occurrence_count: number;
  evidence_grade: string;
};

export type MarketSignalCurrentEvaluationSummary = {
  evaluated_count: number;
  transition_count: number;
  unchanged_count: number;
  data_shortage_count: number;
  failed_count: number;
  evaluated_at?: string | null;
  status?: "COMPLETED" | "ALREADY_RUNNING";
  message?: string;
};

export type MarketSignalCurrentStateItem = {
  definition_id: number;
  signal_version_id: number;
  title?: string | null;
  signal_code?: string | null;
  signal_type?: string | null;
  category?: string | null;
  item_code?: string | null;
  current_state: string;
  stored_state: string;
  calculated_state?: string | null;
  evaluated_at?: string | null;
  effective_date?: string | null;
  evaluation_status: string;
  score?: number | null;
  required: { satisfied: number; total: number };
  confirm: { satisfied: number; total: number };
  opposing: { satisfied: number; total: number };
  conditions: Record<string, unknown>[];
  missing_indicators: Record<string, unknown>[];
  missing_reason?: string | null;
  error_message?: string | null;
  explanation?: string | null;
  from_state?: string | null;
  to_state?: string | null;
  last_transition_at?: string | null;
  current_state_changed?: boolean;
};

export type MarketSignalCurrentStatesResponse = {
  items: MarketSignalCurrentStateItem[];
  summary: Record<string, number>;
  last_evaluated_at?: string | null;
};

export type MarketSignalTodayTransitionsResponse = MarketSignalCurrentStatesResponse & {
  date: string;
};
export type MarketSignalOverview = {
  observation_date: string;
  summary: Record<string, number>;
  today_events: Record<string, unknown>[];
  single_indicator_signals: Record<string, unknown>[];
  composite_indicator_signals: Record<string, unknown>[];
  objective_phenomena: Record<string, unknown>[];
  templates: MarketSignalRuleTemplate[];
};
