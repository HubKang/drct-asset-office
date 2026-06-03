from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class BacktestRuleBase(BaseModel):
    rule_name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    trade_method_id: int | None = None
    buy_conditions_json: dict[str, Any]
    sell_conditions_json: dict[str, Any]
    position_rule_json: dict[str, Any]
    fee_rate: float = Field(default=0.00015, ge=0, le=0.1)
    slippage_rate: float = Field(default=0, ge=0, le=0.1)

    @model_validator(mode="after")
    def validate_rule_payload(self) -> "BacktestRuleBase":
        conditions = self.buy_conditions_json.get("conditions")
        if self.buy_conditions_json.get("operator", "AND") != "AND":
            raise ValueError("MVP에서는 AND 조건만 지원합니다.")
        if not isinstance(conditions, list) or not conditions:
            raise ValueError("매수조건을 1개 이상 선택해 주세요.")
        percent = float(self.position_rule_json.get("percent") or 0)
        if percent <= 0 or percent > 100:
            raise ValueError("진입비중은 0보다 크고 100 이하로 입력해 주세요.")
        return self


class BacktestRuleCreate(BacktestRuleBase):
    pass


class BacktestRuleUpdate(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    trade_method_id: int | None = None
    buy_conditions_json: dict[str, Any] | None = None
    sell_conditions_json: dict[str, Any] | None = None
    position_rule_json: dict[str, Any] | None = None
    fee_rate: float | None = Field(default=None, ge=0, le=0.1)
    slippage_rate: float | None = Field(default=None, ge=0, le=0.1)
    is_active: bool | None = None


class BacktestRuleResponse(BacktestRuleBase):
    id: int
    is_active: int
    created_at: str
    updated_at: str


class BacktestRuleListResponse(BaseModel):
    items: list[BacktestRuleResponse] = Field(default_factory=list)


class BacktestStockItem(BaseModel):
    stock_code: str
    stock_name: str
    market: str | None = None
    first_price_date: str | None = None
    last_price_date: str | None = None
    price_count: int
    source: str | None = None


class BacktestStockListResponse(BaseModel):
    items: list[BacktestStockItem] = Field(default_factory=list)
    keyword: str | None = None
    limit: int


class BacktestConditionField(BaseModel):
    field_key: str
    label: str
    source_table: str
    source_column: str
    data_type: str
    category: str
    is_active: bool
    sort_order: int


class BacktestConditionFieldListResponse(BaseModel):
    items: list[BacktestConditionField] = Field(default_factory=list)


class BacktestRunRequest(BaseModel):
    rule_id: int
    stock_code: str = Field(min_length=1, max_length=20)
    start_date: str | None = None
    end_date: str | None = None
    initial_cash: float = Field(default=10_000_000, gt=0)


class BacktestRunSummary(BaseModel):
    initial_cash: float
    final_asset: float
    total_profit: float
    total_return_rate: float
    max_drawdown: float
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    win_rate: float | None = None
    avg_profit_rate: float | None = None
    avg_loss_rate: float | None = None
    profit_factor: float | None = None
    avg_holding_days: float | None = None
    total_fee: float


class BacktestRunCreateResponse(BaseModel):
    run_id: int
    summary: BacktestRunSummary


class BacktestRunListItem(BaseModel):
    id: int
    rule_id: int
    rule_name: str | None = None
    stock_code: str
    stock_name: str | None = None
    start_date: str
    end_date: str
    initial_cash: float
    final_asset: float | None = None
    total_profit: float | None = None
    total_return_rate: float | None = None
    max_drawdown: float | None = None
    trade_count: int
    win_rate: float | None = None
    status: str
    message: str | None = None
    created_at: str


class BacktestRunListResponse(BaseModel):
    items: list[BacktestRunListItem] = Field(default_factory=list)


class BacktestTradeResponse(BaseModel):
    id: int
    run_id: int
    buy_date: str
    sell_date: str | None = None
    buy_price: float
    sell_price: float | None = None
    quantity: int
    buy_amount: float
    sell_amount: float | None = None
    fee: float
    profit: float | None = None
    profit_rate: float | None = None
    holding_days: int | None = None
    exit_reason: str | None = None
    buy_signal_json: dict[str, Any] | None = None
    sell_signal_json: dict[str, Any] | None = None
    created_at: str


class BacktestEquityPointResponse(BaseModel):
    id: int
    run_id: int
    trade_date: str
    cash: float
    position_qty: int
    position_value: float
    total_asset: float
    drawdown_rate: float
    created_at: str


class BacktestRunDetailResponse(BaseModel):
    run: BacktestRunListItem
    summary: BacktestRunSummary
    rule: BacktestRuleResponse | None = None
    trades: list[BacktestTradeResponse] = Field(default_factory=list)
    equity_curve: list[BacktestEquityPointResponse] = Field(default_factory=list)
