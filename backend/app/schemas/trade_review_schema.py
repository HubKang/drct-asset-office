from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.trade_journal_schema import TradeJournalDetailResponse, TradeMethodResponse


class TradeReviewSaveRequest(BaseModel):
    review_status: str | None = None
    trade_grade: str | None = None
    principle_followed: str | None = None
    entry_quality: str | None = None
    exit_quality: str | None = None
    risk_control_quality: str | None = None
    emotion_control_quality: str | None = None
    impulse_trade: bool | int | None = None
    main_mistake: str | None = None
    good_point: str | None = None
    improvement_point: str | None = None
    next_action: str | None = None
    review_memo: str | None = None
    gpt_review_text: str | None = None
    check_items: list["TradeReviewCheckItemSaveRequest"] | None = None


class TradeReviewCheckItemSaveRequest(BaseModel):
    id: int
    is_checked: bool | int | None = None
    note: str | None = None


class TradeReviewCheckItemResponse(BaseModel):
    id: int
    review_id: int
    journal_id: int
    method_id: int | None = None
    item_type: str
    item_order: int
    item_text: str
    is_checked: int = 0
    note: str | None = None
    source_field: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class TradeReviewResponse(BaseModel):
    id: int | None = None
    journal_id: int
    method_id: int | None = None
    review_status: str = "미복기"
    trade_grade: str | None = None
    principle_followed: str | None = None
    entry_quality: str | None = None
    exit_quality: str | None = None
    risk_control_quality: str | None = None
    emotion_control_quality: str | None = None
    impulse_trade: int = 0
    main_mistake: str | None = None
    good_point: str | None = None
    improvement_point: str | None = None
    next_action: str | None = None
    review_memo: str | None = None
    gpt_review_text: str | None = None
    reviewed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class TradeReviewListItem(BaseModel):
    journal_id: int
    review_id: int | None = None
    stock_name: str
    stock_code: str | None = None
    buy_date: str
    sell_date: str | None = None
    method_id: int | None = None
    method_name: str | None = None
    result_type: str | None = None
    profit_rate: float | None = None
    realized_profit: int | None = None
    image_count: int = 0
    review_status: str = "미복기"
    trade_grade: str | None = None
    principle_followed: str | None = None
    main_mistake: str | None = None
    impulse_trade: int = 0


class TradeReviewListResponse(BaseModel):
    items: list[TradeReviewListItem]
    total_count: int


class TradeReviewDetailResponse(BaseModel):
    journal: TradeJournalDetailResponse
    method: TradeMethodResponse | None = None
    review: TradeReviewResponse
    check_items: list[TradeReviewCheckItemResponse] = []
    image_count: int = 0


class TradeReviewSummaryResponse(BaseModel):
    total_trades: int
    reviewed_count: int
    unreviewed_count: int
    review_rate: float
    principle_followed_count: int
    principle_violation_count: int
    impulse_trade_count: int
    grade_counts: dict[str, int]
    top_mistakes: list[dict[str, int | str]]


class TradeReviewGptPackageResponse(BaseModel):
    journal_id: int
    stock_name: str | None = None
    package_title: str
    generated_prompt: str
    sections: dict[str, str]
