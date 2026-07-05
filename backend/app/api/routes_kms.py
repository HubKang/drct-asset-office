from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.kms_schema import (
    KmsCategoryCreate,
    KmsCategoryResponse,
    KmsCategoryUpdate,
    KmsHomeSummary,
    KmsPostCreate,
    KmsPostSummary,
    KmsPostUpdate,
    KmsTagResponse,
)
from backend.app.services.kms_service import KmsService

router = APIRouter(prefix="/kms", tags=["kms"])


@router.get("/home/summary", response_model=KmsHomeSummary)
def get_kms_home_summary(db: Session = Depends(get_db)) -> KmsHomeSummary:
    return KmsService(db).get_home_summary()


@router.get("/categories", response_model=list[KmsCategoryResponse])
def list_kms_categories(include_inactive: bool = False, db: Session = Depends(get_db)) -> list[KmsCategoryResponse]:
    return KmsService(db).list_categories(include_inactive=include_inactive)


@router.post("/categories", response_model=KmsCategoryResponse)
def create_kms_category(payload: KmsCategoryCreate, db: Session = Depends(get_db)) -> KmsCategoryResponse:
    return KmsService(db).create_category(payload)


@router.put("/categories/{category_id}", response_model=KmsCategoryResponse)
def update_kms_category(category_id: int, payload: KmsCategoryUpdate, db: Session = Depends(get_db)) -> KmsCategoryResponse:
    return KmsService(db).update_category(category_id, payload)


@router.delete("/categories/{category_id}", response_model=KmsCategoryResponse)
def delete_kms_category(category_id: int, db: Session = Depends(get_db)) -> KmsCategoryResponse:
    return KmsService(db).deactivate_category(category_id)


@router.get("/tags", response_model=list[KmsTagResponse])
def list_kms_tags(
    keyword: str | None = None,
    sort: str = Query(default="popular", pattern="^(popular|name)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[KmsTagResponse]:
    return KmsService(db).list_tags(keyword=keyword, sort=sort, limit=limit)


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
    return KmsService(db).deactivate_post(post_id)
