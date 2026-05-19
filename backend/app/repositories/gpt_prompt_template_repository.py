from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.gpt_prompt_template import GptPromptTemplate


class GptPromptTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[GptPromptTemplate]:
        stmt = select(GptPromptTemplate).order_by(GptPromptTemplate.id.asc())
        return list(self.db.scalars(stmt).all())

    def get_by_key(self, prompt_key: str) -> GptPromptTemplate | None:
        stmt = select(GptPromptTemplate).where(GptPromptTemplate.prompt_key == prompt_key)
        return self.db.scalar(stmt)

    def create_default(
        self,
        *,
        prompt_key: str,
        prompt_name: str,
        prompt_type: str,
        description: str,
        template_text: str,
    ) -> GptPromptTemplate:
        now = now_kst()
        row = GptPromptTemplate(
            prompt_key=prompt_key,
            prompt_name=prompt_name,
            prompt_type=prompt_type,
            description=description,
            template_text=template_text,
            is_active=1,
            is_default=1,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(
        self,
        row: GptPromptTemplate,
        *,
        prompt_name: str,
        description: str | None,
        template_text: str,
        is_active: int,
    ) -> GptPromptTemplate:
        row.prompt_name = prompt_name
        row.description = description
        row.template_text = template_text
        row.is_active = is_active
        row.version += 1
        row.updated_at = now_kst()
        self.db.commit()
        self.db.refresh(row)
        return row
