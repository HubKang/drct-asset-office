from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ResearchReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int | None
    report_type: str
    title: str
    report_date: str
    summary: str | None
    markdown_content: str | None
    markdown_path: str
    generated_by: str | None
    created_at: str
