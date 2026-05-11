from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.disclosure_repository import DisclosureRepository
from backend.app.schemas.disclosure_schema import DisclosureResponse


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
        rows = self.repo.list_with_stock(
            stock_id=stock_id,
            keyword=keyword,
            disclosure_type=disclosure_type,
            limit=limit,
            offset=offset,
        )
        result: list[DisclosureResponse] = []
        for disclosure, stock in rows:
            result.append(
                DisclosureResponse.model_validate(
                    {
                        **disclosure.__dict__,
                        "stock_code": stock.stock_code if stock else None,
                        "stock_name": stock.stock_name if stock else None,
                    }
                )
            )
        return result

    def get_disclosure(self, disclosure_id: int):
        item = self.repo.get_by_id(disclosure_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="disclosure not found")
        return item
