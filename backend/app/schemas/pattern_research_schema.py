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


class PatternResearchRunSimulateResponse(BaseModel):
    summary: dict[str, Any]
    samples: list[dict[str, Any]] = Field(default_factory=list)
    gpt_package: dict[str, Any]
    parsed_goal: dict[str, Any]


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


class ScenarioGoal(BaseModel):
    trade_type: str = "swing"
    target_return_pct: float = 5
    holding_days: int = 5
    stop_loss_pct: float = -5
    min_sample_count: int = 50


class ScenarioRiskPlan(BaseModel):
    add_buy_enabled: bool = True
    max_add_buy_count: int = 1
    initial_amount: float = 1_000_000
    add_buy_trigger_loss_pct: float = -5
    final_stop_loss_basis: str = "average_price"
    final_stop_loss_pct: float = -5


class ScenarioValidationRequest(BaseModel):
    goal: ScenarioGoal
    risk_plan: ScenarioRiskPlan
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioValidationSummary(BaseModel):
    total_candidates: int = 0
    simulation_ready: int = 0
    needs_review: int = 0
    unsupported: int = 0
    risky: int = 0
    invalid: int = 0
    structure_error: int = 0
    auto_converted: int = 0


class ScenarioConditionValidationResult(BaseModel):
    section: str = ""
    indicator_key: str | None = None
    operator: str | None = None
    value: Any | None = None
    action: str | None = None
    status: str
    message: str
    original: Any | None = None


class ScenarioAddBuyValidationResult(BaseModel):
    status: str
    message: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ValidatedScenarioCandidate(BaseModel):
    candidate_index: int
    scenario_name: str
    status: str
    status_label: str
    is_simulation_ready: bool
    condition_results: list[ScenarioConditionValidationResult] = Field(default_factory=list)
    risk_filter_results: list[ScenarioConditionValidationResult] = Field(default_factory=list)
    add_buy_result: ScenarioAddBuyValidationResult | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    normalized_candidate: dict[str, Any] = Field(default_factory=dict)
    auto_converted_count: int = 0
    structure_error_count: int = 0


class ScenarioValidationResponse(BaseModel):
    summary: ScenarioValidationSummary
    validated_candidates: list[ValidatedScenarioCandidate] = Field(default_factory=list)


class ScenarioSimulationStock(BaseModel):
    stock_code: str
    stock_name: str | None = None


class ScenarioSimulationRequest(BaseModel):
    goal: ScenarioGoal
    risk_plan: ScenarioRiskPlan
    stocks: list[ScenarioSimulationStock] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioSimulationSummary(BaseModel):
    executed_scenarios: int = 0
    total_candidates: int = 0
    best_strategy_success_rate: float = 0
    best_efficiency_score: float = 0
    add_buy_effective_count: int = 0
    overfit_warning_count: int = 0


class ScenarioTradeSample(BaseModel):
    stock_code: str | None = None
    stock_name: str | None = None
    entry_date: str
    entry_price: float
    base_result: str
    strategy_result: str
    add_buy_count: int
    add_buy_price: float | None = None
    average_price: float | None = None
    capital_used: float
    max_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    exit_reason: str
    warnings: list[str] = Field(default_factory=list)


class ScenarioSimulationResult(BaseModel):
    scenario_index: int
    scenario_name: str
    scenario_type: str | None = None
    status: str
    judgement: str
    judgement_label: str
    candidate_count: int
    success_count: int
    failure_count: int
    neutral_count: int
    base_success_rate: float
    strategy_success_count: int
    strategy_failure_count: int
    strategy_neutral_count: int
    strategy_success_rate: float
    failure_rate: float
    recovery_count_after_add_buy: int
    recovery_rate_after_add_buy: float
    add_buy_trigger_count: int
    avg_add_buy_count: float
    avg_capital_used: float
    max_capital_used: float
    avg_max_return_pct: float
    avg_max_drawdown_pct: float
    efficiency_score: float
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    success_samples: list[ScenarioTradeSample] = Field(default_factory=list)
    failure_samples: list[ScenarioTradeSample] = Field(default_factory=list)
    add_buy_success_samples: list[ScenarioTradeSample] = Field(default_factory=list)
    add_buy_failure_samples: list[ScenarioTradeSample] = Field(default_factory=list)


class ScenarioSimulationResponse(BaseModel):
    summary: ScenarioSimulationSummary
    scenario_results: list[ScenarioSimulationResult] = Field(default_factory=list)
