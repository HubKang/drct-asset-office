from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MarketSignalCondition(BaseModel):
    id: int | None = None
    signal_definition_id: int | None = None
    condition_group: str = "A"
    condition_role: str = "REQUIRED"
    item_type: str = "INDICATOR"
    item_code: str
    transform_type: str = "RAW_VALUE"
    window_size: int = 20
    comparison_operator: str = ">"
    threshold_type: str = "ABSOLUTE"
    threshold_value: float | None = None
    threshold_secondary: float | None = None
    weight: float = 10
    is_required: bool = False
    sort_order: int = 0


class MarketSignalDefinition(BaseModel):
    id: int | None = None
    signal_code: str
    signal_name: str
    description: str | None = None
    category: str | None = None
    signal_type: str = "COMPOSITE"
    horizon: str = "MEDIUM"
    status: str = "DRAFT"
    interpretation_direction: str = "MIXED"
    phenomenon_template: str | None = None
    process_template: str | None = None
    result_template: str | None = None
    persistence_periods: int = 1
    cooldown_periods: int = 0
    minimum_data_quality: float = 60
    current_version: int = 1
    conditions: list[MarketSignalCondition] = Field(default_factory=list)


class MarketSignalDefinitionListResponse(BaseModel):
    items: list[MarketSignalDefinition] = Field(default_factory=list)


class MarketSignalUpsertRequest(BaseModel):
    signal_code: str
    signal_name: str
    description: str | None = None
    category: str | None = None
    signal_type: str = "COMPOSITE"
    horizon: str = "MEDIUM"
    status: str = "DRAFT"
    interpretation_direction: str = "MIXED"
    phenomenon_template: str | None = None
    process_template: str | None = None
    result_template: str | None = None
    persistence_periods: int = 1
    cooldown_periods: int = 0
    minimum_data_quality: float = 60
    conditions: list[MarketSignalCondition] = Field(default_factory=list)
    change_reason: str | None = None


class MarketSignalEvaluation(BaseModel):
    id: int | None = None
    signal_definition_id: int
    signal_code: str | None = None
    signal_name: str | None = None
    evaluated_at: str | None = None
    observation_date: str
    state: str
    score: float
    previous_score: float | None = None
    data_quality_score: float
    required_pass_count: int = 0
    required_total_count: int = 0
    confirm_pass_count: int = 0
    opposing_pass_count: int = 0
    phenomenon_text: str | None = None
    process_text: str | None = None
    result_text: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    opposing_evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_data: list[dict[str, Any]] = Field(default_factory=list)


class MarketSignalEvaluateRequest(BaseModel):
    signal_ids: list[int] | None = None
    active_only: bool = True
    observation_date: str | None = None
    save: bool = True


class MarketSignalEvaluateResponse(BaseModel):
    items: list[MarketSignalEvaluation] = Field(default_factory=list)


class MarketSignalIndicatorCatalogItem(BaseModel):
    code: str
    name: str | None = None
    category: str | None = None
    frequency: str | None = None
    provider: str | None = None
    provider_symbol: str | None = None
    data_count: int = 0
    first_value_date: str | None = None
    latest_value_date: str | None = None
    latest_value: float | None = None
    readiness: str
    classification: str
    recommended_minimum_count: int = 0
    insufficient_count: int = 0
    available_simulation_years: float | None = None
    currently_used_signal_count: int = 0
    supported_transforms: list[str] = Field(default_factory=list)
    readiness_reason: str | None = None


class MarketSignalIndicatorCatalogResponse(BaseModel):
    items: list[MarketSignalIndicatorCatalogItem] = Field(default_factory=list)


class MarketSignalConditionPreviewRequest(BaseModel):
    condition: MarketSignalCondition
    observation_date: str | None = None


class MarketSignalConditionPreviewResponse(BaseModel):
    observation_date: str
    preview: dict[str, Any]
    series: list[dict[str, Any]] = Field(default_factory=list)


class MarketSignalEvent(BaseModel):
    id: int | None = None
    signal_definition_id: int
    signal_code: str | None = None
    signal_name: str | None = None
    event_date: str
    previous_state: str | None = None
    new_state: str
    previous_score: float | None = None
    new_score: float
    event_type: str
    summary: str | None = None
    created_at: str | None = None


class MarketSignalEventListResponse(BaseModel):
    items: list[MarketSignalEvent] = Field(default_factory=list)


class MarketSignalSimulationResponse(BaseModel):
    signal_id: int
    sample_count: int
    triggered_count: int
    occurrence_count: int = 0
    average_persistence: float | None = None
    median_persistence: float | None = None
    max_persistence: int = 0
    average_score: float | None = None
    median_score: float | None = None
    active_ratio: float | None = None
    data_insufficient_count: int = 0
    condition_pass_counts: dict[str, int] = Field(default_factory=dict)
    required_satisfaction_count: int = 0
    confirm_contribution_count: int = 0
    opposing_penalty_count: int = 0
    condition_contributions: list[dict[str, Any]] = Field(default_factory=list)
    variant_summaries: list[dict[str, Any]] = Field(default_factory=list)
    transition_points: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recent_samples: list[MarketSignalEvaluation] = Field(default_factory=list)


class MarketSignalGptDraftRequest(BaseModel):
    goal_text: str
    mode: str = "PROMPT_ONLY"
    gpt_result_json: dict[str, Any] | None = None


class MarketSignalGptDraftResponse(BaseModel):
    mode: str
    prompt: str
    validation_status: str
    validation_messages: list[str] = Field(default_factory=list)
    candidate: dict[str, Any] | None = None


class MarketSignalGenericListResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class MarketSignalGenericItemResponse(BaseModel):
    item: dict[str, Any] = Field(default_factory=dict)


class MarketSignalGenericActionRequest(BaseModel):
    observation_date: str | None = None
    save: bool = True
    years: int = 1
    payload: dict[str, Any] | None = None


class MarketSignalUserReviewRequest(BaseModel):
    signal_definition_id: int | None = None
    episode_id: int | None = None
    review_target_type: str = "PHENOMENON"
    review_target_id: int | None = None
    reviewer: str | None = None
    review_status: str = "PENDING"
    usefulness_score: float | None = None
    accuracy_score: float | None = None
    review_note: str | None = None
