from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.schemas.trade_journal_schema import TradeMethodResponse


class TrainingStockItem(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    market: str | None = None
    price_count: int
    first_date: str | None = None
    last_date: str | None = None
    source: str | None = None


class TrainingStockListResponse(BaseModel):
    items: list[TrainingStockItem] = Field(default_factory=list)
    limit: int


class TradeTrainingAccountBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    initial_capital: float = Field(gt=0)
    commission_rate: float = Field(default=0.001, ge=0, le=1)
    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=100)
    max_open_risk_pct: float = Field(default=3.0, gt=0, le=100)
    max_position_count: int = Field(default=5, ge=1)
    display_days_default: int = Field(default=80, ge=1, le=400)
    moving_average_periods_default: list[int] = Field(default_factory=lambda: [5, 10, 20, 60, 120])


class TradeTrainingAccountCreate(TradeTrainingAccountBase):
    pass


class TradeTrainingAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    status: str | None = None
    initial_capital: float | None = Field(default=None, gt=0)
    cash_balance: float | None = Field(default=None, ge=0)
    realized_equity: float | None = Field(default=None, ge=0)
    commission_rate: float | None = Field(default=None, ge=0, le=1)
    risk_per_trade_pct: float | None = Field(default=None, gt=0, le=100)
    max_open_risk_pct: float | None = Field(default=None, gt=0, le=100)
    max_position_count: int | None = Field(default=None, ge=1)
    display_days_default: int | None = Field(default=None, ge=1, le=400)
    moving_average_periods_default: list[int] | None = None


class TradeTrainingAccountResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: str
    initial_capital: float
    cash_balance: float
    realized_equity: float
    commission_rate: float
    risk_per_trade_pct: float
    max_open_risk_pct: float
    max_position_count: int
    display_days_default: int
    moving_average_periods_default: list[int] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None


class TradeTrainingAccountListResponse(BaseModel):
    items: list[TradeTrainingAccountResponse] = Field(default_factory=list)


class TradeTrainingAccountSummaryResponse(BaseModel):
    account_id: int
    initial_capital: float
    cash_balance: float
    training_equity: float
    current_training_equity: float | None = None
    open_position_cost: float = 0
    open_position_market_value: float = 0
    realized_pnl: float
    unrealized_pnl: float = 0
    cumulative_realized_return_pct: float | None = None
    current_equity_return_pct: float | None = None
    active_session_count: int = 0
    open_position_count: int = 0
    closed_trade_count: int = 0
    winning_ratio: float | None = None
    profit_loss_ratio: float | None = None
    profit_loss_ratio_status: str = "NO_CLOSED_TRADES"
    winning_trade_count: int = 0
    losing_trade_count: int = 0
    flat_trade_count: int = 0
    average_profit: float | None = None
    average_loss: float | None = None


class TradeTrainingAccountDeleteResponse(BaseModel):
    deleted: bool
    account_id: int
    session_count: int = 0
    trade_count: int = 0
    snapshot_count: int = 0
    review_count: int = 0
    message: str


class TradeTrainingAccountRebuildRequest(BaseModel):
    apply_changes: bool = False


class TradeTrainingAccountRebuildResponse(BaseModel):
    account_id: int
    account_name: str | None = None
    initial_capital: float
    session_count: int = 0
    trade_event_count: int = 0
    closed_trade_count: int = 0
    open_position_count: int = 0
    stored_cash_balance: float
    calculated_cash_balance: float
    cash_difference: float
    stored_realized_equity: float
    calculated_realized_equity: float
    realized_equity_difference: float
    calculated_realized_pnl: float
    open_position_market_value: float = 0
    unrealized_pnl: float = 0
    current_training_equity: float
    ledger_event_count_before: int = 0
    ledger_event_count_after: int = 0
    cash_identity_difference: float = 0
    equity_identity_difference: float = 0
    performance_identity_difference: float = 0
    is_consistent_before: bool = False
    is_consistent_after: bool = False
    applied: bool = False
    warnings: list[str] = Field(default_factory=list)


class TradeTrainingAccountSessionResponse(BaseModel):
    id: int
    session_id: int | None = None
    training_account_id: int
    stock_id: int | None = None
    market: str | None = None
    stock_code: str
    stock_name: str | None = None
    status: str
    status_state: str | None = None
    status_display: str | None = None
    start_date: str
    end_date: str
    chart_start_date: str | None = None
    chart_end_date: str | None = None
    current_date: str | None = None
    chart_current_date: str | None = None
    current_index: int
    current_step: int | None = None
    display_days: int | None = None
    moving_averages: list[int] = Field(default_factory=list)
    position_qty: int
    position_quantity: int | None = None
    avg_price: float
    average_entry_price: float | None = None
    current_price: float | None = None
    market_value: float | None = None
    position_cost: float | None = None
    unrealized_pnl: float | None = None
    unrealized_return_pct: float | None = None
    realized_profit: float
    trade_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    last_trained_at: str | None = None


