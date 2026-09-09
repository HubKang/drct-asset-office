export type ThemeGate = "PASS" | "WATCH" | "NO_DATA";
export type FlowGate = "PASS" | "WATCH" | "WEAK" | "NO_DATA";
export type PatternGate = "PASS" | "WATCH" | "WEAK" | "NOT_READY";
export type ExecutionGate = "WAIT" | "READY" | "TRIGGERED" | "INVALID";
export type PatternStatus = "VERIFIED" | "PROMISING" | "WATCH" | "WEAK" | "NOT_READY";
export type CandidateLevel = "FINAL" | "PRELIMINARY" | "NONE";
export type IntradayState = "STRENGTHENING" | "STABLE" | "WEAKENING" | "WARNING";
export type MarketMode = "PRE_MARKET" | "INTRADAY" | "POST_MARKET";
export type OutcomeDirection = "UP" | "DOWN" | "FLAT" | "NOT_READY";
export type MarkerReviewStatus = "UNRECORDED" | "UNDECIDED" | "S" | "F";
export type ReadinessStatus = "READY" | "PARTIAL" | "NOT_READY" | "STALE" | "ERROR";

export type DrctInsightUsLead = {
  linked: boolean; link_id: number | null; us_theme_id: number | null; us_theme_name: string | null;
  metric: string | null; value: number | null; direction: "UP" | "DOWN" | "FLAT" | null;
  strength: "STRONG" | "MODERATE" | "WEAK" | null; breadth_ratio: number | null;
  relation_status: "AVAILABLE" | "MISSING"; response_rate: number | null; sample_count: number;
  source_date: string | null; kr_response_date: string | null;
};

export type InsightGates = {
  theme: ThemeGate;
  flow: FlowGate;
  pattern?: PatternGate | null;
  execution?: ExecutionGate | null;
};

export type DrctInsightTheme = {
  theme_id: number; theme_name: string; observation_rank: number | null;
  change_rate: number | null; theme_strength: number | null; flow_score: number | null; breadth: string | null;
  valid_stock_count: number; linked_stock_count: number;
  theme_score: number | null; theme_percentile: number | null; flow_percentile: number | null;
  us_catalyst: "STRONG" | "MODERATE" | "WEAK" | "NONE"; us_lead: DrctInsightUsLead;
  linked_candidate_count: number; preliminary_candidate_count: number; focus_candidate_count: number; final_candidate_count: number; gates: InsightGates;
  why_items: string[]; warning_items: string[];
};

export type DrctInsightStock = {
  stock_id: number; stock_code: string; stock_name: string; theme_id: number | null;
  theme_name: string | null; observation_rank: number | null; change_rate: number | null;
  theme_change_rate: number | null; theme_strength: number | null; relative_strength: number | null;
  theme_valid_stock_count: number; theme_linked_stock_count: number;
  marker_id: number; marker_name: string; candidate_band: string;
  success_similarity: number; failure_similarity: number | null; pattern_edge: number | null;
  success_sample_count: number; failure_sample_count: number; required_failure_sample_count: number;
  pattern_status: PatternStatus; candidate_level: CandidateLevel; preliminary_candidate: boolean;
  focus_candidate: boolean; focus_rank: number | null; final_candidate: boolean;
  us_lead: DrctInsightUsLead;
  convergence_level: number; gates: InsightGates; why_items: string[]; warning_items: string[];
  outcome: DrctInsightOutcome | null;
};

export type DrctInsightOutcome = {
  status: ReadinessStatus; analysis_date: string | null; close_price: number | null;
  d0_return: number | null; theme_d0_return: number | null; relative_return: number | null;
  direction: OutcomeDirection; marker_status: MarkerReviewStatus; marker_event_id: number | null;
};

export type DrctInsightReviewItem = {
  stock_id: number; stock_code: string; stock_name: string; theme_id: number | null; theme_name: string | null;
  focus_candidate: boolean; candidate_level: CandidateLevel; pattern_status: PatternStatus; success_similarity: number;
  user_status: ExecutionGate; priority: "HIGH" | "NORMAL";
  categories: Array<"STRONG" | "WEAK" | "MISMATCH" | "PATTERN" | "OUTCOME_MISSING">;
  reasons: string[]; outcome: DrctInsightOutcome;
};

export type DrctInsightWatchItem = DrctInsightStock & {
  watchlist_id: number; watch_status: string;
};

