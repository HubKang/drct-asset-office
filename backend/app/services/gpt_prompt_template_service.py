from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.gpt_prompt_template_repository import GptPromptTemplateRepository
from backend.app.schemas.gpt_prompt_template_schema import (
    GptPromptTemplateRestoreResponse,
    GptPromptTemplateUpdateRequest,
)
from backend.app.services.gpt_prompt_template_defaults import (
    DEFAULT_GPT_PROMPT_DESCRIPTION,
    DEFAULT_GPT_PROMPT_KEY,
    DEFAULT_GPT_PROMPT_NAME,
    DEFAULT_GPT_PROMPT_TEMPLATE_TEXT,
    DEFAULT_GPT_PROMPT_TYPE,
)


class GptPromptTemplateService:
    def __init__(self, db: Session) -> None:
        self.repo = GptPromptTemplateRepository(db)

    def ensure_default_template_exists(self) -> None:
        found = self.repo.get_by_key(DEFAULT_GPT_PROMPT_KEY)
        if found:
            return
        self.repo.create_default(
            prompt_key=DEFAULT_GPT_PROMPT_KEY,
            prompt_name=DEFAULT_GPT_PROMPT_NAME,
            prompt_type=DEFAULT_GPT_PROMPT_TYPE,
            description=DEFAULT_GPT_PROMPT_DESCRIPTION,
            template_text=DEFAULT_GPT_PROMPT_TEMPLATE_TEXT,
        )

    def list_templates(self):
        self.ensure_default_template_exists()
        return self.repo.list()

    def get_template(self, prompt_key: str):
        self.ensure_default_template_exists()
        row = self.repo.get_by_key(prompt_key)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gpt prompt template not found")
        return row

    def update_template(self, prompt_key: str, payload: GptPromptTemplateUpdateRequest):
        row = self.get_template(prompt_key)
        if payload.is_active not in {0, 1}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="is_active must be 0 or 1")
        return self.repo.update(
            row,
            prompt_name=payload.prompt_name.strip(),
            description=payload.description.strip() if payload.description else None,
            template_text=payload.template_text,
            is_active=payload.is_active,
        )

    def restore_default(self, prompt_key: str) -> GptPromptTemplateRestoreResponse:
        row = self.get_template(prompt_key)
        if prompt_key != DEFAULT_GPT_PROMPT_KEY:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="default template is not registered")
        updated = self.repo.update(
            row,
            prompt_name=DEFAULT_GPT_PROMPT_NAME,
            description=DEFAULT_GPT_PROMPT_DESCRIPTION,
            template_text=DEFAULT_GPT_PROMPT_TEMPLATE_TEXT,
            is_active=1,
        )
        return GptPromptTemplateRestoreResponse(message="기본 프롬프트로 복원되었습니다.", template=updated)
