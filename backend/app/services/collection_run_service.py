from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.collection_run_repository import CollectionRunRepository


class CollectionRunService:
    def __init__(self, db: Session) -> None:
        self.repo = CollectionRunRepository(db)

    def list_collection_runs(
        self,
        collector_name: str | None,
        status_value: str | None,
        target: str | None,
        limit: int,
        offset: int,
    ):
        return self.repo.list(
            collector_name=collector_name,
            status=status_value,
            target=target,
            limit=limit,
            offset=offset,
        )

    def get_collection_run(self, run_id: int):
        run = self.repo.get_by_id(run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="collection run not found")
        return run
