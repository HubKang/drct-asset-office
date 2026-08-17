from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


IMPORTANCE_VALUES = {"\ub0ae\uc74c", "\ubcf4\ud1b5", "\ub192\uc74c", "\ud575\uc2ec"}
LEARNING_STATUS_VALUES = {"\ubbf8\uc815\ub9ac", "\uc815\ub9ac\uc911", "1\ucc28 \uc815\ub9ac \uc644\ub8cc", "\ubcf5\uc2b5 \ud544\uc694", "\uc2e4\uc804 \uc801\uc6a9 \ud6c4\ubcf4", "\ub9e4\ub9e4\uae30\ubc95 \ubc18\uc601 \uc644\ub8cc", "\ubcf4\ub958"}


class KmsCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    name: str
    description: str | None
    sort_order: int
    is_active: bool
    created_at: str
    updated_at: str
    post_count: int = 0
    total_post_count: int = 0
    child_count: int = 0


class KmsCategoryCreate(BaseModel):
    parent_id: int | None = None
    name: str
    description: str | None = None
    sort_order: int = 100
    is_active: bool = True


class KmsCategoryUpdate(BaseModel):
    parent_id: int | None = None
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class KmsCategoryActiveUpdate(BaseModel):
    is_active: bool


class KmsCategorySortOrderItem(BaseModel):
    id: int
    sort_order: int


class KmsCategorySortOrderUpdate(BaseModel):
    items: list[KmsCategorySortOrderItem]


class KmsCategorySortOrderResponse(BaseModel):
    success: bool
    updated_count: int


class KmsTagResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    use_count: int
    is_active: bool
    created_at: str
    updated_at: str




class KmsLocalImageSelectResponse(BaseModel):
    selected: bool
    path: str | None = None
    url: str | None = None


class KmsPostSummary(BaseModel):
    id: int
    category_id: int
    category_name: str | None = None
    title: str
    summary: str | None = None
    content: str
    source_url: str | None = None
    importance: str
    learning_status: str
    is_pinned: bool
    is_active: bool
    tags: list[str] = []
    created_at: str
    updated_at: str


class KmsPostCreate(BaseModel):
    category_id: int
    title: str
    summary: str | None = None
    content: str
    source_url: str | None = None
    importance: str = "보통"
    learning_status: str = "미정리"
    is_pinned: bool = False
    is_active: bool = True
    tags: list[str] | str | None = None


class KmsPostUpdate(BaseModel):
    category_id: int | None = None
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    source_url: str | None = None
    importance: str | None = None
    learning_status: str | None = None
    is_pinned: bool | None = None
    is_active: bool | None = None
    tags: list[str] | str | None = None


class KmsOverallSummary(BaseModel):
    total_posts: int
    review_needed_count: int
    practice_candidate_count: int
    core_count: int
    recent_7d_count: int


class KmsCategorySummary(BaseModel):
    category_id: int
    category_name: str
    total_posts: int
    core_count: int
    review_needed_count: int
    practice_candidate_count: int
    recent_7d_count: int
    top_tags: list[str]
    last_updated_at: str | None = None


class KmsRecentPost(BaseModel):
    post_id: int
    title: str
    category_name: str | None = None
    learning_status: str
    importance: str
    updated_at: str


class KmsHomeSummary(BaseModel):
    overall: KmsOverallSummary
    categories: list[KmsCategorySummary]
    popular_tags: list[KmsTagResponse]
    recent_posts: list[KmsRecentPost]
    review_needed_posts: list[KmsRecentPost]
    practice_candidate_posts: list[KmsRecentPost]


class KmsSettingGroupResponse(BaseModel):
    id: int
    group_code: str
    group_name: str
    description: str | None = None
    sort_order: int
    is_active: bool
    created_at: str
    updated_at: str
    items: list["KmsSettingItemResponse"] = []


class KmsSettingItemResponse(BaseModel):
    id: int
    group_id: int
    group_code: str | None = None
    item_code: str
    item_name: str
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int
    is_default: bool
    is_system: bool
    is_active: bool
    created_at: str
    updated_at: str


class KmsSettingItemCreate(BaseModel):
    group_code: str
    item_code: str
    item_name: str
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int = 100
    is_default: bool = False
    is_system: bool = False
    is_active: bool = True


class KmsSettingItemUpdate(BaseModel):
    item_code: str | None = None
    item_name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class KmsSettingItemActiveUpdate(BaseModel):
    is_active: bool


class KmsSettingItemSortOrderItem(BaseModel):
    id: int
    sort_order: int


