from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.gpt_prompt_template import GptPromptTemplate


class GptPromptTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, domain: str | None = None) -> list[GptPromptTemplate]:
        stmt = select(GptPromptTemplate)
        if domain:
            stmt = stmt.where(GptPromptTemplate.domain == domain)
        stmt = stmt.order_by(GptPromptTemplate.sort_order.asc(), GptPromptTemplate.id.asc())
        return list(self.db.scalars(stmt).all())

    def get_by_key(self, prompt_key: str) -> GptPromptTemplate | None:
        stmt = select(GptPromptTemplate).where(GptPromptTemplate.prompt_key == prompt_key)
        return self.db.scalar(stmt)

    def create_default(
        self,
        *,
        domain: str,
        prompt_key: str,
        prompt_name: str,
        description: str | None,
        prompt_text: str,
        default_prompt_text: str,
        sort_order: int,
    ) -> GptPromptTemplate:
        now = now_kst()
        row = GptPromptTemplate(
            domain=domain,
            prompt_key=prompt_key,
            prompt_name=prompt_name,
            prompt_type=domain,
            description=description,
            template_text=prompt_text,
            prompt_text=prompt_text,
            default_prompt_text=default_prompt_text,
            is_active=1,
            sort_order=sort_order,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, row: GptPromptTemplate, updates: dict[str, object]) -> GptPromptTemplate:
        if "prompt_text" in updates and "template_text" not in updates:
            updates["template_text"] = updates["prompt_text"]
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = now_kst()
        self.db.commit()
        self.db.refresh(row)
        return row
