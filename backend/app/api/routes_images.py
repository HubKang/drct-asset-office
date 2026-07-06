from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.image_schema import AppImageDeleteResponse, AppImageListResponse, AppImageResponse
from backend.app.services.image_file_service import ImageFileService

router = APIRouter(tags=["images"])


@router.post("/images/upload", response_model=AppImageResponse)
async def upload_image(
    domain: str = Form(...),
    owner_type: str | None = Form(default=None),
    owner_id: int | None = Form(default=None),
    description: str | None = Form(default=None),
    sort_order: int = Form(default=0),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AppImageResponse:
    content = await file.read()
    return ImageFileService(db).save_uploaded_image(
        domain=domain,
        owner_type=owner_type,
        owner_id=owner_id,
        description=description,
        sort_order=sort_order,
        original_filename=file.filename or "image.png",
        content_type=file.content_type,
        file_bytes=content,
    )


@router.get("/images", response_model=AppImageListResponse)
def list_images(
    domain: str | None = None,
    owner_type: str | None = None,
    owner_id: int | None = None,
    db: Session = Depends(get_db),
) -> AppImageListResponse:
    return ImageFileService(db).list_images(domain=domain, owner_type=owner_type, owner_id=owner_id)


@router.delete("/images/{image_id}", response_model=AppImageDeleteResponse)
def delete_image(image_id: int, db: Session = Depends(get_db)) -> AppImageDeleteResponse:
    return ImageFileService(db).delete_image(image_id)
