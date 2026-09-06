from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


CandidateBand = Literal["VERY_SIMILAR", "HIGH_SIMILARITY", "SIMILAR", "BELOW_CANDIDATE"]


class MarkerCurrentPatternScanRequest(BaseModel):
    analysis_date: date | None = None


class MarkerCurrentPatternAlgorithm(BaseModel):
    feature_schema_version: int
    pattern_signature_version: int
    similarity_algorithm_version: int
    candidate_policy_version: int


class MarkerCurrentPatternSignal(BaseModel):
    marker_id: int
    marker_name: str
    marker_symbol: str
    marker_group_id: int
    marker_group: str
    marker_group_color: str
    current_pattern_similarity: float
    candidate_band: CandidateBand
    empirical_percentile: float
    loo_p25: float
    loo_median: float
    loo_p75: float
    training_case_count: int


class MarkerCurrentPatternStock(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    theme_names: list[str]
    signals: list[MarkerCurrentPatternSignal]


class MarkerCurrentPatternMarkerSummary(BaseModel):
    marker_id: int
    marker_name: str
    training_case_count: int
    loo_p25: float
    loo_median: float
    loo_p75: float
    candidate_count: int


class MarkerPatternDistribution(BaseModel):
    min: float
    p10: float
    p25: float
    median: float
    p75: float
    p90: float
    max: float


class MarkerDiagnosticSample(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    theme_names: list[str]
    similarity: float
    empirical_percentile: float
    is_current_candidate: bool


class MarkerThresholdDiagnostic(BaseModel):
    value: float
    candidate_count: int
    candidate_ratio: float
    samples: list[MarkerDiagnosticSample]


class MarkerSegmentDiagnostic(BaseModel):
    count: int
    samples: list[MarkerDiagnosticSample]


class MarkerFriendlyReferenceLevel(BaseModel):
    level: Literal[25, 50, 75, 90]
    similarity_threshold: float
    candidate_count: int
    candidate_ratio: float


class MarkerShadowPolicyDiagnostic(BaseModel):
    status: Literal["VALIDATING"]
    candidate_count: int
    candidate_ratio: float
    similarity_threshold: float
    historical_reference_level: Literal[25]
    market_reference_level: Literal[90]
    policy_version: Literal["CANDIDATE_POLICY_SHADOW_V1"]
    samples: list[MarkerDiagnosticSample]


class MarkerFriendlyDiagnostic(BaseModel):
    current_candidate_count: int
    candidate_range_status: Literal["NARROW", "MODERATE", "BROAD", "VERY_BROAD"]
    discrimination_status: Literal["GOOD", "WEAK", "REVIEW"]
    interpretation_status: Literal["SELECTIVE", "BROAD_REDUCES_STRICT", "BROAD_STABLE", "HARD_TO_DISTINGUISH"]
    action_hint: Literal["KEEP_CURRENT_REVIEW", "REVIEW_STRICT_CHARTS", "REVIEW_STRICT_AND_FEATURES"]
    reference_levels: dict[str, MarkerFriendlyReferenceLevel]
    shadow: MarkerShadowPolicyDiagnostic


class MarkerDiscriminationDiagnostic(BaseModel):
    marker_id: int
    marker_name: str
    marker_symbol: str
    marker_group_id: int
    marker_group: str
    marker_group_color: str
    training_s_count: int
    loo_evaluated_count: int
    loo_distribution: MarkerPatternDistribution
    current_evaluable_count: int
    current_distribution: MarkerPatternDistribution
    median_gap: float
    p75_gap: float
    thresholds: dict[str, MarkerThresholdDiagnostic]
    segments: dict[str, MarkerSegmentDiagnostic]
    current_pair_contribution_ratio: float
    p90_sample_warning: str
    friendly: MarkerFriendlyDiagnostic


class ThresholdPolicyDiagnostic(BaseModel):
    candidate_pair_count: int
    candidate_stock_count: int
    multiple_marker_stock_count: int


class PatternDiscriminationDiagnostics(BaseModel):
    current_policy: Literal["P25"]
    baseline_policy_version: Literal["CANDIDATE_POLICY_BASELINE_V1"]
    shadow_policy: ThresholdPolicyDiagnostic
    shadow_policy_status: Literal["VALIDATING"]
    shadow_policy_version: Literal["CANDIDATE_POLICY_SHADOW_V1"]
    markers: list[MarkerDiscriminationDiagnostic]
    policies: dict[str, ThresholdPolicyDiagnostic]
    storage_policy: Literal["RUNTIME_ONLY"]


class MarkerPolicyValidationTarget(BaseModel):
    chart_marker_event_id: int
    stock_id: int
    stock_code: str
    stock_name: str
    d0: str
    prior_case_count: int
    validation_level: Literal["REFERENCE", "FORMAL"]
    target_in_universe: bool
    baseline_hit: bool
    improvement_hit: bool
    baseline_candidate_count: int
    improvement_candidate_count: int


class MarkerPolicyValidationTimings(BaseModel):
    total_ms: int
    sql_query_count: int
    evaluated_target_count: int
    cache_hit: bool


class MarkerPolicyValidationResponse(BaseModel):
    marker_id: int
    marker_name: str
    marker_symbol: str
    marker_group_id: int
    marker_group: str
    marker_group_color: str
    analysis_date: str
    training_s_count: int
    historical_valid_target_count: int
    formal_target_count: int
    baseline_hit_count: int
    improvement_hit_count: int
    baseline_average_candidate_count: float | None
    improvement_average_candidate_count: float | None
    candidate_reduction_percent: float | None
    automatic_improvement_status: Literal["NEED_MORE_DATA", "VALIDATING", "IMPROVEMENT_READY", "KEEP_CURRENT"]
    status_message: str
    baseline_policy_version: Literal["CANDIDATE_POLICY_BASELINE_V1"]
    improvement_policy_version: Literal["CANDIDATE_POLICY_SHADOW_V1"]
    minimum_prior_case_count: int
    formal_prior_case_count: int
    historical_universe_mode: Literal["CURRENT_ACTIVE_APPROXIMATION"]
    historical_universe_notice: str
    targets: list[MarkerPolicyValidationTarget]
    timings: MarkerPolicyValidationTimings
    storage_policy: Literal["RUNTIME_ONLY"]


class MarkerCurrentPatternTimings(BaseModel):
    universe_ms: int
    signature_ms: int
    feature_ms: int
    similarity_ms: int
    total_ms: int
    sql_query_count: int


class MarkerCurrentPatternSummaryResponse(BaseModel):
    analysis_date: str | None
    universe_count: int
    evaluable_stock_count: int
    incomplete_stock_count: int
    eligible_marker_count: int
    candidate_pair_count: int
    candidate_stock_count: int
    algorithm: MarkerCurrentPatternAlgorithm
    marker_summaries: list[MarkerCurrentPatternMarkerSummary]
    stocks: list[MarkerCurrentPatternStock]
    timings: MarkerCurrentPatternTimings
    storage_policy: Literal["RUNTIME_ONLY"]


class MarkerCurrentPatternScanResponse(BaseModel):
    analysis_date: str | None
    universe_count: int
    evaluable_stock_count: int
    incomplete_stock_count: int
    eligible_marker_count: int
    candidate_pair_count: int
    candidate_stock_count: int
    algorithm: MarkerCurrentPatternAlgorithm
    marker_summaries: list[MarkerCurrentPatternMarkerSummary]
    diagnostics: PatternDiscriminationDiagnostics
    stocks: list[MarkerCurrentPatternStock]
    timings: MarkerCurrentPatternTimings
    storage_policy: Literal["RUNTIME_ONLY"]


class MarkerCurrentPatternDifference(BaseModel):
    key: str
    label: str
    unit: str
    current_value: float
    signature_median: float
    robust_distance: float


class MarkerCurrentPatternDetailResponse(BaseModel):
    analysis_date: str
    stock_id: int
    stock_code: str
    stock_name: str
    theme_names: list[str]
    signal: MarkerCurrentPatternSignal
    top_feature_differences: list[MarkerCurrentPatternDifference]
    storage_policy: Literal["RUNTIME_ONLY"]
