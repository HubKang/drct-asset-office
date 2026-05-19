from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.gpt_prompt_template_schema import (
    GptPromptTemplateResponse,
    GptPromptTemplateRestoreResponse,
    GptPromptTemplateUpdateRequest,
)
from backend.app.services.gpt_prompt_template_service import GptPromptTemplateService

router = APIRouter()


@router.get("/settings/gpt-prompts", response_model=list[GptPromptTemplateResponse])
def list_gpt_prompt_templates(db: Session = Depends(get_db)) -> list[GptPromptTemplateResponse]:
    return GptPromptTemplateService(db).list_templates()


@router.get("/settings/gpt-prompts/{prompt_key}", response_model=GptPromptTemplateResponse)
def get_gpt_prompt_template(prompt_key: str, db: Session = Depends(get_db)) -> GptPromptTemplateResponse:
    return GptPromptTemplateService(db).get_template(prompt_key)


@router.put("/settings/gpt-prompts/{prompt_key}", response_model=GptPromptTemplateResponse)
def update_gpt_prompt_template(
    prompt_key: str,
    payload: GptPromptTemplateUpdateRequest,
    db: Session = Depends(get_db),
) -> GptPromptTemplateResponse:
    return GptPromptTemplateService(db).update_template(prompt_key, payload)


@router.post("/settings/gpt-prompts/{prompt_key}/restore-default", response_model=GptPromptTemplateRestoreResponse)
def restore_gpt_prompt_template_default(prompt_key: str, db: Session = Depends(get_db)) -> GptPromptTemplateRestoreResponse:
    return GptPromptTemplateService(db).restore_default(prompt_key)
