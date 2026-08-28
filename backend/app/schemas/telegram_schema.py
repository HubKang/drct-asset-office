from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramSourceCreate(BaseModel):
    source_name: str = Field(min_length=1, max_length=100)
    channel_username: str = Field(min_length=1, max_length=255)
    channel_title: str | None = None
    description: str | None = None
    is_active: bool = True
    memo: str | None = None


class TelegramSourceUpdate(BaseModel):
    source_name: str | None = Field(default=None, min_length=1, max_length=100)
    channel_username: str | None = Field(default=None, min_length=1, max_length=255)
    channel_title: str | None = None
    description: str | None = None
    is_active: bool | None = None
    is_deleted: bool | None = None
    memo: str | None = None


class TelegramSourceResponse(BaseModel):
    id: int
    source_name: str
    channel_username: str
    channel_title: str | None
    description: str | None
    is_active: int
    is_default: int
    is_deleted: int
    last_collected_message_id: int | None
    last_collected_at: str | None
    memo: str | None
    created_at: str
    updated_at: str | None
    model_config = {"from_attributes": True}


class TelegramCollectDateRequest(BaseModel):
    source_id: int
    target_date: str


class TelegramCollectDateAllRequest(BaseModel):
    target_date: str


class TelegramCollectResult(BaseModel):
    source_id: int
    source_name: str
    target_date: str
    source_mode: str
    success: bool
    telegram_connected: bool
    session_exists: bool
    channel_accessible: bool
    collected: int
    inserted: int
    duplicate_skipped: int
    excluded_skipped: int
    processing_failed: int
    error_code: str | None = None
    error_message: str | None = None
    diagnostics: dict[str, bool] = Field(default_factory=dict)


class TelegramCollectAllResult(BaseModel):
    target_date: str
    source_count: int
    source_mode: str
    success: bool
    telegram_connected: bool
    session_exists: bool
    channel_accessible: bool
    collected: int
    inserted: int
    duplicate_skipped: int
    excluded_skipped: int
    processing_failed: int
    error_code: str | None = None
    error_message: str | None = None
    diagnostics: dict[str, bool] = Field(default_factory=dict)


class TelegramSourceConnectionTestResponse(BaseModel):
    source_id: int
    source_name: str
    channel_username: str
    normalized_channel_username: str | None
    telegram_connected: bool
    session_exists: bool
    channel_accessible: bool
    source_mode: str
    latest_message_id: int | None
    latest_message_date: str | None
    message: str


class TelegramAuthStatusResponse(BaseModel):
    enabled: bool
    has_api_id: bool
    has_api_hash: bool
    has_phone: bool
    has_session: bool
    authorized: bool
    auth_required: bool
    source_mode: str
    error_code: str | None = None
    error_message: str | None = None


class TelegramAuthStartResponse(BaseModel):
    success: bool
    auth_stage: str
    authorized: bool
    error_code: str | None = None
    message: str


class TelegramAuthVerifyCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)


class TelegramAuthVerifyPasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class TelegramAuthVerifyResponse(TelegramAuthStartResponse):
    pass


class TelegramItemResponse(BaseModel):
    id: int
    collection_date: str
    message_at: str
    title: str
    summary: str | None
    source_url: str | None
    created_at: str
    model_config = {"from_attributes": True}


class TelegramItemListResponse(BaseModel):
    items: list[TelegramItemResponse]
    total_count: int
    with_summary_count: int
    title_only_count: int
    limit: int
    offset: int


class TelegramItemsDeleteRequest(BaseModel):
    item_ids: list[int]


class TelegramItemsDeleteResponse(BaseModel):
    requested_count: int
    deleted_count: int


class TelegramItemsSummarizeRequest(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=20)


class TelegramItemsSummarizeResponse(BaseModel):
    requested: int
    summarized: int
    skipped_existing: int
    missing_url: int
    fetch_failed: int
    extraction_failed: int
    processing_failed: int
