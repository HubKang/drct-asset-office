from __future__ import annotations

from pydantic import BaseModel, Field


class BriefingSourceCreate(BaseModel):
    source_type: str
    source_name: str
    source_url: str
    channel_id: str | None = None
    playlist_id: str | None = None
    is_default: int = 0
    is_active: int = 1


class BriefingSourceUpdate(BaseModel):
    source_name: str | None = None
    source_url: str | None = None
    channel_id: str | None = None
    playlist_id: str | None = None
    is_default: int | None = None
    is_active: int | None = None


class BriefingSourceItem(BaseModel):
    id: int
    source_type: str
    source_name: str
    source_url: str
    channel_id: str | None = None
    playlist_id: str | None = None
    is_default: int
    is_active: int
    last_checked_at: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class BriefingVideoManualCreate(BaseModel):
    video_url: str
    source_id: int | None = None


class BriefingVideoStatusUpdate(BaseModel):
    transcript_status: str | None = None
    transcript_language: str | None = None
    transcript_source: str | None = None
    analysis_status: str | None = None
    error_message: str | None = None


class BriefingSourceRefreshRequest(BaseModel):
    max_results: int = 20


class BriefingSummaryJobCreateRequest(BaseModel):
    force: bool = False


class BriefingVideoItem(BaseModel):
    id: int
    source_id: int | None = None
    video_id: str
    video_url: str
    title: str
    channel_name: str | None = None
    published_at: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None
    description_summary: str | None = None
    transcript_status: str
    transcript_language: str | None = None
    transcript_source: str | None = None
    transcript_checked_at: str | None = None
    transcript_text_length: int | None = None
    transcript_chunk_count: int | None = None
    llm_response_length: int | None = None
    llm_timeout_seconds: int | None = None
    analysis_status: str
    summary_exists: bool = False
    summary_has_content: bool = False
    summary_id: int | None = None
    topic_count: int = 0
    last_analyzed_at: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class BriefingSummaryItem(BaseModel):
    id: int
    video_id: int
    summary_type: str
    model_name: str | None = None
    summary_text: str | None = None
    key_points_json: str | None = None
    topic_json: str | None = None
    stock_mentions_json: str | None = None
    theme_mentions_json: str | None = None
    risk_points_json: str | None = None
    quality_meta_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class BriefingSourceListResponse(BaseModel):
    success: bool
    count: int
    items: list[BriefingSourceItem] = Field(default_factory=list)


class BriefingVideoListResponse(BaseModel):
    success: bool
    count: int
    items: list[BriefingVideoItem] = Field(default_factory=list)


class BriefingSummaryListResponse(BaseModel):
    success: bool
    count: int
    items: list[BriefingSummaryItem] = Field(default_factory=list)


class BriefingTopicItem(BaseModel):
    id: int
    video_id: int
    topic_name: str
    summary: str | None = None
    importance_score: int | None = None
    related_themes_json: str | None = None
    related_stocks_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class BriefingMutationResponse(BaseModel):
    success: bool
    message: str
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    fetched_count: int = 0


class BriefingSourceMutationResponse(BriefingMutationResponse):
    source_id: int | None = None
    source_name: str | None = None
    playlist_id: str | None = None
    item: BriefingSourceItem | None = None


class BriefingVideoMutationResponse(BriefingMutationResponse):
    item: BriefingVideoItem | None = None


class BriefingTranscriptChunkPreview(BaseModel):
    index: int
    text_length: int
    preview: str


class BriefingTranscriptCheckResponse(BaseModel):
    success: bool
    video_id: str
    transcript_status: str
    transcript_language: str | None = None
    transcript_source: str | None = None
    text_length: int = 0
    chunk_count: int = 0
    chunk_previews: list[BriefingTranscriptChunkPreview] = Field(default_factory=list)
    message: str
    error: str | None = None
    failure_reason: str | None = None
    error_type: str | None = None
    attempts: list[dict[str, object]] = Field(default_factory=list)
    selected_provider: str | None = None
    provider_results: dict[str, dict[str, object]] = Field(default_factory=dict)
    normalized_error_type: str | None = None
    is_retryable: bool | None = None
    retry_after_minutes: int | None = None


class BriefingVideoSummarizeResponse(BaseModel):
    success: bool
    video_id: str
    analysis_status: str
    summary_id: int | None = None
    topic_count: int = 0
    theme_mentions: list[str] = Field(default_factory=list)
    stock_mentions: list[str] = Field(default_factory=list)
    message: str
    error: str | None = None


class BriefingSummaryDetailResponse(BaseModel):
    success: bool
    video_id: str
    has_content: bool = False
    summary: dict[str, object] | None = None
    topics: list[BriefingTopicItem] = Field(default_factory=list)


class BriefingSummaryJobItem(BaseModel):
    id: int
    video_id: str
    status: str
    progress_percent: int
    current_step: str | None = None
    current_chunk: int = 0
    total_chunks: int = 0
    summary_id: int | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class BriefingSummaryJobCreateResponse(BaseModel):
    success: bool
    job_id: int
    video_id: str
    status: str
    progress_percent: int
    message: str


class BriefingSummaryJobResponse(BaseModel):
    success: bool
    job: BriefingSummaryJobItem
