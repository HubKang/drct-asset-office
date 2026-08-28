from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo

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

    def delete_disclosures_bulk(self, disclosure_ids: list[int]) -> tuple[int, int]:
        selected = sorted(set(int(disclosure_id) for disclosure_id in disclosure_ids if isinstance(disclosure_id, int) and int(disclosure_id) > 0))
        if not selected:
            return 0, 0
        exclusion_date = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        deleted = self.repo.delete_by_ids_with_exclusion(selected, exclusion_date)
        failed = max(0, len(selected) - deleted)
        return deleted, failed

    def list_collection_targets(self):
        return self.repo.list_collection_targets()
