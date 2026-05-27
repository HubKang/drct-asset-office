from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.gpt_prompt_template_schema import (
    GptPromptTemplateResponse,
    GptPromptTemplateRestoreResponse,
    GptPromptTemplateUpdateRequest,
)
from backend.app.services.gpt_prompt_template_service import GptPromptTemplateService

router = APIRouter(tags=["gpt-prompt-templates"])


@router.get("/gpt-prompt-templates", response_model=list[GptPromptTemplateResponse])
def list_gpt_prompt_templates(
    domain: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[GptPromptTemplateResponse]:
    return GptPromptTemplateService(db).list_templates(domain=domain)


@router.get("/gpt-prompt-templates/{prompt_key}", response_model=GptPromptTemplateResponse)
def get_gpt_prompt_template(prompt_key: str, db: Session = Depends(get_db)) -> GptPromptTemplateResponse:
    return GptPromptTemplateService(db).get_template(prompt_key)


@router.patch("/gpt-prompt-templates/{prompt_key}", response_model=GptPromptTemplateResponse)
def update_gpt_prompt_template(
    prompt_key: str,
    payload: GptPromptTemplateUpdateRequest,
    db: Session = Depends(get_db),
) -> GptPromptTemplateResponse:
    return GptPromptTemplateService(db).update_template(prompt_key, payload)


@router.post("/gpt-prompt-templates/{prompt_key}/reset-default", response_model=GptPromptTemplateRestoreResponse)
def reset_gpt_prompt_template_default(prompt_key: str, db: Session = Depends(get_db)) -> GptPromptTemplateRestoreResponse:
    return GptPromptTemplateService(db).restore_default(prompt_key)
