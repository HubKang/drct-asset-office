from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MarkerReviewFilter = Literal["ALL", "S", "F", "UNDECIDED"]
MarkerPatternFeatureProfile = Literal["CORE", "ENRICHED"]


class MarkerLearningMarkerItem(BaseModel):
    marker_id: int
    marker_name: str
    marker_symbol: str
    marker_group_id: int
    marker_group_name: str
    marker_group_color: str
    event_count: int
    s_count: int
    f_count: int
    undecided_count: int
    learning_case_count: int = 0
    review_recommended_count: int = 0
    learning_status: Literal["INSUFFICIENT", "EARLY", "TESTABLE"] = "INSUFFICIENT"


class MarkerLearningCatalogResponse(BaseModel):
    items: list[MarkerLearningMarkerItem]


class MarkerLearningSummary(BaseModel):
    total_event_count: int
    d0_price_ready_count: int
    core_ready_count: int
    enriched_ready_count: int
    pattern_case_count: int
    quality_case_count: int
    review_counts: dict[str, int]
    outcome_coverage: dict[str, int]
    related_search_count: int
    latest_d0: str | None
    feature_schema_version: int
    elapsed_ms: int


class MarkerLearningReadinessResponse(BaseModel):
    marker: MarkerLearningMarkerItem
    summary: MarkerLearningSummary


class MarkerLearningCaseItem(BaseModel):
    chart_marker_event_id: int
    marker_id: int
    marker_name: str
    stock_id: int
    stock_code: str
    stock_name: str
    d0: str
    review_result: Literal["S", "F"] | None
    d0_price_ready: bool
    core_status: str
    enriched_status: str
    d20_return: float | None
    mfe_20: float | None
    mae_20: float | None
    learning_decision: Literal["INCLUDE", "EXCLUDE"] | None = None


class MarkerLearningCasesResponse(BaseModel):
    marker_id: int
    page: int
    page_size: int
    total: int
    items: list[MarkerLearningCaseItem]
    elapsed_ms: int


class MarkerLearningCaseDetailResponse(MarkerLearningCaseItem):
    feature_schema_version: int
    d0_price: dict[str, float | int | None] | None
    core_features: dict[str, float] | None
    enriched_features: dict[str, float] | None
    core_missing: list[str]
    enriched_missing: list[str]
    outcomes: dict[str, float | None]
    outcome_notice: str


class MarkerOutcomeMetric(BaseModel):
    mean: float | None
    median: float | None
    n: int


class MarkerLearningOutcomesResponse(BaseModel):
    marker_id: int
    quality_case_count: int
    labels: dict[str, int]
    outcomes: dict[str, dict[str, MarkerOutcomeMetric]]
    difference: dict[str, float | None]
    elapsed_ms: int


class MarkerRelatedSearchItem(BaseModel):
    search_id: int
    search_name: str
    lifecycle_status: str
    is_active: bool
    current_version_no: int
    rule_status: str


class MarkerRelatedSearchesResponse(BaseModel):
    marker_id: int
    items: list[MarkerRelatedSearchItem]
    notice: str


class MarkerPatternFeatureSignature(BaseModel):
    key: str
    label: str
    category: str
    unit: str
    median: float
    q1: float
    q3: float
    iqr: float
    mad: float
    min: float
    max: float
    valid_count: int
    robust_scale: float | None
    scale_method: Literal["IQR", "MAD", "NONE"]
    status: Literal["ACTIVE", "CONSTANT"]


class MarkerPatternSignatureResponse(BaseModel):
    marker: MarkerLearningMarkerItem
    feature_profile: MarkerPatternFeatureProfile
    feature_schema_version: int
    pattern_signature_version: int
    similarity_algorithm_version: int
    case_count: int
    status: Literal["INSUFFICIENT", "EXPERIMENTAL", "TESTABLE"]
    active_feature_count: int
    constant_feature_count: int
    features: list[MarkerPatternFeatureSignature]
    elapsed_ms: int
    dataset_elapsed_ms: int
    storage_policy: Literal["RUNTIME_ONLY"]


