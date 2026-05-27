from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import PROJECT_ROOT, now_kst
from backend.app.repositories.trade_journal_repository import TradeJournalRepository
from backend.app.services.gpt_prompt_template_service import GptPromptTemplateService


class TradeJournalService:
    VALID_RESULT_TYPES = {"profit", "loss", "holding", "break_even"}
    VALID_IMAGE_TYPES = {
        "trade_time_chart",
        "after_trade_chart",
        "buy_chart",
        "sell_chart",
        "one_week_after_chart",
        "review_chart",
    }
    TRADE_SINGLE_REVIEW_FALLBACK_PROMPT = (
        "당신은 데이터 기반 주식 매매 복기 코치입니다.\n"
        "아래 DrCT에셋 매매복기 패키지를 바탕으로 사용자의 매매 판단 과정과 결과를 객관적으로 분석해 주세요.\n"
        "수익 여부보다 매매 원칙 준수 여부를 우선 평가해 주세요.\n"
        "기록에 없는 사실은 추정하지 말고, 데이터가 부족한 항목은 추가 확인 필요로 표시해 주세요.\n"
        "자동 매수/매도 판단이나 향후 종목 추천은 하지 마세요."
    )

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
        self._validate_image_type((data.get("image_type") or "").strip())
        data["trade_journal_id"] = journal_id
        data["created_at"] = now
        created = self.repo.create_trade_journal_image(data)
        return self._to_image_response(created)

    def upload_trade_journal_image(self, journal_id: int, image_type: str, image_memo: str | None, original_filename: str, file_bytes: bytes):
        _ = self.get_trade_journal(journal_id)
        normalized_type = (image_type or "").strip()
        if not normalized_type:
            raise HTTPException(status_code=400, detail="image_type is required")
        self._validate_image_type(normalized_type)
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

    def update_trade_journal_image(self, image_id: int, payload):
        image = self.repo.get_trade_journal_image(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="trade journal image not found")
        updates = payload.model_dump(exclude_unset=True)
        if "image_type" in updates and updates["image_type"] is not None:
            updates["image_type"] = updates["image_type"].strip()
            self._validate_image_type(updates["image_type"])
        if "image_memo" in updates and updates["image_memo"] is not None:
            updates["image_memo"] = updates["image_memo"].strip() or None
        updated = self.repo.update_trade_journal_image(image, updates)
        return self._to_image_response(updated)

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

    def list_statistics_monthly(self, page: int, page_size: int, start_month: str | None = None, end_month: str | None = None):
        rows, total = self.repo.list_statistics_monthly(
            page=page,
            page_size=page_size,
            start_month=start_month,
            end_month=end_month,
        )
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

    def build_gpt_review_package(self, journal_id: int) -> dict[str, object]:
        journal = self.get_trade_journal(journal_id)
        images = [self._to_image_response(image) for image in self.repo.list_trade_journal_images(journal_id)]
        prompt_key = "trade_single_review"
        prompt_text = GptPromptTemplateService(self.db).resolve_active_prompt_text(
            prompt_key,
            self.TRADE_SINGLE_REVIEW_FALLBACK_PROMPT,
        )
        holding_days = None
        if journal.buy_date and journal.sell_date:
            try:
                holding_days = (datetime.fromisoformat(journal.sell_date) - datetime.fromisoformat(journal.buy_date)).days
            except ValueError:
                holding_days = None

        analysis_hint = (
            "이 이미지는 HTS 종목 차트에서 매수시점과 매도시점이 표시된 차트 캡처 이미지일 수 있습니다. "
            "GPT 분석 시 매수 위치, 매도 위치, 지지/저항, 추세, 거래량, 매매기법 준수 여부를 검토하기 위한 핵심 근거로 사용합니다."
        )
        json_data = {
            "trade": {
                "trade_journal_id": journal.id,
                "stock_id": None,
                "stock_code": journal.stock_code,
                "stock_name": journal.stock_name,
                "buy_date": journal.buy_date,
                "sell_date": journal.sell_date,
                "holding_days": holding_days,
                "status": journal.result_type,
                "profit_rate": journal.profit_rate,
                "realized_profit": journal.realized_profit,
            },
            "strategy": {
                "strategy_id": journal.trade_method_id,
                "strategy_name": journal.trade_method_name,
                "core_concept": None,
                "entry_conditions": None,
                "exit_conditions": None,
                "risk_rules": None,
                "checklist": [],
            },
            "theme": {
                "themes": [x.strip() for x in (journal.stock_theme or "").split(",") if x.strip()],
                "primary_theme": None,
            },
            "review": {
                "trade_record": journal.remark,
                "trade_reason": journal.trade_reason,
                "success_reason": journal.success_reason,
                "failure_reason": journal.failure_reason,
                "review_memo": journal.review_memo,
            },
            "images": [
                {
                    "image_id": image["id"],
                    "image_type": image["image_type"],
                    "memo": image.get("image_memo"),
                    "image_url": image.get("image_url"),
                    "static_url": image.get("image_url"),
                    "stored_path": image.get("image_path"),
                    "analysis_hint": analysis_hint,
                }
                for image in images
            ],
        }
        markdown = (
            "# DrCT에셋 GPT 매매복기 패키지\n\n"
            "## 1. 분석 요청\n"
            f"{prompt_text}\n\n"
            "## 2. 매매 기본 정보\n"
            f"- 종목명: {journal.stock_name or '-'}\n"
            f"- 종목코드: {journal.stock_code or '-'}\n"
            f"- 매수일: {journal.buy_date or '-'}\n"
            f"- 매도일: {journal.sell_date or '-'}\n"
            f"- 보유기간: {holding_days if holding_days is not None else '-'}\n"
            f"- 상태: {journal.result_type or '-'}\n"
            f"- 수익률: {journal.profit_rate if journal.profit_rate is not None else '-'}\n"
            f"- 실현손익: {journal.realized_profit if journal.realized_profit is not None else '-'}\n\n"
            "## 3. 매매기법\n"
            f"- 매매기법명: {journal.trade_method_name or '-'}\n"
            "- 핵심 개념: -\n- 진입 조건: -\n- 청산 조건: -\n- 리스크 규칙: -\n\n"
            "## 4. 시장 테마\n"
            f"- 연결 테마: {journal.stock_theme or '-'}\n\n"
            "## 5. 매매 기록\n"
            f"- 매매기록: {journal.remark or '-'}\n"
            f"- 매매 이유: {journal.trade_reason or '-'}\n"
            f"- 성공 사유: {journal.success_reason or '-'}\n"
            f"- 실패 사유: {journal.failure_reason or '-'}\n"
            f"- 복기 메모: {journal.review_memo or '-'}\n\n"
            "## 6. 차트 이미지 자료\n"
            "- 차트 이미지는 HTS에서 매수시점과 매도시점이 표시된 종목 차트 캡처 이미지일 수 있습니다.\n"
            "- 분석 관점: 진입/청산 원칙 준수, 추세, 지지/저항, 거래량, 매매기법 준수 여부\n\n"
            + "\n".join(
                [
                    f"- 이미지유형: {img['image_type']} | 메모: {img.get('image_memo') or '-'} | URL: {img.get('image_url') or '-'} | PATH: {img.get('image_path') or '-'}"
                    for img in images
                ]
            )
            + "\n\n## 7. 구조화 JSON\n```json\n"
            + json.dumps(json_data, ensure_ascii=False, indent=2)
            + "\n```"
        )
        return {
            "package_type": "single_trade_review",
            "trade_journal_id": journal.id,
            "prompt_key": prompt_key,
            "prompt_text": prompt_text,
            "markdown": markdown,
            "json_data": json_data,
        }

    def _validate_result_type(self, result_type: str | None) -> None:
        if result_type is None:
            return
        normalized = result_type.strip()
        if not normalized:
            return
        if normalized not in self.VALID_RESULT_TYPES:
            raise HTTPException(status_code=400, detail=f"invalid result_type: {normalized}")

    def _validate_image_type(self, image_type: str) -> None:
        if image_type not in self.VALID_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail=f"invalid image_type: {image_type}")
