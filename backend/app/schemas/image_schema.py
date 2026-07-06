from __future__ import annotations

from pydantic import BaseModel, Field


class AppImageResponse(BaseModel):
    id: int
    domain: str
    owner_type: str | None = None
    owner_id: int | None = None
    original_file_name: str
    stored_file_name: str
    relative_path: str
    file_url: str
    file_ext: str
    mime_type: str | None = None
    file_size: int
    width: int | None = None
    height: int | None = None
    sort_order: int = 0
    description: str | None = None
    is_active: int = 1
    created_at: str
    updated_at: str


class AppImageListResponse(BaseModel):
    items: list[AppImageResponse]
    total_count: int = Field(ge=0)


class AppImageDeleteResponse(BaseModel):
    success: bool
    image_id: int
    file_deleted: bool
    file_missing: bool = False
