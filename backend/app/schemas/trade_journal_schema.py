from __future__ import annotations

from pydantic import BaseModel, Field


class TradeMethodCreate(BaseModel):
    method_name: str = Field(min_length=1, max_length=120)
    core_concept: str | None = None
    description: str | None = None
    buy_condition: str | None = None
    sell_condition: str | None = None
    position_sizing_rule: str | None = None
    entry_rule: str | None = None
    exit_rule: str | None = None
    stop_loss_rule: str | None = None
    take_profit_rule: str | None = None
    checklist: str | None = None
    is_active: bool = True
    sort_order: int = 0


class TradeMethodUpdate(BaseModel):
    method_name: str | None = Field(default=None, min_length=1, max_length=120)
    core_concept: str | None = None
    description: str | None = None
    buy_condition: str | None = None
    sell_condition: str | None = None
    position_sizing_rule: str | None = None
    entry_rule: str | None = None
    exit_rule: str | None = None
    stop_loss_rule: str | None = None
    take_profit_rule: str | None = None
    checklist: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class TradeMethodResponse(BaseModel):
    id: int
    method_name: str
    core_concept: str | None
    description: str | None
    buy_condition: str | None
    sell_condition: str | None
    position_sizing_rule: str | None
    entry_rule: str | None
    exit_rule: str | None
    stop_loss_rule: str | None
    take_profit_rule: str | None
    checklist: str | None
    is_active: int
    sort_order: int
    created_at: str
    updated_at: str | None

    model_config = {"from_attributes": True}


class TradeJournalCreate(BaseModel):
    buy_date: str
    sell_date: str | None = None
    stock_code: str | None = None
    stock_name: str = Field(min_length=1, max_length=120)
    stock_theme: str | None = None
    trade_method_id: int | None = None
    trade_method_name: str | None = None
    result_type: str | None = None
    profit_rate: float | None = None
    realized_profit: int | None = None
    buy_price: float | None = None
    buy_quantity: int | None = None
    buy_amount: int | None = None
    sell_price: float | None = None
    sell_quantity: int | None = None
    sell_amount: int | None = None
    trade_reason: str | None = None
    success_reason: str | None = None
    failure_reason: str | None = None
    review_memo: str | None = None
    remark: str | None = None


class TradeJournalUpdate(BaseModel):
    buy_date: str | None = None
    sell_date: str | None = None
    stock_code: str | None = None
    stock_name: str | None = Field(default=None, min_length=1, max_length=120)
    stock_theme: str | None = None
    trade_method_id: int | None = None
    trade_method_name: str | None = None
    result_type: str | None = None
    profit_rate: float | None = None
    realized_profit: int | None = None
    buy_price: float | None = None
    buy_quantity: int | None = None
    buy_amount: int | None = None
    sell_price: float | None = None
    sell_quantity: int | None = None
    sell_amount: int | None = None
    trade_reason: str | None = None
    success_reason: str | None = None
    failure_reason: str | None = None
    review_memo: str | None = None
    remark: str | None = None


class TradeJournalListItem(BaseModel):
    id: int
    buy_date: str
    sell_date: str | None
    stock_theme: str | None
    trade_method_name: str | None
    stock_code: str | None
    stock_name: str
    result_type: str | None
    profit_rate: float | None
    realized_profit: int | None
    image_count: int
    remark: str | None


class TradeJournalDetailResponse(BaseModel):
    id: int
    buy_date: str
    sell_date: str | None
    stock_code: str | None
    stock_name: str
    stock_theme: str | None
    trade_method_id: int | None
    trade_method_name: str | None
    result_type: str | None
    profit_rate: float | None
    realized_profit: int | None
    buy_price: float | None
    buy_quantity: int | None
    buy_amount: int | None
    sell_price: float | None
    sell_quantity: int | None
    sell_amount: int | None
    trade_reason: str | None
    success_reason: str | None
    failure_reason: str | None
    review_memo: str | None
    remark: str | None
    created_at: str
    updated_at: str | None


class TradeJournalListResponse(BaseModel):
    items: list[TradeJournalListItem]
    total_count: int


class TradeJournalImageCreate(BaseModel):
    image_type: str = Field(min_length=1, max_length=40)
    image_path: str = Field(min_length=1, max_length=500)
    image_memo: str | None = None
    original_filename: str | None = None


class TradeJournalImageUpdate(BaseModel):
    image_memo: str | None = None
    image_type: str | None = Field(default=None, min_length=1, max_length=40)


class TradeJournalImageResponse(BaseModel):
    id: int
    trade_journal_id: int
    image_type: str
    image_path: str
    image_url: str | None = None
    image_memo: str | None
    original_filename: str | None
    created_at: str


class TradeMethodImageUpdate(BaseModel):
    image_memo: str | None = None
    image_type: str | None = Field(default=None, min_length=1, max_length=40)
    sort_order: int | None = None


class TradeMethodImageResponse(BaseModel):
    id: int
    trade_method_id: int
    image_type: str
    image_type_label: str
    image_path: str
    image_url: str | None = None
    image_memo: str | None
    original_filename: str | None
    sort_order: int
    created_at: str
    updated_at: str | None


class TradeJournalDeleteResponse(BaseModel):
    success: bool


class TradeJournalMonthlyCalendarItem(BaseModel):
    trade_date: str
    trade_count: int
    realized_profit_sum: int


class TradeJournalMonthlyStatisticItem(BaseModel):
    trade_month: str
    trade_count: int
    profit_count: int
    loss_count: int
    win_rate: float
    realized_profit_sum: int
    avg_profit_rate: float


class TradeJournalMonthlyStatisticResponse(BaseModel):
    items: list[TradeJournalMonthlyStatisticItem]
    total: int
    page: int
    page_size: int


class TradeJournalGptReviewPackageResponse(BaseModel):
    package_type: str
    trade_journal_id: int
    prompt_key: str
    prompt_text: str
    markdown: str
    json_data: dict


class TradeJournalMonthlyGptReviewPackageResponse(BaseModel):
    package_type: str
    year: int
    month: int
    period_label: str
    prompt_key: str
    prompt_text: str
    markdown: str
    json_data: dict


class TradeMethodGptGuidePackageResponse(BaseModel):
    package_type: str
    method_id: int
    prompt_key: str
    prompt_text: str
    markdown: str
    json_data: dict


class TradeJournalFailurePatternGptReviewPackageResponse(BaseModel):
    package_type: str
    prompt_key: str
    prompt_text: str
    from_date: str
    to_date: str
    markdown: str
    json_data: dict
