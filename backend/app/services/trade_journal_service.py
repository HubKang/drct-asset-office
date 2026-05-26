from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import PROJECT_ROOT, now_kst
from backend.app.repositories.trade_journal_repository import TradeJournalRepository


class TradeJournalService:
    VALID_RESULT_TYPES = {"profit", "loss", "holding", "break_even"}

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TradeJournalRepository(db)

    def list_trade_methods(self, is_active: int | None, keyword: str | None):
        return self.repo.list_trade_methods(is_active=is_active, keyword=keyword)

    def create_trade_method(self, payload):
        now = now_kst()
        data = payload.model_dump()
        data["is_active"] = 1 if data.get("is_active", True) else 0
        data["created_at"] = now
        data["updated_at"] = now
        return self.repo.create_trade_method(data)

    def update_trade_method(self, method_id: int, payload):
        item = self.repo.get_trade_method(method_id)
        if not item:
            raise HTTPException(status_code=404, detail="trade method not found")
        updates = payload.model_dump(exclude_unset=True)
        if "is_active" in updates:
            updates["is_active"] = 1 if updates["is_active"] else 0
        return self.repo.update_trade_method(item, updates)

    def list_trade_journals(
        self,
        start_date: str | None,
        end_date: str | None,
        stock_name: str | None,
        stock_theme: str | None,
        trade_method_id: int | None,
        result_type: str | None,
    ) -> dict[str, object]:
        if not start_date or not end_date:
            today = datetime.now().date()
            start = today - timedelta(days=7)
            start_date = start.isoformat()
            end_date = today.isoformat()
        rows, total_count = self.repo.list_trade_journals(
            start_date=start_date,
            end_date=end_date,
            stock_name=stock_name,
            stock_theme=stock_theme,
            trade_method_id=trade_method_id,
            result_type=result_type,
        )
        items = []
        for journal, image_count in rows:
            items.append(
                {
                    "id": journal.id,
                    "buy_date": journal.buy_date,
                    "sell_date": journal.sell_date,
                    "stock_theme": journal.stock_theme,
                    "trade_method_name": journal.trade_method_name,
                    "stock_code": journal.stock_code,
                    "stock_name": journal.stock_name,
                    "result_type": journal.result_type,
                    "profit_rate": journal.profit_rate,
                    "realized_profit": journal.realized_profit,
                    "image_count": int(image_count or 0),
                    "remark": journal.remark,
                }
            )
        return {"items": items, "total_count": total_count}

    def create_trade_journal(self, payload):
        now = now_kst()
        data = payload.model_dump()
        self._validate_result_type(data.get("result_type"))
        data["created_at"] = now
        data["updated_at"] = now
        return self.repo.create_trade_journal(data)

    def get_trade_journal(self, journal_id: int):
        item = self.repo.get_trade_journal(journal_id)
        if not item:
            raise HTTPException(status_code=404, detail="trade journal not found")
        return item

    def update_trade_journal(self, journal_id: int, payload):
        item = self.repo.get_trade_journal(journal_id)
        if not item:
            raise HTTPException(status_code=404, detail="trade journal not found")
        updates = payload.model_dump(exclude_unset=True)
        if "result_type" in updates:
            self._validate_result_type(updates.get("result_type"))
        return self.repo.update_trade_journal(item, updates)

    def delete_trade_journal(self, journal_id: int) -> dict[str, bool]:
        item = self.repo.get_trade_journal(journal_id)
        if not item:
            raise HTTPException(status_code=404, detail="trade journal not found")
        self.repo.delete_trade_journal(item)
        return {"success": True}

    def list_trade_journal_images(self, journal_id: int):
        _ = self.get_trade_journal(journal_id)
        return [self._to_image_response(image) for image in self.repo.list_trade_journal_images(journal_id)]

    def create_trade_journal_image(self, journal_id: int, payload):
        _ = self.get_trade_journal(journal_id)
        now = now_kst()
        data = payload.model_dump()
        data["trade_journal_id"] = journal_id
        data["created_at"] = now
        created = self.repo.create_trade_journal_image(data)
        return self._to_image_response(created)

    def upload_trade_journal_image(self, journal_id: int, image_type: str, image_memo: str | None, original_filename: str, file_bytes: bytes):
        _ = self.get_trade_journal(journal_id)
        normalized_type = (image_type or "").strip()
        if not normalized_type:
            raise HTTPException(status_code=400, detail="image_type is required")
        if not file_bytes:
            raise HTTPException(status_code=400, detail="empty image file")

        now = datetime.now()
        base_dir = PROJECT_ROOT / "data" / "trade_journal_images" / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
        base_dir.mkdir(parents=True, exist_ok=True)

        extension = Path(original_filename or "").suffix.lower() or ".png"
        filename = f"trade_{journal_id}_{normalized_type}_{uuid4().hex[:8]}{extension}"
        save_path = base_dir / filename
        save_path.write_bytes(file_bytes)

        relative_path = save_path.relative_to(PROJECT_ROOT).as_posix()
        created = self.repo.create_trade_journal_image(
            {
                "trade_journal_id": journal_id,
                "image_type": normalized_type,
                "image_path": relative_path,
                "image_memo": (image_memo or "").strip() or None,
                "original_filename": original_filename or filename,
                "created_at": now_kst(),
            }
        )
        return self._to_image_response(created)

    def delete_trade_journal_image(self, image_id: int) -> dict[str, bool]:
        image = self.repo.get_trade_journal_image(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="trade journal image not found")
        self.repo.delete_trade_journal_image(image)
        return {"success": True}

    def _to_image_response(self, image):
        image_url = None
        if image.image_path:
            normalized = str(image.image_path).replace("\\", "/")
            if normalized.startswith("data/"):
                image_url = f"/static/{normalized[len('data/'):]}"
        return {
            "id": image.id,
            "trade_journal_id": image.trade_journal_id,
            "image_type": image.image_type,
            "image_path": image.image_path,
            "image_url": image_url,
            "image_memo": image.image_memo,
            "original_filename": image.original_filename,
            "created_at": image.created_at,
        }

    def list_calendar_monthly(self, month: str):
        return [
            {"trade_date": d, "trade_count": c, "realized_profit_sum": p}
            for d, c, p in self.repo.list_calendar_monthly(month=month)
        ]

    def list_calendar_daily(self, date: str):
        rows, total_count = self.repo.list_trade_journals(
            start_date=date,
            end_date=date,
            stock_name=None,
            stock_theme=None,
            trade_method_id=None,
            result_type=None,
        )
        items = []
        for journal, image_count in rows:
            items.append(
                {
                    "id": journal.id,
                    "buy_date": journal.buy_date,
                    "sell_date": journal.sell_date,
                    "stock_theme": journal.stock_theme,
                    "trade_method_name": journal.trade_method_name,
                    "stock_code": journal.stock_code,
                    "stock_name": journal.stock_name,
                    "result_type": journal.result_type,
                    "profit_rate": journal.profit_rate,
                    "realized_profit": journal.realized_profit,
                    "image_count": int(image_count or 0),
                    "remark": journal.remark,
                }
            )
        return {"items": items, "total_count": total_count}

    def list_statistics_monthly(self, page: int, page_size: int):
        rows, total = self.repo.list_statistics_monthly(page=page, page_size=page_size)
        items = []
        for r in rows:
            trade_count = int(r.trade_count or 0)
            profit_count = int(r.profit_count or 0)
            loss_count = int(r.loss_count or 0)
            win_rate = round((profit_count / trade_count) * 100, 1) if trade_count > 0 else 0.0
            items.append(
                {
                    "trade_month": str(r.trade_month),
                    "trade_count": trade_count,
                    "profit_count": profit_count,
                    "loss_count": loss_count,
                    "win_rate": win_rate,
                    "realized_profit_sum": int(r.realized_profit_sum or 0),
                    "avg_profit_rate": round(float(r.avg_profit_rate or 0.0), 2),
                }
            )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def _validate_result_type(self, result_type: str | None) -> None:
        if result_type is None:
            return
        normalized = result_type.strip()
        if not normalized:
            return
        if normalized not in self.VALID_RESULT_TYPES:
            raise HTTPException(status_code=400, detail=f"invalid result_type: {normalized}")
