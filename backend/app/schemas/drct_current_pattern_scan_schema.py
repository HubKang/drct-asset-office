from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


CandidateBand = Literal["VERY_SIMILAR", "HIGH_SIMILARITY", "SIMILAR"]


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


class MarkerCurrentPatternTimings(BaseModel):
    universe_ms: int
    signature_ms: int
    feature_ms: int
    similarity_ms: int
    total_ms: int
    sql_query_count: int


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
