from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.gpt_prompt_template_repository import GptPromptTemplateRepository
from backend.app.schemas.gpt_prompt_template_schema import (
    GptPromptTemplateRestoreResponse,
    GptPromptTemplateUpdateRequest,
)
from backend.app.services.gpt_prompt_template_defaults import DEFAULT_GPT_PROMPTS


class GptPromptTemplateService:
    def __init__(self, db: Session) -> None:
        self.repo = GptPromptTemplateRepository(db)

    def ensure_default_templates_exist(self) -> None:
        for row in DEFAULT_GPT_PROMPTS:
            prompt_key = str(row["prompt_key"])
            found = self.repo.get_by_key(prompt_key)
            if found:
                continue
            default_prompt_text = str(row["default_prompt_text"])
            self.repo.create_default(
                domain=str(row["domain"]),
                prompt_key=prompt_key,
                prompt_name=str(row["prompt_name"]),
                description=str(row["description"]),
                prompt_text=default_prompt_text,
                default_prompt_text=default_prompt_text,
                sort_order=int(row["sort_order"]),
            )

    def list_templates(self, domain: str | None = None):
        self.ensure_default_templates_exist()
        return self.repo.list(domain=domain)

    def get_template(self, prompt_key: str):
        self.ensure_default_templates_exist()
        row = self.repo.get_by_key(prompt_key)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gpt prompt template not found")
        return row

    def update_template(self, prompt_key: str, payload: GptPromptTemplateUpdateRequest):
        row = self.get_template(prompt_key)
        updates: dict[str, object] = {}
        if payload.prompt_name is not None:
            updates["prompt_name"] = payload.prompt_name.strip() or row.prompt_name
        if payload.description is not None:
            updates["description"] = payload.description.strip() or None
        if payload.prompt_text is not None:
            updates["prompt_text"] = payload.prompt_text
        if payload.is_active is not None:
            if payload.is_active not in {0, 1}:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="is_active must be 0 or 1")
            updates["is_active"] = payload.is_active
        if payload.sort_order is not None:
            updates["sort_order"] = int(payload.sort_order)
        if not updates:
            return row
        return self.repo.update(row, updates)

    def restore_default(self, prompt_key: str) -> GptPromptTemplateRestoreResponse:
        row = self.get_template(prompt_key)
        updated = self.repo.update(
            row,
            {
                "prompt_text": row.default_prompt_text,
            },
        )
        return GptPromptTemplateRestoreResponse(message="기본 프롬프트로 복원되었습니다.", template=updated)

    def resolve_active_prompt_text(self, prompt_key: str, fallback_text: str) -> str:
        self.ensure_default_templates_exist()
        row = self.repo.get_by_key(prompt_key)
        if row and row.is_active == 1 and row.prompt_text.strip():
            return row.prompt_text
        return fallback_text