export type DrctInsightToday = {
  market_mode: MarketMode; analysis_date: string | null; evaluation_captured: boolean;
  summary: { observed_theme_count: number; preliminary_candidate_count: number; focus_candidate_count: number; final_candidate_count: number; my_watch_count: number; ready_count: number; last_updated_at: string | null };
  thresholds: { method: "RUNTIME_DISTRIBUTION"; flow_p25: number | null; flow_median: number | null; pattern_edge_p25: number | null; pattern_edge_median: number | null };
  freshness: Record<string, string | null>;
  readiness: {
    overall: ReadinessStatus;
    theme: { status: ReadinessStatus; source_date: string | null; note: string };
    flow: { status: ReadinessStatus; source_date: string | null; note: string };
    us_kr: { status: ReadinessStatus; source_date: string | null; note: string; linked_count: number; available_count: number; us_date: string | null; kr_date: string | null };
    pattern: { status: ReadinessStatus; source_date: string | null; note: string; success_marker_count: number; failure_marker_count: number; success_ready_marker_count: number; contrast_ready_marker_count: number; failure_shortage_marker_count: number; required_sample_count: number };
    realtime: { status: ReadinessStatus; source_date: string | null; note: string };
    outcome: { status: ReadinessStatus; source_date: string | null; note: string };
  };
  outcome_summary: { focus_count: number; available_count: number; positive_count: number; negative_count: number; average_d0_return: number | null; median_d0_return: number | null; theme_outperform_count: number; review_count: number; high_review_count: number; marker_recorded_count: number; not_ready_count: number };
  review_queue: DrctInsightReviewItem[];
  themes: DrctInsightTheme[]; stocks: DrctInsightStock[]; my_watch: DrctInsightWatchItem[];
  storage_policy: "RUNTIME_PLUS_COMPACT_CANDIDATE_HISTORY";
};

export type CandidateOutcomeStatus = "PENDING" | "PARTIAL" | "COMPLETE";
export type DrctInsightPerformanceMetric = { n: number; positive_ratio: number | null; mean: number | null; median: number | null };
export type DrctInsightPerformanceItem = {
  id: number; analysis_date: string; stock_id: number; stock_code: string; stock_name: string;
  theme_id: number | null; theme_name: string | null; candidate_level: "FOCUS" | "FINAL";
  focus_rank: number | null; observation_rank: number | null; success_similarity: number | null;
  failure_similarity: number | null; pattern_edge: number | null; user_status: string | null;
  theme_gate: string | null; flow_gate: string | null; pattern_status: string | null;
  us_lead_status: string | null; insight_rule_version: string | null;
  d0_return: number | null; d1_return: number | null; d3_return: number | null; d5_return: number | null;
  mfe_5d: number | null; mae_5d: number | null; outcome_status: CandidateOutcomeStatus;
  outcome_evaluated_at: string | null; marker_status: MarkerReviewStatus; marker_event_id: number | null;
};
export type DrctInsightPerformanceGroup = {
  key: string; label: string; n: number; sample_status: "ENOUGH" | "INSUFFICIENT" | "ACCUMULATING";
  d5: DrctInsightPerformanceMetric; mfe_5d: DrctInsightPerformanceMetric; mae_5d: DrctInsightPerformanceMetric;
};
export type DrctInsightPerformance = {
  page: number; page_size: number; total: number; total_pages: number; period: "20" | "60" | "120" | "ALL";
  items: DrctInsightPerformanceItem[]; themes: Array<{ id: number; name: string }>;
  summary: {
    total_count: number; pending_count: number; partial_count: number; complete_count: number;
    d0: DrctInsightPerformanceMetric; d1: DrctInsightPerformanceMetric; d3: DrctInsightPerformanceMetric;
    d5: DrctInsightPerformanceMetric; mfe_5d: DrctInsightPerformanceMetric; mae_5d: DrctInsightPerformanceMetric;
    marker_counts: Record<MarkerReviewStatus, number>;
  };
  groups: Record<string, DrctInsightPerformanceGroup[]>; latest_evaluated_at: string | null;
};
export type DrctInsightPerformanceFilters = {
  period: "20" | "60" | "120" | "ALL"; candidate_level?: "FOCUS" | "FINAL";
  theme_id?: number; pattern_status?: string; outcome_status?: CandidateOutcomeStatus;
  page: number; page_size: 20 | 50 | 100;
};
export type DrctInsightPerformanceRefresh = {
  target_count: number; updated_count: number; pending_count: number; partial_count: number;
  complete_count: number; evaluated_at: string;
};