class KmsSettingItemSortOrderUpdate(BaseModel):
    items: list[KmsSettingItemSortOrderItem]


class KmsSettingItemSortOrderResponse(BaseModel):
    success: bool
    updated_count: int


class KmsKnowledgeItemTagResponse(BaseModel):
    id: int
    tag_id: int
    tag_name: str
    tag_type_id: int | None = None
    tag_type_name: str | None = None
    weight: float = 1.0
    source: str = "USER"
    is_confirmed: bool = True


class KmsSettingItemSummary(BaseModel):
    id: int
    item_code: str
    item_name: str
    color: str | None = None
    icon: str | None = None


class KmsKnowledgeExtractionResponse(BaseModel):
    id: int
    extraction_type: str
    extraction_text: str
    source: str
    model_name: str | None = None
    confidence_score: float | None = None
    created_at: str
    updated_at: str


class KmsKnowledgeItemResponse(BaseModel):
    id: int
    legacy_post_id: int | None = None
    legacy_source_type: str | None = None
    legacy_source_id: int | None = None
    title: str
    content: str
    content_format: str = "HTML"
    plain_text_snippet: str | None = None
    one_line_conclusion: str | None = None
    summary: str | None = None
    para_type_id: int | None = None
    category_id: int | None = None
    status_id: int | None = None
    importance_id: int | None = None
    usage_context_id: int | None = None
    source_type_id: int | None = None
    source_url: str | None = None
    source_title: str | None = None
    ai_extract_status: str = "PENDING"
    embedding_status: str = "PENDING"
    is_active: bool
    created_at: str
    updated_at: str
    para_type: KmsSettingItemSummary | None = None
    category: KmsSettingItemSummary | None = None
    status: KmsSettingItemSummary | None = None
    importance: KmsSettingItemSummary | None = None
    usage_context: KmsSettingItemSummary | None = None
    source_type: KmsSettingItemSummary | None = None
    tags: list[KmsKnowledgeItemTagResponse] = []
    extractions: list[KmsKnowledgeExtractionResponse] = []


class KmsKnowledgeCategoryCount(BaseModel):
    category_id: int
    count: int


class KmsKnowledgeItemPage(BaseModel):
    items: list[KmsKnowledgeItemResponse]
    total: int
    limit: int
    offset: int
    category_counts: list[KmsKnowledgeCategoryCount] = Field(default_factory=list)


class KmsKnowledgeItemCreate(BaseModel):
    title: str
    content: str
    content_format: str | None = None
    one_line_conclusion: str | None = None
    summary: str | None = None
    para_type_id: int | None = None
    category_id: int | None = None
    status_id: int | None = None
    importance_id: int | None = None
    usage_context_id: int | None = None
    source_type_id: int | None = None
    source_url: str | None = None
    source_title: str | None = None
    tags: list[str] | str | None = None
    editor_uploaded_image_urls: list[str] = Field(default_factory=list)


class KmsKnowledgeItemUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    content_format: str | None = None
    one_line_conclusion: str | None = None
    summary: str | None = None
    para_type_id: int | None = None
    category_id: int | None = None
    status_id: int | None = None
    importance_id: int | None = None
    usage_context_id: int | None = None
    source_type_id: int | None = None
    source_url: str | None = None
    source_title: str | None = None
    is_active: bool | None = None
    tags: list[str] | str | None = None
    editor_uploaded_image_urls: list[str] = Field(default_factory=list)
    editor_removed_image_urls: list[str] = Field(default_factory=list)


class KmsKnowledgeItemTagUpdate(BaseModel):
    tag_names: list[str] | str | None = None
    tag_type_id: int | None = None


class KmsKnowledgeItemActiveUpdate(BaseModel):
    is_active: bool


class KmsSummaryHelpApplyRequest(BaseModel):
    apply_summary: bool = False
    summary: str | None = None
    add_keywords_as_tags: bool = False
    keywords: list[str] = Field(default_factory=list)


class KmsSummaryHelpResponse(BaseModel):
    knowledge_item_id: int
    status: str
    summary: str | None = None
    keywords: list[str] = Field(default_factory=list)
    error_message: str | None = None
    item: KmsKnowledgeItemResponse | None = None


class KmsTagCreate(BaseModel):
    tag_name: str
    tag_type_id: int | None = None
    description: str | None = None
    color: str | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    is_active: bool = True


class KmsTagUpdate(BaseModel):
    tag_name: str | None = None
    tag_type_id: int | None = None
    description: str | None = None
    color: str | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    is_active: bool | None = None
