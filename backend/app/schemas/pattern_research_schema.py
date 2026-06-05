from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PatternIndicatorItem(BaseModel):
    indicator_key: str
    indicator_name: str
    description: str
    source_type: str
    source_table: str | None = None
    source_column: str | None = None
    calculation_type: str
    data_type: str
    unit: str | None = None
    category: str
    status: str


class PatternIndicatorListResponse(BaseModel):
    items: list[PatternIndicatorItem] = Field(default_factory=list)


class PatternGoalParseRequest(BaseModel):
    goal_text: str = Field(min_length=1)
    use_llm: bool = False
    llm_mode: str | None = "assist"


class PatternGoalParseResponse(BaseModel):
    parsed_goal: dict[str, Any]
    interpreted_items: list[dict[str, Any]] = Field(default_factory=list)
    entry_filters: list[dict[str, Any]] = Field(default_factory=list)
    exclude_filters: list[dict[str, Any]] = Field(default_factory=list)
    needs_review_items: list[dict[str, Any]] = Field(default_factory=list)
    unsupported_items: list[dict[str, Any]] = Field(default_factory=list)
    llm_assist: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class PatternResearchRunRequest(BaseModel):
    research_name: str | None = None
    stock_codes: list[str] = Field(min_length=1)
    start_date: str
    end_date: str
    goal_text: str = Field(min_length=1)
    parsed_goal: dict[str, Any]


class PatternResearchRunCreateResponse(BaseModel):
    run_id: int
    summary: dict[str, Any]


class PatternResearchRunListItem(BaseModel):
    id: int
    research_name: str | None = None
    stock_codes: list[str]
    start_date: str
    end_date: str
    goal_text: str | None = None
    target_return_pct: float | None = None
    target_days: int | None = None
    stop_loss_pct: float | None = None
    max_holding_days: int | None = None
    summary: dict[str, Any] | None = None
    status: str
    created_at: str
    updated_at: str


class PatternResearchRunListResponse(BaseModel):
    items: list[PatternResearchRunListItem] = Field(default_factory=list)


class PatternResearchRunDetailResponse(PatternResearchRunListItem):
    parsed_goal: dict[str, Any] | None = None
    gpt_prompt_text: str | None = None
    gpt_response_text: str | None = None


class PatternResearchSampleResponse(BaseModel):
    id: int
    run_id: int
    stock_code: str
    stock_name: str | None = None
    trade_date: str
    entry_price: float | None = None
    max_future_return_pct: float | None = None
    min_future_return_pct: float | None = None
    future_return_pct: float | None = None
    target_hit: int
    stop_hit: int
    result_label: str
    features: dict[str, Any] = Field(default_factory=dict)
    pattern_tags: list[str] = Field(default_factory=list)
    created_at: str


class PatternResearchSampleListResponse(BaseModel):
    items: list[PatternResearchSampleResponse] = Field(default_factory=list)


class PatternResearchGptPackageResponse(BaseModel):
    gpt_prompt_text: str
    summary: dict[str, Any]
    sample_counts: dict[str, int]


class PatternGptGoalParsePromptRequest(BaseModel):
    goal_text: str = Field(min_length=1)
    parsed_goal: dict[str, Any] | None = None


class PatternGptGoalParsePromptResponse(BaseModel):
    prompt_text: str
    sentence_splits: list[str] = Field(default_factory=list)


class PatternGptGoalResultValidateRequest(BaseModel):
    goal_text: str = Field(min_length=1)
    gpt_result_text: str = Field(min_length=1)
    parsed_goal: dict[str, Any] | None = None


class PatternValidationMessage(BaseModel):
    source_text: str = ""
    message: str = ""


class PatternInterpretationConflict(BaseModel):
    source_text: str = ""
    drct_first_pass: str = ""
    gpt_correction: str = ""
    suggested_indicator_key: str = ""


class PatternGptGoalResultValidateResponse(BaseModel):
    status: str
    validated_conditions: list[dict[str, Any]] = Field(default_factory=list)
    new_indicator_candidates: list[dict[str, Any]] = Field(default_factory=list)
    unsupported_items: list[PatternValidationMessage] = Field(default_factory=list)
    warnings: list[PatternValidationMessage] = Field(default_factory=list)
    interpretation_conflicts: list[PatternInterpretationConflict] = Field(default_factory=list)
    raw_error: str = ""
    validation_message: str = ""
    parsed_json: dict[str, Any] = Field(default_factory=dict)
