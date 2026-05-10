from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.disclosure_repository import DisclosureRepository


class DisclosureService:
    def __init__(self, db: Session) -> None:
        self.repo = DisclosureRepository(db)

    def list_disclosures(
        self,
        stock_id: int | None,
        keyword: str | None,
        disclosure_type: str | None,
        limit: int,
        offset: int,
    ):
        return self.repo.list(
            stock_id=stock_id,
            keyword=keyword,
            disclosure_type=disclosure_type,
            limit=limit,
            offset=offset,
        )

    def get_disclosure(self, disclosure_id: int):
        item = self.repo.get_by_id(disclosure_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="disclosure not found")
        return item
