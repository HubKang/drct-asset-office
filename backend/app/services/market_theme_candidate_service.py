from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.disclosure import Disclosure
from backend.app.entities.market_theme_stock_candidate import MarketThemeStockCandidate
from backend.app.entities.news import NewsItem
from backend.app.repositories.market_theme_candidate_repository import MarketThemeCandidateRepository
from backend.app.repositories.market_theme_repository import MarketThemeRepository
from backend.app.repositories.market_theme_stock_repository import MarketThemeStockRepository
from backend.app.schemas.market_theme_candidate_schema import (
    MarketThemeCandidateApproveResponse,
    MarketThemeCandidateGenerateRequest,
    MarketThemeCandidateGenerateResponse,
    MarketThemeCandidateListResponse,
)
from backend.app.services.market_theme_stock_service import MarketThemeStockService
from backend.app.schemas.market_theme_stock_schema import MarketThemeStockCreateRequest

ALLOWED_SOURCES = {"all", "news", "disclosure"}
ALLOWED_STATUSES = {"pending", "approved", "rejected", "ignored"}


class MarketThemeCandidateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.theme_repo = MarketThemeRepository(db)
        self.theme_stock_repo = MarketThemeStockRepository(db)
        self.candidate_repo = MarketThemeCandidateRepository(db)
        self.theme_stock_service = MarketThemeStockService(db)

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return (value or "").lower()

    @staticmethod
    def _safe_split_tags(tags: str | None) -> str:
        if not tags:
            return ""
        tags = tags.strip()
        if not tags:
            return ""
        try:
            parsed = json.loads(tags)
            if isinstance(parsed, list):
                return " ".join(str(x) for x in parsed)
        except json.JSONDecodeError:
            pass
        return tags

    @staticmethod
    def _confidence(matched_keyword_count: int, ai_importance_score: int | None, candidate_source: str) -> float:
        base_score = 0.3
        keyword_score = min(0.4, matched_keyword_count * 0.1)
        importance_score = min(0.2, (max(0, min(100, int(ai_importance_score or 0))) / 100.0) * 0.2)
        source_score = 0.05 if candidate_source == "news" else 0.08
        value = base_score + keyword_score + importance_score + source_score
        return round(max(0.0, min(1.0, value)), 4)

    @staticmethod
    def _merge_keywords(existing: list[str], incoming: list[str]) -> list[str]:
        return list(dict.fromkeys([*existing, *incoming]))

    @staticmethod
    def _build_summary(source: str, matched_keywords: list[str], evidence_count: int, titles: list[str]) -> str:
        source_label = "뉴스" if source == "news" else "공시"
        title_part = ", ".join(titles[:3]) if titles else "-"
        keywords_part = ", ".join(matched_keywords[:6]) if matched_keywords else "-"
        return f"최근 {source_label} {evidence_count}건에서 키워드({keywords_part})가 감지되었습니다. 대표: {title_part}"

    def _to_candidate_response(self, row_tuple: tuple) -> MarketThemeCandidateListResponse:
        candidate, theme, stock = row_tuple
        return MarketThemeCandidateListResponse(
            id=candidate.id,
            theme_id=candidate.theme_id,
            theme_name=theme.theme_name,
            stock_id=candidate.stock_id,
            stock_code=stock.stock_code,
            stock_name=stock.stock_name,
            candidate_source=candidate.candidate_source,
            confidence_score=candidate.confidence_score,
            matched_keywords=self.candidate_repo.parse_keywords(candidate.matched_keywords),
            evidence_count=candidate.evidence_count,
            evidence_summary=candidate.evidence_summary,
            status=candidate.status,
            review_memo=candidate.review_memo,
            reviewed_at=candidate.reviewed_at,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )

    def list_candidates(
        self,
        *,
        status: str | None,
        theme_id: int | None,
        stock_id: int | None,
        candidate_source: str | None,
        limit: int,
        offset: int,
    ) -> list[MarketThemeCandidateListResponse]:
        rows = self.candidate_repo.list_candidates(
            status=status,
            theme_id=theme_id,
            stock_id=stock_id,
            candidate_source=candidate_source,
            limit=limit,
            offset=offset,
        )
        return [self._to_candidate_response(row) for row in rows]

    def _scan_news(self, cutoff_text: str, limit: int) -> list[NewsItem]:
        stmt = (
            select(NewsItem)
            .where(NewsItem.stock_id.is_not(None), NewsItem.created_at >= cutoff_text)
            .order_by(NewsItem.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def _scan_disclosures(self, cutoff_text: str, limit: int) -> list[Disclosure]:
        stmt = (
            select(Disclosure)
            .where(Disclosure.created_at >= cutoff_text)
            .order_by(Disclosure.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def generate_candidates(self, payload: MarketThemeCandidateGenerateRequest) -> MarketThemeCandidateGenerateResponse:
        source = (payload.source or "all").strip().lower()
        if source not in ALLOWED_SOURCES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid source")

        lookback_days = max(1, min(int(payload.lookback_days or 7), 30))
        limit = max(1, min(int(payload.limit or 500), 2000))
        cutoff_text = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")

        themes = self.theme_repo.list_with_stock_count(
            is_active=1,
            theme_type=None,
            keyword=None,
            limit=2000,
            offset=0,
        )
        theme_rows = [(row, self.theme_repo.parse_keywords(row.keywords)) for row, _ in themes]

        generated_count = 0
        updated_count = 0
        skipped_existing_mapping_count = 0
        skipped_rejected_count = 0

        if source in {"all", "news"}:
            news_rows = self._scan_news(cutoff_text, limit)
            for item in news_rows:
                text = " ".join(
                    [
                        item.title or "",
                        item.ai_summary or "",
                        self._safe_split_tags(item.ai_tags),
                    ]
                ).lower()
                if not item.stock_id:
                    continue
                for theme, keywords in theme_rows:
                    matched = [kw for kw in keywords if kw.lower() in text]
                    if not matched:
                        continue
                    existing_mapping = self.theme_stock_repo.get_by_theme_stock(theme.id, item.stock_id)
                    if existing_mapping and existing_mapping.is_active == 1:
                        skipped_existing_mapping_count += 1
                        continue
                    existing = self.candidate_repo.get_by_unique(theme.id, item.stock_id, "news")
                    confidence = self._confidence(len(matched), item.ai_importance_score, "news")
                    now = now_kst()
                    if existing:
                        if existing.status == "rejected" and not payload.force:
                            skipped_rejected_count += 1
                            continue
                        if existing.status == "approved":
                            continue
                        merged = self._merge_keywords(self.candidate_repo.parse_keywords(existing.matched_keywords), matched)
                        existing.matched_keywords = json.dumps(merged, ensure_ascii=False)
                        existing.evidence_count = int(existing.evidence_count or 0) + 1
                        existing.confidence_score = max(float(existing.confidence_score or 0), confidence)
                        existing.evidence_summary = self._build_summary("news", merged, existing.evidence_count, [item.title or ""])
                        existing.status = "pending"
                        existing.updated_at = now
                        self.candidate_repo.update(existing)
                        updated_count += 1
                    else:
                        row = MarketThemeStockCandidate(
                            theme_id=theme.id,
                            stock_id=item.stock_id,
                            candidate_source="news",
                            confidence_score=confidence,
                            matched_keywords=json.dumps(matched, ensure_ascii=False),
                            evidence_count=1,
                            evidence_summary=self._build_summary("news", matched, 1, [item.title or ""]),
                            status="pending",
                            review_memo=None,
                            reviewed_at=None,
                            created_at=now,
                            updated_at=now,
                        )
                        self.candidate_repo.create(row)
                        generated_count += 1

        if source in {"all", "disclosure"}:
            disclosure_rows = self._scan_disclosures(cutoff_text, limit)
            for item in disclosure_rows:
                text = " ".join(
                    [
                        item.disclosure_title or "",
                        item.ai_summary or "",
                        item.ai_event_type or "",
                        item.ai_risk_level or "",
                    ]
                ).lower()
                for theme, keywords in theme_rows:
                    matched = [kw for kw in keywords if kw.lower() in text]
                    if not matched:
                        continue
                    existing_mapping = self.theme_stock_repo.get_by_theme_stock(theme.id, item.stock_id)
                    if existing_mapping and existing_mapping.is_active == 1:
                        skipped_existing_mapping_count += 1
                        continue
                    existing = self.candidate_repo.get_by_unique(theme.id, item.stock_id, "disclosure")
                    confidence = self._confidence(len(matched), item.ai_importance_score, "disclosure")
                    now = now_kst()
                    if existing:
                        if existing.status == "rejected" and not payload.force:
                            skipped_rejected_count += 1
                            continue
                        if existing.status == "approved":
                            continue
                        merged = self._merge_keywords(self.candidate_repo.parse_keywords(existing.matched_keywords), matched)
                        existing.matched_keywords = json.dumps(merged, ensure_ascii=False)
                        existing.evidence_count = int(existing.evidence_count or 0) + 1
                        existing.confidence_score = max(float(existing.confidence_score or 0), confidence)
                        existing.evidence_summary = self._build_summary("disclosure", merged, existing.evidence_count, [item.disclosure_title or ""])
                        existing.status = "pending"
                        existing.updated_at = now
                        self.candidate_repo.update(existing)
                        updated_count += 1
                    else:
                        row = MarketThemeStockCandidate(
                            theme_id=theme.id,
                            stock_id=item.stock_id,
                            candidate_source="disclosure",
                            confidence_score=confidence,
                            matched_keywords=json.dumps(matched, ensure_ascii=False),
                            evidence_count=1,
                            evidence_summary=self._build_summary("disclosure", matched, 1, [item.disclosure_title or ""]),
                            status="pending",
                            review_memo=None,
                            reviewed_at=None,
                            created_at=now,
                            updated_at=now,
                        )
                        self.candidate_repo.create(row)
                        generated_count += 1

        return MarketThemeCandidateGenerateResponse(
            generated_count=generated_count,
            updated_count=updated_count,
            skipped_existing_mapping_count=skipped_existing_mapping_count,
            skipped_rejected_count=skipped_rejected_count,
            source=source,
            lookback_days=lookback_days,
        )

    def approve_candidate(self, candidate_id: int) -> MarketThemeCandidateApproveResponse:
        row = self.candidate_repo.get_by_id(candidate_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
        if row.status not in {"pending", "ignored"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="candidate is not approvable")

        mapping_response = self.theme_stock_service.create_theme_stock(
            row.theme_id,
            payload=MarketThemeStockCreateRequest(stock_id=row.stock_id, is_primary=False),
        )
        mapping_row = self.theme_stock_repo.get_by_id(mapping_response.mapping_id)
        if mapping_row:
            mapping_row.mapping_source = row.candidate_source
            mapping_row.confidence_score = row.confidence_score
            mapping_row.updated_at = now_kst()
            self.theme_stock_repo.update(mapping_row)

        row.status = "approved"
        row.reviewed_at = now_kst()
        row.updated_at = row.reviewed_at
        updated = self.candidate_repo.update(row)

        item = self.candidate_repo.list_candidates(
            status=None,
            theme_id=updated.theme_id,
            stock_id=updated.stock_id,
            candidate_source=updated.candidate_source,
            limit=1,
            offset=0,
        )[0]
        return MarketThemeCandidateApproveResponse(
            candidate=self._to_candidate_response(item),
            mapping_id=mapping_response.mapping_id,
            message="후보가 정식 테마 매핑으로 승인되었습니다.",
        )

    def review_candidate(self, candidate_id: int, target_status: str, review_memo: str | None) -> MarketThemeCandidateListResponse:
        if target_status not in {"rejected", "ignored"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid target status")
        row = self.candidate_repo.get_by_id(candidate_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
        row.status = target_status
        row.review_memo = review_memo
        row.reviewed_at = now_kst()
        row.updated_at = row.reviewed_at
        self.candidate_repo.update(row)
        item = self.candidate_repo.list_candidates(
            status=None,
            theme_id=row.theme_id,
            stock_id=row.stock_id,
            candidate_source=row.candidate_source,
            limit=1,
            offset=0,
        )[0]
        return self._to_candidate_response(item)
