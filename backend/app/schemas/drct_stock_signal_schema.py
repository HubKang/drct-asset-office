from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


LifecycleStatus = Literal["REFERENCE", "LEARNING", "SHADOW", "ACTIVE", "INACTIVE"]


class DrctSignalSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    hts_reference_conditions: str = Field(min_length=1, max_length=30000)
    hts_condition_expression: str = Field(min_length=1, max_length=10000)
    change_note: str | None = Field(default=None, max_length=2000)


class DrctSignalSearchPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    lifecycle_status: LifecycleStatus | None = None
    display_order: int | None = Field(default=None, ge=0, le=999999)
    is_active: bool | None = None

    @model_validator(mode="after")
    def keep_inactive_status_consistent(self) -> "DrctSignalSearchPatch":
        if self.is_active is False and self.lifecycle_status not in (None, "INACTIVE"):
            raise ValueError("비활성 검색식의 상태는 INACTIVE여야 합니다.")
        return self


class DrctSignalVersionCreate(BaseModel):
    hts_reference_conditions: str = Field(min_length=1, max_length=30000)
    hts_condition_expression: str = Field(min_length=1, max_length=10000)
    drct_rule_text: str | None = Field(default=None, max_length=30000)
    change_note: str = Field(min_length=1, max_length=2000)


class DrctStructuredCondition(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    type: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    configured: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class DrctStructuredPredicate(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=300)
    configured: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class DrctStructuredConditionGroup(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    label: str | None = Field(default=None, max_length=300)
    source_text: str | None = Field(default=None, max_length=4000)
    join: Literal["AND", "OR"] = "AND"
    configured: bool = True
    predicates: list[DrctStructuredPredicate] = Field(default_factory=list, max_length=30)


class DrctStructuredRule(BaseModel):
    schema_version: Literal[1, 2] = 1
    conditions: list[DrctStructuredCondition | DrctStructuredConditionGroup] = Field(default_factory=list, max_length=100)
    expression: str = Field(default="", max_length=10000)


class DrctHtsImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=40000)
    expression: str | None = Field(default=None, max_length=10000)
    resolutions: dict[str, dict[str, str | int | float]] = Field(default_factory=dict)


class DrctHtsImportCondition(BaseModel):
    code: str
    title: str
    source_text: str
    status: Literal["AUTO_CONVERTED", "NEEDS_CONFIRMATION", "UNSUPPORTED", "INVALID_SOURCE"]
    status_label: str
    required: bool
    used_label: str
    human_description: str
    issue: str | None = None
    resolution_kind: Literal["RELATION", "PRICE_FIELD", "THRESHOLD"] | None = None
    resolution_options: list[dict[str, str]] = Field(default_factory=list)


class DrctHtsImportSummary(BaseModel):
    total: int
    auto_converted: int
    needs_confirmation: int
    unsupported: int
    invalid_source: int


class DrctHtsImportResponse(BaseModel):
    status: Literal["READY", "NEEDS_REVIEW", "INVALID"]
    status_label: str
    normalized_expression: str
    expression_korean: str
    conditions: list[DrctHtsImportCondition]
    summary: DrctHtsImportSummary
    rule: DrctStructuredRule | None = None


class DrctRuleValidationResponse(BaseModel):
    status: Literal["DRAFT", "VALID", "INVALID"]
    errors: list[dict[str, str]]
    required_lookback: int


class DrctRuleVersionCreate(BaseModel):
    rule: DrctStructuredRule
    change_note: str = Field(min_length=1, max_length=2000)
    hts_reference_conditions: str | None = Field(default=None, min_length=1, max_length=30000)
    hts_condition_expression: str | None = Field(default=None, min_length=1, max_length=10000)


class DrctRuleResponse(BaseModel):
    id: int
    search_version_id: int
    schema_version: int
    validation_status: Literal["DRAFT", "VALID", "INVALID"]
    rule: DrctStructuredRule
    validation_errors: list[dict[str, str]] = Field(default_factory=list)
    required_lookback: int = 0
    created_at: datetime | str


class DrctRulePreviewRequest(BaseModel):
    analysis_date: date | None = None
    include_all: bool = False


class DrctRuleDiagnoseRequest(BaseModel):
    stock_id: int = Field(gt=0)
    analysis_date: date | None = None


class DrctRulePreviewItem(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    theme_names: list[str]
    analysis_date: str
    close: float | None
    status: Literal["MATCH", "NO_MATCH", "DATA_INCOMPLETE"]


class DrctRulePreviewResponse(BaseModel):
    search_id: int
    search_version_id: int
    version_no: int
    analysis_date: str
    universe_count: int
    evaluable_count: int
    data_incomplete_count: int
    matched_count: int
    elapsed_ms: int
    items: list[DrctRulePreviewItem]


class DrctRuleConditionDiagnostic(BaseModel):
    code: str
    type: str
    label: str
    status: Literal["PASS", "FAIL", "DATA_INCOMPLETE"]
    criteria: str
    actual_value: str


class DrctRuleDiagnoseResponse(DrctRulePreviewItem):
    search_id: int
    search_version_id: int
    version_no: int
    elapsed_ms: int
    conditions: list[DrctRuleConditionDiagnostic]


class DrctSignalMarkerLinksPut(BaseModel):
    marker_definition_ids: list[int] = Field(default_factory=list, max_length=200)


class TrainingSummary(BaseModel):
    linked_marker_count: int
    total_case_count: int
    success_count: int
    failure_count: int
    undecided_count: int
    latest_case_date: str | None


class DrctSignalVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    search_id: int
    version_no: int
    hts_reference_conditions: str
    hts_condition_expression: str
    drct_rule_text: str | None
    change_note: str | None
    is_current: bool
    created_at: datetime | str
    structured_rule: DrctRuleResponse | None = None


class MarkerLinkResponse(BaseModel):
    id: int
    marker_definition_id: int
    marker_name: str
    marker_description: str | None
    marker_symbol: str
    marker_group_id: int
    marker_group_name: str
    group_color: str


class DrctSignalSearchListItem(BaseModel):
    id: int
    search_key: str
    name: str
    description: str | None
    lifecycle_status: LifecycleStatus
    display_order: int
    is_active: bool
    current_version_no: int
    training_summary: TrainingSummary
    created_at: datetime | str
    updated_at: datetime | str


class DrctSignalSearchDetail(DrctSignalSearchListItem):
    current_version: DrctSignalVersionResponse
    marker_links: list[MarkerLinkResponse]


class MarkerOption(BaseModel):
    id: int
    name: str
    description: str | None
    symbol: str
    is_active: bool


class MarkerOptionGroup(BaseModel):
    id: int
    name: str
    color: str
    markers: list[MarkerOption]


class MarkerOptionsResponse(BaseModel):
    items: list[MarkerOptionGroup]
