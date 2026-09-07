from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ThemeGate = Literal["PASS", "WATCH", "NO_DATA"]
FlowGate = Literal["PASS", "WATCH", "WEAK", "NO_DATA"]
PatternGate = Literal["PASS", "WATCH", "WEAK", "NOT_READY"]
ExecutionGate = Literal["WAIT", "READY", "TRIGGERED", "INVALID"]
PatternStatus = Literal["VERIFIED", "PROMISING", "WATCH", "WEAK", "NOT_READY"]
CandidateLevel = Literal["FINAL", "PRELIMINARY", "NONE"]
ReadinessStatus = Literal["READY", "PARTIAL", "NOT_READY", "STALE", "ERROR"]
MarketMode = Literal["PRE_MARKET", "INTRADAY", "POST_MARKET"]
OutcomeDirection = Literal["UP", "DOWN", "FLAT", "NOT_READY"]
MarkerReviewStatus = Literal["UNRECORDED", "UNDECIDED", "S", "F"]
ReviewPriority = Literal["HIGH", "NORMAL"]


class DrctInsightGateSet(BaseModel):
    theme: ThemeGate
    flow: FlowGate
    pattern: PatternGate | None = None
    execution: ExecutionGate | None = None


class DrctInsightThresholds(BaseModel):
    method: Literal["RUNTIME_DISTRIBUTION"] = "RUNTIME_DISTRIBUTION"
    flow_p25: float | None = None
    flow_median: float | None = None
    pattern_edge_p25: float | None = None
    pattern_edge_median: float | None = None


class DrctInsightUsLead(BaseModel):
    linked: bool = False
    link_id: int | None = None
    us_theme_id: int | None = None
    us_theme_name: str | None = None
    metric: str | None = None
    value: float | None = None
    direction: Literal["UP", "DOWN", "FLAT"] | None = None
    strength: Literal["STRONG", "MODERATE", "WEAK"] | None = None
    breadth_ratio: float | None = None
    relation_status: Literal["AVAILABLE", "MISSING"] = "MISSING"
    response_rate: float | None = None
    sample_count: int = 0
    source_date: str | None = None
    kr_response_date: str | None = None


class DrctInsightSourceReadiness(BaseModel):
    status: ReadinessStatus
    source_date: str | None = None
    note: str


class DrctInsightPatternReadiness(DrctInsightSourceReadiness):
    success_marker_count: int = 0
    failure_marker_count: int = 0
    success_ready_marker_count: int = 0
    contrast_ready_marker_count: int = 0
    failure_shortage_marker_count: int = 0
    required_sample_count: int = 5


class DrctInsightUsKrReadiness(DrctInsightSourceReadiness):
    linked_count: int = 0
    available_count: int = 0
    us_date: str | None = None
    kr_date: str | None = None


class DrctInsightReadiness(BaseModel):
    overall: ReadinessStatus
    theme: DrctInsightSourceReadiness
    flow: DrctInsightSourceReadiness
    us_kr: DrctInsightUsKrReadiness
    pattern: DrctInsightPatternReadiness
    realtime: DrctInsightSourceReadiness
    outcome: DrctInsightSourceReadiness


class DrctInsightOutcome(BaseModel):
    status: ReadinessStatus
    analysis_date: str | None = None
    close_price: float | None = None
    d0_return: float | None = None
    theme_d0_return: float | None = None
    relative_return: float | None = None
    direction: OutcomeDirection = "NOT_READY"
    marker_status: MarkerReviewStatus = "UNRECORDED"
    marker_event_id: int | None = None


class DrctInsightReviewItem(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    theme_id: int | None = None
    theme_name: str | None = None
    focus_candidate: bool = False
    candidate_level: CandidateLevel
    pattern_status: PatternStatus
    success_similarity: float
    user_status: ExecutionGate
    priority: ReviewPriority
    categories: list[Literal["STRONG", "WEAK", "MISMATCH", "PATTERN", "OUTCOME_MISSING"]] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    outcome: DrctInsightOutcome


class DrctInsightOutcomeSummary(BaseModel):
    focus_count: int = 0
    available_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    average_d0_return: float | None = None
    median_d0_return: float | None = None
    theme_outperform_count: int = 0
    review_count: int = 0
    high_review_count: int = 0
    marker_recorded_count: int = 0
    not_ready_count: int = 0


class DrctInsightTheme(BaseModel):
    theme_id: int
    theme_name: str
    observation_rank: int | None = None
    change_rate: float | None = None
    theme_strength: float | None = None
    valid_stock_count: int = 0
    linked_stock_count: int = 0
    flow_score: float | None = None
    theme_score: float | None = None
    theme_percentile: float | None = None
    flow_percentile: float | None = None
    us_catalyst: Literal["STRONG", "MODERATE", "WEAK", "NONE"] = "NONE"
    us_lead: DrctInsightUsLead
    breadth: str | None = None
    linked_candidate_count: int = 0
    preliminary_candidate_count: int = 0
    focus_candidate_count: int = 0
    final_candidate_count: int = 0
    gates: DrctInsightGateSet
    why_items: list[str] = Field(default_factory=list)
    warning_items: list[str] = Field(default_factory=list)


class DrctInsightStock(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    theme_id: int | None = None
    theme_name: str | None = None
    observation_rank: int | None = None
    change_rate: float | None = None
    theme_change_rate: float | None = None
    theme_strength: float | None = None
    theme_valid_stock_count: int = 0
    theme_linked_stock_count: int = 0
    relative_strength: float | None = None
    marker_id: int
    marker_name: str
    candidate_band: str
    success_similarity: float
    failure_similarity: float | None = None
    pattern_edge: float | None = None
    success_sample_count: int
    failure_sample_count: int
    required_failure_sample_count: int = 5
    pattern_status: PatternStatus
    candidate_level: CandidateLevel = "NONE"
    preliminary_candidate: bool = False
    focus_candidate: bool = False
    focus_rank: int | None = None
    final_candidate: bool = False
    us_lead: DrctInsightUsLead
    convergence_level: int = 0
    gates: DrctInsightGateSet
    why_items: list[str] = Field(default_factory=list)
    warning_items: list[str] = Field(default_factory=list)
    outcome: DrctInsightOutcome | None = None


class DrctInsightWatchItem(DrctInsightStock):
    watchlist_id: int
    watch_status: str


class DrctInsightSummary(BaseModel):
    observed_theme_count: int = 0
    final_candidate_count: int = 0
    preliminary_candidate_count: int = 0
    focus_candidate_count: int = 0
    my_watch_count: int = 0
    ready_count: int = 0
    last_updated_at: str | None = None


class DrctInsightTodayResponse(BaseModel):
    market_mode: MarketMode
    analysis_date: str | None = None
    evaluation_captured: bool = False
    summary: DrctInsightSummary
    thresholds: DrctInsightThresholds
    freshness: dict[str, str | None]
    readiness: DrctInsightReadiness
    themes: list[DrctInsightTheme] = Field(default_factory=list)
    stocks: list[DrctInsightStock] = Field(default_factory=list)
    my_watch: list[DrctInsightWatchItem] = Field(default_factory=list)
    outcome_summary: DrctInsightOutcomeSummary
    review_queue: list[DrctInsightReviewItem] = Field(default_factory=list)
    storage_policy: Literal["RUNTIME_PLUS_COMPACT_CANDIDATE_HISTORY"] = "RUNTIME_PLUS_COMPACT_CANDIDATE_HISTORY"
