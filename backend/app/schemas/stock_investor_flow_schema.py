from __future__ import annotations

from pydantic import BaseModel, Field


class InvestorFlowCollectRequest(BaseModel):
    watchlist_ids: list[int] = Field(default_factory=list)
    stock_ids: list[int] = Field(default_factory=list)
    period: str = "RECENT_7D"
    start_date: str | None = None
    end_date: str | None = None
    source: str = "kiwoom"
    prefer_real_source: bool = True
    fallback_to_derived: bool = False
    include_trade_breakdown: bool = True
    include_foreign_holding: bool = True


class InvestorFlowCollectItem(BaseModel):
    watchlist_id: int | None = None
    stock_id: int
    stock_code: str
    stock_name: str
    collected_days: int = 0
    saved_count: int = 0
    status: str
    data_source_type: str | None = None
    individual_status: str | None = None
    foreign_status: str | None = None
    institution_status: str | None = None
    program_status: str | None = None
    foreign_holding_status: str | None = None
    message: str | None = None


class InvestorFlowCollectResponse(BaseModel):
    status: str
    requested_count: int
    success_count: int
    failed_count: int
    saved_count: int = 0
    items: list[InvestorFlowCollectItem] = Field(default_factory=list)


class InvestorFlowChartItem(BaseModel):
    date: str
    source: str | None = None
    data_source_type: str | None = None
    source_method: str | None = None
    is_real_investor_flow: bool = False
    collection_status: str | None = None
    individual_net_qty: int | None = None
    individual_net_amount: int | None = None
    foreign_net_qty: int | None = None
    foreign_net_amount: int | None = None
    foreign_holding_qty: int | None = None
    foreign_holding_ratio: float | None = None
    institution_net_qty: int | None = None
    institution_net_amount: int | None = None
    program_net_qty: int | None = None
    program_net_amount: int | None = None


class InvestorFlowChartResponse(BaseModel):
    watchlist_id: int
    stock_id: int
    stock_code: str
    stock_name: str
    latest_date: str | None = None
    selected_source_type: str | None = None
    fallback_source_type: str | None = None
    is_real_investor_flow: bool = False
    source_method: str | None = None
    source_methods: list[str] = Field(default_factory=list)
    has_real_data: bool = False
    amount_available: bool = False
    available_subjects: dict[str, bool] = Field(default_factory=lambda: {"foreign": False, "institution": False, "program": False})
    available_metrics: dict[str, bool] = Field(default_factory=dict)
    data_notice: str | None = None
    items: list[InvestorFlowChartItem] = Field(default_factory=list)


class InvestorFlowSummary(BaseModel):
    latest_date: str | None = None
    foreign_5d_net_qty: int | None = None
    institution_5d_net_qty: int | None = None
    program_5d_net_qty: int | None = None
    foreign_streak: int = 0
    institution_streak: int = 0
    program_streak: int = 0
    selected_source_type: str | None = None
    is_real_investor_flow: bool = False