class TradeTrainingAccountSessionListResponse(BaseModel):
    items: list[TradeTrainingAccountSessionResponse] = Field(default_factory=list)


class TradeTrainingClosedTradeResponse(BaseModel):
    id: str
    closed_trade_id: str | None = None
    trade_sequence: int
    training_account_id: int
    training_session_id: int
    simulation_session_id: int | None = None
    stock_id: int | None = None
    stock_code: str
    stock_name: str | None = None
    opened_chart_date: str
    closed_chart_date: str
    chart_entry_date: str | None = None
    chart_exit_date: str | None = None
    completed_at: str | None = None
    gross_buy_amount: float
    gross_sell_amount: float
    gross_pnl: float | None = None
    commission_amount: float
    tax_amount: float = 0
    net_pnl: float
    return_pct: float
    holding_bars: int
    result_type: str
    quantity: int
    actual_quantity: int | None = None
    avg_buy_price: float
    avg_sell_price: float
    average_entry_price: float | None = None
    average_exit_price: float | None = None
    planned_risk_pct: float | None = None
    planned_risk_amount: float | None = None
    realized_r: float | None = None
    atr_value: float | None = None
    atr_pct: float | None = None
    recommended_quantity: int | None = None


class TradeTrainingClosedTradeListResponse(BaseModel):
    items: list[TradeTrainingClosedTradeResponse] = Field(default_factory=list)


class TradeTrainingPerformancePoint(BaseModel):
    closed_trade_id: str | None = None
    trade_sequence: int
    simulation_session_id: int | None = None
    training_session_id: int | None = None
    training_account_id: int | None = None
    stock_id: int | None = None
    stock_code: str
    stock_name: str | None = None
    chart_entry_date: str | None = None
    chart_exit_date: str | None = None
    completed_at: str | None = None
    quantity: int | None = None
    average_entry_price: float | None = None
    average_exit_price: float | None = None
    gross_buy_amount: float | None = None
    gross_sell_amount: float | None = None
    gross_pnl: float | None = None
    commission_amount: float | None = None
    tax_amount: float | None = None
    net_pnl: float
    return_pct: float
    holding_bars: int | None = None
    equity_before: float | None = None
    equity_after: float
    cumulative_return_pct: float | None = None
    planned_risk_pct: float | None = None
    planned_risk_amount: float | None = None
    realized_r: float | None = None
    atr_value: float | None = None
    atr_pct: float | None = None
    recommended_quantity: int | None = None
    actual_quantity: int | None = None


class TradeTrainingAccountPerformanceResponse(BaseModel):
    account_id: int | None = None
    initial_capital: float
    current_realized_equity: float | None = None
    cumulative_return_pct: float | None = None
    closed_trade_count: int = 0
    winning_ratio: float | None = None
    profit_loss_ratio: float | None = None
    profit_loss_ratio_status: str = "NO_CLOSED_TRADES"
    winning_trade_count: int = 0
    losing_trade_count: int = 0
    flat_trade_count: int = 0
    average_profit: float | None = None
    average_loss: float | None = None
    items: list[TradeTrainingPerformancePoint] = Field(default_factory=list)


class TrainingSessionCreate(BaseModel):
    stock_code: str
    method_id: int | None = None
    initial_cash: float = Field(default=50_000_000, gt=0)
    fee_rate: float = Field(default=0.001, ge=0, le=0.1)
    display_days: int = Field(default=80, ge=1, le=400)
    start_date: str | None = None
    end_date: str | None = None
    moving_averages: list[int] = Field(default_factory=lambda: [5, 20, 60])
    training_account_id: int | None = None


class TrainingOrderRequest(BaseModel):
    price: float = Field(gt=0)
    quantity: int = Field(gt=0)
    reason: str | None = None
    method_review: dict | None = None
    client_order_id: str | None = None


class TrainingSessionResponse(BaseModel):
    id: int
    stock_code: str
    stock_name: str | None = None
    method_id: int | None = None
    start_date: str
    end_date: str
    current_date: str | None = None
    current_index: int
    initial_cash: float
    cash: float
    position_qty: int
    avg_price: float
    realized_profit: float
    status: str
    options: dict = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class TrainingCandle(BaseModel):
    trade_date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    trading_value: int | None = None
    moving_averages: dict[str, float | None] = Field(default_factory=dict)


class TrainingAccountResponse(BaseModel):
    current_price: float
    evaluation_amount: float
    cash_balance: float | None = None
    open_position_cost: float | None = None
    open_position_market_value: float | None = None
    current_training_equity: float | None = None
    unrealized_profit: float
    unrealized_return_rate: float
    position_profit: float
    position_return_rate: float
    realized_profit: float
    total_asset: float
    total_profit: float
    total_return_rate: float


