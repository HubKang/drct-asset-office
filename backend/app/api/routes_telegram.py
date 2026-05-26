from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.telegram_schema import (
    TelegramAuthStartResponse,
    TelegramAuthStatusResponse,
    TelegramAuthVerifyCodeRequest,
    TelegramAuthVerifyPasswordRequest,
    TelegramAuthVerifyResponse,
    TelegramCollectDateAllRequest,
    TelegramCollectDateRequest,
    TelegramCollectAllResult,
    TelegramCollectResult,
    TelegramDailySummaryGenerateRequest,
    TelegramDailySummaryResponse,
    TelegramItemListResponse,
    TelegramItemsDeleteRequest,
    TelegramItemsDeleteResponse,
    TelegramItemSummarizeResponse,
    TelegramSourceCreate,
    TelegramSourceConnectionTestResponse,
    TelegramSourceResponse,
    TelegramSourceUpdate,
)
from backend.app.services.telegram_service import TelegramService

router = APIRouter(prefix="/telegram", tags=["telegram"])

@router.get("/auth/status", response_model=TelegramAuthStatusResponse)
async def get_telegram_auth_status(db: Session = Depends(get_db)):
    return await TelegramService(db).get_auth_status()


@router.post("/auth/start", response_model=TelegramAuthStartResponse)
async def start_telegram_auth(db: Session = Depends(get_db)):
    return await TelegramService(db).start_auth()


@router.post("/auth/verify-code", response_model=TelegramAuthVerifyResponse)
async def verify_telegram_auth_code(payload: TelegramAuthVerifyCodeRequest, db: Session = Depends(get_db)):
    return await TelegramService(db).verify_auth_code(payload.code)


@router.post("/auth/verify-password", response_model=TelegramAuthVerifyResponse)
async def verify_telegram_auth_password(payload: TelegramAuthVerifyPasswordRequest, db: Session = Depends(get_db)):
    return await TelegramService(db).verify_auth_password(payload.password)


@router.get("/sources", response_model=list[TelegramSourceResponse])
def list_sources(
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return TelegramService(db).list_sources(include_deleted=include_deleted)


@router.post("/sources", response_model=TelegramSourceResponse)
def create_source(payload: TelegramSourceCreate, db: Session = Depends(get_db)):
    return TelegramService(db).create_source(payload)


@router.patch("/sources/{source_id}", response_model=TelegramSourceResponse)
def update_source(source_id: int, payload: TelegramSourceUpdate, db: Session = Depends(get_db)):
    return TelegramService(db).update_source(source_id, payload)


@router.delete("/sources/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    return TelegramService(db).delete_source(source_id)


@router.post("/sources/{source_id}/test-connection", response_model=TelegramSourceConnectionTestResponse)
async def test_source_connection(source_id: int, db: Session = Depends(get_db)):
    return await TelegramService(db).test_source_connection(source_id)


@router.post("/collect/date", response_model=TelegramCollectResult)
async def collect_by_date(payload: TelegramCollectDateRequest, db: Session = Depends(get_db)):
    return await TelegramService(db).collect_source_by_date(
        source_id=payload.source_id,
        target_date=payload.target_date,
        summarize_new_items=payload.summarize_new_items,
        include_notice=payload.include_notice,
        include_advertisement=payload.include_advertisement,
    )


@router.post("/collect/date/all", response_model=TelegramCollectAllResult)
async def collect_all_by_date(payload: TelegramCollectDateAllRequest, db: Session = Depends(get_db)):
    return await TelegramService(db).collect_all_sources_by_date(
        target_date=payload.target_date,
        summarize_new_items=payload.summarize_new_items,
        include_notice=payload.include_notice,
        include_advertisement=payload.include_advertisement,
    )


@router.get("/items", response_model=TelegramItemListResponse)
def list_items(
    source_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    message_type: str | None = None,
    tag: str | None = None,
    sentiment: str | None = None,
    risk_level: str | None = None,
    event_type: str | None = None,
    related_stock_name: str | None = None,
    related_theme: str | None = None,
    summary_status: str | None = None,
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return TelegramService(db).list_items(
        source_id=source_id,
        date_from=date_from,
        date_to=date_to,
        keyword=keyword,
        message_type=message_type,
        tag=tag,
        sentiment=sentiment,
        risk_level=risk_level,
        event_type=event_type,
        related_stock_name=related_stock_name,
        related_theme=related_theme,
        summary_status=summary_status,
        limit=limit,
        offset=offset,
    )


@router.post("/items/{item_id}/summarize", response_model=TelegramItemSummarizeResponse)
def summarize_item(item_id: int, db: Session = Depends(get_db)):
    return TelegramService(db).summarize_item(item_id)


@router.delete("/items/{item_id}", response_model=TelegramItemsDeleteResponse)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    return TelegramService(db).delete_item(item_id)


@router.post("/items/delete-selected", response_model=TelegramItemsDeleteResponse)
def delete_items(payload: TelegramItemsDeleteRequest, db: Session = Depends(get_db)):
    return TelegramService(db).delete_items(payload.item_ids)


@router.post("/daily-summaries/generate", response_model=TelegramDailySummaryResponse)
def generate_daily_summary(payload: TelegramDailySummaryGenerateRequest, db: Session = Depends(get_db)):
    return TelegramService(db).generate_daily_summary(target_date=payload.target_date, source_id=payload.source_id)
