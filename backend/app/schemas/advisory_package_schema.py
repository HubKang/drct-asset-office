from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AdvisoryPackageGenerateRequest(BaseModel):
    stock_id: int
    news_ids: list[int] = Field(default_factory=list)
    disclosure_ids: list[int] = Field(default_factory=list)
    title: str
    purpose: str
    package_type: Literal["swing", "long_term"]


class AdvisoryPackageGenerateResponse(BaseModel):
    id: int
    stock_id: int
    title: str
    report_type: str
    package_type: Literal["swing", "long_term"]
    markdown_content: str
    created_at: str
