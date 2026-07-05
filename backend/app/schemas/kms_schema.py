from __future__ import annotations

from pydantic import BaseModel, ConfigDict


IMPORTANCE_VALUES = {"낮음", "보통", "높음", "핵심"}
LEARNING_STATUS_VALUES = {"미정리", "정리중", "1차 정리 완료", "복습 필요", "실전 적용 후보", "매매기법 반영 완료", "보류"}


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
