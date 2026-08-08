from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MarketThemeStockCreateRequest(BaseModel):
    stock_id: int
    is_primary: bool = False


class MarketThemeStockUpdateRequest(BaseModel):
    is_primary: bool | None = None
    is_active: int | None = None
    confidence_score: float | None = None


class MarketThemeStockMemoUpdateRequest(BaseModel):
    stock_memo: str | None = Field(default=None, max_length=100)


class MarketThemeStockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mapping_id: int
    theme_id: int
    stock_id: int
    stock_code: str
    stock_name: str
    market: str | None
    mapping_source: str
    confidence_score: float | None
    is_primary: int
    is_active: int
    stock_memo: str | None = None
    supply_day_count: int = 0
    recent_30d_supply_day_count: int = 0
    first_supply_date: str | None = None
    last_supply_date: str | None = None
    created_at: str
    updated_at: str


class MarketThemeStockSupplyCurrentTheme(BaseModel):
    theme_id: int
    theme_name: str
    color: str = "#dc2626"


class MarketThemeStockLinkedThemeSupplySummary(BaseModel):
    theme_id: int
    theme_name: str
    supply_count: int = 0
    supply_dates: list[str] = Field(default_factory=list)
    is_current_theme: bool = False


class MarketThemeStockSupplyMemoItem(BaseModel):
    detected_date: str
    memo: str
    source: str | None = None
    is_current_theme_supply_date: bool = False

class MarketThemeStockSupplySummaryResponse(BaseModel):
    theme_id: int
    theme_name: str
    stock_id: int
    stock_code: str
    stock_name: str
    supply_day_count: int = 0
    recent_30d_supply_day_count: int = 0
    first_supply_date: str | None = None
    last_supply_date: str | None = None
    all_theme_supply_day_count: int = 0
    recent_supply_dates: list[str] = Field(default_factory=list)
    current_theme: MarketThemeStockSupplyCurrentTheme
    linked_theme_supply_summaries: list[MarketThemeStockLinkedThemeSupplySummary] = Field(default_factory=list)
    period_start_date: str
    period_end_date: str
    recent_30d_theme_supply_count: int = 0
    current_theme_supply_count: int = 0
    overall_stock_supply_count: int = 0
    latest_current_theme_supply_date: str | None = None
    first_current_theme_supply_date: str | None = None
    current_theme_supply_dates: list[str] = Field(default_factory=list)
    overall_stock_supply_dates: list[str] = Field(default_factory=list)
    stock_memos: list[MarketThemeStockSupplyMemoItem] = Field(default_factory=list)


class MarketThemeByStockItem(BaseModel):
    theme_id: int
    theme_name: str
    is_primary: bool


class MarketThemeByStockResponse(BaseModel):
    stock_code: str
    stock_name: str | None
    themes: list[MarketThemeByStockItem]


class MarketThemeStockMemoItem(BaseModel):
    memo_date: str
    memo: str
    source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MarketThemeStockMemoResponse(BaseModel):
    stock_code: str
    stock_name: str | None = None
    items: list[MarketThemeStockMemoItem]


