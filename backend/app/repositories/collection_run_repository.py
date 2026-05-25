from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.collection_run import CollectionRun


class CollectionRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _apply_filters(
        stmt: Select,
        collector_name: str | None = None,
        status: str | None = None,
        target: str | None = None,
    ) -> Select:
        if collector_name:
            stmt = stmt.where(CollectionRun.collector_name == collector_name)
        if status:
            stmt = stmt.where(CollectionRun.status == status)
        if target:
            stmt = stmt.where(CollectionRun.target.like(f"%{target}%"))
        return stmt

    def create_running(self, collector_name: str, target: str | None) -> CollectionRun:
        now = now_kst()
        run = CollectionRun(
            collector_name=collector_name,
            target=target,
            status="running",
            started_at=now,
            finished_at=None,
            message=None,
            created_at=now,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_success(self, run: CollectionRun, message: str) -> CollectionRun:
        run.status = "success"
        run.finished_at = now_kst()
        run.message = message
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_failed(self, run: CollectionRun, message: str) -> CollectionRun:
        run.status = "failed"
        run.finished_at = now_kst()
        run.message = message
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_partial(self, run: CollectionRun, message: str) -> CollectionRun:
        run.status = "partial"
        run.finished_at = now_kst()
        run.message = message
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_by_id(self, run_id: int) -> CollectionRun | None:
        return self.db.get(CollectionRun, run_id)

    def list(
        self,
        collector_name: str | None = None,
        status: str | None = None,
        target: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CollectionRun]:
        stmt: Select[tuple[CollectionRun]] = select(CollectionRun)
        stmt = self._apply_filters(stmt, collector_name=collector_name, status=status, target=target)
        stmt = stmt.order_by(CollectionRun.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def count(
        self,
        collector_name: str | None = None,
        status: str | None = None,
        target: str | None = None,
    ) -> int:
        stmt: Select = select(func.count()).select_from(CollectionRun)
        stmt = self._apply_filters(stmt, collector_name=collector_name, status=status, target=target)
        return int(self.db.scalar(stmt) or 0)

    def count_older_than(self, cutoff_datetime: str) -> int:
        stmt: Select = (
            select(func.count())
            .select_from(CollectionRun)
            .where(CollectionRun.created_at < cutoff_datetime)
        )
        return int(self.db.scalar(stmt) or 0)

    def delete_older_than(self, cutoff_datetime: str) -> int:
        targets = list(
            self.db.scalars(
                select(CollectionRun.id).where(CollectionRun.created_at < cutoff_datetime)
            ).all()
        )
        if not targets:
            return 0
        deleted_count = (
            self.db.query(CollectionRun)
            .filter(CollectionRun.id.in_(targets))
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return int(deleted_count or 0)
