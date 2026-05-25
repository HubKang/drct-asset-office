from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CollectionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collector_name: str
    target: str | None
    status: str
    started_at: str
    finished_at: str | None
    message: str | None
    created_at: str
    collector_display_name: str | None = None
    run_type: str | None = None
    run_type_label: str | None = None
    collector_group: str | None = None
    collector_group_label: str | None = None


class CollectionRunListResponse(BaseModel):
    items: list[CollectionRunResponse]
    total_count: int
    limit: int
    offset: int


class CollectionRunCleanupPreviewResponse(BaseModel):
    success: bool
    cutoff_date: str
    target_count: int
    message: str


class CollectionRunCleanupResponse(BaseModel):
    success: bool
    cutoff_date: str
    deleted_count: int
    message: str
