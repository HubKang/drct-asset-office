from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.kms_schema import (
    KmsCategoryActiveUpdate,
    KmsCategoryCreate,
    KmsCategoryResponse,
    KmsCategorySortOrderResponse,
    KmsCategorySortOrderUpdate,
    KmsCategoryUpdate,
    KmsHomeSummary,
    KmsKnowledgeItemActiveUpdate,
    KmsKnowledgeItemCreate,
    KmsKnowledgeItemPage,
    KmsKnowledgeItemResponse,
    KmsKnowledgeItemTagUpdate,
    KmsKnowledgeItemUpdate,
    KmsLocalImageSelectResponse,
    KmsPostCreate,
    KmsPostSummary,
    KmsPostUpdate,
    KmsSettingGroupResponse,
    KmsSettingItemActiveUpdate,
    KmsSettingItemCreate,
    KmsSettingItemResponse,
    KmsSettingItemSortOrderResponse,
    KmsSettingItemSortOrderUpdate,
    KmsSettingItemUpdate,
    KmsSummaryHelpApplyRequest,
    KmsSummaryHelpResponse,
    KmsTagCreate,
    KmsTagResponse,
    KmsTagUpdate,
)
from backend.app.services.kms_service import KmsService

router = APIRouter(prefix="/kms", tags=["kms"])


@router.get("/home/summary", response_model=KmsHomeSummary)
def get_kms_home_summary(db: Session = Depends(get_db)) -> KmsHomeSummary:
    return KmsService(db).get_home_summary()


@router.get("/settings/groups", response_model=list[KmsSettingGroupResponse])
def list_kms_setting_groups(
    include_inactive: bool = False,
    include_items: bool = True,
    db: Session = Depends(get_db),
) -> list[KmsSettingGroupResponse]:
    return KmsService(db).list_setting_groups(include_inactive=include_inactive, include_items=include_items)