class TrainingTradeResponse(BaseModel):
    id: int
    session_id: int
    trade_date: str
    side: str
    price: float
    quantity: int
    fee: float
    amount: float
    realized_profit: float
    reason: str | None = None
    method_review: dict | None = None
    created_at: str | None = None


class TrainingSessionDetailResponse(BaseModel):
    session: TrainingSessionResponse
    trade_method: TradeMethodResponse | None = None
    candles: list[TrainingCandle] = Field(default_factory=list)
    current_candle: TrainingCandle | None = None
    account: TrainingAccountResponse
    trades: list[TrainingTradeResponse] = Field(default_factory=list)


class TrainingFinishResponse(BaseModel):
    session: TrainingSessionResponse
    account: TrainingAccountResponse
    message: str


class TrainingTradePairResponse(BaseModel):
    buy_date: str
    sell_date: str
    buy_price: float
    sell_price: float
    quantity: int
    holding_days: int
    profit_amount: float
    profit_rate: float
    buy_reason: str | None = None
    sell_reason: str | None = None
    buy_reason_quality: str | None = None
    sell_reason_quality: str | None = None
    buy_reason_quality_guide: str | None = None
    sell_reason_quality_guide: str | None = None
    buy_method_review: dict | None = None
    sell_method_review: dict | None = None


class TrainingOpenPositionResponse(BaseModel):
    position_qty: int
    avg_price: float
    evaluation_amount: float
    unrealized_profit: float
    unrealized_return_rate: float


class TrainingEquityCurvePoint(BaseModel):
    trade_date: str
    total_asset: float
    cash: float
    evaluation_amount: float


class TrainingResultResponse(BaseModel):
    session_id: int
    stock_code: str
    stock_name: str | None = None
    start_date: str
    end_date: str
    current_date: str | None = None
    status: str
    initial_cash: float
    final_cash: float
    final_evaluation_amount: float
    final_total_asset: float
    total_profit: float
    total_return_rate: float
    trade_count: int
    buy_count: int
    sell_count: int
    round_trip_count: int
    winning_trade_count: int
    losing_trade_count: int
    break_even_trade_count: int
    win_rate: float | None = None
    average_profit_rate: float | None = None
    average_loss_rate: float | None = None
    max_profit_amount: float | None = None
    max_loss_amount: float | None = None
    average_holding_days: float | None = None
    total_fees: float
    buy_reason_fill_rate: float | None = None
    sell_reason_fill_rate: float | None = None
    buy_reason_quality_summary: dict[str, int] = Field(default_factory=dict)
    sell_reason_quality_summary: dict[str, int] = Field(default_factory=dict)
    weak_buy_reason_count: int = 0
    weak_sell_reason_count: int = 0
    method_review_stats: dict = Field(default_factory=dict)
    trade_pairs: list[TrainingTradePairResponse] = Field(default_factory=list)
    open_position: TrainingOpenPositionResponse
    equity_curve: list[TrainingEquityCurvePoint] = Field(default_factory=list)


class TrainingGptPackageResponse(BaseModel):
    session_id: int
    stock_code: str
    stock_name: str | None = None
    package_title: str
    generated_prompt: str
    sections: dict[str, str] = Field(default_factory=dict)


class SimulationReviewResponse(BaseModel):
    session_id: int
    review_status: str = "미복기"
    self_review_text: str = ""
    gpt_prompt_text: str = ""
    gpt_review_text: str = ""
    improvement_point: str = ""
    next_training_goal: str = ""
    main_mistake: str = ""
    discipline_score: int | None = None
    reviewed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SimulationReviewSaveRequest(BaseModel):
    review_status: str = "미복기"
    self_review_text: str | None = None
    gpt_prompt_text: str | None = None
    gpt_review_text: str | None = None
    improvement_point: str | None = None
    next_training_goal: str | None = None
    main_mistake: str | None = None
    discipline_score: int | None = Field(default=None, ge=0, le=100)


class TrainingCalendarStock(BaseModel):
    stock_code: str | None = None
    stock_name: str
    training_count: int
    total_return_rate: float
    avg_return_rate: float
    review_saved_count: int


class TrainingCalendarMethodGroup(BaseModel):
    trade_method_id: int | None = None
    trade_method_name: str
    training_count: int
    total_return_rate: float
    avg_return_rate: float
    review_saved_count: int
    stocks: list[TrainingCalendarStock] = Field(default_factory=list)


class TrainingCalendarDay(BaseModel):
    date: str
    training_count: int
    total_return_rate: float
    avg_return_rate: float
    training_score: int
    review_saved_count: int
    review_required_count: int
    method_groups: list[TrainingCalendarMethodGroup] = Field(default_factory=list)


class TrainingCalendarSummary(BaseModel):
    total_sessions: int
    training_days: int
    avg_training_score: int
    avg_return_rate: float
    review_completion_rate: float


class TrainingCalendarResponse(BaseModel):
    month: str
    summary: TrainingCalendarSummary
    days: list[TrainingCalendarDay] = Field(default_factory=list)
