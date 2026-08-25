export type ThemeLinkOption = { id: number; group_name: string; theme_name: string; active: number; linked: boolean };
export type UsKrThemeLink = {
  id: number; us_theme_id: number; us_group_name: string; us_theme_name: string;
  kr_theme_id: number; kr_group_name: string; kr_theme_name: string;
  memo: string | null; active: number; created_at: string; updated_at: string;
};
export type UsKrThemeLinkSummary = {
  us_active_themes: number; kr_active_themes: number; linked_themes: number;
  unlinked_us_themes: number; unlinked_kr_themes: number;
};
export type UsKrThemeLinkOverview = { summary: UsKrThemeLinkSummary; links: UsKrThemeLink[]; us_themes: ThemeLinkOption[]; kr_themes: ThemeLinkOption[] };
export type UsKrThemeLinkInput = { us_theme_id: number; kr_theme_id: number; memo?: string | null };
export type UsKrLeadPair = {
  us_trade_date: string; us_value: number; kr_trade_date: string; kr_return: number;
  calendar_gap_days: number; direction_match: boolean | null;
};
export type UsKrLeadThreshold = {
  direction: "UP" | "DOWN"; condition: string; threshold: number; sample_count: number;
  response_rate: number | null; avg_kr_return: number | null; median_kr_return: number | null;
};
export type UsKrLeadMetrics = {
  candidate_count: number; sample_count: number; excluded_count: number; direction_sample_count: number;
  direction_match_rate: number | null; us_up_kr_up_rate: number | null; us_down_kr_down_rate: number | null;
  avg_kr_return: number | null; median_kr_return: number | null; pearson_correlation: number | null;
  spearman_correlation: number | null; regression_slope: number | null; regression_intercept: number | null;
  sample_guidance: string;
};
export type UsKrLeadAnalysis = {
  link: UsKrThemeLink; window: number | null; us_metric: "theme_strength" | "simple_return";
  us_metric_label: string; kr_metric_label: string; latest_us_date: string | null; latest_kr_date: string | null;
  max_calendar_gap_days: number; metrics: UsKrLeadMetrics; thresholds: UsKrLeadThreshold[]; pairs: UsKrLeadPair[];
};
export type UsKrTodayObservationItem = {
  rank: number; link_id: number; us_theme_id: number; us_group_name: string; us_theme_name: string;
  kr_theme_id: number; kr_group_name: string; kr_theme_name: string; available: boolean;
  latest_us_date: string | null; previous_us_date: string | null; kr_target_date: string | null;
  latest_value: number | null; previous_value: number | null; delta: number | null;
  breadth_ratio: number | null; valid_stock_count: number; up_count: number; down_count: number;
  threshold_direction: "UP" | "DOWN" | null; threshold_condition: string | null; threshold: number | null;
  sample_count: number; response_rate: number | null; avg_kr_return: number | null; median_kr_return: number | null;
  previous_kr_date: string | null; previous_kr_return: number | null;
  sample_guidance: string; missing_reason: string | null;
};
export type UsKrTodayObservation = {
  window: number | null; us_metric: "theme_strength" | "simple_return"; us_metric_label: string;
  latest_us_date: string | null; previous_us_date: string | null; kr_target_date: string | null;
  max_calendar_gap_days: number;
  summary: { linked_count: number; available_count: number; missing_count: number; up_count: number; down_count: number };
  items: UsKrTodayObservationItem[];
};
