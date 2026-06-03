from __future__ import annotations

from datetime import datetime, timedelta
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.repositories.trade_review_repository import TradeReviewRepository


class TradeReviewService:
    VALID_REVIEW_STATUSES = {"미복기", "복기완료"}
    VALID_GRADES = {"A", "B", "C", "D"}
    VALID_PRINCIPLE = {"지킴", "일부 위반", "위반", "미확인"}
    VALID_QUALITY = {"좋음", "보통", "나쁨", "미확인"}
    METHOD_CHECK_SOURCES = (
        ("buy", "buy_condition", "buy_condition"),
        ("sell", "sell_condition", "sell_condition"),
        ("position", "position_sizing_rule", "position_sizing_rule"),
        ("take_profit", "take_profit_rule", "take_profit_rule"),
        ("stop_loss", "stop_loss_rule", "stop_loss_rule"),
        ("checklist", "checklist", "checklist"),
        ("buy", "entry_rule", "entry_rule"),
        ("sell", "exit_rule", "exit_rule"),
    )

    def __init__(self, db: Session) -> None:
        self.repo = TradeReviewRepository(db)

    def list_reviews(
        self,
        *,
        from_date: str | None,
        to_date: str | None,
        review_status: str | None,
        trade_grade: str | None,
        result_type: str | None,
        method_id: int | None,
        stock_name: str | None,
        main_mistake: str | None,
        impulse_trade: bool | None,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        start, end = self._date_range(from_date, to_date)
        rows, total = self.repo.list_reviews(
            from_date=start,
            to_date=end,
            review_status=self._clean(review_status),
            trade_grade=self._clean(trade_grade),
            result_type=self._clean(result_type),
            method_id=method_id,
            stock_name=self._clean(stock_name),
            main_mistake=self._clean(main_mistake),
            impulse_trade=None if impulse_trade is None else (1 if impulse_trade else 0),
            limit=max(1, min(limit, 200)),
            offset=max(0, offset),
        )
        items = []
        for journal, method, review, image_count in rows:
            items.append(
                {
                    "journal_id": journal.id,
                    "review_id": review.id if review else None,
                    "stock_name": journal.stock_name,
                    "stock_code": journal.stock_code,
                    "buy_date": journal.buy_date,
                    "sell_date": journal.sell_date,
                    "method_id": journal.trade_method_id,
                    "method_name": method.method_name if method else journal.trade_method_name,
                    "result_type": journal.result_type,
                    "profit_rate": journal.profit_rate,
                    "realized_profit": journal.realized_profit,
                    "image_count": int(image_count or 0),
                    "review_status": review.review_status if review else "미복기",
                    "trade_grade": review.trade_grade if review else None,
                    "principle_followed": review.principle_followed if review else None,
                    "main_mistake": review.main_mistake if review else None,
                    "impulse_trade": int(review.impulse_trade or 0) if review else 0,
                }
            )
        return {"items": items, "total_count": total}

    def get_detail(self, journal_id: int) -> dict[str, object]:
        journal = self.repo.get_journal(journal_id)
        if not journal:
            raise HTTPException(status_code=404, detail="trade journal not found")
        method = self.repo.get_method(journal.trade_method_id)
        review = self.ensure_review_for_journal(journal_id)
        check_items = self._ensure_check_items(review, method)
        return {
            "journal": journal,
            "method": method,
            "review": review,
            "check_items": check_items,
            "image_count": self.repo.count_images(journal_id),
        }

    def save_review(self, journal_id: int, payload) -> dict[str, object]:
        journal = self.repo.get_journal(journal_id)
        if not journal:
            raise HTTPException(status_code=404, detail="trade journal not found")
        data = payload.model_dump(exclude_unset=True)
        check_items = data.pop("check_items", None)
        normalized = self._normalize_payload(data)
        review = self.repo.upsert_review(journal, normalized)
        if isinstance(check_items, list):
            self.repo.update_check_items(check_items)
        return self.get_detail(review.journal_id)

    def summarize(self, *, from_date: str | None, to_date: str | None) -> dict[str, object]:
        start, end = self._date_range(from_date, to_date)
        return self.repo.summarize(from_date=start, to_date=end)

    def build_gpt_review_package(self, journal_id: int) -> dict[str, object]:
        detail = self.get_detail(journal_id)
        journal = detail["journal"]
        method = detail["method"]
        review = detail["review"]
        check_items = detail["check_items"]
        images = self.repo.list_images(journal_id)

        trade_summary = self._build_trade_summary(journal)
        method_summary = self._build_method_summary(method)
        review_summary = self._build_review_summary(review)
        check_items_summary = self._build_check_items_summary(check_items)
        image_summary = self._build_image_summary(images)
        gpt_request = self._build_gpt_request()

        generated_prompt = (
            "[DrCT 매매복기 요청]\n\n"
            "당신은 투자 종목 추천자가 아니라, 개인 투자자의 매매 습관을 교정하는 매매복기 코치입니다.\n"
            "아래 매매일지와 복기 데이터를 바탕으로 수익/손실보다 매매 과정의 질을 중심으로 분석해 주세요.\n"
            "매수/매도 추천은 하지 말고, 사용자가 자신의 원칙을 지켰는지와 반복 실수를 줄이는 데 집중해 주세요.\n\n"
            "[분석 요청]\n"
            "1. 이 매매의 핵심 요약\n"
            "2. 매매기법 기준 준수 여부 평가\n"
            "3. 진입 판단의 품질 평가\n"
            "4. 청산 판단의 품질 평가\n"
            "5. 리스크 관리와 감정 통제 평가\n"
            "6. 이 매매의 과정 등급 평가\n"
            "7. 반복될 위험이 있는 나쁜 습관\n"
            "8. 잘한 점\n"
            "9. 개선할 점\n"
            "10. 다음 매매 전 반드시 확인할 체크리스트\n"
            "11. 사용자가 부여한 A/B/C/D 등급이 적절한지 검토\n\n"
            "[주의]\n"
            "- 이 분석은 투자 조언이 아니라 매매복기와 습관 교정을 위한 참고 자료입니다.\n"
            "- 새로운 매수/매도 종목 추천은 하지 마세요.\n"
            "- 원칙을 지킨 손실은 나쁜 매매로 단정하지 마세요.\n"
            "- 원칙을 어긴 수익은 좋은 매매로 단정하지 마세요.\n\n"
            f"{trade_summary}\n\n"
            f"{method_summary}\n\n"
            f"{review_summary}\n\n"
            f"{check_items_summary}\n\n"
            f"{image_summary}\n\n"
            f"{gpt_request}"
        )
        stock_name = getattr(journal, "stock_name", None)
        return {
            "journal_id": journal_id,
            "stock_name": stock_name,
            "package_title": f"{self._display(stock_name)} 매매복기 GPT 패키지",
            "generated_prompt": generated_prompt,
            "sections": {
                "trade_summary": trade_summary,
                "method_summary": method_summary,
                "review_summary": review_summary,
                "check_items_summary": check_items_summary,
                "image_summary": image_summary,
                "gpt_request": gpt_request,
            },
        }

    def ensure_review_for_journal(self, journal_id: int):
        review = self.repo.get_by_journal_id(journal_id)
        if review:
            return review
        journal = self.repo.get_journal(journal_id)
        if not journal:
            raise HTTPException(status_code=404, detail="trade journal not found")
        return self.repo.create_review(journal)

    def _ensure_check_items(self, review, method) -> list[object]:
        if not review or not review.id:
            return []
        existing = self.repo.list_check_items(review.id)
        if existing:
            return existing
        if not method:
            return []
        items = self._build_check_items_from_method(review, method)
        if not items:
            return []
        return self.repo.create_check_items(items)

    def _build_check_items_from_method(self, review, method) -> list[dict[str, object]]:
        now = now_kst()
        rows: list[dict[str, object]] = []
        order = 1
        seen_lines: set[tuple[str, str]] = set()
        for item_type, attr_name, source_field in self.METHOD_CHECK_SOURCES:
            if attr_name in {"entry_rule", "exit_rule"}:
                fallback_blocked_by = "buy_condition" if attr_name == "entry_rule" else "sell_condition"
                if getattr(method, fallback_blocked_by, None):
                    continue
            text = getattr(method, attr_name, None)
            for line in self.normalize_rule_lines(text):
                dedupe_key = (item_type, line)
                if dedupe_key in seen_lines:
                    continue
                seen_lines.add(dedupe_key)
                rows.append(
                    {
                        "review_id": review.id,
                        "journal_id": review.journal_id,
                        "method_id": review.method_id,
                        "item_type": item_type,
                        "item_order": order,
                        "item_text": line,
                        "is_checked": 0,
                        "note": None,
                        "source_field": source_field,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                order += 1
        return rows

    def normalize_rule_lines(self, text: str | None) -> list[str]:
        lines: list[str] = []
        for raw_line in (text or "").splitlines():
            line = re.sub(r"^\s*(?:[-*•]+|\d+[.)]|[①②③④⑤⑥⑦⑧⑨⑩])\s*", "", raw_line).strip()
            if line:
                lines.append(line)
        return lines

    def _build_trade_summary(self, journal) -> str:
        sell_reason = self._display(getattr(journal, "success_reason", None) or getattr(journal, "failure_reason", None))
        return (
            "[1. 매매 기본정보]\n"
            f"- 종목명: {self._display(getattr(journal, 'stock_name', None))}\n"
            f"- 종목코드: {self._display(getattr(journal, 'stock_code', None))}\n"
            f"- 매수일자: {self._display(getattr(journal, 'buy_date', None))}\n"
            f"- 매도일자: {self._display(getattr(journal, 'sell_date', None))}\n"
            f"- 매수가: {self._display(getattr(journal, 'buy_price', None))}\n"
            f"- 매도가: {self._display(getattr(journal, 'sell_price', None))}\n"
            f"- 매수수량: {self._display(getattr(journal, 'buy_quantity', None))}\n"
            f"- 매도수량: {self._display(getattr(journal, 'sell_quantity', None))}\n"
            f"- 매수금액: {self._display(getattr(journal, 'buy_amount', None))}\n"
            f"- 매도금액: {self._display(getattr(journal, 'sell_amount', None))}\n"
            f"- 수익률: {self._display(getattr(journal, 'profit_rate', None))}\n"
            f"- 실현손익: {self._display(getattr(journal, 'realized_profit', None))}\n"
            f"- 결과: {self._result_label(getattr(journal, 'result_type', None))}\n"
            f"- 매수 이유: {self._display(getattr(journal, 'trade_reason', None))}\n"
            f"- 매도 이유: {sell_reason}\n"
            f"- 기존 복기 메모: {self._display(getattr(journal, 'review_memo', None))}"
        )

    def _build_method_summary(self, method) -> str:
        if not method:
            return "[2. 연결된 매매기법]\n- 연결된 매매기법: 등록된 내용 없음"
        core_concept = getattr(method, "core_concept", None) or self._extract_core_concept(getattr(method, "description", None))
        buy_condition = getattr(method, "buy_condition", None) or getattr(method, "entry_rule", None)
        sell_condition = getattr(method, "sell_condition", None) or getattr(method, "exit_rule", None)
        return (
            "[2. 연결된 매매기법]\n"
            f"- 매매기법명: {self._display(getattr(method, 'method_name', None))}\n"
            f"- 핵심 개념: {self._display(core_concept)}\n"
            f"- 설명: {self._display(getattr(method, 'description', None))}\n\n"
            "매수조건:\n"
            f"{self._line_block(buy_condition)}\n\n"
            "매도조건:\n"
            f"{self._line_block(sell_condition)}\n\n"
            "진입&비중 방식:\n"
            f"{self._line_block(getattr(method, 'position_sizing_rule', None))}\n\n"
            "익절기준:\n"
            f"{self._line_block(getattr(method, 'take_profit_rule', None))}\n\n"
            "손절기준:\n"
            f"{self._line_block(getattr(method, 'stop_loss_rule', None))}\n\n"
            "체크리스트:\n"
            f"{self._line_block(getattr(method, 'checklist', None) or getattr(method, 'take_profit_rule', None))}"
        )

    def _build_review_summary(self, review) -> str:
        return (
            "[3. 사용자의 복기 입력]\n"
            f"- 복기 상태: {self._display(getattr(review, 'review_status', None))}\n"
            f"- 사용자가 부여한 등급: {self._display(getattr(review, 'trade_grade', None))}\n"
            f"- 원칙 준수 여부: {self._display(getattr(review, 'principle_followed', None))}\n"
            f"- 진입 품질: {self._display(getattr(review, 'entry_quality', None))}\n"
            f"- 청산 품질: {self._display(getattr(review, 'exit_quality', None))}\n"
            f"- 리스크 관리: {self._display(getattr(review, 'risk_control_quality', None))}\n"
            f"- 감정 통제: {self._display(getattr(review, 'emotion_control_quality', None))}\n"
            f"- 충동매매 여부: {'예' if int(getattr(review, 'impulse_trade', 0) or 0) == 1 else '아니오'}\n"
            f"- 주요 실수: {self._display(getattr(review, 'main_mistake', None))}\n"
            f"- 잘한 점: {self._display(getattr(review, 'good_point', None))}\n"
            f"- 개선할 점: {self._display(getattr(review, 'improvement_point', None))}\n"
            f"- 다음 매매 전 지킬 것: {self._display(getattr(review, 'next_action', None))}\n"
            f"- 복기 메모: {self._display(getattr(review, 'review_memo', None))}"
        )

    def _build_check_items_summary(self, check_items: list[object]) -> str:
        groups = (
            ("entry", "진입 조건 체크"),
            ("exit", "청산 조건 체크"),
            ("failure", "실패 패턴 해당 여부"),
            ("checklist", "체크리스트 확인"),
        )
        lines = ["[4. 매매기법 체크 결과]"]
        for item_type, title in groups:
            lines.append("")
            lines.append(f"{title}:")
            rows = [item for item in check_items if getattr(item, "item_type", None) == item_type]
            if not rows:
                lines.append("- 등록된 내용 없음")
                continue
            for item in rows:
                checked = int(getattr(item, "is_checked", 0) or 0) == 1
                if item_type == "failure":
                    label = "해당" if checked else "해당 없음"
                elif item_type == "checklist":
                    label = "확인" if checked else "미확인"
                else:
                    label = "지킴" if checked else "미준수"
                note = self._display(getattr(item, "note", None), empty="메모 없음")
                lines.append(f"- [{label}] {self._display(getattr(item, 'item_text', None))} / 메모: {note}")
        return "\n".join(lines)

    def _build_image_summary(self, images: list[object]) -> str:
        lines = [
            "[5. 차트 이미지 정보]",
            f"- 첨부 이미지 수: {len(images)}",
            "- 안내: 차트 이미지를 GPT에 함께 첨부하면 더 정확한 복기가 가능합니다.",
            "- 이미지 메모:",
        ]
        if not images:
            lines.append("  - 등록된 이미지 메모 없음")
        for image in images:
            filename = self._display(getattr(image, "original_filename", None) or getattr(image, "image_path", None))
            memo = self._display(getattr(image, "image_memo", None), empty="메모 없음")
            lines.append(f"  - {filename}: {memo}")
        return "\n".join(lines)

    def _build_gpt_request(self) -> str:
        return (
            "[6. 최종 요청]\n"
            "위 내용을 바탕으로 이 매매가 원칙을 지킨 매매였는지, 어떤 습관을 고쳐야 하는지, "
            "다음 매매 전에 무엇을 반드시 확인해야 하는지 구체적으로 분석해 주세요."
        )

    def _line_block(self, text: str | None) -> str:
        lines = self.normalize_rule_lines(text)
        if not lines:
            return "- 등록된 내용 없음"
        return "\n".join(f"- {line}" for line in lines)

    def _display(self, value: object, *, empty: str = "미입력") -> str:
        if value is None:
            return empty
        text = str(value).strip()
        return text if text else empty

    def _result_label(self, value: str | None) -> str:
        labels = {"profit": "익절", "loss": "손절", "holding": "보유중", "break_even": "본전"}
        return labels.get((value or "").strip(), self._display(value))

    def _extract_core_concept(self, description: str | None) -> str:
        text = (description or "").strip()
        if "[시장환경]" not in text:
            return text
        return text.split("[시장환경]", 1)[0].strip()

    def _normalize_payload(self, data: dict[str, object]) -> dict[str, object]:
        normalized = {key: self._normalize_value(value) for key, value in data.items()}
        status = str(normalized.get("review_status") or "복기완료")
        if status not in self.VALID_REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail=f"invalid review_status: {status}")
        normalized["review_status"] = status
        if normalized.get("trade_grade") and normalized["trade_grade"] not in self.VALID_GRADES:
            raise HTTPException(status_code=400, detail=f"invalid trade_grade: {normalized['trade_grade']}")
        if normalized.get("principle_followed") and normalized["principle_followed"] not in self.VALID_PRINCIPLE:
            raise HTTPException(status_code=400, detail=f"invalid principle_followed: {normalized['principle_followed']}")
        for key in ("entry_quality", "exit_quality", "risk_control_quality", "emotion_control_quality"):
            if normalized.get(key) and normalized[key] not in self.VALID_QUALITY:
                raise HTTPException(status_code=400, detail=f"invalid {key}: {normalized[key]}")
        normalized["impulse_trade"] = 1 if bool(normalized.get("impulse_trade")) else 0
        normalized["reviewed_at"] = now_kst() if status == "복기완료" else None
        return normalized

    def _date_range(self, from_date: str | None, to_date: str | None) -> tuple[str, str]:
        if from_date and to_date:
            return from_date, to_date
        today = datetime.now().date()
        return (today - timedelta(days=30)).isoformat(), today.isoformat()

    def _empty_review(self, *, journal_id: int, method_id: int | None) -> dict[str, object]:
        return {
            "id": None,
            "journal_id": journal_id,
            "method_id": method_id,
            "review_status": "미복기",
            "trade_grade": None,
            "principle_followed": "미확인",
            "entry_quality": "미확인",
            "exit_quality": "미확인",
            "risk_control_quality": "미확인",
            "emotion_control_quality": "미확인",
            "impulse_trade": 0,
            "main_mistake": None,
            "good_point": None,
            "improvement_point": None,
            "next_action": None,
            "review_memo": None,
            "gpt_review_text": None,
            "reviewed_at": None,
            "created_at": None,
            "updated_at": None,
        }

    def _clean(self, value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None

    def _normalize_value(self, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value
