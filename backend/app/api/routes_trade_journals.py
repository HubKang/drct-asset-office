from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.trade_journal_schema import (
    TradeJournalCreate,
    TradeJournalDeleteResponse,
    TradeJournalDetailResponse,
    TradeJournalImageCreate,
    TradeJournalImageUpdate,
    TradeJournalImageResponse,
    TradeJournalGptReviewPackageResponse,
    TradeJournalListResponse,
    TradeJournalMonthlyCalendarItem,
    TradeJournalMonthlyStatisticResponse,
    TradeJournalUpdate,
    TradeMethodCreate,
    TradeMethodResponse,
    TradeMethodUpdate,
)
from backend.app.services.trade_journal_service import TradeJournalService

router = APIRouter(tags=["trade-journals"])


@router.get("/trade-methods", response_model=list[TradeMethodResponse])
def list_trade_methods(
    is_active: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return TradeJournalService(db).list_trade_methods(is_active=is_active, keyword=keyword)


@router.post("/trade-methods", response_model=TradeMethodResponse)
def create_trade_method(payload: TradeMethodCreate, db: Session = Depends(get_db)):
    return TradeJournalService(db).create_trade_method(payload)


@router.patch("/trade-methods/{method_id}", response_model=TradeMethodResponse)
def update_trade_method(method_id: int, payload: TradeMethodUpdate, db: Session = Depends(get_db)):
    return TradeJournalService(db).update_trade_method(method_id, payload)


@router.get("/trade-journals", response_model=TradeJournalListResponse)
def list_trade_journals(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    stock_name: str | None = Query(default=None),
    stock_theme: str | None = Query(default=None),
    trade_method_id: int | None = Query(default=None),
    result_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return TradeJournalService(db).list_trade_journals(
        start_date=start_date,
        end_date=end_date,
        stock_name=stock_name,
        stock_theme=stock_theme,
        trade_method_id=trade_method_id,
        result_type=result_type,
    )


@router.post("/trade-journals", response_model=TradeJournalDetailResponse)
def create_trade_journal(payload: TradeJournalCreate, db: Session = Depends(get_db)):
    return TradeJournalService(db).create_trade_journal(payload)


@router.get("/trade-journals/{journal_id}", response_model=TradeJournalDetailResponse)
def get_trade_journal(journal_id: int, db: Session = Depends(get_db)):
    return TradeJournalService(db).get_trade_journal(journal_id)


@router.patch("/trade-journals/{journal_id}", response_model=TradeJournalDetailResponse)
def update_trade_journal(journal_id: int, payload: TradeJournalUpdate, db: Session = Depends(get_db)):
    return TradeJournalService(db).update_trade_journal(journal_id, payload)


@router.delete("/trade-journals/{journal_id}", response_model=TradeJournalDeleteResponse)
def delete_trade_journal(journal_id: int, db: Session = Depends(get_db)):
    return TradeJournalService(db).delete_trade_journal(journal_id)


@router.get("/trade-journals/{journal_id}/images", response_model=list[TradeJournalImageResponse])
def list_trade_journal_images(journal_id: int, db: Session = Depends(get_db)):
    return TradeJournalService(db).list_trade_journal_images(journal_id)


@router.post("/trade-journals/{journal_id}/images", response_model=TradeJournalImageResponse)
def create_trade_journal_image(journal_id: int, payload: TradeJournalImageCreate, db: Session = Depends(get_db)):
    return TradeJournalService(db).create_trade_journal_image(journal_id, payload)


@router.post("/trade-journals/{journal_id}/images/upload", response_model=TradeJournalImageResponse)
async def upload_trade_journal_image(
    journal_id: int,
    image_type: str = Form(...),
    image_memo: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    return TradeJournalService(db).upload_trade_journal_image(
        journal_id=journal_id,
        image_type=image_type,
        image_memo=image_memo,
        original_filename=file.filename or "upload.png",
        file_bytes=content,
    )


@router.delete("/trade-journal-images/{image_id}", response_model=TradeJournalDeleteResponse)
def delete_trade_journal_image(image_id: int, db: Session = Depends(get_db)):
    return TradeJournalService(db).delete_trade_journal_image(image_id)


@router.patch("/trade-journal-images/{image_id}", response_model=TradeJournalImageResponse)
def update_trade_journal_image(image_id: int, payload: TradeJournalImageUpdate, db: Session = Depends(get_db)):
    return TradeJournalService(db).update_trade_journal_image(image_id, payload)


@router.get("/trade-journals/calendar/monthly", response_model=list[TradeJournalMonthlyCalendarItem])
def get_trade_journal_calendar_monthly(month: str = Query(...), db: Session = Depends(get_db)):
    return TradeJournalService(db).list_calendar_monthly(month=month)


@router.get("/trade-journals/calendar/daily", response_model=TradeJournalListResponse)
def get_trade_journal_calendar_daily(date: str = Query(...), db: Session = Depends(get_db)):
    return TradeJournalService(db).list_calendar_daily(date=date)


@router.get("/trade-journals/statistics/monthly", response_model=TradeJournalMonthlyStatisticResponse)
def get_trade_journal_statistics_monthly(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    start_month: str | None = Query(default=None),
    end_month: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return TradeJournalService(db).list_statistics_monthly(
        page=page,
        page_size=page_size,
        start_month=start_month,
        end_month=end_month,
    )


@router.get("/trade-journals/{journal_id}/gpt-review-package", response_model=TradeJournalGptReviewPackageResponse)
def get_trade_journal_gpt_review_package(journal_id: int, db: Session = Depends(get_db)):
    return TradeJournalService(db).build_gpt_review_package(journal_id)
