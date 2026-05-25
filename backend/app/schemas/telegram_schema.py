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
    summarize_new_items: bool = True
    include_notice: bool = False
    include_advertisement: bool = False


class TelegramCollectDateAllRequest(BaseModel):
    target_date: str
    summarize_new_items: bool = True
    include_notice: bool = False
    include_advertisement: bool = False


class TelegramCollectResult(BaseModel):
    source_id: int
    source_name: str
    target_date: str
    source_mode: str
    telegram_connected: bool
    session_exists: bool
    channel_accessible: bool
    fetched_message_count: int
    new_item_count: int
    duplicate_count: int
    summarized_count: int
    failed_count: int
    collection_run_id: int


class TelegramCollectAllResult(BaseModel):
    target_date: str
    source_count: int
    source_mode: str
    telegram_connected: bool
    session_exists: bool
    channel_accessible: bool
    fetched_message_count: int
    new_item_count: int
    duplicate_count: int
    summarized_count: int
    failed_count: int


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


class TelegramItemResponse(BaseModel):
    id: int
    source_id: int
    source_name: str
    telegram_message_id: int
    message_date: str
    message_text: str | None
    item_title: str | None = None
    summary_text: str | None
    key_points_json: str | None = None
    message_type: str
    item_category: str
    tag: str | None
    score: int
    sentiment: str
    risk_level: str
    event_type: str
    related_stock_name: str | None
    related_stock_code: str | None
    related_theme: str | None
    summary_status: str
    summary_has_content: int
    summary_error_message: str | None = None
    item_url: str | None
    normalized_url: str | None = None
    updated_at: str | None = None


class TelegramItemListResponse(BaseModel):
    items: list[TelegramItemResponse]
    total_count: int
    limit: int
    offset: int


class TelegramDailySummaryGenerateRequest(BaseModel):
    target_date: str
    source_id: int | None = None


class TelegramDailySummaryResponse(BaseModel):
    id: int
    summary_date: str
    source_id: int
    item_count: int
    summary_text: str | None
    key_points: list[str]
    top_tags: list[str]
    top_event_types: list[str]
    message_type_stats: list[dict[str, int | str]]
    theme_mentions: list[str]
    stock_mentions: list[str]
    risk_points: list[str]
    summary_has_content: int
    llm_model: str | None


class TelegramItemSummarizeResponse(BaseModel):
    item_id: int
    summary_status: str
    summary_has_content: int
    summary_text: str | None
    summary_error_message: str | None = None


class TelegramItemsDeleteRequest(BaseModel):
    item_ids: list[int]


class TelegramItemsDeleteResponse(BaseModel):
    requested_count: int
    deleted_count: int
