from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.stock_tracking_schema import (
    CollectStockTrackingPricesRequest,
    CollectStockTrackingPricesResponse,
    RegisterTrackingItemsFromCandidatesRequest,
    RegisterTrackingItemsFromCandidatesResponse,
    StockTrackingGroupAnalysisListResponse,
    StockTrackingGroupCreateRequest,
    StockTrackingGroupResponse,
    StockTrackingGroupUpdateRequest,
    StockTrackingImageListResponse,
    StockTrackingImageResponse,
    StockTrackingItemListResponse,
    StockTrackingItemResponse,
    StockTrackingChartResponse,
    UpdateStockTrackingReviewRequest,
)
from backend.app.services.stock_tracking_service import StockTrackingService

router = APIRouter()


@router.get("/stock-tracking/groups", response_model=list[StockTrackingGroupResponse])
def list_stock_tracking_groups(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[StockTrackingGroupResponse]:
    return StockTrackingService(db).list_groups(active_only=active_only)


@router.post("/stock-tracking/groups", response_model=StockTrackingGroupResponse)
def create_stock_tracking_group(
    payload: StockTrackingGroupCreateRequest,
    db: Session = Depends(get_db),
) -> StockTrackingGroupResponse:
    return StockTrackingService(db).create_group(payload)


@router.put("/stock-tracking/groups/{group_id}", response_model=StockTrackingGroupResponse)
def update_stock_tracking_group(
    group_id: int,
    payload: StockTrackingGroupUpdateRequest,
    db: Session = Depends(get_db),
) -> StockTrackingGroupResponse:
    return StockTrackingService(db).update_group(group_id, payload)


@router.delete("/stock-tracking/groups/{group_id}")
def delete_stock_tracking_group(group_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return StockTrackingService(db).delete_group(group_id)


@router.get("/stock-tracking/items", response_model=StockTrackingItemListResponse)
def list_stock_tracking_items(
    group_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    price_status: str | None = Query(default=None),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> StockTrackingItemListResponse:
    return StockTrackingService(db).list_items(
        group_id=group_id,
        item_status=status,
        price_status=price_status,
        from_date=from_date,
        to_date=to_date,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.post("/stock-tracking/items/from-candidates", response_model=RegisterTrackingItemsFromCandidatesResponse)
def register_stock_tracking_items_from_candidates(
    payload: RegisterTrackingItemsFromCandidatesRequest,
    db: Session = Depends(get_db),
) -> RegisterTrackingItemsFromCandidatesResponse:
    return StockTrackingService(db).register_from_candidates(payload)


@router.get("/stock-tracking/analysis/groups", response_model=StockTrackingGroupAnalysisListResponse)
def list_stock_tracking_group_analysis(
    active_only: bool = Query(default=True),
    group_id: int | None = Query(default=None),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    min_completed_count: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> StockTrackingGroupAnalysisListResponse:
    return StockTrackingService(db).list_group_analysis(
        active_only=active_only,
        group_id=group_id,
        from_date=from_date,
        to_date=to_date,
        min_completed_count=min_completed_count,
    )


@router.post("/stock-tracking/items/collect-prices", response_model=CollectStockTrackingPricesResponse)
def collect_stock_tracking_prices(
    payload: CollectStockTrackingPricesRequest,
    db: Session = Depends(get_db),
) -> CollectStockTrackingPricesResponse:
    return StockTrackingService(db).collect_prices(payload)




@router.get("/stock-tracking/items/{item_id}/images", response_model=StockTrackingImageListResponse)
def list_stock_tracking_item_images(item_id: int, db: Session = Depends(get_db)) -> StockTrackingImageListResponse:
    return StockTrackingService(db).list_images(item_id)


@router.post("/stock-tracking/items/{item_id}/images", response_model=StockTrackingImageResponse)
async def upload_stock_tracking_item_image(
    item_id: int,
    image_type: str = Form(...),
    caption: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> StockTrackingImageResponse:
    content = await file.read()
    return StockTrackingService(db).upload_image(
        item_id=item_id,
        image_type=image_type,
        caption=caption,
        original_filename=file.filename or "upload.png",
        content_type=file.content_type,
        file_bytes=content,
    )


@router.delete("/stock-tracking/images/{image_id}")
def delete_stock_tracking_image(image_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return StockTrackingService(db).delete_image(image_id)


@router.get("/stock-tracking/items/{item_id}", response_model=StockTrackingItemResponse)
def get_stock_tracking_item(item_id: int, db: Session = Depends(get_db)) -> StockTrackingItemResponse:
    return StockTrackingService(db).get_item(item_id)


@router.get("/stock-tracking/items/{item_id}/chart", response_model=StockTrackingChartResponse)
def get_stock_tracking_item_chart(item_id: int, db: Session = Depends(get_db)) -> StockTrackingChartResponse:
    return StockTrackingService(db).get_chart(item_id)


@router.put("/stock-tracking/items/{item_id}/review", response_model=StockTrackingItemResponse)
def update_stock_tracking_item_review(
    item_id: int,
    payload: UpdateStockTrackingReviewRequest,
    db: Session = Depends(get_db),
) -> StockTrackingItemResponse:
    return StockTrackingService(db).update_review(item_id, payload)


@router.delete("/stock-tracking/items/{item_id}")
def delete_stock_tracking_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return StockTrackingService(db).delete_item(item_id)
