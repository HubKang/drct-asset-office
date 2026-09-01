from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


FeatureProfile = Literal["CORE", "ENRICHED", "AUTO"]


class TrainingDatasetRequest(BaseModel):
    search_version_id: int | None = Field(default=None, gt=0)
    feature_profile: FeatureProfile = "AUTO"


class TrainingOutcomeLabelSummary(BaseModel):
    case_count: int
    d5_return: float | None
    d5_return_coverage: int
    d10_return: float | None
    d10_return_coverage: int
    d20_return: float | None
    d20_return_coverage: int
    mfe_20: float | None
    mfe_20_coverage: int
    mae_20: float | None
    mae_20_coverage: int


class TrainingDatasetSummary(BaseModel):
    readiness_status: str
    blocking_reasons: list[str]
    marker_link_count: int
    linked_event_count: int
    reviewed_event_count: int
    dedup_case_count: int
    label_conflict_count: int
    undecided_count: int
    rule_evaluable_count: int
    rule_matched_count: int
    rule_no_match_count: int
    rule_data_incomplete_count: int
    rule_match_rate: float | None
    core_ready_count: int
    enriched_ready_count: int
    core_data_incomplete_count: int
    enriched_data_incomplete_count: int
    success_count: int
    failure_count: int
    latest_d0: str | None
    outcome_coverage: dict[str, int]
    outcome_by_label: dict[str, TrainingOutcomeLabelSummary]


class TrainingReadinessResponse(BaseModel):
    search_id: int
    search_version_id: int
    version_no: int
    feature_schema_version: int
    rule_status: str
    elapsed_ms: int
    summary: TrainingDatasetSummary


class TrainingCaseItem(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    d0: str
    label: str
    matched_marker_names: list[str]
    rule_status: str
    core_status: str
    enriched_status: str
    d20_return: float | None
    mfe_20: float | None
    mae_20: float | None
    failed_conditions: list[dict[str, Any]] = Field(default_factory=list)


class TrainingCaseListResponse(BaseModel):
    search_id: int
    search_version_id: int
    page: int
    page_size: int
    total: int
    items: list[TrainingCaseItem]
    elapsed_ms: int


class TrainingCaseDetailResponse(TrainingCaseItem):
    source_marker_event_ids: list[int]
    rule_diagnostics: list[dict[str, Any]]
    feature_schema_version: int
    core_features: dict[str, float] | None
    enriched_features: dict[str, float] | None
    core_missing: list[str]
    enriched_missing: list[str]
    outcomes: dict[str, float | None]
    outcome_notice: str


class RuleMismatchConditionSummary(BaseModel):
    code: str
    label: str
    evaluated_count: int
    pass_count: int
    fail_count: int
    incomplete_count: int
    fail_rate: float | None


class RuleMismatchBranchSummary(BaseModel):
    expression: str
    label: str
    evaluated_count: int
    pass_count: int
    fail_count: int
    incomplete_count: int


class RuleMismatchSummaryResponse(BaseModel):
    search_id: int
    search_version_id: int
    version_no: int
    case_count: int
    conditions: list[RuleMismatchConditionSummary]
    branches: list[RuleMismatchBranchSummary]
    elapsed_ms: int


class BaselineEvaluateResponse(BaseModel):
    search_id: int
    search_version_id: int
    version_no: int
    feature_profile: Literal["CORE", "ENRICHED"]
    feature_schema_version: int
    prototype: dict[str, Any]
    logistic: dict[str, Any]
    elapsed_ms: int


class TrainingOverviewItem(BaseModel):
    search_id: int
    search_name: str
    search_version_id: int
    version_no: int
    rule_valid: bool
    marker_linked: bool
    dataset_ready: bool
    baseline_possible: bool
    research_status: str
    success_count: int
    failure_count: int


class TrainingOverviewResponse(BaseModel):
    registered_search_count: int
    rule_valid_count: int
    marker_linked_count: int
    dataset_ready_count: int
    baseline_possible_count: int
    items: list[TrainingOverviewItem]


class ValidationReportResponse(BaseModel):
    metadata: dict[str, Any]
    research_status: str
    checklist: dict[str, bool]
    readiness: TrainingDatasetSummary
    quality_gate: dict[str, Any]
    labels: dict[str, Any]
    outcomes: dict[str, Any]
    prototype: dict[str, Any]
    logistic: dict[str, Any]
    score_relationship: dict[str, Any]
    rule_mismatch_cases: list[dict[str, Any]]
    data_incomplete_cases: list[dict[str, Any]]
    model_disagreement_cases: list[dict[str, Any]]
    feature_distribution: list[dict[str, Any]]
    high_correlation_pairs: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    elapsed_ms: int
