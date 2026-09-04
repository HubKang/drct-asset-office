from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class MarkerGroupWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    color: str = Field(default="#64748b", pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int = 0
    is_active: bool = True
    knowledge_item_ids: list[int] = Field(default_factory=list, max_length=50)


class MarkerGroupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int | None = None
    is_active: bool | None = None
    knowledge_item_ids: list[int] | None = Field(default=None, max_length=50)


class MarkerWrite(BaseModel):
    marker_group_id: int
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    symbol: str = Field(default="◆", min_length=1, max_length=12)
    sort_order: int = 0
    is_active: bool = True


class MarkerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    symbol: str | None = Field(default=None, min_length=1, max_length=12)
    sort_order: int | None = None
    is_active: bool | None = None


class MarkerEventWrite(BaseModel):
    stock_id: int
    marker_id: int
    marker_date: date
    memo: str | None = Field(default=None, max_length=4000)


class MarkerEventPatch(BaseModel):
    marker_id: int | None = None
    memo: str | None = Field(default=None, max_length=4000)
    review_result: Literal["S", "F"] | None = None