class MarkerSimilarityValidationRequest(BaseModel):
    feature_profile: MarkerPatternFeatureProfile = "CORE"


class MarkerSimilarityDistribution(BaseModel):
    min: float
    p10: float
    p25: float
    median: float
    p75: float
    p90: float
    max: float
    iqr: float


class MarkerSimilarityCase(BaseModel):
    chart_marker_event_id: int
    stock_id: int
    stock_code: str
    stock_name: str
    d0: str
    review_result: Literal["S", "F"] | None
    feature_profile: MarkerPatternFeatureProfile
    pattern_distance: float
    pattern_similarity: float
    usable_feature_count: int
    excluded_constant_feature_count: int


class MarkerSimilarityValidationResponse(BaseModel):
    marker: MarkerLearningMarkerItem
    feature_profile: MarkerPatternFeatureProfile
    feature_schema_version: int
    pattern_signature_version: int
    similarity_algorithm_version: int
    status: Literal["INSUFFICIENT", "EXPERIMENTAL", "TESTABLE"]
    evaluated_count: int
    distribution: MarkerSimilarityDistribution | None
    cases: list[MarkerSimilarityCase]
    elapsed_ms: int
    dataset_elapsed_ms: int
    storage_policy: Literal["RUNTIME_ONLY"]


class MarkerSimilarityFeatureDifference(BaseModel):
    key: str
    label: str
    unit: str
    case_value: float
    signature_median: float
    robust_distance: float
    raw_robust_distance: float


class MarkerSimilarityCaseDetailResponse(BaseModel):
    chart_marker_event_id: int
    marker: MarkerLearningMarkerItem
    stock_id: int
    stock_code: str
    stock_name: str
    d0: str
    review_result: Literal["S", "F"] | None
    feature_profile: MarkerPatternFeatureProfile
    pattern_distance: float
    pattern_similarity: float
    usable_feature_count: int
    excluded_constant_feature_count: int
    top_feature_differences: list[MarkerSimilarityFeatureDifference]
    storage_policy: Literal["RUNTIME_ONLY"]


class MarkerAutoLearningSummaryResponse(BaseModel):
    marker: MarkerLearningMarkerItem
    success_count: int
    learning_case_count: int
    manual_excluded_count: int
    data_incomplete_count: int
    review_recommended_count: int
    learning_status: Literal["INSUFFICIENT", "EARLY", "TESTABLE"]
    recommendation_readiness: Literal["INSUFFICIENT", "RESEARCH", "READY"]
    consistency_median: float | None
    consistency_p25: float | None
    consistency_p75: float | None
    latest_d0: str | None
    calculated_at: str
    pattern_algorithm_version: int


class MarkerLearningReviewCase(BaseModel):
    chart_marker_event_id: int
    marker_id: int
    marker_name: str
    stock_id: int
    stock_code: str
    stock_name: str
    d0: str
    review_result: Literal["S"]
    feature_profile: Literal["CORE"]
    pattern_distance: float
    pattern_similarity: float
    usable_feature_count: int
    excluded_constant_feature_count: int
    reason: str
    outlier_threshold: float
    learning_decision: None = None


class MarkerLearningReviewCasesResponse(BaseModel):
    marker_id: int
    total: int
    outlier_threshold: float | None
    items: list[MarkerLearningReviewCase]


class MarkerLearningReviewCaseDetail(MarkerLearningReviewCase):
    marker: MarkerLearningMarkerItem
    top_feature_differences: list[MarkerSimilarityFeatureDifference]
    storage_policy: Literal["RUNTIME_ONLY"]


class MarkerLearningDecisionPut(BaseModel):
    decision: Literal["INCLUDE", "EXCLUDE"]
    decision_reason: str | None = Field(default=None, max_length=120)


class MarkerLearningDecisionResponse(BaseModel):
    chart_marker_event_id: int
    decision: Literal["INCLUDE", "EXCLUDE"]
    decision_reason: str | None
    pattern_algorithm_version: int
    updated_at: str