@router.get("/settings/items", response_model=list[KmsSettingItemResponse])
def list_kms_setting_items(
    group_code: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> list[KmsSettingItemResponse]:
    return KmsService(db).list_setting_items(group_code=group_code, include_inactive=include_inactive)


@router.post("/settings/items", response_model=KmsSettingItemResponse)
def create_kms_setting_item(payload: KmsSettingItemCreate, db: Session = Depends(get_db)) -> KmsSettingItemResponse:
    return KmsService(db).create_setting_item(payload)


@router.put("/settings/items/{item_id}", response_model=KmsSettingItemResponse)
def update_kms_setting_item(item_id: int, payload: KmsSettingItemUpdate, db: Session = Depends(get_db)) -> KmsSettingItemResponse:
    return KmsService(db).update_setting_item(item_id, payload)


@router.patch("/settings/items/{item_id}/active", response_model=KmsSettingItemResponse)
def update_kms_setting_item_active(item_id: int, payload: KmsSettingItemActiveUpdate, db: Session = Depends(get_db)) -> KmsSettingItemResponse:
    return KmsService(db).set_setting_item_active(item_id, payload)


@router.patch("/settings/items/{item_id}/default", response_model=KmsSettingItemResponse)
def update_kms_setting_item_default(item_id: int, db: Session = Depends(get_db)) -> KmsSettingItemResponse:
    return KmsService(db).set_setting_item_default(item_id)


@router.patch("/settings/items/reorder", response_model=KmsSettingItemSortOrderResponse)
def reorder_kms_setting_items(payload: KmsSettingItemSortOrderUpdate, db: Session = Depends(get_db)) -> KmsSettingItemSortOrderResponse:
    return KmsService(db).reorder_setting_items(payload)


@router.get("/knowledge-items", response_model=list[KmsKnowledgeItemResponse])
def list_kms_knowledge_items(
    keyword: str | None = None,
    para_type_id: int | None = None,
    category_id: int | None = None,
    status_id: int | None = None,
    importance_id: int | None = None,
    usage_context_id: int | None = None,
    source_type_id: int | None = None,
    tag_id: int | None = None,
    tag: str | None = None,
    is_active: bool | None = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[KmsKnowledgeItemResponse]:
    return KmsService(db).list_knowledge_items(
        keyword=keyword,
        para_type_id=para_type_id,
        category_id=category_id,
        status_id=status_id,
        importance_id=importance_id,
        usage_context_id=usage_context_id,
        source_type_id=source_type_id,
        tag_id=tag_id,
        tag=tag,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.get("/knowledge-items/page", response_model=KmsKnowledgeItemPage)
def list_kms_knowledge_items_page(
    keyword: str | None = None,
    para_type_id: int | None = None,
    category_id: int | None = None,
    status_id: int | None = None,
    importance_id: int | None = None,
    usage_context_id: int | None = None,
    source_type_id: int | None = None,
    tag_names: list[str] | str = Query(default=[]),
    tag_match_mode: str = Query(default="AND", pattern="^(AND|OR)$"),
    recent_days: int | None = Query(default=None, ge=1, le=3650),
    is_active: bool | None = True,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> KmsKnowledgeItemPage:
    return KmsService(db).list_knowledge_items_page(
        keyword=keyword,
        para_type_id=para_type_id,
        category_id=category_id,
        status_id=status_id,
        importance_id=importance_id,
        usage_context_id=usage_context_id,
        source_type_id=source_type_id,
        tag_names=tag_names,
        tag_match_mode=tag_match_mode,
        recent_days=recent_days,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.get("/knowledge-items/{item_id}", response_model=KmsKnowledgeItemResponse)
def get_kms_knowledge_item(item_id: int, db: Session = Depends(get_db)) -> KmsKnowledgeItemResponse:
    return KmsService(db).get_knowledge_item(item_id)


@router.post("/knowledge-items", response_model=KmsKnowledgeItemResponse)
def create_kms_knowledge_item(payload: KmsKnowledgeItemCreate, db: Session = Depends(get_db)) -> KmsKnowledgeItemResponse:
    return KmsService(db).create_knowledge_item(payload)


@router.put("/knowledge-items/{item_id}", response_model=KmsKnowledgeItemResponse)
def update_kms_knowledge_item(item_id: int, payload: KmsKnowledgeItemUpdate, db: Session = Depends(get_db)) -> KmsKnowledgeItemResponse:
    return KmsService(db).update_knowledge_item(item_id, payload)


@router.patch("/knowledge-items/{item_id}/active", response_model=KmsKnowledgeItemResponse)
def update_kms_knowledge_item_active(item_id: int, payload: KmsKnowledgeItemActiveUpdate, db: Session = Depends(get_db)) -> KmsKnowledgeItemResponse:
    return KmsService(db).set_knowledge_item_active(item_id, payload.is_active)


@router.delete("/knowledge-items/{item_id}", response_model=KmsKnowledgeItemResponse)
def delete_kms_knowledge_item(item_id: int, db: Session = Depends(get_db)) -> KmsKnowledgeItemResponse:
    return KmsService(db).delete_knowledge_item(item_id)


@router.post("/knowledge-items/{item_id}/ai/summary", response_model=KmsSummaryHelpResponse)
def generate_kms_knowledge_item_summary_help(item_id: int, db: Session = Depends(get_db)) -> KmsSummaryHelpResponse:
    return KmsService(db).generate_knowledge_item_summary_help(item_id)


@router.post("/knowledge-items/{item_id}/ai/summary/apply", response_model=KmsSummaryHelpResponse)
def apply_kms_knowledge_item_summary_help(item_id: int, payload: KmsSummaryHelpApplyRequest, db: Session = Depends(get_db)) -> KmsSummaryHelpResponse:
    return KmsService(db).apply_knowledge_item_summary_help(item_id, payload)


@router.post("/knowledge-items/{item_id}/tags", response_model=KmsKnowledgeItemResponse)
def replace_kms_knowledge_item_tags(item_id: int, payload: KmsKnowledgeItemTagUpdate, db: Session = Depends(get_db)) -> KmsKnowledgeItemResponse:
    return KmsService(db).replace_knowledge_item_tags(item_id, payload)


@router.post("/knowledge-items/{item_id}/tags/sync", response_model=KmsKnowledgeItemResponse)
def sync_kms_knowledge_item_tags(item_id: int, payload: KmsKnowledgeItemTagUpdate, db: Session = Depends(get_db)) -> KmsKnowledgeItemResponse:
    return KmsService(db).sync_knowledge_item_confirmed_tags(item_id, payload)


@router.delete("/knowledge-items/{item_id}/tags/{tag_id}", response_model=KmsKnowledgeItemResponse)
def remove_kms_knowledge_item_tag(item_id: int, tag_id: int, db: Session = Depends(get_db)) -> KmsKnowledgeItemResponse:
    return KmsService(db).remove_knowledge_item_tag(item_id, tag_id)


@router.get("/categories", response_model=list[KmsCategoryResponse])
def list_kms_categories(include_inactive: bool = False, db: Session = Depends(get_db)) -> list[KmsCategoryResponse]:
    return KmsService(db).list_categories(include_inactive=include_inactive)


@router.post("/categories", response_model=KmsCategoryResponse)
def create_kms_category(payload: KmsCategoryCreate, db: Session = Depends(get_db)) -> KmsCategoryResponse:
    return KmsService(db).create_category(payload)


@router.put("/categories/sort-orders", response_model=KmsCategorySortOrderResponse)
def update_kms_category_sort_orders(payload: KmsCategorySortOrderUpdate, db: Session = Depends(get_db)) -> KmsCategorySortOrderResponse:
    return KmsService(db).update_category_sort_orders(payload)


@router.put("/categories/{category_id}", response_model=KmsCategoryResponse)
def update_kms_category(category_id: int, payload: KmsCategoryUpdate, db: Session = Depends(get_db)) -> KmsCategoryResponse:
    return KmsService(db).update_category(category_id, payload)


@router.patch("/categories/{category_id}/active", response_model=KmsCategoryResponse)
def update_kms_category_active(category_id: int, payload: KmsCategoryActiveUpdate, db: Session = Depends(get_db)) -> KmsCategoryResponse:
    return KmsService(db).set_category_active(category_id, payload.is_active)


@router.delete("/categories/{category_id}")
def delete_kms_category(category_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    return KmsService(db).delete_category(category_id)


@router.get("/tags", response_model=list[KmsTagResponse])
def list_kms_tags(
    keyword: str | None = None,
    sort: str = Query(default="popular", pattern="^(popular|name)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[KmsTagResponse]:
    return KmsService(db).list_tags(keyword=keyword, sort=sort, limit=limit)


@router.post("/tags", response_model=KmsTagResponse)
def create_kms_tag(payload: KmsTagCreate, db: Session = Depends(get_db)) -> KmsTagResponse:
    return KmsService(db).create_tag(payload)


@router.put("/tags/{tag_id}", response_model=KmsTagResponse)
def update_kms_tag(tag_id: int, payload: KmsTagUpdate, db: Session = Depends(get_db)) -> KmsTagResponse:
    return KmsService(db).update_tag(tag_id, payload)



@router.get("/local-image/select", response_model=KmsLocalImageSelectResponse)
def select_kms_local_image(db: Session = Depends(get_db)) -> KmsLocalImageSelectResponse:
    return KmsService(db).select_local_image()


@router.get("/local-image")
def get_kms_local_image(path: str = Query(...), db: Session = Depends(get_db)) -> FileResponse:
    file_path, media_type = KmsService(db).resolve_local_image(path)
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/posts/search-by-tags", response_model=list[KmsPostSummary])
def search_kms_posts_by_tags(
    tag_names: list[str] | str = Query(default=[]),
    match_mode: str = Query(default="AND", pattern="^(AND|OR)$"),
    category_id: int | None = None,
    learning_status: str | None = None,
    importance: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[KmsPostSummary]:
    return KmsService(db).search_by_tags(
        tag_names=tag_names,
        match_mode=match_mode,
        category_id=category_id,
        learning_status=learning_status,
        importance=importance,
        limit=limit,
        offset=offset,
    )


@router.get("/posts", response_model=list[KmsPostSummary])
def list_kms_posts(
    keyword: str | None = None,
    category_id: int | None = None,
    learning_status: str | None = None,
    importance: str | None = None,
    is_active: bool | None = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[KmsPostSummary]:
    return KmsService(db).list_posts(
        keyword=keyword,
        category_id=category_id,
        learning_status=learning_status,
        importance=importance,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.get("/posts/{post_id}", response_model=KmsPostSummary)
def get_kms_post(post_id: int, db: Session = Depends(get_db)) -> KmsPostSummary:
    return KmsService(db).get_post(post_id)


@router.post("/posts", response_model=KmsPostSummary)
def create_kms_post(payload: KmsPostCreate, db: Session = Depends(get_db)) -> KmsPostSummary:
    return KmsService(db).create_post(payload)


@router.put("/posts/{post_id}", response_model=KmsPostSummary)
def update_kms_post(post_id: int, payload: KmsPostUpdate, db: Session = Depends(get_db)) -> KmsPostSummary:
    return KmsService(db).update_post(post_id, payload)


@router.delete("/posts/{post_id}", response_model=KmsPostSummary)
def delete_kms_post(post_id: int, db: Session = Depends(get_db)) -> KmsPostSummary:
    return KmsService(db).delete_post(post_id)
