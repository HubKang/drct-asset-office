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


class TrainingSessionCreate(BaseModel):
    stock_code: str
    method_id: int | None = None
    initial_cash: float = Field(default=50_000_000, gt=0)
    fee_rate: float = Field(default=0.001, ge=0, le=0.1)
    display_days: int = Field(default=80, ge=1, le=400)
    start_date: str | None = None
    end_date: str | None = None
    moving_averages: list[int] = Field(default_factory=lambda: [5, 20, 60])


class TrainingOrderRequest(BaseModel):
    price: float = Field(gt=0)
    quantity: int = Field(gt=0)
    reason: str | None = None
    method_review: dict | None = None


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
