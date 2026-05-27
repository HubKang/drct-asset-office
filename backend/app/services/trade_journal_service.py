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
    TRADE_MONTHLY_REVIEW_FALLBACK_PROMPT = (
        "당신은 데이터 기반 주식 매매 복기 코치입니다.\n"
        "아래 월간 매매복기 패키지를 바탕으로 월간 매매 습관, 원칙 준수, 반복 실패 패턴을 분석해 주세요.\n"
        "수익 자체보다 재현 가능한 원칙 준수와 리스크 관리 관점으로 평가해 주세요.\n"
        "기록에 없는 사실은 추정하지 말고, 데이터 부족 항목은 추가 확인 필요로 표시해 주세요.\n"
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

    def build_monthly_gpt_review_package(self, year: int, month: int) -> dict[str, object]:
        month_start = f"{year}-{month:02d}-01"
        month_end = f"{year}-{month:02d}-31"
        period_label = f"{year}-{month:02d}"
        rows, _ = self.repo.list_trade_journals(
            start_date=month_start,
            end_date=month_end,
            stock_name=None,
            stock_theme=None,
            trade_method_id=None,
            result_type=None,
        )
        prompt_key = "trade_monthly_review"
        prompt_text = GptPromptTemplateService(self.db).resolve_active_prompt_text(
            prompt_key,
            self.TRADE_MONTHLY_REVIEW_FALLBACK_PROMPT,
        )

        trade_items: list[dict[str, object]] = []
        success_reasons: list[str] = []
        failure_reasons: list[str] = []
        review_memos: list[str] = []
        trade_reasons: list[str] = []
        strategy_bucket: dict[str, dict[str, object]] = {}
        theme_bucket: dict[str, dict[str, object]] = {}
        total_image_count = 0
        chart_image_count = 0
        chart_image_memos: list[str] = []

        for journal, image_count in rows:
            images = self.repo.list_trade_journal_images(journal.id)
            total_image_count += len(images)
            chart_images = [img for img in images if img.image_type in self.VALID_IMAGE_TYPES]
            chart_image_count += len(chart_images)
            chart_image_hints = [img.image_memo for img in chart_images if img.image_memo]
            chart_image_memos.extend([memo for memo in chart_image_hints if memo])

            holding_days = None
            if journal.buy_date and journal.sell_date:
                try:
                    holding_days = (datetime.fromisoformat(journal.sell_date) - datetime.fromisoformat(journal.buy_date)).days
                except ValueError:
                    holding_days = None

            themes = [x.strip() for x in (journal.stock_theme or "").split(",") if x.strip()]
            status = journal.result_type or ""
            profit_rate = self._safe_float(journal.profit_rate)
            realized_profit = int(journal.realized_profit or 0)
            is_closed = status != "holding" and journal.sell_date is not None
            is_win = (status == "profit") or (profit_rate is not None and profit_rate > 0)
            is_loss = (status == "loss") or (profit_rate is not None and profit_rate < 0)

            if journal.success_reason:
                success_reasons.append(journal.success_reason)
            if journal.failure_reason:
                failure_reasons.append(journal.failure_reason)
            if journal.review_memo:
                review_memos.append(journal.review_memo)
            if journal.trade_reason:
                trade_reasons.append(journal.trade_reason)

            trade_items.append(
                {
                    "trade_journal_id": journal.id,
                    "stock_id": None,
                    "stock_code": journal.stock_code,
                    "stock_name": journal.stock_name,
                    "buy_date": journal.buy_date,
                    "sell_date": journal.sell_date,
                    "holding_days": holding_days,
                    "status": status,
                    "profit_rate": profit_rate,
                    "realized_profit": realized_profit,
                    "strategy_name": journal.trade_method_name,
                    "themes": themes,
                    "trade_reason": journal.trade_reason,
                    "success_reason": journal.success_reason,
                    "failure_reason": journal.failure_reason,
                    "review_memo": journal.review_memo,
                    "image_count": int(image_count or 0),
                    "chart_image_hints": chart_image_hints,
                }
            )

            strategy_key = str(journal.trade_method_id or f"name:{journal.trade_method_name or '미분류'}")
            if strategy_key not in strategy_bucket:
                strategy_bucket[strategy_key] = {
                    "strategy_id": journal.trade_method_id,
                    "strategy_name": journal.trade_method_name or "미분류",
                    "trade_count": 0,
                    "closed_count": 0,
                    "win_count": 0,
                    "loss_count": 0,
                    "total_realized_profit": 0,
                    "profit_rates": [],
                }
            strategy_row = strategy_bucket[strategy_key]
            strategy_row["trade_count"] = int(strategy_row["trade_count"]) + 1
            strategy_row["total_realized_profit"] = int(strategy_row["total_realized_profit"]) + realized_profit
            if is_closed:
                strategy_row["closed_count"] = int(strategy_row["closed_count"]) + 1
            if is_win:
                strategy_row["win_count"] = int(strategy_row["win_count"]) + 1
            if is_loss:
                strategy_row["loss_count"] = int(strategy_row["loss_count"]) + 1
            if profit_rate is not None:
                cast_list = strategy_row["profit_rates"]
                if isinstance(cast_list, list):
                    cast_list.append(profit_rate)

            theme_names = themes if themes else ["미분류"]
            for theme_name in theme_names:
                if theme_name not in theme_bucket:
                    theme_bucket[theme_name] = {
                        "theme_id": None,
                        "theme_name": theme_name,
                        "trade_count": 0,
                        "closed_count": 0,
                        "win_count": 0,
                        "loss_count": 0,
                        "total_realized_profit": 0,
                        "profit_rates": [],
                    }
                theme_row = theme_bucket[theme_name]
                theme_row["trade_count"] = int(theme_row["trade_count"]) + 1
                theme_row["total_realized_profit"] = int(theme_row["total_realized_profit"]) + realized_profit
                if is_closed:
                    theme_row["closed_count"] = int(theme_row["closed_count"]) + 1
                if is_win:
                    theme_row["win_count"] = int(theme_row["win_count"]) + 1
                if is_loss:
                    theme_row["loss_count"] = int(theme_row["loss_count"]) + 1
                if profit_rate is not None:
                    cast_theme_rates = theme_row["profit_rates"]
                    if isinstance(cast_theme_rates, list):
                        cast_theme_rates.append(profit_rate)

        all_profit_rates = [self._safe_float(x.get("profit_rate")) for x in trade_items]
        valid_profit_rates = [x for x in all_profit_rates if x is not None]
        closed_trades = [x for x in trade_items if (x.get("status") != "holding" and x.get("sell_date"))]
        win_count = len([x for x in trade_items if self._is_win(x.get("status"), self._safe_float(x.get("profit_rate")))])
        loss_count = len([x for x in trade_items if self._is_loss(x.get("status"), self._safe_float(x.get("profit_rate")))])
        total_realized_profit = sum(int(x.get("realized_profit") or 0) for x in trade_items)

        by_strategy = [self._finalize_group_row(x, "strategy") for x in strategy_bucket.values()]
        by_theme = [self._finalize_group_row(x, "theme") for x in theme_bucket.values()]
        by_strategy.sort(key=lambda x: (x["trade_count"], x["total_realized_profit"]), reverse=True)
        by_theme.sort(key=lambda x: (x["trade_count"], x["total_realized_profit"]), reverse=True)

        sortable = [x for x in trade_items if self._safe_float(x.get("profit_rate")) is not None]
        best_trades = sorted(sortable, key=lambda x: float(x.get("profit_rate") or 0), reverse=True)[:5]
        worst_trades = sorted(sortable, key=lambda x: float(x.get("profit_rate") or 0))[:5]

        image_analysis_hint = (
            "사용자가 업로드한 차트 이미지는 HTS 종목 차트에서 매수시점과 매도시점이 표시된 캡처 이미지일 수 있습니다. "
            "이번 월간 복기에서는 이미지 자체를 직접 분석하지 않더라도, 개별 거래의 차트 이미지 메모와 이미지 존재 여부를 근거로 "
            "매수·매도 타이밍, 지지/저항, 추세, 거래량, 매매기법 준수 여부를 추가 확인 대상으로 분류합니다."
        )
        summary = {
            "year": year,
            "month": month,
            "period_label": period_label,
            "aggregation_basis": "buy_date 기준",
            "total_trades": len(trade_items),
            "closed_trades": len(closed_trades),
            "holding_trades": len([x for x in trade_items if x.get("status") == "holding"]),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round((win_count / len(closed_trades)) * 100, 2) if closed_trades else 0.0,
            "total_realized_profit": total_realized_profit,
            "average_profit_rate": round(sum(valid_profit_rates) / len(valid_profit_rates), 4) if valid_profit_rates else 0.0,
            "best_profit_rate": max(valid_profit_rates) if valid_profit_rates else None,
            "worst_profit_rate": min(valid_profit_rates) if valid_profit_rates else None,
        }
        json_data = {
            "summary": summary,
            "trades": trade_items,
            "by_strategy": by_strategy,
            "by_theme": by_theme,
            "best_trades": best_trades,
            "worst_trades": worst_trades,
            "review_text_sources": {
                "success_reasons": success_reasons,
                "failure_reasons": failure_reasons,
                "review_memos": review_memos,
                "trade_reasons": trade_reasons,
            },
            "chart_image_summary": {
                "total_image_count": total_image_count,
                "chart_image_count": chart_image_count,
                "chart_image_memos": chart_image_memos,
                "image_analysis_hint": image_analysis_hint,
            },
        }
        markdown = self._build_monthly_markdown(
            prompt_text=prompt_text,
            period_label=period_label,
            summary=summary,
            by_strategy=by_strategy,
            by_theme=by_theme,
            best_trades=best_trades,
            worst_trades=worst_trades,
            success_reasons=success_reasons,
            failure_reasons=failure_reasons,
            review_memos=review_memos,
            trade_reasons=trade_reasons,
            chart_image_summary=json_data["chart_image_summary"],
            json_data=json_data,
        )
        return {
            "package_type": "monthly_trade_review",
            "year": year,
            "month": month,
            "period_label": period_label,
            "prompt_key": prompt_key,
            "prompt_text": prompt_text,
            "markdown": markdown,
            "json_data": json_data,
        }

    def _safe_float(self, value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _is_win(self, status: object, profit_rate: float | None) -> bool:
        return status == "profit" or (profit_rate is not None and profit_rate > 0)

    def _is_loss(self, status: object, profit_rate: float | None) -> bool:
        return status == "loss" or (profit_rate is not None and profit_rate < 0)

    def _finalize_group_row(self, row: dict[str, object], group_type: str) -> dict[str, object]:
        profit_rates = [float(x) for x in row.get("profit_rates", []) if isinstance(x, (int, float))]
        closed_count = int(row["closed_count"])
        win_count = int(row["win_count"])
        result = {
            f"{group_type}_id": row.get(f"{group_type}_id"),
            f"{group_type}_name": row.get(f"{group_type}_name"),
            "trade_count": int(row["trade_count"]),
            "closed_count": closed_count,
            "win_count": win_count,
            "loss_count": int(row["loss_count"]),
            "win_rate": round((win_count / closed_count) * 100, 2) if closed_count > 0 else 0.0,
            "total_realized_profit": int(row["total_realized_profit"]),
            "average_profit_rate": round(sum(profit_rates) / len(profit_rates), 4) if profit_rates else 0.0,
        }
        if group_type == "strategy":
            result["best_profit_rate"] = max(profit_rates) if profit_rates else None
            result["worst_profit_rate"] = min(profit_rates) if profit_rates else None
        return result

    def _build_monthly_markdown(
        self,
        *,
        prompt_text: str,
        period_label: str,
        summary: dict[str, object],
        by_strategy: list[dict[str, object]],
        by_theme: list[dict[str, object]],
        best_trades: list[dict[str, object]],
        worst_trades: list[dict[str, object]],
        success_reasons: list[str],
        failure_reasons: list[str],
        review_memos: list[str],
        trade_reasons: list[str],
        chart_image_summary: dict[str, object],
        json_data: dict[str, object],
    ) -> str:
        strategy_lines = [
            f"- {x.get('strategy_name')}: 거래 {x.get('trade_count')} / 승률 {x.get('win_rate')}% / 평균수익률 {x.get('average_profit_rate')} / 총손익 {x.get('total_realized_profit')}"
            for x in by_strategy
        ] or ["- 데이터 없음"]
        theme_lines = [
            f"- {x.get('theme_name')}: 거래 {x.get('trade_count')} / 승률 {x.get('win_rate')}% / 평균수익률 {x.get('average_profit_rate')} / 총손익 {x.get('total_realized_profit')}"
            for x in by_theme
        ] or ["- 데이터 없음"]
        best_lines = [
            f"- #{x.get('trade_journal_id')} {x.get('stock_name')} ({x.get('stock_code')}) / 수익률 {x.get('profit_rate')} / 실현손익 {x.get('realized_profit')}"
            for x in best_trades
        ] or ["- 데이터 없음"]
        worst_lines = [
            f"- #{x.get('trade_journal_id')} {x.get('stock_name')} ({x.get('stock_code')}) / 수익률 {x.get('profit_rate')} / 실현손익 {x.get('realized_profit')}"
            for x in worst_trades
        ] or ["- 데이터 없음"]

        def list_or_empty(items: list[str]) -> str:
            return "\n".join([f"- {x}" for x in items]) if items else "- 없음"

        return (
            "# DrCT에셋 월간 GPT 매매복기 패키지\n\n"
            "## 1. 분석 요청\n"
            f"{prompt_text}\n\n"
            "## 2. 월간 요약\n"
            f"- 기간: {period_label}\n"
            f"- 집계 기준: {summary.get('aggregation_basis')}\n"
            f"- 총 거래 수: {summary.get('total_trades')}\n"
            f"- 종료 거래 수: {summary.get('closed_trades')}\n"
            f"- 보유중 거래 수: {summary.get('holding_trades')}\n"
            f"- 익절 수: {summary.get('win_count')}\n"
            f"- 손절 수: {summary.get('loss_count')}\n"
            f"- 승률: {summary.get('win_rate')}%\n"
            f"- 총 실현손익: {summary.get('total_realized_profit')}\n"
            f"- 평균 수익률: {summary.get('average_profit_rate')}\n"
            f"- 최고 수익률: {summary.get('best_profit_rate')}\n"
            f"- 최저 수익률: {summary.get('worst_profit_rate')}\n\n"
            "## 3. 매매기법별 성과\n"
            + "\n".join(strategy_lines)
            + "\n\n## 4. 테마별 성과\n"
            + "\n".join(theme_lines)
            + "\n\n## 5. 수익 상위 거래\n"
            + "\n".join(best_lines)
            + "\n\n## 6. 손실 하위 거래\n"
            + "\n".join(worst_lines)
            + "\n\n## 7. 성공 사유 / 실패 사유 / 복기 메모 원문\n"
            + "### 성공 사유\n"
            + list_or_empty(success_reasons)
            + "\n### 실패 사유\n"
            + list_or_empty(failure_reasons)
            + "\n### 복기 메모\n"
            + list_or_empty(review_memos)
            + "\n### 매매 이유\n"
            + list_or_empty(trade_reasons)
            + "\n\n## 8. 차트 이미지 참고 정보\n"
            f"- 이미지 수: {chart_image_summary.get('total_image_count')}\n"
            f"- 차트 이미지 수: {chart_image_summary.get('chart_image_count')}\n"
            f"- 분석 힌트: {chart_image_summary.get('image_analysis_hint')}\n"
            "\n## 9. 구조화 JSON\n```json\n"
            + json.dumps(json_data, ensure_ascii=False, indent=2)
            + "\n```"
        )

    def build_trade_method_gpt_guide_package(self, method_id: int) -> dict[str, object]:
        method = self.repo.get_trade_method(method_id)
        if not method:
            raise HTTPException(status_code=404, detail="trade method not found")

        rows, _ = self.repo.list_trade_journals(
            start_date="2000-01-01",
            end_date="2099-12-31",
            stock_name=None,
            stock_theme=None,
            trade_method_id=method_id,
            result_type=None,
        )
        prompt_key = "strategy_performance_review"
        fallback_prompt = (
            "당신은 데이터 기반 매매기법 개선 코치입니다.\n"
            "이 매매기법을 앞으로도 반복 사용할 예정입니다.\n"
            "수익 거래와 손실 거래를 비교하여 이 기법을 더 잘 쓰기 위한 개선 가이드를 작성해 주세요.\n"
            "수익률만 평가하지 말고 진입 조건 준수, 제외 조건, 손절/익절 기준, 차트 위치, 거래량, 테마 적합성을 중심으로 분석해 주세요.\n"
            "자동 매수/매도 추천은 하지 마세요."
        )
        prompt_text = GptPromptTemplateService(self.db).resolve_active_prompt_text(prompt_key, fallback_prompt)

        strategy_info = {
            "method_id": method.id,
            "strategy_name": method.method_name,
            "description": method.description,
            "core_concept": method.description,
            "entry_conditions": method.entry_rule,
            "exit_conditions": method.exit_rule,
            "risk_rules": method.stop_loss_rule,
            "checklist": self._parse_checklist(method.entry_rule),
            "market_environment": self._extract_market_environment(method.description),
            "is_active": method.is_active,
        }
        trade_items: list[dict[str, object]] = []
        success_reasons: list[str] = []
        failure_reasons: list[str] = []
        review_memos: list[str] = []
        trade_reasons: list[str] = []
        theme_bucket: dict[str, dict[str, object]] = {}
        total_image_count = 0
        chart_image_count = 0
        holding_days_values: list[int] = []

        for journal, image_count in rows:
            images = self.repo.list_trade_journal_images(journal.id)
            total_image_count += len(images)
            chart_images = [img for img in images if img.image_type in self.VALID_IMAGE_TYPES]
            chart_image_count += len(chart_images)
            hints = [img.image_memo for img in chart_images if img.image_memo]

            holding_days = None
            if journal.buy_date and journal.sell_date:
                try:
                    holding_days = (datetime.fromisoformat(journal.sell_date) - datetime.fromisoformat(journal.buy_date)).days
                except ValueError:
                    holding_days = None
            if holding_days is not None:
                holding_days_values.append(holding_days)

            themes = [x.strip() for x in (journal.stock_theme or "").split(",") if x.strip()]
            status = journal.result_type or ""
            profit_rate = self._safe_float(journal.profit_rate)
            realized_profit = int(journal.realized_profit or 0)
            is_closed = status != "holding" and journal.sell_date is not None
            is_win = self._is_win(status, profit_rate)
            is_loss = self._is_loss(status, profit_rate)

            if journal.success_reason:
                success_reasons.append(journal.success_reason)
            if journal.failure_reason:
                failure_reasons.append(journal.failure_reason)
            if journal.review_memo:
                review_memos.append(journal.review_memo)
            if journal.trade_reason:
                trade_reasons.append(journal.trade_reason)

            trade_items.append(
                {
                    "trade_journal_id": journal.id,
                    "stock_id": None,
                    "stock_code": journal.stock_code,
                    "stock_name": journal.stock_name,
                    "buy_date": journal.buy_date,
                    "sell_date": journal.sell_date,
                    "holding_days": holding_days,
                    "status": status,
                    "profit_rate": profit_rate,
                    "realized_profit": realized_profit,
                    "themes": themes,
                    "trade_reason": journal.trade_reason,
                    "success_reason": journal.success_reason,
                    "failure_reason": journal.failure_reason,
                    "review_memo": journal.review_memo,
                    "image_count": int(image_count or 0),
                    "chart_image_hints": hints,
                    "_is_closed": is_closed,
                    "_is_win": is_win,
                    "_is_loss": is_loss,
                }
            )

            for theme_name in (themes if themes else ["미분류"]):
                if theme_name not in theme_bucket:
                    theme_bucket[theme_name] = {
                        "theme_id": None,
                        "theme_name": theme_name,
                        "trade_count": 0,
                        "closed_count": 0,
                        "win_count": 0,
                        "loss_count": 0,
                        "total_realized_profit": 0,
                        "profit_rates": [],
                    }
                row = theme_bucket[theme_name]
                row["trade_count"] = int(row["trade_count"]) + 1
                row["total_realized_profit"] = int(row["total_realized_profit"]) + realized_profit
                if is_closed:
                    row["closed_count"] = int(row["closed_count"]) + 1
                if is_win:
                    row["win_count"] = int(row["win_count"]) + 1
                if is_loss:
                    row["loss_count"] = int(row["loss_count"]) + 1
                if profit_rate is not None and isinstance(row["profit_rates"], list):
                    row["profit_rates"].append(profit_rate)

        trade_items.sort(key=lambda x: (str(x.get("buy_date") or ""), int(x.get("trade_journal_id") or 0)), reverse=True)
        closed_items = [x for x in trade_items if bool(x.get("_is_closed"))]
        win_count = len([x for x in trade_items if bool(x.get("_is_win"))])
        loss_count = len([x for x in trade_items if bool(x.get("_is_loss"))])
        realized_total = sum(int(x.get("realized_profit") or 0) for x in trade_items)
        valid_rates = [self._safe_float(x.get("profit_rate")) for x in trade_items if self._safe_float(x.get("profit_rate")) is not None]
        by_theme = [self._finalize_group_row(x, "theme") for x in theme_bucket.values()]
        by_theme.sort(key=lambda x: (x["trade_count"], x["total_realized_profit"]), reverse=True)
        sortable = [x for x in trade_items if self._safe_float(x.get("profit_rate")) is not None]
        winning_trades = sorted(sortable, key=lambda x: float(x.get("profit_rate") or 0), reverse=True)[:5]
        losing_trades = sorted(sortable, key=lambda x: float(x.get("profit_rate") or 0))[:5]
        summary = {
            "trade_count": len(trade_items),
            "closed_trades": len(closed_items),
            "holding_trades": len([x for x in trade_items if not bool(x.get("_is_closed"))]),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round((win_count / len(closed_items)) * 100, 2) if closed_items else 0.0,
            "total_realized_profit": realized_total,
            "average_profit_rate": round(sum(valid_rates) / len(valid_rates), 4) if valid_rates else 0.0,
            "best_profit_rate": max(valid_rates) if valid_rates else None,
            "worst_profit_rate": min(valid_rates) if valid_rates else None,
            "average_holding_days": round(sum(holding_days_values) / len(holding_days_values), 2) if holding_days_values else None,
            "aggregation_basis": "선택한 매매기법으로 연결된 매매일지 기준",
        }
        image_analysis_hint = (
            "사용자가 업로드한 차트 이미지는 HTS 종목 차트에서 매수시점과 매도시점이 표시된 캡처 이미지일 수 있습니다. "
            "이 매매기법 개선 가이드에서는 차트 이미지 메모와 이미지 존재 여부를 근거로, 해당 기법의 진입 조건이 실제 차트 위치에서 잘 지켜졌는지, "
            "매도 기준이 준수되었는지, 추세/지지/저항/거래량 관점에서 기법 적용이 적절했는지를 추가 확인 대상으로 분류합니다."
        )
        clean = lambda xs: [{k: v for k, v in row.items() if not str(k).startswith("_")} for row in xs]
        json_data = {
            "strategy": strategy_info,
            "summary": summary,
            "trades": clean(trade_items),
            "winning_trades": clean(winning_trades),
            "losing_trades": clean(losing_trades),
            "review_text_sources": {
                "success_reasons": success_reasons,
                "failure_reasons": failure_reasons,
                "review_memos": review_memos,
                "trade_reasons": trade_reasons,
            },
            "by_theme": by_theme,
            "guide_focus": {
                "success_conditions_to_repeat": [],
                "failure_conditions_to_avoid": [],
                "entry_rule_improvements": [],
                "exclusion_rule_candidates": [],
                "stop_loss_rule_review": [],
                "profit_taking_rule_review": [],
                "next_trade_checklist": [],
                "next_10_trades_test_plan": [],
            },
            "chart_image_summary": {
                "total_image_count": total_image_count,
                "chart_image_count": chart_image_count,
                "image_analysis_hint": image_analysis_hint,
            },
        }
        markdown = self._build_strategy_guide_markdown(
            prompt_text=prompt_text,
            strategy=strategy_info,
            summary=summary,
            trades=json_data["trades"],
            winning_trades=json_data["winning_trades"],
            losing_trades=json_data["losing_trades"],
            by_theme=by_theme,
            review_text_sources=json_data["review_text_sources"],
            chart_image_summary=json_data["chart_image_summary"],
            json_data=json_data,
        )
        return {
            "package_type": "strategy_improvement_guide",
            "method_id": method.id,
            "prompt_key": prompt_key,
            "prompt_text": prompt_text,
            "markdown": markdown,
            "json_data": json_data,
        }

    def build_failure_pattern_gpt_review_package(
        self,
        *,
        from_date: str | None,
        to_date: str | None,
        method_id: int | None,
        theme_id: int | None,
        limit: int,
    ) -> dict[str, object]:
        today = datetime.now().date()
        parsed_to = self._parse_iso_date(to_date) if to_date else today
        parsed_from = self._parse_iso_date(from_date) if from_date else (parsed_to - timedelta(days=90))
        if parsed_from > parsed_to:
            raise HTTPException(status_code=400, detail="from_date must be less than or equal to to_date")

        rows, _ = self.repo.list_trade_journals(
            start_date=parsed_from.isoformat(),
            end_date=parsed_to.isoformat(),
            stock_name=None,
            stock_theme=None,
            trade_method_id=method_id,
            result_type=None,
        )
        prompt_key = "failure_pattern_review"
        fallback_prompt = (
            "당신은 데이터 기반 주식 매매 복기 코치입니다.\n"
            "아래는 손실 거래, 손절 거래, 실패 사유가 기록된 거래를 모은 실패 패턴 분석 패키지입니다.\n"
            "사용자를 비난하지 말고 반복되는 행동 패턴과 개선 가능한 체크리스트 중심으로 분석해 주세요.\n"
            "기록에 없는 심리 상태는 단정하지 말고 데이터가 부족한 항목은 추가 확인 필요로 표시해 주세요.\n"
            "향후 종목 추천이나 매수/매도 지시는 하지 마세요."
        )
        prompt_text = GptPromptTemplateService(self.db).resolve_active_prompt_text(prompt_key, fallback_prompt)

        total_trades_in_period = len(rows)
        failure_rows: list[dict[str, object]] = []
        by_method_bucket: dict[str, dict[str, object]] = {}
        by_theme_bucket: dict[str, dict[str, object]] = {}
        failure_reasons: list[str] = []
        review_memos: list[str] = []
        trade_reasons: list[str] = []
        total_image_count = 0
        chart_image_count = 0
        chart_image_hints: list[str] = []
        holding_days_values: list[int] = []

        loss_status_count = 0
        negative_profit_count = 0
        failure_reason_count = 0

        for journal, image_count in rows:
            status = str(journal.result_type or "").strip().lower()
            profit_rate = self._safe_float(journal.profit_rate)
            realized_profit = int(journal.realized_profit or 0)
            has_failure_reason = bool((journal.failure_reason or "").strip())
            loss_by_status = status in {"loss", "손절"}
            loss_by_profit_rate = profit_rate is not None and profit_rate < 0
            include_failure = loss_by_status or loss_by_profit_rate or has_failure_reason
            if not include_failure:
                continue

            if loss_by_status:
                loss_status_count += 1
            if loss_by_profit_rate:
                negative_profit_count += 1
            if has_failure_reason:
                failure_reason_count += 1

            images = self.repo.list_trade_journal_images(journal.id)
            total_image_count += len(images)
            chart_images = [img for img in images if img.image_type in self.VALID_IMAGE_TYPES]
            chart_image_count += len(chart_images)
            image_hints = [img.image_memo for img in chart_images if img.image_memo]
            chart_image_hints.extend(image_hints)

            holding_days = None
            if journal.buy_date and journal.sell_date:
                try:
                    holding_days = (datetime.fromisoformat(journal.sell_date) - datetime.fromisoformat(journal.buy_date)).days
                except ValueError:
                    holding_days = None
            if holding_days is not None:
                holding_days_values.append(holding_days)

            if journal.failure_reason:
                failure_reasons.append(journal.failure_reason)
            if journal.review_memo:
                review_memos.append(journal.review_memo)
            if journal.trade_reason:
                trade_reasons.append(journal.trade_reason)

            themes = [x.strip() for x in (journal.stock_theme or "").split(",") if x.strip()]
            failure_item = {
                "trade_journal_id": journal.id,
                "stock_id": None,
                "stock_code": journal.stock_code,
                "stock_name": journal.stock_name,
                "buy_date": journal.buy_date,
                "sell_date": journal.sell_date,
                "holding_days": holding_days,
                "status": journal.result_type,
                "profit_rate": profit_rate,
                "realized_profit": realized_profit,
                "method_id": journal.trade_method_id,
                "method_name": journal.trade_method_name,
                "themes": themes,
                "trade_reason": journal.trade_reason,
                "success_reason": journal.success_reason,
                "failure_reason": journal.failure_reason,
                "review_memo": journal.review_memo,
                "image_count": int(image_count or 0),
                "chart_image_hints": image_hints,
                "failure_classification": {
                    "loss_by_status": loss_by_status,
                    "loss_by_profit_rate": loss_by_profit_rate,
                    "has_failure_reason": has_failure_reason,
                    "failure_reason_only": has_failure_reason and not loss_by_status and not loss_by_profit_rate,
                },
            }
            failure_rows.append(failure_item)

            method_key = str(journal.trade_method_id or f"name:{journal.trade_method_name or '미분류'}")
            if method_key not in by_method_bucket:
                by_method_bucket[method_key] = {
                    "method_id": journal.trade_method_id,
                    "method_name": journal.trade_method_name or "미분류",
                    "failure_trade_count": 0,
                    "loss_status_count": 0,
                    "negative_profit_count": 0,
                    "loss_rates": [],
                    "total_loss_amount": 0,
                    "failure_reasons": [],
                }
            m_row = by_method_bucket[method_key]
            m_row["failure_trade_count"] = int(m_row["failure_trade_count"]) + 1
            m_row["total_loss_amount"] = int(m_row["total_loss_amount"]) + min(realized_profit, 0)
            if loss_by_status:
                m_row["loss_status_count"] = int(m_row["loss_status_count"]) + 1
            if loss_by_profit_rate:
                m_row["negative_profit_count"] = int(m_row["negative_profit_count"]) + 1
                if isinstance(m_row["loss_rates"], list):
                    m_row["loss_rates"].append(profit_rate)
            if has_failure_reason and isinstance(m_row["failure_reasons"], list):
                m_row["failure_reasons"].append((journal.failure_reason or "").strip())

            for theme in (themes if themes else ["미분류"]):
                if theme not in by_theme_bucket:
                    by_theme_bucket[theme] = {
                        "theme_id": None,
                        "theme_name": theme,
                        "failure_trade_count": 0,
                        "loss_rates": [],
                        "total_loss_amount": 0,
                        "failure_reasons": [],
                    }
                t_row = by_theme_bucket[theme]
                t_row["failure_trade_count"] = int(t_row["failure_trade_count"]) + 1
                t_row["total_loss_amount"] = int(t_row["total_loss_amount"]) + min(realized_profit, 0)
                if loss_by_profit_rate and isinstance(t_row["loss_rates"], list):
                    t_row["loss_rates"].append(profit_rate)
                if has_failure_reason and isinstance(t_row["failure_reasons"], list):
                    t_row["failure_reasons"].append((journal.failure_reason or "").strip())

        if theme_id is not None:
            # theme_id 매핑 테이블이 없어 1차에서는 미지원, 후속 확장 여지 유지
            pass

        failure_rows.sort(key=lambda x: (str(x.get("sell_date") or ""), str(x.get("buy_date") or ""), int(x.get("trade_journal_id") or 0)), reverse=True)
        if limit > 0:
            failure_rows = failure_rows[:limit]

        loss_rates = [float(x["profit_rate"]) for x in failure_rows if isinstance(x.get("profit_rate"), (int, float)) and float(x["profit_rate"]) < 0]
        total_loss_amount = sum(min(int(x.get("realized_profit") or 0), 0) for x in failure_rows)
        worst_loss_rate = min(loss_rates) if loss_rates else None

        by_method: list[dict[str, object]] = []
        for row in by_method_bucket.values():
            rates = [float(x) for x in row.get("loss_rates", []) if isinstance(x, (int, float))]
            reasons = [x for x in row.get("failure_reasons", []) if isinstance(x, str) and x]
            by_method.append(
                {
                    "method_id": row.get("method_id"),
                    "method_name": row.get("method_name"),
                    "failure_trade_count": int(row.get("failure_trade_count") or 0),
                    "loss_status_count": int(row.get("loss_status_count") or 0),
                    "negative_profit_count": int(row.get("negative_profit_count") or 0),
                    "average_loss_rate": round(sum(rates) / len(rates), 4) if rates else 0.0,
                    "worst_loss_rate": min(rates) if rates else None,
                    "total_loss_amount": int(row.get("total_loss_amount") or 0),
                    "common_failure_reasons": reasons[:5],
                }
            )
        by_method.sort(key=lambda x: (int(x.get("failure_trade_count") or 0), abs(int(x.get("total_loss_amount") or 0))), reverse=True)

        by_theme: list[dict[str, object]] = []
        for row in by_theme_bucket.values():
            rates = [float(x) for x in row.get("loss_rates", []) if isinstance(x, (int, float))]
            reasons = [x for x in row.get("failure_reasons", []) if isinstance(x, str) and x]
            by_theme.append(
                {
                    "theme_id": row.get("theme_id"),
                    "theme_name": row.get("theme_name"),
                    "failure_trade_count": int(row.get("failure_trade_count") or 0),
                    "average_loss_rate": round(sum(rates) / len(rates), 4) if rates else 0.0,
                    "worst_loss_rate": min(rates) if rates else None,
                    "total_loss_amount": int(row.get("total_loss_amount") or 0),
                    "common_failure_reasons": reasons[:5],
                }
            )
        by_theme.sort(key=lambda x: (int(x.get("failure_trade_count") or 0), abs(int(x.get("total_loss_amount") or 0))), reverse=True)

        worst_trades = sorted(
            [x for x in failure_rows if isinstance(x.get("profit_rate"), (int, float))],
            key=lambda x: float(x.get("profit_rate") or 0),
        )[:5]
        largest_loss_trades = sorted(failure_rows, key=lambda x: int(x.get("realized_profit") or 0))[:5]

        image_analysis_hint = (
            "사용자가 업로드한 차트 이미지는 HTS 종목 차트에서 매수시점과 매도시점이 표시된 캡처 이미지일 수 있습니다. "
            "실패 패턴 분석에서는 차트 이미지 메모와 이미지 존재 여부를 근거로, 진입 시점이 매매기법 조건에 맞았는지, "
            "추세 이탈 이후 반등을 눌림목으로 오판했는지, 손절 기준이 지켜졌는지, 거래량/지지/저항 관점에서 손실 전 경고 신호가 있었는지를 추가 확인 대상으로 분류합니다."
        )
        summary = {
            "from_date": parsed_from.isoformat(),
            "to_date": parsed_to.isoformat(),
            "aggregation_basis": "기간 내 손절 거래, 마이너스 수익률 거래, 실패 사유가 기록된 거래 기준",
            "total_trades_in_period": total_trades_in_period,
            "failure_trade_count": len(failure_rows),
            "loss_status_count": loss_status_count,
            "negative_profit_count": negative_profit_count,
            "failure_reason_count": failure_reason_count,
            "average_loss_rate": round(sum(loss_rates) / len(loss_rates), 4) if loss_rates else 0.0,
            "worst_loss_rate": worst_loss_rate,
            "total_loss_amount": total_loss_amount,
            "average_holding_days": round(sum(holding_days_values) / len(holding_days_values), 2) if holding_days_values else None,
            "chart_image_count": chart_image_count,
        }
        json_data = {
            "summary": summary,
            "failure_trades": failure_rows,
            "by_method": by_method,
            "by_theme": by_theme,
            "failure_reason_sources": {
                "failure_reasons": failure_reasons,
                "review_memos": review_memos,
                "trade_reasons": trade_reasons,
            },
            "worst_trades": worst_trades,
            "largest_loss_trades": largest_loss_trades,
            "chart_image_summary": {
                "total_image_count": total_image_count,
                "chart_image_count": chart_image_count,
                "image_analysis_hint": image_analysis_hint,
                "chart_image_hints": chart_image_hints[:50],
            },
            "guide_focus": {
                "repeated_loss_causes": [],
                "delayed_stop_loss": [],
                "entry_rule_violations": [],
                "chasing_buy_risk": [],
                "weak_theme_or_late_theme_entry": [],
                "volume_decline_entry": [],
                "strategy_misuse": [],
                "emotional_trade_risk": [],
                "forbidden_actions": [],
                "loss_prevention_checklist": [],
                "next_10_trades_rules": [],
            },
        }
        markdown = self._build_failure_pattern_markdown(
            prompt_text=prompt_text,
            summary=summary,
            failure_trades=failure_rows,
            by_method=by_method,
            by_theme=by_theme,
            worst_trades=worst_trades,
            largest_loss_trades=largest_loss_trades,
            failure_reason_sources=json_data["failure_reason_sources"],
            chart_image_summary=json_data["chart_image_summary"],
            json_data=json_data,
        )
        return {
            "package_type": "failure_pattern_review",
            "prompt_key": prompt_key,
            "prompt_text": prompt_text,
            "from_date": parsed_from.isoformat(),
            "to_date": parsed_to.isoformat(),
            "markdown": markdown,
            "json_data": json_data,
        }

    def _build_failure_pattern_markdown(
        self,
        *,
        prompt_text: str,
        summary: dict[str, object],
        failure_trades: list[dict[str, object]],
        by_method: list[dict[str, object]],
        by_theme: list[dict[str, object]],
        worst_trades: list[dict[str, object]],
        largest_loss_trades: list[dict[str, object]],
        failure_reason_sources: dict[str, object],
        chart_image_summary: dict[str, object],
        json_data: dict[str, object],
    ) -> str:
        def line_trade(x: dict[str, object]) -> str:
            return (
                f"- #{x.get('trade_journal_id')} {x.get('stock_name')} ({x.get('stock_code')}) / "
                f"매수 {x.get('buy_date')} / 매도 {x.get('sell_date') or '-'} / "
                f"상태 {x.get('status') or '-'} / 수익률 {x.get('profit_rate')} / 실현손익 {x.get('realized_profit')}"
            )

        method_lines = [
            f"- {x.get('method_name')}: 실패 {x.get('failure_trade_count')} / 평균손실률 {x.get('average_loss_rate')} / 총손실액 {x.get('total_loss_amount')} / 공통실패사유 {', '.join(x.get('common_failure_reasons') or []) or '-'}"
            for x in by_method
        ] or ["- 데이터 없음"]
        theme_lines = [
            f"- {x.get('theme_name')}: 실패 {x.get('failure_trade_count')} / 평균손실률 {x.get('average_loss_rate')} / 총손실액 {x.get('total_loss_amount')} / 공통실패사유 {', '.join(x.get('common_failure_reasons') or []) or '-'}"
            for x in by_theme
        ] or ["- 데이터 없음"]
        failure_lines = [line_trade(x) for x in failure_trades] or ["- 실패 분석 대상 거래 없음"]
        worst_lines = [line_trade(x) for x in worst_trades] or ["- 데이터 없음"]
        loss_amount_lines = [line_trade(x) for x in largest_loss_trades] or ["- 데이터 없음"]

        def source_block(title: str, key: str) -> str:
            rows = failure_reason_sources.get(key) if isinstance(failure_reason_sources, dict) else []
            values = rows if isinstance(rows, list) else []
            if not values:
                return f"### {title}\n- 없음"
            return "### " + title + "\n" + "\n".join([f"- {v}" for v in values])

        guide_request = (
            "1. 가장 자주 반복된 실패 원인\n"
            "2. 진입 전 확인하지 못한 조건\n"
            "3. 손절 지연 여부\n"
            "4. 매매기법 오적용 여부\n"
            "5. 추격매수 가능성\n"
            "6. 테마 후발주 진입 가능성\n"
            "7. 거래대금 감소 구간 진입 여부\n"
            "8. 추세 이탈 후 반등을 눌림목으로 착각한 사례\n"
            "9. 다음 매매 전 금지 행동 리스트\n"
            "10. 손실 방지 체크리스트\n"
            "11. 다음 10회 매매에서 반드시 지킬 원칙"
        )

        return (
            "# DrCT에셋 실패 패턴 GPT 분석 패키지\n\n"
            "## 1. 분석 요청\n"
            f"{prompt_text}\n\n"
            "아래는 손실 거래, 손절 거래, 실패 사유가 기록된 거래를 모은 실패 패턴 분석 패키지입니다.\n"
            "사용자를 비난하지 말고, 반복되는 행동 패턴과 개선 가능한 체크리스트 중심으로 분석해 주세요.\n"
            "기록에 없는 심리 상태는 단정하지 말고, 데이터가 부족한 항목은 추가 확인 필요로 표시해 주세요.\n"
            "향후 종목 추천이나 매수/매도 지시는 하지 마세요.\n\n"
            "## 2. 분석 기간 및 기준\n"
            f"- 분석 기간: {summary.get('from_date')} ~ {summary.get('to_date')}\n"
            f"- 집계 기준: {summary.get('aggregation_basis')}\n"
            f"- 전체 거래 수: {summary.get('total_trades_in_period')}\n"
            f"- 실패 분석 대상 거래 수: {summary.get('failure_trade_count')}\n"
            f"- 손절 거래 수: {summary.get('loss_status_count')}\n"
            f"- 마이너스 수익률 거래 수: {summary.get('negative_profit_count')}\n"
            f"- 실패 사유 기록 거래 수: {summary.get('failure_reason_count')}\n\n"
            "## 3. 실패 요약\n"
            f"- 평균 손실률: {summary.get('average_loss_rate')}\n"
            f"- 최대 손실률: {summary.get('worst_loss_rate')}\n"
            f"- 총 손실액: {summary.get('total_loss_amount')}\n"
            f"- 평균 보유일: {summary.get('average_holding_days')}\n"
            f"- 차트 이미지 포함 건수: {summary.get('chart_image_count')}\n\n"
            "## 4. 실패 거래 목록\n"
            + "\n".join(failure_lines)
            + "\n\n## 5. 매매기법별 실패 패턴\n"
            + "\n".join(method_lines)
            + "\n\n## 6. 테마별 실패 패턴\n"
            + "\n".join(theme_lines)
            + "\n\n## 7. 대표 손실 거래\n"
            + "### 손실률 기준 하위 5건\n"
            + "\n".join(worst_lines)
            + "\n\n### 실현손실액 기준 하위 5건\n"
            + "\n".join(loss_amount_lines)
            + "\n\n## 8. 실패 사유 / 복기 메모 / 매매 이유 원문\n"
            + source_block("실패 사유", "failure_reasons")
            + "\n"
            + source_block("복기 메모", "review_memos")
            + "\n"
            + source_block("매매 이유", "trade_reasons")
            + "\n\n## 9. 차트 이미지 참고 정보\n"
            f"- 이미지 수: {chart_image_summary.get('total_image_count')}\n"
            f"- 차트 이미지 수: {chart_image_summary.get('chart_image_count')}\n"
            f"- 차트 이미지 메모: {', '.join(chart_image_summary.get('chart_image_hints') or []) or '-'}\n"
            f"- 분석 힌트: {chart_image_summary.get('image_analysis_hint')}\n\n"
            "## 10. GPT에게 요청할 실패 패턴 분석 관점\n"
            + guide_request
            + "\n\n## 11. 구조화 JSON\n```json\n"
            + json.dumps(json_data, ensure_ascii=False, indent=2)
            + "\n```"
        )

    def _parse_iso_date(self, value: str) -> datetime.date:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid date format: {value}") from exc

    def _parse_checklist(self, entry_rule: str | None) -> list[str]:
        return [x.strip().lstrip("-").strip() for x in (entry_rule or "").split("\n") if x.strip()]

    def _extract_market_environment(self, description: str | None) -> list[str]:
        text = (description or "").strip()
        if "[시장환경]" not in text:
            return []
        tail = text.split("[시장환경]", 1)[1].strip()
        return [x.strip() for x in tail.split(",") if x.strip()]

    def _build_strategy_guide_markdown(
        self,
        *,
        prompt_text: str,
        strategy: dict[str, object],
        summary: dict[str, object],
        trades: list[dict[str, object]],
        winning_trades: list[dict[str, object]],
        losing_trades: list[dict[str, object]],
        by_theme: list[dict[str, object]],
        review_text_sources: dict[str, object],
        chart_image_summary: dict[str, object],
        json_data: dict[str, object],
    ) -> str:
        def _trade_line(x: dict[str, object]) -> str:
            return (
                f"- #{x.get('trade_journal_id')} {x.get('stock_name')} ({x.get('stock_code')}) "
                f"/ 매수 {x.get('buy_date')} / 매도 {x.get('sell_date') or '-'} / 수익률 {x.get('profit_rate')} / 실현손익 {x.get('realized_profit')}"
            )

        trades_lines = [_trade_line(x) for x in trades] or ["- 거래 없음"]
        win_lines = [_trade_line(x) for x in winning_trades] or ["- 거래 없음"]
        loss_lines = [_trade_line(x) for x in losing_trades] or ["- 거래 없음"]
        theme_lines = [
            f"- {x.get('theme_name')}: 거래 {x.get('trade_count')} / 승률 {x.get('win_rate')}% / 평균수익률 {x.get('average_profit_rate')} / 총손익 {x.get('total_realized_profit')}"
            for x in by_theme
        ] or ["- 데이터 없음"]

        def list_block(title: str, arr: object) -> str:
            values = arr if isinstance(arr, list) else []
            if not values:
                return f"### {title}\n- 없음"
            return "### " + title + "\n" + "\n".join([f"- {v}" for v in values])

        no_samples_note = ""
        if int(summary.get("trade_count") or 0) == 0:
            no_samples_note = "\n표본이 부족합니다. 매매기법 정의/체크리스트/손절·익절 원칙의 사전 점검 가이드를 우선 작성해 주세요.\n"

        guide_request = (
            "1. 이 매매기법의 현재 강점\n"
            "2. 수익 거래에서 반복된 성공 조건\n"
            "3. 손실 거래에서 반복된 실패 조건\n"
            "4. 진입 조건 중 강화해야 할 항목\n"
            "5. 진입을 피해야 할 제외 조건\n"
            "6. 손절 기준 개선안\n"
            "7. 익절 기준 개선안\n"
            "8. 차트 이미지 기준으로 확인해야 할 위치\n"
            "9. 다음 매매 전 체크리스트\n"
            "10. 다음 10회 매매 테스트 기준\n"
            "11. 이 기법을 숙련하기 위한 훈련 과제"
        )

        return (
            "# DrCT에셋 매매기법 가이드 패키지\n\n"
            "## 1. 분석 요청\n"
            f"{prompt_text}\n\n"
            "이 매매기법을 앞으로도 반복 사용할 예정입니다.\n"
            "아래는 이 기법으로 실제 매매한 기록입니다.\n"
            "수익 거래와 손실 거래를 비교하여, 이 기법을 더 잘 쓰기 위한 개선 가이드를 작성해 주세요.\n"
            "단순히 수익률만 평가하지 말고, 진입 조건 준수, 제외 조건, 손절/익절 기준, 차트 위치, 거래량, 테마 적합성을 중심으로 분석해 주세요.\n"
            + no_samples_note
            + "\n## 2. 매매기법 기본 정보\n"
            f"- 매매기법명: {strategy.get('strategy_name')}\n"
            f"- 핵심 개념: {strategy.get('core_concept') or '-'}\n"
            f"- 설명: {strategy.get('description') or '-'}\n"
            f"- 진입 조건: {strategy.get('entry_conditions') or '-'}\n"
            f"- 청산 조건: {strategy.get('exit_conditions') or '-'}\n"
            f"- 리스크 규칙: {strategy.get('risk_rules') or '-'}\n"
            f"- 체크리스트: {', '.join(strategy.get('checklist') or []) or '-'}\n"
            f"- 시장 환경: {', '.join(strategy.get('market_environment') or []) or '-'}\n\n"
            "## 3. 현재 실전 성과 요약\n"
            f"- 총 거래 수: {summary.get('trade_count')}\n"
            f"- 종료 거래 수: {summary.get('closed_trades')}\n"
            f"- 보유중 거래 수: {summary.get('holding_trades')}\n"
            f"- 익절 수: {summary.get('win_count')}\n"
            f"- 손절 수: {summary.get('loss_count')}\n"
            f"- 승률: {summary.get('win_rate')}%\n"
            f"- 총 실현손익: {summary.get('total_realized_profit')}\n"
            f"- 평균 수익률: {summary.get('average_profit_rate')}\n"
            f"- 최고 수익률: {summary.get('best_profit_rate')}\n"
            f"- 최저 수익률: {summary.get('worst_profit_rate')}\n"
            f"- 평균 보유일: {summary.get('average_holding_days')}\n\n"
            "## 4. 이 기법으로 매매한 종목 목록\n"
            + "\n".join(trades_lines)
            + "\n\n## 5. 수익 거래 대표 사례\n"
            + "\n".join(win_lines)
            + "\n\n## 6. 손실 거래 대표 사례\n"
            + "\n".join(loss_lines)
            + "\n\n## 7. 테마별 적합도\n"
            + "\n".join(theme_lines)
            + "\n\n## 8. 성공 사유 / 실패 사유 / 복기 메모 원문\n"
            + list_block("성공 사유", review_text_sources.get("success_reasons"))
            + "\n"
            + list_block("실패 사유", review_text_sources.get("failure_reasons"))
            + "\n"
            + list_block("복기 메모", review_text_sources.get("review_memos"))
            + "\n"
            + list_block("매매 이유", review_text_sources.get("trade_reasons"))
            + "\n\n## 9. 차트 이미지 참고 정보\n"
            f"- 이미지 수: {chart_image_summary.get('total_image_count')}\n"
            f"- 차트 이미지 수: {chart_image_summary.get('chart_image_count')}\n"
            f"- 분석 힌트: {chart_image_summary.get('image_analysis_hint')}\n\n"
            "## 10. GPT에게 요청할 개선 가이드\n"
            + guide_request
            + "\n\n## 11. 구조화 JSON\n```json\n"
            + json.dumps(json_data, ensure_ascii=False, indent=2)
            + "\n```"
        )

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
