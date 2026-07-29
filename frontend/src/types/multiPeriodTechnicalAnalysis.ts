import type {
  TechnicalAnalysisConfiguration,
  TechnicalAnalysisPeriod,
  TechnicalAnalysisPoint,
  TechnicalAnalysisPreview,
} from "@/types/tradeTraining";

export type MultiPeriodTrendDirection = "UP_TREND" | "DOWN_TREND" | "SIDEWAYS" | "INSUFFICIENT";

export type MultiPeriodSummary = {
  period: TechnicalAnalysisPeriod;
  display_start_date: string | null;
  display_end_date: string | null;
  observation_count: number;
  minimum_observation_count: number;
  available: boolean;
  period_direction: string;
  period_direction_label: string;
  period_slope?: number | null;
  period_normalized_slope?: number | null;
  period_r_squared?: number | null;
  period_trend_strength?: number | null;
  period_channel_position?: number | null;
  period_channel_position_label?: string;
  current_trend_direction: MultiPeriodTrendDirection;
  current_trend_label: string;
  current_state: string;
  current_state_label: string;
  trend_start_date: string | null;
  persistence_count: number;
  trend_strength?: number | null;
  r_squared?: number | null;
  channel_position?: number | null;
  channel_position_label: string;
  model_label: string;
  sensitivity_label: string;
};

export type TrendTransitionEvent = {
  observation_date: string;
  previous_state: string;
  previous_state_label: string;
  current_state: string;
  current_state_label: string;
  direction: MultiPeriodTrendDirection;
  direction_label: string;
  reason: string;
  trend_strength?: number | null;
  channel_position?: number | null;
};

export type MultiPeriodChartCandle = {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  moving_averages: Record<string, number | null>;
};

export type MultiPeriodSelectedDetail = TechnicalAnalysisPreview & {
  period_summary: MultiPeriodSummary;
  period_direction: {
    direction: string;
    direction_label: string;
    slope?: number | null;
    normalized_slope?: number | null;
    r_squared?: number | null;
  };
  current_trend: {
    observation_date?: string;
    direction: MultiPeriodTrendDirection;
    direction_label: string;
    transition_state: string;
    state_label: string;
    trend_start_date: string | null;
    persistence_count: number;
    trend_strength?: number | null;
    r_squared?: number | null;
    channel_position?: number | null;
    channel_position_label: string;
  };
  trend_overlay: {
    regression_points: TechnicalAnalysisPoint[];
    upper_channel_points: TechnicalAnalysisPoint[];
    lower_channel_points: TechnicalAnalysisPoint[];
    trend_start_date?: string | null;
    trend_end_date?: string | null;
    current_point?: TechnicalAnalysisPoint | null;
  };
  period_overlay: {
    regression_points: TechnicalAnalysisPoint[];
    upper_channel_points: TechnicalAnalysisPoint[];
    lower_channel_points: TechnicalAnalysisPoint[];
    trend_start_date?: string | null;
    trend_end_date?: string | null;
    current_point?: TechnicalAnalysisPoint | null;
  };
  transition_events: TrendTransitionEvent[];
  chart_candles: MultiPeriodChartCandle[];
  easy_explanation: string;
  next_checks: string[];
};

export type MultiPeriodTechnicalAnalysis = {
  as_of_date: string;
  default_period: TechnicalAnalysisPeriod;
  selected_period: TechnicalAnalysisPeriod;
  applied_configuration: TechnicalAnalysisConfiguration;
  period_summaries: MultiPeriodSummary[];
  alignment: {
    short_direction: string;
    short_label: string;
    medium_direction: string;
    medium_label: string;
    long_direction: string;
    long_label: string;
    alignment_label: string;
    easy_explanation: string;
  };
  selected_period_detail: MultiPeriodSelectedDetail;
  performance: {
    cache_hit?: boolean;
    queried_row_count?: number;
    query_ms?: number;
    common_indicator_ms?: number;
    period_summary_ms?: number;
    trend_start_detection_ms?: number;
    selected_period_detail_ms?: number;
    calculation_ms?: number;
    total_ms?: number;
    payload_bytes?: number;
  };
};

export type MultiPeriodTechnicalAnalysisRequest = {
  training_session_id: number;
  stock_code?: string | null;
  as_of_date?: string | null;
  selected_period: TechnicalAnalysisPeriod;
  configuration?: Partial<TechnicalAnalysisConfiguration>;
};
