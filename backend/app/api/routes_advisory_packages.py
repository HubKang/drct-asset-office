from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.advisory_package_schema import AdvisoryPackageGenerateRequest, AdvisoryPackageGenerateResponse
from backend.app.services.advisory_package_service import AdvisoryPackageService

router = APIRouter()


@router.post("/advisory-packages/generate", response_model=AdvisoryPackageGenerateResponse)
def generate_advisory_package(
    payload: AdvisoryPackageGenerateRequest,
    db: Session = Depends(get_db),
) -> AdvisoryPackageGenerateResponse:
    return AdvisoryPackageService(db).generate_package(
        stock_id=payload.stock_id,
        news_ids=payload.news_ids,
        disclosure_ids=payload.disclosure_ids,
        title=payload.title,
        purpose=payload.purpose,
        package_type=payload.package_type,
    )