class MarketThemePriceFlowChartStock(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    market: str | None = None


class MarketThemePriceFlowChartPeriod(BaseModel):
    code: Literal["1M", "3M", "6M"]
    requested_trading_days: int
    actual_trading_days: int
    start_date: str | None = None
    end_date: str | None = None


class MarketThemePriceFlowLatestDates(BaseModel):
    price: str | None = None
    investor: str | None = None
    program: str | None = None
    common: str | None = None


class MarketThemePriceFlowDataQuality(BaseModel):
    status: Literal["ENOUGH", "PERIOD_SHORT", "PARTIAL", "LATEST_MISMATCH", "EMPTY"]
    valid_days: int = 0
    missing_price_days: int = 0
    missing_investor_days: int = 0
    missing_program_days: int = 0
    completeness_ratio: float = 0.0


class MarketThemePriceFlowSummary(BaseModel):
    price_return_pct: float | None = None
    individual_cumulative: int | None = None
    foreign_cumulative: int | None = None
    institution_cumulative: int | None = None
    program_cumulative: int | None = None
    individual_positive_days: int = 0
    foreign_positive_days: int = 0
    institution_positive_days: int = 0
    program_positive_days: int = 0
    individual_streak: int = 0
    foreign_streak: int = 0
    institution_streak: int = 0
    program_streak: int = 0


class MarketThemePriceFlowSeriesItem(BaseModel):
    trade_date: str
    close_price: float | None = None
    daily_return_pct: float | None = None
    price_return_pct: float | None = None
    individual_daily: int | None = None
    individual_cumulative: int | None = None
    foreign_daily: int | None = None
    foreign_cumulative: int | None = None
    institution_daily: int | None = None
    institution_cumulative: int | None = None
    program_daily: int | None = None
    program_cumulative: int | None = None
    normalized_price: float | None = None
    normalized_individual: float | None = None
    normalized_foreign: float | None = None
    normalized_institution: float | None = None
    normalized_program: float | None = None


class MarketThemePriceFlowEventItem(BaseModel):
    theme_id: int | None = None
    theme_name: str | None = None
    memo: str | None = None
    is_current_theme: bool = False


class MarketThemePriceFlowEvent(BaseModel):
    event_date: str
    event_count: int
    is_current_theme: bool = False
    items: list[MarketThemePriceFlowEventItem] = Field(default_factory=list)


class MarketThemePriceFlowChartResponse(BaseModel):
    stock: MarketThemePriceFlowChartStock
    requested_unit: Literal["QUANTITY", "AMOUNT"]
    requested_view: Literal["ACTUAL", "NORMALIZED"]
    period: MarketThemePriceFlowChartPeriod
    latest_dates: MarketThemePriceFlowLatestDates
    data_quality: MarketThemePriceFlowDataQuality
    summary: MarketThemePriceFlowSummary
    series: list[MarketThemePriceFlowSeriesItem] = Field(default_factory=list)
    events: list[MarketThemePriceFlowEvent] = Field(default_factory=list)


class StockDailyFlowSummary(BaseModel):
    individual_net_amount: int | None = None
    foreign_net_amount: int | None = None
    institution_net_amount: int | None = None
    program_net_amount: int | None = None
    individual_flow_strength: float | None = None
    foreign_flow_strength: float | None = None
    institution_flow_strength: float | None = None
    program_flow_strength: float | None = None
    summary_code: Literal[
        "FOREIGN_INSTITUTION_BUY", "FOREIGN_LEAD", "INSTITUTION_LEAD",
        "INDIVIDUAL_LEAD", "FOREIGN_INSTITUTION_SELL", "MIXED", "NO_DATA",
    ] = "NO_DATA"
    has_investor_data: bool = False
    has_program_data: bool = False


class ThemeActorDailyFlowSummary(BaseModel):
    net_amount: int | None = None
    flow_strength: float | None = None
    positive_stock_count: int = 0
    data_stock_count: int = 0


class ThemeDailyFlowSummary(BaseModel):
    base_date: str
    aggregation_basis: Literal["CURRENT_ACTIVE_LINKS"] = "CURRENT_ACTIVE_LINKS"
    attribution_mode: Literal["FULL"] = "FULL"
    connected_stock_count: int = 0
    investor_data_stock_count: int = 0
    program_data_stock_count: int = 0
    complete_stock_count: int = 0
    completeness_ratio: float = 0.0
    quality_status: Literal["ENOUGH", "PARTIAL", "INSUFFICIENT", "EMPTY"] = "EMPTY"
    theme_trading_value: int | None = None
    summary_code: str = "NO_DATA"
    individual: ThemeActorDailyFlowSummary
    foreign: ThemeActorDailyFlowSummary
    institution: ThemeActorDailyFlowSummary
    program: ThemeActorDailyFlowSummary


class MarketThemeFlowChartPeriod(BaseModel):
    code: Literal["1M", "3M", "6M"]
    requested_trading_days: int
    actual_trading_days: int
    start_date: str | None = None
    end_date: str | None = None


class MarketThemeFlowChartActorSummary(BaseModel):
    cumulative_amount: int | None = None
    positive_days: int = 0
    positive_stock_count: int = 0
    data_stock_count: int = 0


class MarketThemeFlowChartSummary(BaseModel):
    theme_return_pct: float | None = None
    individual: MarketThemeFlowChartActorSummary
    foreign: MarketThemeFlowChartActorSummary
    institution: MarketThemeFlowChartActorSummary
    program: MarketThemeFlowChartActorSummary


class MarketThemeFlowChartSeriesItem(BaseModel):
    trade_date: str
    theme_daily_return_pct: float | None = None
    theme_cumulative_return_pct: float | None = None
    theme_trading_value: int | None = None
    individual_daily_amount: int | None = None
    individual_cumulative_amount: int | None = None
    foreign_daily_amount: int | None = None
    foreign_cumulative_amount: int | None = None
    institution_daily_amount: int | None = None
    institution_cumulative_amount: int | None = None
    program_daily_amount: int | None = None
    program_cumulative_amount: int | None = None
    individual_positive_stock_count: int = 0
    foreign_positive_stock_count: int = 0
    institution_positive_stock_count: int = 0
    program_positive_stock_count: int = 0
    individual_data_stock_count: int = 0
    foreign_data_stock_count: int = 0
    institution_data_stock_count: int = 0
    program_data_stock_count: int = 0
    investor_data_stock_count: int = 0
    complete_stock_count: int = 0
    connected_stock_count: int = 0
    completeness_ratio: float = 0.0


class MarketThemeFlowChartResponse(BaseModel):
    theme_id: int
    theme_name: str
    period: MarketThemeFlowChartPeriod
    latest_theme_return_date: str | None = None
    latest_flow_date: str | None = None
    common_latest_date: str | None = None
    aggregation_basis: Literal["CURRENT_ACTIVE_LINKS"] = "CURRENT_ACTIVE_LINKS"
    attribution_mode: Literal["FULL"] = "FULL"
    data_quality: Literal["ENOUGH", "PARTIAL", "INSUFFICIENT", "EMPTY"] = "EMPTY"
    summary: MarketThemeFlowChartSummary
    series: list[MarketThemeFlowChartSeriesItem] = Field(default_factory=list)
    focus_date: str | None = None
    selected: MarketThemeFlowChartSeriesItem | None = None


class MarketThemeFlowTrendContributor(BaseModel):
    stock_id: int
    stock_code: str | None = None
    stock_name: str
    net_buy_amount: int


class MarketThemeFlowTrendCell(BaseModel):
    trade_date: str
    net_buy_amount: int | None = None
    trading_value: int | None = None
    flow_strength: float | None = None
    breadth_ratio: float | None = None
    positive_stock_count: int = 0
    negative_stock_count: int = 0
    zero_stock_count: int = 0
    actor_data_stock_count: int = 0
    connected_stock_count: int = 0
    missing_stock_count: int = 0
    completeness_ratio: float = 0.0
    data_quality: Literal["ENOUGH", "PARTIAL", "INSUFFICIENT", "EMPTY"] = "EMPTY"
    theme_return_pct: float | None = None
    top_contributors: list[MarketThemeFlowTrendContributor] = Field(default_factory=list)


class MarketThemeFlowTrendPeriodSummary(BaseModel):
    cumulative_net_buy_amount: int | None = None
    cumulative_trading_value: int | None = None
    flow_strength: float | None = None
    latest_breadth_ratio: float | None = None
    positive_stock_count: int = 0
    actor_data_stock_count: int = 0
    current_streak: int = 0
    connected_stock_count: int = 0
    completeness_ratio: float = 0.0
    data_quality: Literal["ENOUGH", "PARTIAL", "INSUFFICIENT", "EMPTY"] = "EMPTY"


class MarketThemeFlowTrendTheme(BaseModel):
    theme_id: int
    theme_name: str
    theme_group_id: int | None = None
    theme_group_name: str | None = None
    sort_order: int = 0
    connected_stock_count: int = 0
    twenty_day_summary: MarketThemeFlowTrendPeriodSummary
    cells: list[MarketThemeFlowTrendCell] = Field(default_factory=list)


class MarketThemeFlowTrendTopItem(BaseModel):
    theme_id: int
    theme_name: str
    flow_strength: float | None = None
    net_buy_amount: int | None = None
    breadth_ratio: float | None = None
    positive_stock_count: int = 0
    actor_data_stock_count: int = 0
    current_streak: int = 0
    completeness_ratio: float = 0.0
    data_quality: str = "EMPTY"


class MarketThemeFlowTrendSummary(BaseModel):
    top_today: MarketThemeFlowTrendTopItem | None = None
    top_five_day: MarketThemeFlowTrendTopItem | None = None
    top_breadth: MarketThemeFlowTrendTopItem | None = None
    top_streak: MarketThemeFlowTrendTopItem | None = None


class MarketThemeFlowTrendRequestMeta(BaseModel):
    end_date: str
    actual_end_date: str | None = None
    recent_days: int
    actor: Literal["FOREIGN", "INSTITUTION", "FOREIGN_INSTITUTION", "INDIVIDUAL", "PROGRAM"]
    metric: Literal["FLOW_STRENGTH", "NET_AMOUNT", "BREADTH"]
    attribution_mode: Literal["FRACTIONAL", "FULL"]
    aggregation_basis: Literal["CURRENT_ACTIVE_LINKS"] = "CURRENT_ACTIVE_LINKS"
    theme_group_id: int | None = None
    search: str | None = None
    limit: int | None = None


class MarketThemeFlowTrendResponse(BaseModel):
    request: MarketThemeFlowTrendRequestMeta
    dates: list[str] = Field(default_factory=list)
    summary: MarketThemeFlowTrendSummary
    themes: list[MarketThemeFlowTrendTheme] = Field(default_factory=list)
    performance: dict[str, int | float | bool] = Field(default_factory=dict)
