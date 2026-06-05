from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalysisIndicatorBase(BaseModel):
    indicator_key: str | None = None
    indicator_name: str | None = None
    description: str | None = None
    source_type: str | None = None
    source_table: str | None = None
    source_column: str | None = None
    calculation_formula: str | None = None
    calculation_type: str | None = None
    parameters_json: str | None = None
    required_columns_json: str | None = None
    data_type: str | None = None
    unit: str | None = None
    category: str | None = None
    allowed_operators_json: str | None = None
    default_operator: str | None = None
    default_value_json: str | None = None
    example_expressions: str | None = None
    is_available_for_rule: int | None = None
    is_available_for_llm: int | None = None
    is_entry_allowed: int | None = None
    is_success_allowed: int | None = None
    is_failure_allowed: int | None = None
    needs_review_default: int | None = None
    execution_supported: int | None = None
    execution_status: str | None = None
    execution_message: str | None = None
    is_active: int | None = None
    sort_order: int | None = None


class AnalysisIndicatorCreate(AnalysisIndicatorBase):
    indicator_key: str = Field(min_length=1)
    indicator_name: str = Field(min_length=1)
    source_type: str = Field(min_length=1)


class AnalysisIndicatorUpdate(AnalysisIndicatorBase):
    pass


class AnalysisIndicatorItem(AnalysisIndicatorBase):
    id: int
    indicator_key: str
    indicator_name: str
    source_type: str
    created_at: str
    updated_at: str


class AnalysisIndicatorListResponse(BaseModel):
    items: list[AnalysisIndicatorItem] = Field(default_factory=list)


class AnalysisIndicatorAliasBase(BaseModel):
    alias_text: str | None = None
    indicator_key: str | None = None
    alias_type: str | None = None
    match_type: str | None = None
    default_operator: str | None = None
    default_value_json: str | None = None
    default_category: str | None = None
    apply_to_samples_default: int | None = None
    needs_review: int | None = None
    confidence: float | None = None
    description: str | None = None
    is_active: int | None = None
    sort_order: int | None = None


class AnalysisIndicatorAliasCreate(AnalysisIndicatorAliasBase):
    alias_text: str = Field(min_length=1)
    indicator_key: str = Field(min_length=1)


class AnalysisIndicatorAliasUpdate(AnalysisIndicatorAliasBase):
    pass


class AnalysisIndicatorAliasItem(AnalysisIndicatorAliasBase):
    id: int
    alias_text: str
    indicator_key: str
    created_at: str
    updated_at: str


class AnalysisIndicatorAliasListResponse(BaseModel):
    items: list[AnalysisIndicatorAliasItem] = Field(default_factory=list)


class AnalysisConditionTemplateBase(BaseModel):
    template_key: str | None = None
    template_name: str | None = None
    description: str | None = None
    template_type: str | None = None
    condition_json: str | None = None
    default_apply_to_samples: int | None = None
    needs_review: int | None = None
    is_available_for_llm: int | None = None
    is_active: int | None = None
    sort_order: int | None = None


class AnalysisConditionTemplateCreate(AnalysisConditionTemplateBase):
    template_key: str = Field(min_length=1)
    template_name: str = Field(min_length=1)
    condition_json: str = Field(min_length=1)


class AnalysisConditionTemplateUpdate(AnalysisConditionTemplateBase):
    pass


class AnalysisConditionTemplateItem(AnalysisConditionTemplateBase):
    id: int
    template_key: str
    template_name: str
    condition_json: str
    created_at: str
    updated_at: str


class AnalysisConditionTemplateListResponse(BaseModel):
    items: list[AnalysisConditionTemplateItem] = Field(default_factory=list)


class AnalysisLlmCatalogResponse(BaseModel):
    indicators: list[dict[str, Any]] = Field(default_factory=list)
    aliases: list[dict[str, Any]] = Field(default_factory=list)
    condition_templates: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisIndicatorCandidateBase(BaseModel):
    source_type: str | None = None
    source_text: str | None = None
    suggested_indicator_key: str | None = None
    suggested_indicator_name: str | None = None
    description: str | None = None
    calculation_type: str | None = None
    formula_description: str | None = None
    parameters_json: str | None = None
    required_indicators_json: str | None = None
    usage_json: str | None = None
    lookahead_risk: int | None = None
    validation_status: str | None = None
    validation_message: str | None = None
    execution_supported: int | None = None
    execution_status: str | None = None
    execution_message: str | None = None
    decision_status: str | None = None
    decision_note: str | None = None
    linked_indicator_id: int | None = None
    origin_research_run_id: int | None = None
    is_active: int | None = None


class AnalysisIndicatorCandidateCreate(AnalysisIndicatorCandidateBase):
    suggested_indicator_key: str = Field(min_length=1)


class AnalysisIndicatorCandidateUpdate(AnalysisIndicatorCandidateBase):
    pass


class AnalysisIndicatorCandidateItem(AnalysisIndicatorCandidateBase):
    id: int
    suggested_indicator_key: str
    created_at: str
    updated_at: str


class AnalysisIndicatorCandidateListResponse(BaseModel):
    items: list[AnalysisIndicatorCandidateItem] = Field(default_factory=list)
