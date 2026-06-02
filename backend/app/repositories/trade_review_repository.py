from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.trade_journal import TradeJournal
from backend.app.entities.trade_journal_image import TradeJournalImage
from backend.app.entities.trade_method import TradeMethod
from backend.app.entities.trade_review import TradeReview
from backend.app.entities.trade_review_check_item import TradeReviewCheckItem
from backend.app.entities.stock import Stock


class TradeReviewRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_journal(self, journal_id: int) -> TradeJournal | None:
        return self.db.get(TradeJournal, journal_id)

    def get_method(self, method_id: int | None) -> TradeMethod | None:
        if method_id is None:
            return None
        return self.db.get(TradeMethod, method_id)

    def get_by_journal_id(self, journal_id: int) -> TradeReview | None:
        stmt = select(TradeReview).where(TradeReview.journal_id == journal_id).order_by(TradeReview.id.desc())
        return self.db.scalars(stmt).first()

    def count_images(self, journal_id: int) -> int:
        stmt = select(func.count()).select_from(TradeJournalImage).where(TradeJournalImage.trade_journal_id == journal_id)
        return int(self.db.scalar(stmt) or 0)

    def list_images(self, journal_id: int) -> list[TradeJournalImage]:
        stmt = (
            select(TradeJournalImage)
            .where(TradeJournalImage.trade_journal_id == journal_id)
            .order_by(TradeJournalImage.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_check_items(self, review_id: int) -> list[TradeReviewCheckItem]:
        stmt = (
            select(TradeReviewCheckItem)
            .where(TradeReviewCheckItem.review_id == review_id)
            .order_by(TradeReviewCheckItem.item_order.asc(), TradeReviewCheckItem.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def count_check_items(self, review_id: int) -> int:
        stmt = select(func.count()).select_from(TradeReviewCheckItem).where(TradeReviewCheckItem.review_id == review_id)
        return int(self.db.scalar(stmt) or 0)

    def list_reviews(
        self,
        *,
        from_date: str,
        to_date: str,
        review_status: str | None,
        trade_grade: str | None,
        result_type: str | None,
        method_id: int | None,
        stock_name: str | None,
        main_mistake: str | None,
        impulse_trade: int | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple], int]:
        image_count_subq = (
            select(
                TradeJournalImage.trade_journal_id.label("journal_id"),
                func.count(TradeJournalImage.id).label("image_count"),
            )
            .group_by(TradeJournalImage.trade_journal_id)
            .subquery()
        )
        review_status_expr = func.coalesce(TradeReview.review_status, "미복기")
        conditions = [
            TradeJournal.buy_date >= from_date,
            TradeJournal.buy_date <= to_date,
        ]
        if review_status:
            conditions.append(review_status_expr == review_status.strip())
        if trade_grade:
            conditions.append(TradeReview.trade_grade == trade_grade.strip())
        if result_type:
            conditions.append(TradeJournal.result_type == result_type.strip())
        if method_id is not None:
            conditions.append(TradeJournal.trade_method_id == method_id)
        if stock_name:
            conditions.append(TradeJournal.stock_name.like(f"%{stock_name.strip()}%"))
        if main_mistake:
            conditions.append(TradeReview.main_mistake == main_mistake.strip())
        if impulse_trade is not None:
            conditions.append(func.coalesce(TradeReview.impulse_trade, 0) == impulse_trade)

        base = (
            select(
                TradeJournal,
                TradeMethod,
                TradeReview,
                func.coalesce(image_count_subq.c.image_count, 0).label("image_count"),
            )
            .outerjoin(TradeMethod, TradeMethod.id == TradeJournal.trade_method_id)
            .outerjoin(TradeReview, TradeReview.journal_id == TradeJournal.id)
            .outerjoin(image_count_subq, image_count_subq.c.journal_id == TradeJournal.id)
            .where(and_(*conditions))
        )
        count_stmt = (
            select(func.count())
            .select_from(TradeJournal)
            .outerjoin(TradeReview, TradeReview.journal_id == TradeJournal.id)
            .where(and_(*conditions))
        )
        stmt = base.order_by(TradeJournal.buy_date.desc(), TradeJournal.id.desc()).offset(offset).limit(limit)
        return list(self.db.execute(stmt).all()), int(self.db.scalar(count_stmt) or 0)

    def upsert_review(self, journal: TradeJournal, payload: dict) -> TradeReview:
        now = now_kst()
        review = self.get_by_journal_id(journal.id)
        if review is None:
            review = TradeReview(
                stock_id=self._resolve_stock_id(journal),
                review_date=now,
                journal_id=journal.id,
                method_id=journal.trade_method_id,
                created_at=now,
                updated_at=now,
                **payload,
            )
        else:
            for key, value in payload.items():
                setattr(review, key, value)
            review.method_id = journal.trade_method_id
            review.updated_at = now
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def create_review(self, journal: TradeJournal) -> TradeReview:
        now = now_kst()
        review = TradeReview(
            stock_id=self._resolve_stock_id(journal),
            review_date=now,
            journal_id=journal.id,
            method_id=journal.trade_method_id,
            review_status="미복기",
            principle_followed="미확인",
            entry_quality="미확인",
            exit_quality="미확인",
            risk_control_quality="미확인",
            emotion_control_quality="미확인",
            impulse_trade=0,
            created_at=now,
            updated_at=now,
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def create_check_items(self, items: list[dict]) -> list[TradeReviewCheckItem]:
        rows = [TradeReviewCheckItem(**item) for item in items]
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def update_check_items(self, items: list[dict]) -> None:
        now = now_kst()
        for item in items:
            item_id = int(item.get("id") or 0)
            if item_id <= 0:
                continue
            row = self.db.get(TradeReviewCheckItem, item_id)
            if row is None:
                continue
            row.is_checked = 1 if bool(item.get("is_checked")) else 0
            note = item.get("note")
            row.note = note.strip() if isinstance(note, str) and note.strip() else None
            row.updated_at = now
            self.db.add(row)
        self.db.commit()

    def _resolve_stock_id(self, journal: TradeJournal) -> int:
        if journal.stock_code:
            stock_id = self.db.scalar(select(Stock.id).where(Stock.stock_code == journal.stock_code.strip()))
            if stock_id:
                return int(stock_id)
        if journal.stock_name:
            stock_id = self.db.scalar(select(Stock.id).where(Stock.stock_name == journal.stock_name.strip()))
            if stock_id:
                return int(stock_id)
        fallback_id = self.db.scalar(select(Stock.id).order_by(Stock.id.asc()).limit(1))
        return int(fallback_id or 0)

    def summarize(self, *, from_date: str, to_date: str) -> dict[str, object]:
        review_status_expr = func.coalesce(TradeReview.review_status, "미복기")
        base_conditions = [
            TradeJournal.buy_date >= from_date,
            TradeJournal.buy_date <= to_date,
        ]
        joined = (
            select(TradeJournal.id, TradeReview)
            .outerjoin(TradeReview, TradeReview.journal_id == TradeJournal.id)
            .where(and_(*base_conditions))
        )
        rows = list(self.db.execute(joined).all())
        total = len(rows)
        reviewed = sum(1 for _, review in rows if review and review.review_status == "복기완료")
        unreviewed = total - reviewed
        principle_followed = sum(1 for _, review in rows if review and review.principle_followed == "지킴")
        principle_violation = sum(
            1 for _, review in rows if review and review.principle_followed in {"일부 위반", "위반"}
        )
        impulse_count = sum(1 for _, review in rows if review and int(review.impulse_trade or 0) == 1)

        grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        mistakes: dict[str, int] = {}
        for _, review in rows:
            if not review:
                continue
            if review.trade_grade in grade_counts:
                grade_counts[review.trade_grade] += 1
            mistake = (review.main_mistake or "").strip()
            if mistake:
                mistakes[mistake] = mistakes.get(mistake, 0) + 1

        top_mistakes = [
            {"name": name, "count": count}
            for name, count in sorted(mistakes.items(), key=lambda item: item[1], reverse=True)[:5]
        ]
        return {
            "total_trades": total,
            "reviewed_count": reviewed,
            "unreviewed_count": unreviewed,
            "review_rate": round((reviewed / total) * 100, 1) if total else 0.0,
            "principle_followed_count": principle_followed,
            "principle_violation_count": principle_violation,
            "impulse_trade_count": impulse_count,
            "grade_counts": grade_counts,
            "top_mistakes": top_mistakes,
        }
