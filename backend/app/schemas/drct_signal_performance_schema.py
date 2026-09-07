from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


EvaluationStatus = Literal["PENDING", "D5_READY", "D10_READY", "COMPLETE"]


class SignalPerformanceMarkerSummary(BaseModel):
    marker_id: int
    marker_name: str
    signal_count: int
    completed_count: int
    d5_average_pct: float | None
    d10_average_pct: float | None
    d20_average_pct: float | None
    max_rise_average_pct: float | None
    max_fall_average_pct: float | None


class SignalPerformanceEventItem(BaseModel):
    id: int
    stock_id: int
    stock_code: str
    stock_name: str
    marker_id: int
    marker_name: str
    marker_symbol: str
    marker_group_name: str
    marker_group_color: str
    signal_date: str
    last_seen_date: str
    ended_date: str | None
    similarity_score: float
    evaluation_status: EvaluationStatus
    d5_date: str | None
    d5_return_pct: float | None
    d10_date: str | None
    d10_return_pct: float | None
    d20_date: str | None
    d20_return_pct: float | None
    max_rise_20_pct: float | None
    max_fall_20_pct: float | None
    evaluated_at: datetime | None


class SignalPerformanceSummaryResponse(BaseModel):
    total_count: int
    completed_count: int
    pending_count: int
    d20_average_pct: float | None
    markers: list[SignalPerformanceMarkerSummary]
    refreshed_at: datetime


class SignalPerformanceEventsResponse(BaseModel):
    total: int
    items: list[SignalPerformanceEventItem]


class SignalPerformanceEventDetail(SignalPerformanceEventItem):
    d0_close: float

