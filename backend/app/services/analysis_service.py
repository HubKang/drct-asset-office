from __future__ import annotations

import json
import logging
import ast
import html
import re
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import (
    AI_SUMMARY_BATCH_DISCLOSURE_LIMIT,
    AI_SUMMARY_BATCH_NEWS_LIMIT,
    ANALYSIS_MAX_DISCLOSURE_LIMIT,
    ANALYSIS_MAX_NEWS_LIMIT,
    LLM_CHUNK_MAX_OUTPUT_TOKENS,
    LLM_CHUNK_SIZE,
    LLM_FINAL_MAX_OUTPUT_TOKENS,
    LLM_ITEM_SUMMARY_MAX_OUTPUT_TOKENS,
    LLM_ITEM_SUMMARY_RETRY_COUNT,
    LLM_ITEM_SUMMARY_TIMEOUT_SECONDS,
    LLM_MAX_ITEM_SUMMARY_CHARS,
    LLM_REPORT_BASE_DIR,
    PROJECT_ROOT,
    now_kst,
)
from backend.app.entities.analysis_source_item import AnalysisSourceItem
from backend.app.entities.research_report import ResearchReport
from backend.app.llm.lmstudio_client import LMStudioClient
from backend.app.repositories.analysis_source_item_repository import AnalysisSourceItemRepository
from backend.app.repositories.classification_rule_repository import ClassificationRuleRepository
from backend.app.repositories.disclosure_repository import DisclosureRepository
from backend.app.repositories.news_repository import NewsRepository
from backend.app.repositories.research_report_repository import ResearchReportRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.analysis_schema import (
    AiSummarizeResponse,
    ClassificationResponse,
    StockBriefingCandidateCounts,
    StockBriefingCandidateDisclosureItem,
    StockBriefingCandidateNewsItem,
    StockBriefingCandidateResponse,
    StockBriefingResponse,
)
from backend.app.services.analysis_classifier import AnalysisClassifier

logger = logging.getLogger(__name__)

MAX_NEWS_BODY_CHARS = 4000
MAX_DISCLOSURE_BODY_CHARS = 4000
NEWS_BODY_MISSING_MESSAGE = "수집된 본문이 부족하여 원문 확인이 필요합니다."
DISCLOSURE_BODY_MISSING_MESSAGE = "수집된 공시 본문이 부족하여 원문 확인이 필요합니다."
NEWS_ARTICLE_FETCH_TIMEOUT_SECONDS = 8

DEFAULT_NEWS_ITEM_SUMMARY_TEMPLATE = """당신은 개인 투자자의 뉴스 판단 훈련을 돕는 뉴스 요약 분석가입니다.

아래 뉴스 제목과 본문을 바탕으로 JSON만 출력하세요.
투자 추천, 매수 의견, 매도 의견, 목표가 제시는 절대 하지 마세요.
본문에 없는 내용을 추측하지 마세요.

요약 작성 기준:
1. summary는 기사 원문을 충실하게 반영해 4~6문장으로 작성하세요.
2. 단순히 제목을 반복하지 말고, 기사에서 실제로 발생한 일과 배경을 설명하세요.
3. 다음 요소가 본문에 있으면 반드시 포함하세요.
   - 관련 기업/기관/지자체/정부 부처
   - 사업 규모, 금액, 기업 수, 수주 규모, 경제효과 등 수치
   - 발표 시점 또는 향후 일정
   - 관심종목과의 직접적 또는 간접적 연결성
   - 기대효과
   - 아직 확인이 필요한 부분
4. 본문 품질이 short 또는 empty이면 억지로 추론하지 말고, 본문 부족으로 원문 확인이 필요하다고 적으세요.
5. summary는 사용자가 원문을 읽지 않아도 기사 핵심을 이해할 수 있을 정도로 충분히 작성하세요.
6. keywords는 기사 핵심 키워드 5~8개를 작성하세요.
7. importance_score는 관심종목과의 관련성, 구체적 수치, 사업 영향 가능성을 기준으로 0~100 사이 정수로 작성하세요.

중요도 기준:
- 80~100: 관심종목과 직접 관련 있고, 수주/실적/계약/정책/대규모 투자 등 영향 가능성이 큼
- 60~79: 관심종목 또는 핵심 테마와 강하게 관련 있음
- 40~59: 업종이나 테마 관련성은 있으나 직접 영향은 제한적
- 20~39: 단순 언급 또는 시황성 기사
- 0~19: 관련성 낮음

{
  "summary": "4~6문장의 충실한 원문 기반 요약",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "importance_score": 0
}

종목명: {{stock_name}}
종목코드: {{stock_code}}
제목: {{title}}
본문 출처: {{body_source}}
본문 품질: {{body_quality}}
내용: {{content}}
보조 내용: {{snippet}}
출처: {{source}}
발행일: {{published_at}}
원문 URL: {{url}}
"""

DEFAULT_DISCLOSURE_ITEM_SUMMARY_TEMPLATE = """당신은 개인 투자자의 공시 확인 훈련을 돕는 공시 요약 분석가입니다.

아래 공시 제목과 원문 본문을 바탕으로 JSON만 출력하세요.
투자 추천, 매수 의견, 매도 의견, 목표가 제시는 절대 하지 마세요.
본문에 없는 내용을 추측하지 마세요.

요약 작성 기준:
1. summary는 공시 원문의 단락 흐름을 유지해 작성하세요.
2. 원문 각 단락의 핵심 내용을 한 문장으로 요약하세요.
3. 단락 수가 많으면 핵심 단락 중심으로 4~8문장 이내로 요약하세요.
4. 표, 주석, 정정 사유, 계약 내용, 대상자, 금액, 기간 등 공시에 명시된 정보는 원문에 있는 범위 안에서만 반영하세요.
5. 문서 탐색 경로, 메뉴명, 저작권 문구, 공시 시스템 안내 문구처럼 실제 공시 내용이 아닌 문구는 요약에서 제외하세요.
6. 같은 내용이 반복되는 단락은 하나의 문장으로 합쳐도 됩니다.
7. 제목만 반복하지 말고 본문 단락의 실제 내용을 반영하세요.
8. 본문이 부족하거나 실제 공시 내용이 확인되지 않으면 “수집된 공시 본문이 부족하여 원문 확인이 필요합니다.”라고 summary에 포함하세요.
9. keywords는 공시 핵심 키워드 3~8개를 작성하세요.
10. importance_score는 공시의 구체성, 금액·계약·지분·정정·실적 등 투자자가 확인할 필요가 있는 정도를 기준으로 0~100 사이 정수로 작성하세요.

{
  "summary": "공시 원문 단락별 핵심을 한 문장씩 요약한 내용",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "importance_score": 0
}

공시 제목: {{disclosure_title}}
공시 유형: {{disclosure_type}}
공시일: {{disclosed_at}}
접수번호: {{dart_receipt_no}}
DART URL: {{dart_url}}
본문 출처: {{body_source}}
본문 품질: {{body_quality}}
공시 본문:
{{disclosure_body}}
"""

DEFAULT_CHUNK_SUMMARY_TEMPLATE = """아래 {{source_label}} 항목들을 간결하게 요약해 주세요.
핵심 사실과 투자 관점에서 중요한 포인트를 중심으로 작성하세요.

{{items}}
"""

DEFAULT_FINAL_SUMMARY_TEMPLATE = """# 종목 리서치 브리핑

## 1. 핵심 이슈
{{news_summary}}

## 2. 긍정 요인
뉴스/공시 기반 긍정 요인을 정리하세요.

## 3. 부정 요인 및 리스크
뉴스/공시 기반 리스크를 정리하세요.

## 4. 추가 확인 사항
추가로 확인해야 할 포인트를 정리하세요.

## 5. 투자 검토 메모
투자 판단에 참고할 메모를 간결히 작성하세요.

## 6. 결론
{{stock_name}}({{stock_code}})에 대한 종합 의견을 작성하세요.
"""


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.news_repo = NewsRepository(db)
        self.disclosure_repo = DisclosureRepository(db)
        self.report_repo = ResearchReportRepository(db)
        self.analysis_source_repo = AnalysisSourceItemRepository(db)
        self.classification_rule_repo = ClassificationRuleRepository(db)
        self.classifier = AnalysisClassifier()
        self.llm_client = LMStudioClient()
        self._news_body_context_cache: dict[int, tuple[str, str]] = {}

    def get_stock_briefing_candidates(
        self,
        stock_id: int,
        news_limit: int = 20,
        disclosure_limit: int = 20,
    ) -> StockBriefingCandidateResponse:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=404, detail="stock not found")

        news_limit = max(1, min(news_limit, ANALYSIS_MAX_NEWS_LIMIT))
        disclosure_limit = max(1, min(disclosure_limit, ANALYSIS_MAX_DISCLOSURE_LIMIT))

        news_items = self.news_repo.list_recent_by_stock(stock_id, news_limit)
        disclosures = self.disclosure_repo.list_recent_by_stock(stock_id, disclosure_limit)

        used_news = self.analysis_source_repo.list_used_source_ids(stock_id=stock_id, source_type="news")
        used_disclosures = self.analysis_source_repo.list_used_source_ids(stock_id=stock_id, source_type="disclosure")

        news_payload = [
            StockBriefingCandidateNewsItem(
                id=item.id,
                title=item.title,
                published_at=item.published_at,
                summary=item.summary,
                source=item.source,
                url=item.url,
                used_in_report=item.id in used_news,
            )
            for item in news_items
        ]
        disclosure_payload = [
            StockBriefingCandidateDisclosureItem(
                id=item.id,
                disclosure_title=item.disclosure_title,
                disclosure_type=item.disclosure_type,
                disclosed_at=item.disclosed_at,
                url=item.url,
                used_in_report=item.id in used_disclosures,
            )
            for item in disclosures
        ]

        return StockBriefingCandidateResponse(
            stock_id=stock.id,
            stock_code=stock.stock_code,
            stock_name=stock.stock_name,
            news=news_payload,
            disclosures=disclosure_payload,
            counts=StockBriefingCandidateCounts(
                news_total=len(news_payload),
                news_unused=sum(1 for n in news_payload if not n.used_in_report),
                disclosure_total=len(disclosure_payload),
                disclosure_unused=sum(1 for d in disclosure_payload if not d.used_in_report),
            ),
        )

    def generate_stock_briefing(
        self,
        stock_id: int,
        mode: str = "incremental",
        news_limit: int = 20,
        disclosure_limit: int = 20,
        chunk_size: int = 5,
        news_ids: list[int] | None = None,
        disclosure_ids: list[int] | None = None,
    ) -> StockBriefingResponse:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=404, detail="stock not found")

        if mode not in {"incremental", "full", "selected"}:
            raise HTTPException(status_code=400, detail="invalid mode")

        news_limit = max(1, min(news_limit, ANALYSIS_MAX_NEWS_LIMIT))
        disclosure_limit = max(1, min(disclosure_limit, ANALYSIS_MAX_DISCLOSURE_LIMIT))
        chunk_size = max(1, chunk_size or LLM_CHUNK_SIZE)

        if mode == "incremental":
            used_news = self.analysis_source_repo.list_used_source_ids(stock_id=stock_id, source_type="news")
            used_disclosures = self.analysis_source_repo.list_used_source_ids(stock_id=stock_id, source_type="disclosure")
            selected_news = self.news_repo.list_recent_unused_by_stock(stock_id, used_news, news_limit)
            selected_disclosures = self.disclosure_repo.list_recent_unused_by_stock(stock_id, used_disclosures, disclosure_limit)
        elif mode == "full":
            selected_news = self.news_repo.list_recent_by_stock(stock_id, news_limit)
            selected_disclosures = self.disclosure_repo.list_recent_by_stock(stock_id, disclosure_limit)
        else:
            news_ids = news_ids or []
            disclosure_ids = disclosure_ids or []
            if not news_ids and not disclosure_ids:
                raise HTTPException(status_code=400, detail="selected mode requires news_ids or disclosure_ids")
            selected_news = self.news_repo.list_by_ids(stock_id, news_ids)
            selected_disclosures = self.disclosure_repo.list_by_ids(stock_id, disclosure_ids)

        if not selected_news and not selected_disclosures:
            raise HTTPException(status_code=400, detail="no source items available for briefing")

        news_chunks = self._chunk_items(selected_news, chunk_size)
        disclosure_chunks = self._chunk_items(selected_disclosures, chunk_size)
        chunk_count = len(news_chunks) + len(disclosure_chunks)

        news_summaries: list[str] = []
        disclosure_summaries: list[str] = []

        for index, chunk in enumerate(news_chunks):
            prompt = self._build_chunk_prompt("뉴스", self._format_news_chunk(chunk))
            try:
                summary = self.llm_client.generate_text(
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=LLM_CHUNK_MAX_OUTPUT_TOKENS,
                    purpose=f"chunk_summary:news:{index + 1}",
                )
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"chunk_summary failed: source_type=news, chunk_index={index + 1}, reason={exc}",
                ) from exc
            news_summaries.append(summary)

        for index, chunk in enumerate(disclosure_chunks):
            prompt = self._build_chunk_prompt("공시", self._format_disclosure_chunk(chunk))
            try:
                summary = self.llm_client.generate_text(
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=LLM_CHUNK_MAX_OUTPUT_TOKENS,
                    purpose=f"chunk_summary:disclosure:{index + 1}",
                )
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"chunk_summary failed: source_type=disclosure, chunk_index={index + 1}, reason={exc}",
                ) from exc
            disclosure_summaries.append(summary)

        final_prompt = self._build_final_prompt(
            stock_name=stock.stock_name,
            stock_code=stock.stock_code,
            analysis_date=now_kst(),
            news_summary="\n\n".join(news_summaries) if news_summaries else "제공 자료 내 확인 불가",
            disclosure_summary="\n\n".join(disclosure_summaries) if disclosure_summaries else "제공 자료 내 확인 불가",
        )

        try:
            raw_markdown = self.llm_client.generate_text(
                prompt=final_prompt,
                temperature=0.2,
                max_tokens=LLM_FINAL_MAX_OUTPUT_TOKENS,
                purpose="final_briefing",
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        normalized = self._normalize_markdown_for_validation(raw_markdown)
        normalized = self._normalize_report_headings(normalized)
        complete, missing = self._validate_report_complete(normalized)

        if not complete:
            retry_prompt = (
                final_prompt
                + "\n\n이전 응답은 지정된 Markdown 제목을 따르지 않았습니다. "
                "아래 6개 제목을 글자 하나 바꾸지 말고 그대로 사용하여 완성본만 다시 작성하세요."
            )
            try:
                second = self.llm_client.generate_text(
                    prompt=retry_prompt,
                    temperature=0.1,
                    max_tokens=LLM_FINAL_MAX_OUTPUT_TOKENS,
                    purpose="final_briefing_retry",
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

            normalized = self._normalize_report_headings(self._normalize_markdown_for_validation(second))
            complete, missing = self._validate_report_complete(normalized)

            if not complete:
                self._save_failed_llm_output("final_briefing", normalized, missing)
                preview = normalized[:300]
                raise HTTPException(
                    status_code=503,
                    detail=f"LLM report generation incomplete. Missing sections: {', '.join(missing)}. Output preview: {preview}",
                )

        markdown_path = self._save_report_file(stock.stock_code, normalized)
        report = self.report_repo.create(
            ResearchReport(
                stock_id=stock.id,
                report_type="llm_stock_briefing",
                title=f"{stock.stock_name} ({stock.stock_code}) 종목 리서치 브리핑",
                report_date=now_kst().split(" ")[0],
                summary=normalized[:500],
                markdown_content=normalized,
                markdown_path=markdown_path,
                generated_by="lmstudio",
                created_at=now_kst(),
            )
        )

        source_items = [
            AnalysisSourceItem(
                report_id=report.id,
                stock_id=stock.id,
                source_type="news",
                source_id=item.id,
                used_stage="final_briefing",
                created_at=now_kst(),
            )
            for item in selected_news
        ] + [
            AnalysisSourceItem(
                report_id=report.id,
                stock_id=stock.id,
                source_type="disclosure",
                source_id=item.id,
                used_stage="final_briefing",
                created_at=now_kst(),
            )
            for item in selected_disclosures
        ]
        self.analysis_source_repo.create_many(source_items)

        return StockBriefingResponse(
            status="success",
            stock_id=stock.id,
            report_id=report.id,
            markdown_path=markdown_path,
            used_news_count=len(selected_news),
            used_disclosure_count=len(selected_disclosures),
            chunk_count=chunk_count,
            message="stock briefing generated",
        )

    def summarize_news_items(
        self,
        stock_id: int | None = None,
        news_ids: list[int] | None = None,
        limit: int = 10,
        only_unprocessed: bool = True,
        overwrite: bool = False,
    ) -> AiSummarizeResponse:
        selected_ids = [nid for nid in (news_ids or []) if isinstance(nid, int)]
        if selected_ids:
            items = self.news_repo.list_by_ids_any(selected_ids)
            if only_unprocessed and not overwrite:
                items = [item for item in items if not item.ai_summary]
        else:
            resolved_limit = max(1, min(limit, AI_SUMMARY_BATCH_NEWS_LIMIT))
            items = self.news_repo.list_for_ai_summary(
                stock_id=stock_id,
                limit=resolved_limit,
                only_unprocessed=only_unprocessed,
                overwrite=overwrite,
            )

        if not items:
            return AiSummarizeResponse(
                status="success",
                target="news",
                processed_count=0,
                success_count=0,
                failed_count=0,
                skipped_count=0,
                message="no news items to summarize",
            )

        success_count = 0
        failed_count = 0
        skipped_count = 0
        item_system_prompt = (
            "너는 국내 주식 뉴스 요약 보조 AI이다. "
            "내부 사고 과정, Thinking Process, Analysis, Reasoning을 절대 출력하지 마라. "
            "기사 원문에 있는 사실만 바탕으로 4~6문장 요약을 만들고, summary, keywords, importance_score만 포함한 JSON 객체만 출력하라."
        )

        for item in items:
            processed_at = now_kst()
            base_prompt = self._build_news_item_prompt(item)
            attempts = max(1, LLM_ITEM_SUMMARY_RETRY_COUNT + 1)
            saved = False
            last_error = ""
            logger.info(
                "news_ai_summary start news_id=%s title_len=%s content_len=%s source=%s published_at=%s",
                getattr(item, "id", None),
                len(self._normalize_news_text(getattr(item, "title", ""))),
                len(self._normalize_news_text(getattr(item, "summary", ""))),
                getattr(item, "source", None),
                getattr(item, "published_at", None),
            )

            best_result: dict[str, Any] | None = None
            for attempt in range(attempts):
                prompt = base_prompt
                if attempt > 0:
                    prompt += "\n\n이전 응답이 형식 기준을 충족하지 못했습니다. summary, keywords, importance_score만 담은 JSON 객체만 출력하세요."
                try:
                    raw = self.llm_client.generate_text(
                        prompt=prompt,
                        temperature=0.1,
                        max_tokens=LLM_ITEM_SUMMARY_MAX_OUTPUT_TOKENS,
                        timeout=LLM_ITEM_SUMMARY_TIMEOUT_SECONDS,
                        purpose=f"news_ai_summary:{item.id}:attempt{attempt + 1}",
                        system_prompt=item_system_prompt,
                    )
                    logger.debug(
                        "news_ai_summary raw_response news_id=%s attempt=%s len=%s preview=%s",
                        getattr(item, "id", None),
                        attempt + 1,
                        len(raw or ""),
                        (raw or "")[:400],
                    )
                    cleaned = self._clean_item_summary_text(raw)
                    structured = self._parse_simple_news_summary_payload(cleaned, item)
                    if not structured:
                        last_error = "json_parse_failed"
                        logger.warning("[news_ai_summary] news_id=%s attempt=%s parse_success=False quality=0 reason=%s", item.id, attempt + 1, last_error)
                        continue
                    if not self._is_valid_simple_news_summary(structured) and attempt + 1 < attempts:
                        last_error = "quality_too_low"
                        continue

                    quality_score = self._score_simple_news_summary(structured, raw)
                    logger.info(
                        "[news_ai_summary] news_id=%s attempt=%s parse_success=True quality=%s importance=%s keywords=%s",
                        item.id,
                        attempt + 1,
                        quality_score,
                        structured["importance_score"],
                        len(structured.get("keywords") or []),
                    )
                    candidate = {
                        "structured": structured,
                        "quality_score": quality_score,
                    }
                    if best_result is None or candidate["quality_score"] > best_result["quality_score"]:
                        best_result = candidate

                    if quality_score < 50 and attempt + 1 < attempts:
                        last_error = "quality_too_low"
                        continue

                    cleaned = self._format_simple_news_summary(structured)
                    importance_value = int(structured.get("importance_score") or 50)
                    tags_value = self._normalize_tags(structured.get("keywords") or [])
                    self.news_repo.update_ai_summary(
                        news_id=item.id,
                        ai_summary=cleaned,
                        ai_sentiment=None,
                        ai_importance_score=importance_value,
                        ai_tags=tags_value,
                        ai_processed_at=processed_at,
                        ai_summary_error=None,
                    )
                    success_count += 1
                    saved = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)
                    logger.warning("[news_ai_summary] news_id=%s attempt=%s parse_success=False quality=0 reason=%s", item.id, attempt + 1, last_error)

            if not saved and best_result is not None and best_result.get("quality_score", 0) >= 50:
                chosen = best_result["structured"]
                cleaned = self._format_simple_news_summary(chosen)
                importance_value = int(chosen.get("importance_score") or 50)
                tags_value = self._normalize_tags(chosen.get("keywords") or [])
                self.news_repo.update_ai_summary(
                    news_id=item.id,
                    ai_summary=cleaned,
                    ai_sentiment=None,
                    ai_importance_score=importance_value,
                    ai_tags=tags_value,
                    ai_processed_at=processed_at,
                    ai_summary_error=None,
                )
                logger.info("[news_ai_summary] news_id=%s selected_result_attempt=best quality=%s", item.id, best_result["quality_score"])
                success_count += 1
                saved = True

            if not saved:
                fallback_payload = self._build_simple_news_summary_fallback(item, last_error or "invalid or empty summary response")
                fallback_summary = self._format_simple_news_summary(fallback_payload)
                self.news_repo.update_ai_summary(
                    news_id=item.id,
                    ai_summary=fallback_summary,
                    ai_sentiment=None,
                    ai_importance_score=int(fallback_payload.get("importance_score") or 30),
                    ai_tags=self._normalize_tags(fallback_payload.get("keywords") or []),
                    ai_processed_at=processed_at,
                    ai_summary_error=f"fallback:{last_error or 'applied'}",
                )
                logger.warning("news ai summary fallback applied: news_id=%s reason=%s", item.id, last_error or "invalid response")
                failed_count += 1

        return AiSummarizeResponse(
            status="success",
            target="news",
            processed_count=len(items),
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            message="news ai summary completed",
        )

    def summarize_disclosures(
        self,
        stock_id: int | None = None,
        disclosure_ids: list[int] | None = None,
        limit: int = 10,
        only_unprocessed: bool = True,
        overwrite: bool = False,
    ) -> AiSummarizeResponse:
        selected_ids = [did for did in (disclosure_ids or []) if isinstance(did, int)]
        if selected_ids:
            items = self.disclosure_repo.list_by_ids_any(selected_ids)
            if only_unprocessed and not overwrite:
                items = [item for item in items if not item.ai_summary]
        else:
            resolved_limit = max(1, min(limit, AI_SUMMARY_BATCH_DISCLOSURE_LIMIT))
            items = self.disclosure_repo.list_for_ai_summary(
                stock_id=stock_id,
                limit=resolved_limit,
                only_unprocessed=only_unprocessed,
                overwrite=overwrite,
            )

        if not items:
            return AiSummarizeResponse(
                status="success",
                target="disclosures",
                processed_count=0,
                success_count=0,
                failed_count=0,
                skipped_count=0,
                message="no disclosures to summarize",
            )

        success_count = 0
        failed_count = 0
        skipped_count = 0
        item_system_prompt = (
            "너는 개인 투자자의 공시 확인 훈련을 돕는 공시 요약 분석가이다. "
            "내부 사고 과정, Thinking Process, Analysis, Reasoning을 절대 출력하지 마라. "
            "summary, keywords, importance_score만 포함한 JSON 객체만 출력하라."
        )

        for item in items:
            processed_at = now_kst()
            disclosure_body, body_error, body_source = self._resolve_disclosure_body_text(item)
            body_quality = self._get_disclosure_body_quality(disclosure_body)
            base_prompt = self._build_disclosure_item_prompt(
                item,
                disclosure_body=disclosure_body,
                body_source=body_source,
                body_quality=body_quality,
            )
            attempts = max(1, LLM_ITEM_SUMMARY_RETRY_COUNT + 1)
            saved = False
            last_error = ""

            if body_quality in {"missing", "navigation_only"}:
                fallback_reason = body_error or "missing_disclosure_body"
                fallback_payload = self._build_simple_disclosure_summary_fallback(item, disclosure_body, fallback_reason)
                fallback_summary = self._format_simple_disclosure_summary(fallback_payload)
                event_type = self._infer_disclosure_event_type(item.disclosure_title, item.disclosure_type, "other")
                risk_level = self._infer_disclosure_risk_level(item.disclosure_title, item.disclosure_type, "unknown")
                self.disclosure_repo.update_ai_summary(
                    disclosure_id=item.id,
                    ai_summary=fallback_summary,
                    ai_importance_score=int(fallback_payload.get("importance_score") or 30),
                    ai_tags=self._normalize_tags(fallback_payload.get("keywords") or []),
                    ai_risk_level=risk_level,
                    ai_event_type=event_type,
                    ai_processed_at=processed_at,
                    ai_summary_error=fallback_reason,
                )
                success_count += 1
                continue

            for attempt in range(attempts):
                prompt = base_prompt
                if attempt > 0:
                    prompt += "\n\n이전 응답이 형식 기준을 충족하지 못했습니다. summary, keywords, importance_score만 담은 JSON 객체만 출력하세요."
                try:
                    raw = self.llm_client.generate_text(
                        prompt=prompt,
                        temperature=0.1,
                        max_tokens=max(LLM_ITEM_SUMMARY_MAX_OUTPUT_TOKENS, 700),
                        timeout=LLM_ITEM_SUMMARY_TIMEOUT_SECONDS,
                        purpose=f"disclosure_ai_summary:{item.id}:attempt{attempt + 1}",
                        system_prompt=item_system_prompt,
                    )
                    cleaned = self._clean_item_summary_text(raw)
                    structured = self._parse_simple_disclosure_summary_payload(cleaned, item, disclosure_body)
                    if not structured:
                        last_error = "json_parse_failed"
                        continue
                    if not self._is_valid_simple_news_summary(structured):
                        last_error = "quality_too_low"
                        continue

                    event_type = self._infer_disclosure_event_type(item.disclosure_title, item.disclosure_type, "other")
                    risk_level = self._infer_disclosure_risk_level(item.disclosure_title, item.disclosure_type, "unknown")
                    cleaned_summary = self._format_simple_disclosure_summary(structured)
                    self.disclosure_repo.update_ai_summary(
                        disclosure_id=item.id,
                        ai_summary=cleaned_summary,
                        ai_importance_score=int(structured.get("importance_score") or 30),
                        ai_tags=self._normalize_tags(structured.get("keywords") or []),
                        ai_risk_level=risk_level,
                        ai_event_type=event_type,
                        ai_processed_at=processed_at,
                        ai_summary_error=None,
                    )
                    success_count += 1
                    saved = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)

            if not saved:
                fallback_payload = self._build_simple_disclosure_summary_fallback(item, disclosure_body, last_error or "invalid or empty summary response")
                fallback_summary = self._format_simple_disclosure_summary(fallback_payload)
                try:
                    event_type = self._infer_disclosure_event_type(item.disclosure_title, item.disclosure_type, "other")
                    risk_level = self._infer_disclosure_risk_level(item.disclosure_title, item.disclosure_type, "unknown")
                    self.disclosure_repo.update_ai_summary(
                        disclosure_id=item.id,
                        ai_summary=fallback_summary,
                        ai_importance_score=int(fallback_payload.get("importance_score") or 30),
                        ai_tags=self._normalize_tags(fallback_payload.get("keywords") or []),
                        ai_risk_level=risk_level,
                        ai_event_type=event_type,
                        ai_processed_at=processed_at,
                        ai_summary_error=f"fallback:{last_error or 'applied'}",
                    )
                    success_count += 1
                    logger.warning("disclosure ai summary fallback applied: disclosure_id=%s reason=%s", item.id, last_error or "invalid response")
                except Exception:
                    failed_count += 1
                    error_message = last_error or "invalid or empty summary response"
                    self.disclosure_repo.mark_ai_summary_failed(
                        disclosure_id=item.id,
                        error_message=error_message,
                        ai_processed_at=processed_at,
                    )

        return AiSummarizeResponse(
            status="success",
            target="disclosures",
            processed_count=len(items),
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            message="disclosure ai summary completed",
        )

    def summarize_source_items(
        self,
        stock_id: int | None = None,
        news_limit: int = 10,
        disclosure_limit: int = 10,
        only_unprocessed: bool = True,
        overwrite: bool = False,
    ) -> AiSummarizeResponse:
        news_result = self.summarize_news_items(
            stock_id=stock_id,
            limit=news_limit,
            only_unprocessed=only_unprocessed,
            overwrite=overwrite,
        )
        disclosure_result = self.summarize_disclosures(
            stock_id=stock_id,
            limit=disclosure_limit,
            only_unprocessed=only_unprocessed,
            overwrite=overwrite,
        )

        return AiSummarizeResponse(
            status="success",
            target="source_items",
            processed_count=news_result.processed_count + disclosure_result.processed_count,
            success_count=news_result.success_count + disclosure_result.success_count,
            failed_count=news_result.failed_count + disclosure_result.failed_count,
            skipped_count=news_result.skipped_count + disclosure_result.skipped_count,
            message="source item ai summary completed",
        )

    def classify_news_items(self, stock_id: int | None = None, limit: int = 100) -> ClassificationResponse:
        items = self.news_repo.list_for_classification(stock_id=stock_id, limit=limit)
        rules = self.classification_rule_repo.list_active_by_target("news")
        self._warn_if_no_active_rules(target_type="news", active_rule_count=len(rules))
        processed = 0
        for item in items:
            classified = self.classifier.classify_news(
                title=item.title,
                summary=item.summary,
                ai_summary=item.ai_summary,
                rules=rules,
            )
            self.news_repo.update_ai_summary(
                news_id=item.id,
                ai_summary=item.ai_summary or "",
                ai_sentiment=str(classified.get("ai_sentiment", "neutral")),
                ai_importance_score=int(classified.get("ai_importance_score", 50)),
                ai_tags=str(classified.get("ai_tags", "뉴스")),
                ai_processed_at=now_kst(),
                ai_summary_error=item.ai_summary_error,
            )
            processed += 1
        return ClassificationResponse(
            status="success",
            target="news",
            processed_count=processed,
            message=self._message_with_active_rules("news classification completed", len(rules)),
        )

    def classify_disclosures(self, stock_id: int | None = None, limit: int = 100) -> ClassificationResponse:
        items = self.disclosure_repo.list_for_classification(stock_id=stock_id, limit=limit)
        rules = self.classification_rule_repo.list_active_by_target("disclosure")
        self._warn_if_no_active_rules(target_type="disclosure", active_rule_count=len(rules))
        processed = 0
        for item in items:
            classified = self.classifier.classify_disclosure(
                disclosure_title=item.disclosure_title,
                disclosure_type=item.disclosure_type,
                ai_summary=item.ai_summary,
                rules=rules,
            )
            self.disclosure_repo.update_ai_summary(
                disclosure_id=item.id,
                ai_summary=item.ai_summary or "",
                ai_importance_score=int(classified.get("ai_importance_score", 50)),
                ai_tags=str(classified.get("ai_tags", "공시")),
                ai_risk_level=str(classified.get("ai_risk_level", "unknown")),
                ai_event_type=str(classified.get("ai_event_type", "기타")),
                ai_processed_at=now_kst(),
                ai_summary_error=item.ai_summary_error,
            )
            processed += 1
        return ClassificationResponse(
            status="success",
            target="disclosures",
            processed_count=processed,
            message=self._message_with_active_rules("disclosure classification completed", len(rules)),
        )

    def classify_source_items(
        self,
        stock_id: int | None = None,
        news_limit: int = 100,
        disclosure_limit: int = 100,
    ) -> ClassificationResponse:
        news_result = self.classify_news_items(stock_id=stock_id, limit=news_limit)
        disclosure_result = self.classify_disclosures(stock_id=stock_id, limit=disclosure_limit)
        news_active_rules = len(self.classification_rule_repo.list_active_by_target("news"))
        disclosure_active_rules = len(self.classification_rule_repo.list_active_by_target("disclosure"))
        return ClassificationResponse(
            status="success",
            target="source_items",
            processed_count=news_result.processed_count + disclosure_result.processed_count,
            message=(
                "source items classification completed "
                f"(active_rules: news={news_active_rules}, disclosure={disclosure_active_rules})"
            ),
        )

    def _warn_if_no_active_rules(self, target_type: str, active_rule_count: int) -> None:
        if active_rule_count > 0:
            return
        logger.warning(
            "No active classification rules found for target_type=%s. Default classification values will be used.",
            target_type,
        )

    def _message_with_active_rules(self, base_message: str, active_rule_count: int) -> str:
        message = f"{base_message} (active_rules={active_rule_count})"
        if active_rule_count == 0:
            return f"{message}; defaults applied"
        return message

    def _build_news_item_prompt(self, item: Any) -> str:
        template = self._read_prompt_template("lmstudio_news_item_summary_template.md", DEFAULT_NEWS_ITEM_SUMMARY_TEMPLATE)
        title = self._normalize_news_text(getattr(item, "title", ""))
        content, body_source = self._resolve_news_body_context(item)
        body_quality = self._get_news_body_quality(content)
        snippet = self._truncate_text(self._normalize_news_text(content), 240)
        content_for_prompt = self._truncate_news_body_text(content, MAX_NEWS_BODY_CHARS)
        if body_quality in {"empty", "short"}:
            content_for_prompt = "\n".join(part for part in [content_for_prompt, NEWS_BODY_MISSING_MESSAGE] if part).strip()
        content_for_prompt = content_for_prompt or NEWS_BODY_MISSING_MESSAGE
        logger.debug(
            "news_ai_summary prompt_input news_id=%s title_len=%s content_len=%s snippet_len=%s body_source=%s body_quality=%s",
            getattr(item, "id", None),
            len(title),
            len(content_for_prompt),
            len(snippet),
            body_source,
            body_quality,
        )
        return (
            template.replace("{{stock_name}}", getattr(item, "stock_name", None) or "정보 없음")
            .replace("{{stock_code}}", getattr(item, "stock_code", None) or "정보 없음")
            .replace("{{title}}", self._truncate_text(title, 200))
            .replace("{{published_at}}", item.published_at or "정보 없음")
            .replace("{{body_source}}", body_source)
            .replace("{{body_quality}}", body_quality)
            .replace("{{summary}}", content_for_prompt)
            .replace("{{content}}", content_for_prompt)
            .replace("{{snippet}}", snippet or "정보 없음")
            .replace("{{source}}", item.source or "정보 없음")
            .replace("{{url}}", getattr(item, "url", None) or "정보 없음")
        )

    def _build_disclosure_item_prompt(self, item: Any, disclosure_body: str, body_source: str, body_quality: str) -> str:
        template = self._read_prompt_template("lmstudio_disclosure_item_summary_template.md", DEFAULT_DISCLOSURE_ITEM_SUMMARY_TEMPLATE)
        body_for_prompt = self._truncate_disclosure_body_text(disclosure_body, MAX_DISCLOSURE_BODY_CHARS)
        if body_quality in {"missing", "short", "navigation_only"}:
            body_for_prompt = "\n".join(part for part in [body_for_prompt, DISCLOSURE_BODY_MISSING_MESSAGE] if part).strip()
        body_for_prompt = body_for_prompt or DISCLOSURE_BODY_MISSING_MESSAGE
        return (
            template.replace("{{disclosure_title}}", self._truncate_text(item.disclosure_title, 220))
            .replace("{{disclosure_type}}", item.disclosure_type or "정보 없음")
            .replace("{{disclosed_at}}", item.disclosed_at or "정보 없음")
            .replace("{{dart_receipt_no}}", getattr(item, "dart_receipt_no", None) or "정보 없음")
            .replace("{{dart_url}}", getattr(item, "url", None) or "정보 없음")
            .replace("{{body_source}}", body_source)
            .replace("{{body_quality}}", body_quality)
            .replace("{{disclosure_body}}", body_for_prompt)
        )

    def _build_chunk_prompt(self, source_label: str, items_text: str) -> str:
        template = self._read_prompt_template("lmstudio_chunk_summary_template.md", DEFAULT_CHUNK_SUMMARY_TEMPLATE)
        return template.replace("{{source_label}}", source_label).replace("{{items}}", items_text)

    def _build_final_prompt(
        self,
        stock_name: str,
        stock_code: str,
        analysis_date: str,
        news_summary: str,
        disclosure_summary: str,
    ) -> str:
        template = self._read_prompt_template("lmstudio_summary_template.md", DEFAULT_FINAL_SUMMARY_TEMPLATE)
        return (
            template.replace("{{stock_name}}", stock_name)
            .replace("{{stock_code}}", stock_code)
            .replace("{{analysis_date}}", analysis_date)
            .replace("{{news_summary}}", news_summary)
            .replace("{{disclosure_summary}}", disclosure_summary)
        )

    def _read_prompt_template(self, filename: str, fallback_template: str) -> str:
        template_path = PROJECT_ROOT / "prompts" / filename
        try:
            return template_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("Prompt template not found: %s. Using fallback template.", template_path)
            return fallback_template

    def _format_news_chunk(self, items: list[Any]) -> str:
        lines: list[str] = []
        for item in items:
            lines.append(f"- 제목: {self._truncate_text(item.title, 150)}")
            lines.append(f"  발행일: {item.published_at or '정보 없음'}")
            lines.append(f"  요약: {self._truncate_text(item.summary, LLM_MAX_ITEM_SUMMARY_CHARS) or '정보 없음'}")
            lines.append(f"  URL: {item.url or '정보 없음'}")
        return "\n".join(lines)

    def _format_disclosure_chunk(self, items: list[Any]) -> str:
        lines: list[str] = []
        for item in items:
            lines.append(f"- 공시 제목: {self._truncate_text(item.disclosure_title, 200)}")
            lines.append(f"  공시일: {item.disclosed_at or '정보 없음'}")
            lines.append(f"  공시 유형: {item.disclosure_type or '정보 없음'}")
            lines.append(f"  URL: {item.url or '정보 없음'}")
        return "\n".join(lines)

    def _chunk_items(self, items: list[Any], chunk_size: int) -> list[list[Any]]:
        return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]

    def _truncate_text(self, value: str | None, max_chars: int) -> str:
        if not value:
            return ""
        text = value.strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    def _normalize_markdown_for_validation(self, text: str) -> str:
        normalized = (text or "").strip().replace("\ufeff", "")
        if normalized.startswith("```markdown"):
            normalized = normalized.replace("```markdown", "", 1).strip()
        if normalized.startswith("```"):
            normalized = normalized.replace("```", "", 1).strip()
        if normalized.endswith("```"):
            normalized = normalized[:-3].strip()
        return normalized.replace("\r\n", "\n")

    def _normalize_report_headings(self, text: str) -> str:
        normalized = text
        replacements = {
            "# 삼성전자 리서치 브리핑": "# 종목 리서치 브리핑",
            "## 핵심 이슈": "## 1. 핵심 이슈",
            "## 긍정 요인": "## 2. 긍정 요인",
            "## 리스크": "## 3. 부정 요인 및 리스크",
            "## 부정 요인": "## 3. 부정 요인 및 리스크",
            "## 확인 사항": "## 4. 추가 확인 사항",
            "## 추가 확인": "## 4. 추가 확인 사항",
            "## 투자 메모": "## 5. 투자 검토 메모",
        }
        for src, dst in replacements.items():
            normalized = normalized.replace(src, dst)
        if "# 종목 리서치 브리핑" not in normalized:
            normalized = "# 종목 리서치 브리핑\n\n" + normalized
        return normalized

    def _validate_report_complete(self, markdown_text: str) -> tuple[bool, list[str]]:
        checks = {
            "종목 리서치 브리핑": ["종목 리서치 브리핑"],
            "핵심 이슈": ["핵심 이슈"],
            "긍정 요인": ["긍정 요인"],
            "부정 요인 및 리스크": ["부정", "리스크"],
            "추가 확인 사항": ["추가 확인", "확인 사항"],
            "투자 검토 메모": ["투자 검토", "투자 메모"],
        }
        missing: list[str] = []
        lowered = markdown_text
        for label, patterns in checks.items():
            if not any(p in lowered for p in patterns):
                missing.append(label)
        return len(missing) == 0, missing

    def _save_report_file(self, stock_code: str, markdown_text: str) -> str:
        report_dir = (PROJECT_ROOT / LLM_REPORT_BASE_DIR).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)

        date_part = now_kst().split(" ")[0]
        base_name = f"{stock_code}_{date_part}_llm_briefing.md"
        path = report_dir / base_name
        if path.exists():
            ts = now_kst().split(" ")[1].replace(":", "")
            path = report_dir / f"{stock_code}_{date_part}_{ts}_llm_briefing.md"

        path.write_text(markdown_text, encoding="utf-8")
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")

    def _save_failed_llm_output(self, purpose: str, normalized_output: str, missing: list[str]) -> None:
        debug_dir = PROJECT_ROOT / "data" / "debug" / "llm_failed"
        debug_dir.mkdir(parents=True, exist_ok=True)
        filename = f"failed_{purpose}_{now_kst().replace(' ', '_').replace(':', '')}.md"
        payload = (
            f"purpose: {purpose}\n"
            f"missing_sections: {', '.join(missing)}\n\n"
            "## normalized_output\n"
            f"{normalized_output}\n"
        )
        (debug_dir / filename).write_text(payload, encoding="utf-8")

    def _clean_item_summary_text(self, text: str | None) -> str:
        if not text:
            return ""
        cleaned = (text or "").strip().replace("\ufeff", "")
        cleaned = cleaned.replace("\r\n", "\n").strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        prefixes = ["출력:", "요약:", "투자 관점 요약:", "최종 답변:"]
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
        return cleaned

    def _parse_simple_news_summary_payload(self, text: str, item: Any | None = None) -> dict[str, Any] | None:
        payload = self._extract_json_object(text)
        if not payload:
            repaired = self._repair_json_like_text(text)
            payload = self._extract_json_object(repaired)
        if not payload:
            logger.warning("news_ai_summary simple parse failed after repair")
            return None

        title_text = self._normalize_news_text(getattr(item, "title", "")) if item is not None else ""
        content_text = self._resolve_news_body_text(item) if item is not None else ""
        summary = self._normalize_summary_text(payload.get("summary"))
        if not summary:
            summary = self._fallback_simple_news_summary_text(title_text, content_text)

        keywords = self._normalize_string_list(payload.get("keywords"))
        keywords = self._normalize_simple_news_keywords(keywords)
        if not keywords:
            keywords = self._fallback_news_keywords(f"{title_text} {content_text}")

        importance_score = self._normalize_importance_score(payload.get("importance_score"))
        if importance_score is None:
            importance_score = self._normalize_importance_score(getattr(item, "importance_score", None)) if item is not None else None
        if importance_score is None:
            importance_score = 30

        return {
            "summary": summary,
            "keywords": keywords,
            "importance_score": importance_score,
        }

    def _is_valid_simple_news_summary(self, payload: dict[str, Any]) -> bool:
        summary = self._normalize_news_text(payload.get("summary"))
        keywords = payload.get("keywords") or []
        return len(summary) >= 12 and bool(keywords) and self._normalize_importance_score(payload.get("importance_score")) is not None

    def _score_simple_news_summary(self, payload: dict[str, Any], raw_response: str | None = None) -> int:
        score = 0
        summary_len = len(self._normalize_news_text(payload.get("summary")))
        keywords = payload.get("keywords") or []
        if summary_len >= 40:
            score += 55
        elif summary_len >= 20:
            score += 40
        elif summary_len >= 12:
            score += 25
        if 3 <= len(keywords) <= 8:
            score += 30
        elif keywords:
            score += 15
        if self._normalize_importance_score(payload.get("importance_score")) is not None:
            score += 15
        raw = (raw_response or "").lower()
        if any(term in raw for term in ["thinking", "reasoning", "analysis:", "cannot", "unable"]):
            score -= 30
        return max(0, min(100, score))

    def _format_simple_news_summary(self, payload: dict[str, Any]) -> str:
        summary = self._normalize_summary_text(payload.get("summary")) or "-"
        keywords = self._normalize_simple_news_keywords(payload.get("keywords") or [])
        score = self._normalize_importance_score(payload.get("importance_score"))
        return "\n\n".join(
            [
                "[기사 요약]\n" + summary,
                "[관련 키워드]\n" + (", ".join(keywords) if keywords else "-"),
                f"[중요도]\n{30 if score is None else score}",
            ]
        )

    def _build_simple_news_summary_fallback(self, item: Any, reason: str) -> dict[str, Any]:
        title = self._normalize_news_text(getattr(item, "title", "")) or "제목 정보 없음"
        content = self._resolve_news_body_text(item)
        summary = self._fallback_simple_news_summary_text(title, content)
        keywords = self._fallback_news_keywords(f"{title} {content}")
        score = self._fallback_news_importance_score(item)
        return {
            "summary": summary,
            "keywords": keywords,
            "importance_score": score,
            "error_reason": reason,
        }

    def _fallback_simple_news_summary_text(self, title: str, content: str) -> str:
        title_text = self._truncate_text(self._normalize_news_text(title), 120)
        content_text = self._normalize_news_body_text(content)
        if len(self._normalize_news_text(content_text)) < 100:
            return f"{title_text or '뉴스'} 기사입니다. {NEWS_BODY_MISSING_MESSAGE}"

        sentences = self._split_korean_sentences(content_text)
        picked: list[str] = [sentence for sentence in sentences[:3] if sentence]
        if picked:
            prefix = f"{title_text} 기사입니다. " if title_text else ""
            suffix = ""
            if self._get_news_body_quality(content_text) == "short":
                suffix = " 다만 현재 수집된 본문만으로는 세부 사업 규모나 직접적인 실적 영향까지는 확인하기 어렵다."
            return prefix + " ".join(picked) + suffix

        picked = []
        for paragraph in self._split_news_paragraphs(content_text):
            if paragraph and paragraph not in picked:
                picked.append(self._truncate_text(paragraph, 220))
            if len(picked) >= 5:
                break
        if picked:
            return "\n".join(picked)
        return f"{title_text or '뉴스'} 기사입니다. {NEWS_BODY_MISSING_MESSAGE}"

    def _normalize_simple_news_keywords(self, keywords: Any) -> list[str]:
        raw_keywords = self._normalize_string_list(keywords)
        filtered: list[str] = []
        blocked_prefixes = ("risk:", "event:", "relevance:")
        for keyword in raw_keywords:
            value = self._normalize_news_text(keyword).strip(" ,.#")
            if not value or value.lower().startswith(blocked_prefixes):
                continue
            if value not in filtered:
                filtered.append(value)
            if len(filtered) >= 8:
                break
        return filtered

    def _fallback_news_keywords(self, text: str) -> list[str]:
        normalized = self._normalize_news_text(text)
        tokens = re.findall(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9·\-/]{1,24}", normalized)
        stopwords = {
            "뉴스",
            "기사",
            "관련",
            "오늘",
            "기준",
            "대한",
            "이번",
            "지난",
            "있는",
            "없는",
            "으로",
            "에서",
            "투자",
            "시장",
        }
        keywords: list[str] = []
        for token in tokens:
            value = token.strip(" ,.")
            if len(value) < 2 or value in stopwords:
                continue
            if value not in keywords:
                keywords.append(value)
            if len(keywords) >= 5:
                break
        return keywords or ["뉴스"]

    def _parse_news_summary_payload(self, text: str) -> dict[str, Any] | None:
        payload = self._extract_json_object(text)
        if not payload:
            repaired = self._repair_json_like_text(text)
            payload = self._extract_json_object(repaired)
        if not payload:
            logger.warning("news_ai_summary parse failed after repair")
            return None
        key_facts = self._normalize_string_list(payload.get("key_facts"))
        if not key_facts:
            key_facts = self._normalize_string_list(payload.get("positive_factors"))
        keywords = self._normalize_string_list(payload.get("keywords"))
        if not keywords:
            keywords = self._normalize_string_list(payload.get("tags"))
        follow_up_points = self._normalize_string_list(payload.get("follow_up_points"))
        if not key_facts:
            key_facts = ["원문에서 확인 가능한 구체 사실은 제한적입니다."]
        if not keywords:
            keywords = ["뉴스"]
        if not follow_up_points:
            follow_up_points = ["관련 공시와 이후 주가/거래량 반응을 추가 확인해 주세요."]
        relevance_level = str(payload.get("relevance_level", "")).strip().lower()
        if relevance_level not in {"high", "medium", "low"}:
            relevance_level = "medium"
        relevance_reason = str(payload.get("relevance_reason", "")).strip()
        if not relevance_reason:
            relevance_reason = "후속 분석 참고용으로 원문 핵심 사실을 정리했습니다."
        return {
            "summary": str(payload.get("summary", "")).strip(),
            "key_facts": key_facts,
            "keywords": keywords,
            "relevance_level": relevance_level,
            "relevance_reason": relevance_reason,
            "follow_up_points": follow_up_points,
            "sentiment": self._normalize_sentiment(payload.get("sentiment")) or "neutral",
            "importance_score": self._normalize_importance_score(payload.get("importance_score")) or 50,
            "risk_level": self._normalize_risk_level(payload.get("risk_level")) or "unknown",
            "event_type": self._normalize_event_type(payload.get("event_type")) or "other",
            "tags": self._normalize_string_list(payload.get("tags")),
            "key_numbers": self._normalize_string_list(payload.get("key_numbers")),
            "risk_level_reason": str(payload.get("risk_level_reason", "")).strip(),
            "event_type_reason": str(payload.get("event_type_reason", "")).strip(),
        }

    def _normalize_string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return []

    def _normalize_news_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            text = " ".join(self._normalize_news_text(v) for v in value if v is not None)
        elif isinstance(value, dict):
            text = json.dumps(value, ensure_ascii=False)
        else:
            text = str(value)
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = ast.literal_eval(text)
                    if isinstance(parsed, (list, tuple)):
                        text = " ".join(str(v) for v in parsed if v)
                except Exception:  # noqa: BLE001
                    pass
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("\\n", " ").replace("\\t", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _resolve_news_body_text(self, item: Any) -> str:
        return self._resolve_news_body_context(item)[0]

    def _resolve_news_body_context(self, item: Any) -> tuple[str, str]:
        if item is None:
            return "", "missing"

        item_id = getattr(item, "id", None)
        if isinstance(item_id, int) and item_id in self._news_body_context_cache:
            return self._news_body_context_cache[item_id]

        article_text = self._fetch_news_article_body(getattr(item, "url", None))
        if len(self._normalize_news_text(article_text)) >= 100:
            result = (article_text, "article_url")
            if isinstance(item_id, int):
                self._news_body_context_cache[item_id] = result
            return result

        summary_text = self._normalize_news_body_text(getattr(item, "summary", ""))
        if len(self._normalize_news_text(summary_text)) >= 30:
            result = (summary_text, "stored_description")
            if isinstance(item_id, int):
                self._news_body_context_cache[item_id] = result
            return result

        raw_text = self._read_news_raw_text(getattr(item, "raw_text_path", None), getattr(item, "url", None))
        if raw_text:
            result = (raw_text, "raw_response")
            if isinstance(item_id, int):
                self._news_body_context_cache[item_id] = result
            return result

        result = (summary_text, "missing")
        if isinstance(item_id, int):
            self._news_body_context_cache[item_id] = result
        return result

    def _fetch_news_article_body(self, url: str | None) -> str:
        normalized_url = str(url or "").strip()
        if not normalized_url.startswith(("http://", "https://")):
            return ""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        }
        try:
            response = requests.get(
                normalized_url,
                headers=headers,
                timeout=NEWS_ARTICLE_FETCH_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if content_type and "html" not in content_type and "text" not in content_type:
                return ""
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding or "utf-8"
            return self._extract_news_article_body_from_html(response.text)
        except Exception as exc:  # noqa: BLE001
            logger.info("news article body fetch skipped: url=%s reason=%s", normalized_url, exc)
            return ""

    def _extract_news_article_body_from_html(self, html_text: str) -> str:
        if not html_text:
            return ""

        cleaned = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html_text)
        cleaned = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", cleaned)
        cleaned = re.sub(r"(?is)<svg[^>]*>.*?</svg>", " ", cleaned)

        candidate_htmls: list[str] = []
        for tag in ("article", "main"):
            candidate_htmls.extend(re.findall(rf"(?is)<{tag}\b[^>]*>.*?</{tag}>", cleaned))

        attr_pattern = (
            r"(?is)<(?P<tag>div|section)\b(?=[^>]*(?:id|class)\s*=\s*"
            r"['\"][^'\"]*(?:article|news|body|content|view|read|본문|기사)[^'\"]*['\"])[^>]*>"
            r"(?P<body>.*?)</(?P=tag)>"
        )
        candidate_htmls.extend(match.group(0) for match in re.finditer(attr_pattern, cleaned))

        candidates = [self._html_to_news_text(candidate) for candidate in candidate_htmls]
        candidates = [candidate for candidate in candidates if len(self._normalize_news_text(candidate)) >= 200]
        if candidates:
            return max(candidates, key=lambda value: len(self._normalize_news_text(value)))

        return self._extract_news_text_from_full_html(cleaned)

    def _html_to_news_text(self, html_text: str) -> str:
        text = re.sub(r"(?i)<br\s*/?>", "\n", html_text)
        text = re.sub(r"(?i)</p\s*>", "\n", text)
        text = re.sub(r"(?i)</div\s*>", "\n", text)
        text = re.sub(r"(?i)</li\s*>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        return self._filter_article_lines(text)

    def _extract_news_text_from_full_html(self, html_text: str) -> str:
        text = self._html_to_news_text(html_text)
        paragraphs = self._split_news_paragraphs(text)
        return "\n".join(paragraphs[:20])

    def _filter_article_lines(self, text: str) -> str:
        normalized = self._normalize_news_body_text(text)
        blocked_terms = (
            "무단전재",
            "재배포 금지",
            "저작권",
            "copyright",
            "관련기사",
            "많이 본 뉴스",
            "구독",
            "로그인",
            "댓글",
            "광고",
            "제보",
            "기자",
        )
        lines: list[str] = []
        for line in normalized.split("\n"):
            compact = self._normalize_news_text(line)
            if len(compact) < 25:
                continue
            lowered = compact.lower()
            if any(term in lowered for term in blocked_terms) and len(compact) < 120:
                continue
            lines.append(compact)
        return "\n".join(lines)

    def _read_news_raw_text(self, raw_text_path: str | None, url: str | None = None) -> str:
        if not raw_text_path:
            return ""
        try:
            path = Path(raw_text_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if not path.exists():
                return ""
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return ""

        entries = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return ""

        target_url = str(url or "").strip()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_url = str(entry.get("originallink") or entry.get("link") or "").strip()
            if target_url and entry_url and entry_url != target_url:
                continue
            for key in ("content", "body", "raw_content", "text_content", "description", "summary"):
                value = self._normalize_news_body_text(entry.get(key))
                if len(self._normalize_news_text(value)) >= 80:
                    return value
        return ""

    def _get_news_body_quality(self, body: str) -> str:
        length = len(self._normalize_news_text(body))
        if length < 100:
            return "empty"
        if length < 500:
            return "short"
        return "sufficient"

    def _normalize_news_body_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            text = "\n".join(str(v) for v in value if v is not None)
        elif isinstance(value, dict):
            text = json.dumps(value, ensure_ascii=False)
        else:
            text = str(value)
        text = html.unescape(text)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</p\s*>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line).strip()

    def _normalize_summary_text(self, value: Any) -> str:
        text = self._normalize_news_body_text(value)
        lines = [self._normalize_news_text(line) for line in text.split("\n")]
        return "\n".join(line for line in lines if line).strip()

    def _truncate_news_body_text(self, value: str, max_chars: int) -> str:
        text = self._normalize_news_body_text(value)
        if len(text) <= max_chars:
            return text
        head_chars = min(2500, max_chars)
        tail_chars = max(0, max_chars - head_chars)
        head = text[:head_chars].rstrip()
        tail = text[-tail_chars:].lstrip() if tail_chars else ""
        head_cut = max(head.rfind("\n\n"), head.rfind("\n"))
        if head_cut >= head_chars // 2:
            head = head[:head_cut].rstrip()
        tail_cut = min((cut for cut in [tail.find("\n\n"), tail.find("\n")] if cut >= 0), default=-1)
        if tail_cut >= 0 and tail_cut < len(tail) // 2:
            tail = tail[tail_cut:].lstrip()
        if not tail:
            return head + "\n..."
        return head + "\n...\n[본문 후반부]\n" + tail

    def _split_news_paragraphs(self, value: str) -> list[str]:
        paragraphs = []
        blocked_terms = ("무단전재", "재배포 금지", "저작권", "기자", "구독", "광고", "제보")
        for paragraph in self._normalize_news_body_text(value).split("\n"):
            normalized = self._normalize_news_text(paragraph)
            if len(normalized) < 25:
                continue
            if any(term in normalized for term in blocked_terms) and len(normalized) < 80:
                continue
            paragraphs.append(normalized)
        return paragraphs

    def _split_korean_sentences(self, value: str) -> list[str]:
        text = self._normalize_news_body_text(value)
        sentences: list[str] = []
        for paragraph in self._split_news_paragraphs(text):
            parts = re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+", paragraph)
            for part in parts:
                sentence = self._normalize_news_text(part)
                if len(sentence) < 20:
                    continue
                sentences.append(self._truncate_text(sentence, 240))
                if len(sentences) >= 6:
                    return sentences
        return sentences

    def _extract_first_sentence(self, paragraph: str) -> str:
        normalized = self._normalize_news_text(paragraph)
        if not normalized:
            return ""
        sentences = re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+", normalized)
        sentence = next((item.strip() for item in sentences if item.strip()), normalized)
        return self._truncate_text(sentence, 220)

    def _fallback_news_importance_score(self, item: Any) -> int:
        existing_score = self._normalize_importance_score(getattr(item, "importance_score", None))
        if existing_score and existing_score > 0:
            return existing_score
        relevance = str(
            getattr(item, "relevance_level", None)
            or getattr(item, "ai_relevance_level", None)
            or getattr(item, "relevance", None)
            or ""
        ).strip().lower()
        relevance_scores = {
            "direct": 75,
            "strong": 65,
            "indirect": 45,
            "low": 30,
            "exclude": 15,
        }
        return relevance_scores.get(relevance, 30)

    def _parse_simple_disclosure_summary_payload(self, text: str, item: Any | None = None, disclosure_body: str = "") -> dict[str, Any] | None:
        payload = self._extract_json_object(text)
        if not payload:
            repaired = self._repair_json_like_text(text)
            payload = self._extract_json_object(repaired)
        if not payload:
            logger.warning("disclosure_ai_summary simple parse failed after repair")
            return None

        title_text = self._normalize_news_text(getattr(item, "disclosure_title", "")) if item is not None else ""
        body_text = self._normalize_news_body_text(disclosure_body)
        summary = self._normalize_summary_text(payload.get("summary"))
        if not summary:
            summary = self._fallback_simple_disclosure_summary_text(title_text, body_text)

        keywords = self._normalize_simple_news_keywords(payload.get("keywords"))
        if not keywords:
            keywords = self._fallback_news_keywords(f"{title_text} {body_text}")

        importance_score = self._normalize_importance_score(payload.get("importance_score"))
        if importance_score is None:
            importance_score = self._normalize_importance_score(getattr(item, "importance_score", None)) if item is not None else None
        if importance_score is None:
            importance_score = 30

        return {
            "summary": summary,
            "keywords": keywords,
            "importance_score": importance_score,
        }

    def _format_simple_disclosure_summary(self, payload: dict[str, Any]) -> str:
        summary = self._normalize_summary_text(payload.get("summary")) or DISCLOSURE_BODY_MISSING_MESSAGE
        keywords = self._normalize_simple_news_keywords(payload.get("keywords") or [])
        score = self._normalize_importance_score(payload.get("importance_score"))
        return json.dumps(
            {
                "summary": summary,
                "keywords": keywords,
                "importance_score": 30 if score is None else score,
            },
            ensure_ascii=False,
        )

    def _build_simple_disclosure_summary_fallback(self, item: Any, disclosure_body: str, reason: str) -> dict[str, Any]:
        title = self._normalize_news_text(getattr(item, "disclosure_title", "")) or "공시 제목 정보 없음"
        body_text = self._normalize_news_body_text(disclosure_body or getattr(item, "summary", ""))
        summary = self._fallback_simple_disclosure_summary_text(title, body_text)
        keywords = self._fallback_news_keywords(f"{title} {body_text}")
        score = self._normalize_importance_score(getattr(item, "importance_score", None)) or 30
        return {
            "summary": summary,
            "keywords": keywords,
            "importance_score": score,
            "error_reason": reason,
        }

    def _fallback_simple_disclosure_summary_text(self, title: str, body: str) -> str:
        title_text = self._truncate_text(self._normalize_news_text(title), 120)
        body_text = self._normalize_news_body_text(body)
        if self._get_disclosure_body_quality(body_text) in {"missing", "navigation_only"}:
            return f"{title_text or '공시'} 공시입니다. {DISCLOSURE_BODY_MISSING_MESSAGE}"

        picked: list[str] = []
        for paragraph in self._split_disclosure_paragraphs(body_text):
            sentence = self._extract_first_sentence(paragraph)
            if sentence and sentence not in picked:
                picked.append(sentence)
            if len(picked) >= 6:
                break
        if picked:
            return "\n".join(picked)
        return f"{title_text or '공시'} 공시입니다. {DISCLOSURE_BODY_MISSING_MESSAGE}"

    def _resolve_disclosure_body_text(self, item: Any) -> tuple[str, str | None, str]:
        # 1) Prefer a temporary DART URL fetch. The fetched body is not persisted.
        dart_text, dart_error = self._fetch_dart_disclosure_text(getattr(item, "url", None), getattr(item, "dart_receipt_no", None))
        if dart_text:
            return self._truncate_disclosure_body_text(dart_text, 12000), None, "dart_fetch"

        # 2) Use disclosure fields already persisted in DB.
        db_candidates = [
            getattr(item, "summary", None),
        ]
        for candidate in db_candidates:
            normalized = self._normalize_news_text(candidate)
            if len(normalized) >= 80:
                return self._truncate_disclosure_body_text(self._normalize_news_body_text(candidate), 12000), None, "db_summary"

        # 3) Try the saved raw response file.
        raw_from_file = self._extract_disclosure_text_from_raw_file(getattr(item, "raw_text_path", None), getattr(item, "dart_receipt_no", None))
        if raw_from_file:
            return self._truncate_disclosure_body_text(raw_from_file, 12000), None, "raw_file"

        return "", dart_error or "missing_disclosure_body", "missing"

    def _extract_disclosure_text_from_raw_file(self, raw_text_path: str | None, receipt_no: str | None) -> str:
        if not raw_text_path:
            return ""
        try:
            path = Path(raw_text_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if not path.exists():
                return ""
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return ""

        entries: list[Any] = []
        if isinstance(payload, dict):
            entries = list(payload.get("list") or [])
        if not isinstance(entries, list):
            return ""
        target_receipt = (receipt_no or "").strip()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if target_receipt and str(entry.get("rcept_no") or "").strip() != target_receipt:
                continue
            for key in ("summary", "content", "raw_content", "text_content", "report_content", "rm"):
                value = self._normalize_news_body_text(entry.get(key))
                if len(self._normalize_news_text(value)) >= 80:
                    return value
        return ""

    def _get_disclosure_body_quality(self, body: str) -> str:
        normalized = self._normalize_news_text(body)
        if len(normalized) < 100:
            return "missing"
        if self._looks_like_navigation_only_disclosure(normalized):
            return "navigation_only"
        if len(normalized) < 500:
            return "short"
        return "sufficient"

    def _looks_like_navigation_only_disclosure(self, text: str) -> bool:
        normalized = self._normalize_news_text(text).lower()
        if not normalized:
            return True
        navigation_terms = [
            "문서목차",
            "첨부문서",
            "공시서류검색",
            "viewer",
            "dart",
            "인쇄",
            "닫기",
            "이전",
            "다음",
            "검색",
            "회사명",
            "보고서명",
        ]
        hit_count = sum(1 for term in navigation_terms if term.lower() in normalized)
        business_terms = [
            "계약금액",
            "계약기간",
            "계약상대",
            "매출액",
            "발행주식",
            "보유주식",
            "취득",
            "처분",
            "정정",
            "공급계약",
            "판매",
            "영업이익",
            "당기순이익",
        ]
        has_business_term = any(term in normalized for term in business_terms)
        return hit_count >= 4 and not has_business_term

    def _truncate_disclosure_body_text(self, value: str, max_chars: int) -> str:
        text = self._normalize_news_body_text(value)
        if len(text) <= max_chars:
            return text
        head_chars = min(3000, max_chars)
        tail_chars = max(0, max_chars - head_chars)
        head = text[:head_chars].rstrip()
        tail = text[-tail_chars:].lstrip() if tail_chars else ""
        head_cut = max(head.rfind("\n\n"), head.rfind("\n"))
        if head_cut >= head_chars // 2:
            head = head[:head_cut].rstrip()
        if not tail:
            return head + "\n..."
        return head + "\n...\n[공시 본문 후반부]\n" + tail

    def _split_disclosure_paragraphs(self, value: str) -> list[str]:
        paragraphs: list[str] = []
        blocked_terms = (
            "문서목차",
            "첨부문서",
            "공시서류검색",
            "인쇄",
            "닫기",
            "이전",
            "다음",
            "저작권",
            "copyright",
        )
        for paragraph in self._normalize_news_body_text(value).split("\n"):
            normalized = self._normalize_news_text(paragraph)
            if len(normalized) < 20:
                continue
            if any(term.lower() in normalized.lower() for term in blocked_terms) and len(normalized) < 100:
                continue
            paragraphs.append(normalized)
        return paragraphs

    def _fetch_dart_disclosure_text(self, dart_url: str | None, receipt_no: str | None) -> tuple[str, str | None]:
        rcp_no = self._extract_dart_receipt_no(dart_url, receipt_no)
        if not rcp_no:
            return "", "missing_disclosure_body"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; DrCT-Asset/1.0)"}
        try:
            main_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"
            response = requests.get(main_url, headers=headers, timeout=10)
            response.raise_for_status()
            main_html = response.text
            # Try viewer link parsing first.
            viewer_args = self._extract_dart_viewer_args(main_html, rcp_no)
            if viewer_args:
                viewer_url = (
                    "https://dart.fss.or.kr/report/viewer.do"
                    f"?rcpNo={viewer_args.get('rcpNo') or rcp_no}"
                    f"&dcmNo={viewer_args.get('dcmNo') or ''}"
                    f"&eleId={viewer_args.get('eleId') or '0'}"
                    f"&offset={viewer_args.get('offset') or '0'}"
                    f"&length={viewer_args.get('length') or '0'}"
                    f"&dtd={viewer_args.get('dtd') or 'dart3.xsd'}"
                )
                viewer_response = requests.get(viewer_url, headers=headers, timeout=10)
                viewer_response.raise_for_status()
                if not viewer_response.encoding or viewer_response.encoding.lower() == "iso-8859-1":
                    viewer_response.encoding = viewer_response.apparent_encoding or "utf-8"
                viewer_text = self._extract_visible_disclosure_text_from_html(viewer_response.text)
                if len(viewer_text) >= 80:
                    return viewer_text, None

            # Fallback to main page text (can be sparse if iframe-based, still useful).
            main_text = self._extract_visible_disclosure_text_from_html(main_html)
            if len(main_text) >= 80:
                return main_text, None
            return "", "missing_disclosure_body"
        except Exception:  # noqa: BLE001
            return "", "dart_fetch_failed"

    def _extract_dart_viewer_args(self, main_html: str, receipt_no: str) -> dict[str, str] | None:
        if not main_html:
            return None
        quoted_call_pattern = re.compile(
            r"""viewDoc\(\s*
            (?P<q1>['"])(?P<rcpNo>\d+)(?P=q1)\s*,\s*
            (?P<q2>['"])(?P<dcmNo>\d+)(?P=q2)\s*,\s*
            (?P<q3>['"]?)(?P<eleId>\d*)(?P=q3)\s*,\s*
            (?P<q4>['"]?)(?P<offset>\d*)(?P=q4)\s*,\s*
            (?P<q5>['"]?)(?P<length>\d*)(?P=q5)\s*,\s*
            (?P<q6>['"])(?P<dtd>[^'"]+)(?P=q6)
            (?:\s*,\s*(?P<q7>['"]?)[^'")]*?(?P=q7))?
            \s*\)""",
            re.IGNORECASE | re.VERBOSE,
        )
        for match in quoted_call_pattern.finditer(main_html):
            groups = {key: (value or "") for key, value in match.groupdict().items()}
            if receipt_no and groups.get("rcpNo") != receipt_no:
                continue
            return {
                "rcpNo": groups.get("rcpNo") or receipt_no,
                "dcmNo": groups.get("dcmNo") or "",
                "eleId": groups.get("eleId") or "0",
                "offset": groups.get("offset") or "0",
                "length": groups.get("length") or "0",
                "dtd": groups.get("dtd") or "dart3.xsd",
            }
        return None

    def _extract_dart_receipt_no(self, dart_url: str | None, fallback_receipt_no: str | None) -> str:
        if fallback_receipt_no and str(fallback_receipt_no).strip():
            return str(fallback_receipt_no).strip()
        text = str(dart_url or "")
        match = re.search(r"rcpNo=(\d+)", text)
        return match.group(1) if match else ""

    def _extract_visible_text_from_html(self, html_text: str) -> str:
        if not html_text:
            return ""
        cleaned = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html_text)
        cleaned = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
        cleaned = cleaned.replace("\xa0", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _extract_visible_disclosure_text_from_html(self, html_text: str) -> str:
        if not html_text:
            return ""
        cleaned = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html_text)
        cleaned = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?is)<nav[^>]*>.*?</nav>", " ", cleaned)
        cleaned = re.sub(r"(?is)<header[^>]*>.*?</header>", " ", cleaned)
        cleaned = re.sub(r"(?is)<footer[^>]*>.*?</footer>", " ", cleaned)
        cleaned = re.sub(r"(?is)<button[^>]*>.*?</button>", " ", cleaned)
        cleaned = re.sub(r"(?is)<select[^>]*>.*?</select>", " ", cleaned)
        cleaned = re.sub(r"(?is)<option[^>]*>.*?</option>", " ", cleaned)
        cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
        cleaned = re.sub(r"(?i)</p\s*>", "\n", cleaned)
        cleaned = re.sub(r"(?i)</tr\s*>", "\n", cleaned)
        cleaned = re.sub(r"(?i)</td\s*>", " ", cleaned)
        cleaned = re.sub(r"(?i)</th\s*>", " ", cleaned)
        cleaned = re.sub(r"(?i)</div\s*>", "\n", cleaned)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
        cleaned = cleaned.replace("\xa0", " ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in cleaned.split("\n")]
        return "\n".join(line for line in lines if line).strip()

    def _normalize_sentiment(self, value: Any) -> str | None:
        normalized = str(value or "").strip().lower()
        return normalized if normalized in {"positive", "neutral", "negative"} else None

    def _normalize_importance_score(self, value: Any) -> int | None:
        try:
            score = int(float(value))
        except (TypeError, ValueError):
            return None
        return max(0, min(100, score))

    def _normalize_risk_level(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        return normalized if normalized in {"low", "medium", "high", "unknown"} else "unknown"

    def _normalize_event_type(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        allowed = {
            "earnings",
            "contract",
            "investment",
            "regulation",
            "lawsuit",
            "product",
            "market",
            "supply",
            "policy",
            "real_estate",
            "project",
            "financing",
            "disclosure_correction",
            "governance",
            "report",
            "other",
        }
        return normalized if normalized in allowed else "other"

    def _infer_disclosure_event_type(self, title: str | None, disclosure_type: str | None, current: str) -> str:
        base = str(current or "").strip().lower()
        if base in {"governance", "disclosure_correction", "financing", "contract", "investment", "lawsuit", "report", "earnings"}:
            return base
        text = f"{title or ''} {disclosure_type or ''}".lower()
        if any(keyword in text for keyword in ["지배구조", "기업지배구조"]):
            return "governance"
        if any(keyword in text for keyword in ["정정", "정정공시"]):
            return "disclosure_correction"
        if any(keyword in text for keyword in ["유상증자", "cb", "bw", "전환사채", "신주인수권부사채"]):
            return "financing"
        if any(keyword in text for keyword in ["공급계약", "수주", "계약"]):
            return "contract"
        if any(keyword in text for keyword in ["소송", "판결", "가처분"]):
            return "lawsuit"
        if any(keyword in text for keyword in ["사업보고서", "분기보고서", "반기보고서"]):
            return "report"
        return self._normalize_event_type(base)

    def _infer_disclosure_risk_level(self, title: str | None, disclosure_type: str | None, current: str) -> str:
        level = self._normalize_risk_level(current)
        if level in {"low", "medium", "high"}:
            return level
        text = f"{title or ''} {disclosure_type or ''}".lower()
        if any(keyword in text for keyword in ["지배구조", "기업지배구조"]):
            return "low"
        return "unknown"

    def _normalize_tags(self, value: Any) -> str:
        tags = self._normalize_string_list(value)
        return ",".join(tags)

    def _extract_key_numbers(self, text: str) -> list[str]:
        if not text:
            return []
        patterns = [
            r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:억원|만원|원|세대|가구|건|명|평|㎡|%|조)",
            r"\d+\s*:\s*\d+",
        ]
        found: list[str] = []
        for pattern in patterns:
            for match in re.findall(pattern, text):
                value = str(match).strip()
                if value and value not in found:
                    found.append(value)
                if len(found) >= 8:
                    return found
        return found

    def _infer_risk_level(self, title: str, content: str, current: str) -> str:
        if current in {"low", "medium", "high"}:
            return current
        text = f"{title} {content}".lower()
        high_words = ["소송", "법원", "거래정지", "상장폐지", "채무불이행", "압수수색", "횡령", "배임"]
        medium_words = ["미분양", "청약", "분양가", "pf", "차입", "자금조달", "지연", "불확실", "우려", "리스크"]
        low_words = ["출시", "공급", "납품", "호조", "확대", "수주"]
        if any(word in text for word in high_words):
            return "high"
        if any(word in text for word in medium_words):
            return "medium"
        if any(word in text for word in low_words):
            return "low"
        return "unknown"

    def _infer_event_type(self, title: str, content: str, current: str) -> str:
        if current != "other":
            return current
        text = f"{title} {content}".lower()
        rules = [
            ("real_estate", ["분양", "청약", "주택", "아파트", "오피스텔", "부동산"]),
            ("project", ["프로젝트", "인프라", "개발", "철도", "항만", "공항", "soc"]),
            ("financing", ["pf", "자금조달", "차입", "유상증자"]),
            ("contract", ["수주", "계약", "공급계약", "납품"]),
            ("earnings", ["실적", "매출", "영업이익", "순이익"]),
            ("investment", ["투자", "증설", "공장", "설비"]),
            ("lawsuit", ["소송", "분쟁", "법원", "판결"]),
            ("regulation", ["규제", "허가", "인가", "제재"]),
            ("policy", ["정책", "정부", "공공사업"]),
            ("market", ["시황", "수요", "공급", "가격"]),
        ]
        for event_type, keywords in rules:
            if any(word in text for word in keywords):
                return event_type
        return "other"

    def _normalize_importance_with_context(self, score: Any, event_type: str, risk_level: str, key_numbers: list[str]) -> int:
        normalized = self._normalize_importance_score(score)
        value = 50 if normalized is None else normalized
        if 0 <= value <= 10:
            value *= 10
        if event_type in {"earnings", "contract", "real_estate", "project"}:
            value = max(value, 55)
        if risk_level == "high":
            value = max(value, 80)
        elif risk_level == "medium":
            value = max(value, 55)
        if key_numbers:
            value = min(100, value + 5)
        return max(0, min(100, value))

    def _is_valid_structured_summary(self, payload: dict[str, Any]) -> bool:
        summary = str(payload.get("summary", "")).strip()
        key_facts = payload.get("key_facts") or []
        keywords = payload.get("keywords") or []
        follow_ups = payload.get("follow_up_points") or []
        if len(summary) < 20:
            return False
        if not key_facts and not follow_ups:
            return False
        if not keywords:
            return False
        if str(payload.get("relevance_level", "")).lower() not in {"high", "medium", "low"}:
            return False
        return True

    def _format_structured_disclosure_summary(self, payload: dict[str, Any]) -> str:
        summary = str(payload.get("summary", "")).strip() or "-"
        key_facts = payload.get("key_facts") or []
        keywords = payload.get("keywords") or []
        relevance = str(payload.get("relevance_level", "medium")).lower()
        relevance_reason = str(payload.get("relevance_reason", "")).strip() or "후속 분석 참고용으로 정리된 공시입니다."
        follow_ups = payload.get("follow_up_points") or []
        key_numbers = payload.get("key_numbers") or []

        def _section(title: str, items: list[str]) -> str:
            if not items:
                return f"[{title}]\n- 확인 필요"
            return f"[{title}]\n" + "\n".join(f"- {item}" for item in items)

        return "\n\n".join(
            [
                "[공시 요약]\n" + summary,
                _section("주요 사실", key_facts),
                "[주요 수치]\n" + (", ".join(key_numbers) if key_numbers else "-"),
                "[관련 키워드]\n" + (", ".join(keywords) if keywords else "-"),
                f"[투자 관련성]\n{relevance}: {relevance_reason}",
                _section("후속 확인", follow_ups),
            ]
        )

    def _format_structured_news_summary(self, payload: dict[str, Any]) -> str:
        return self._format_structured_disclosure_summary(payload)

    def _build_news_summary_fallback(self, item: Any, reason: str) -> dict[str, Any]:
        title = self._truncate_text(self._normalize_news_text(getattr(item, "title", "")) or "제목 정보 없음", 80)
        return {
            "summary": f"'{title}' 기사의 핵심 내용을 자동 요약하는 과정에서 일부 정보 정리가 제한되었습니다.",
            "key_facts": ["원문 기사에서 확인 가능한 사실 기반으로 재확인이 필요합니다."],
            "keywords": ["뉴스"],
            "relevance_level": "medium",
            "relevance_reason": "후속 분석 참고용으로 원문 사실 확인이 필요합니다.",
            "follow_up_points": ["원문 기사와 관련 공시를 직접 확인해 주세요."],
            "sentiment": "neutral",
            "importance_score": 50,
            "risk_level": "unknown",
            "event_type": "other",
            "tags": [],
            "error_reason": reason,
        }

    def _build_disclosure_summary_fallback(self, item: Any, reason: str) -> str:
        title = self._truncate_text(str(getattr(item, "disclosure_title", "") or "공시 제목 정보 없음"), 80)
        disclosed_at = self._truncate_text(str(getattr(item, "disclosed_at", "") or "정보 없음"), 20)
        receipt_no = self._truncate_text(str(getattr(item, "dart_receipt_no", "") or "정보 없음"), 20)
        error_code = "dart_fetch_failed" if "dart_fetch_failed" in reason else "missing_disclosure_body"
        reason_text = "공시 본문 미수집" if error_code == "missing_disclosure_body" else "DART 본문 조회 실패"
        body_text = self._normalize_news_body_text(getattr(item, "summary", ""))
        body_sentences = self._split_korean_sentences(body_text)[:4] if len(self._normalize_news_text(body_text)) >= 100 else []
        if body_sentences:
            return (
                "[공시 요약]\n"
                f"{title} 공시입니다. " + " ".join(body_sentences) + "\n\n"
                "[주요 사실]\n"
                + "\n".join(f"- {sentence}" for sentence in body_sentences[:3])
                + "\n\n"
                "[관련 키워드]\n"
                + ", ".join(self._fallback_news_keywords(f"{title} {body_text}"))
                + "\n\n"
                "[투자 관련성]\n"
                "medium: 공시 원문 기반으로 세부 조건과 사업 영향을 추가 확인해야 합니다.\n\n"
                "[후속 확인]\n"
                "- 계약금액, 계약기간, 상대방, 정정 여부를 DART 원문에서 확인하세요.\n"
                "- 해당 공시가 매출과 수주잔고에 반영되는 시점을 추가 확인하세요."
            )
        return (
            "[공시 요약]\n"
            "공시 원문 본문을 확보하지 못해 상세 요약을 생성할 수 없습니다. 제목/접수정보 기준 최소 사실만 정리합니다.\n\n"
            "[주요 사실]\n"
            f"- 공시명: {title}\n"
            f"- 공시일: {disclosed_at}\n"
            f"- 접수번호: {receipt_no}\n\n"
            "[관련 키워드]\n"
            "DART, 공시, 본문미수집\n\n"
            "[투자 관련성]\n"
            f"low: {reason_text} 상태로 원문 사실 확인이 선행되어야 합니다.\n\n"
            "[후속 확인]\n"
            "- DART 원문을 직접 열어 핵심 수치/일정/의사결정 항목을 확인하세요.\n"
            "- 공시 본문 수집 상태를 점검한 뒤 AI 요약을 다시 실행하세요."
        )

    def _repair_json_like_text(self, text: str) -> str:
        candidate = (text or "").strip()
        candidate = candidate.replace("“", '"').replace("”", '"').replace("’", "'")
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        return candidate

    def _score_structured_summary(self, payload: dict[str, Any], raw_response: str | None = None) -> int:
        score = 0
        if payload:
            score += 30
        summary_len = len(str(payload.get("summary", "")).strip())
        key_facts = payload.get("key_facts") or []
        keywords = payload.get("keywords") or []
        follow_ups = payload.get("follow_up_points") or []
        relevance_level = str(payload.get("relevance_level", "")).strip().lower()
        if summary_len >= 40:
            score += 15
        elif summary_len >= 20:
            score += 8
        if key_facts:
            score += 5
        if keywords:
            score += 5
        if follow_ups:
            score += 5
        if relevance_level in {"high", "medium", "low"}:
            score += 5
        if self._normalize_sentiment(payload.get("sentiment")):
            score += 5
        if self._normalize_importance_score(payload.get("importance_score")) is not None:
            score += 5
        if self._normalize_risk_level(payload.get("risk_level")) != "unknown":
            score += 3
        if self._normalize_event_type(payload.get("event_type")) not in {"other"}:
            score += 3
        raw = (raw_response or "").lower()
        if any(term in raw for term in ["실패", "생성하지 못", "unable", "cannot"]):
            score -= 40
        return max(0, min(100, score))

    def _looks_like_reasoning_output(self, text: str) -> bool:
        lowered = (text or "").lower()
        markers = [
            "thinking process",
            "analyze the request",
            "analysis:",
            "reasoning",
            "final json construction",
            "draft the summary",
            "determine sentiment",
        ]
        return any(marker in lowered for marker in markers)

    def _is_valid_item_summary(self, text: str) -> bool:
        if not text:
            return False
        if self._looks_like_reasoning_output(text):
            return False
        if text.startswith("{") or '"ai_summary"' in text:
            return False
        if len(text) < 30 or len(text) > 2000:
            return False

        valid_endings = (".", "다.", "요.", "함.", "됨.", "필요하다.", "필요합니다.")
        return text.rstrip().endswith(valid_endings)

    def _extract_json_object(self, text: str) -> dict | None:
        # Keep for structured workflows; not used by item-level summarize in current policy.
        if not text:
            return None
        cleaned = text.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        json_text = cleaned[start : end + 1]
        try:
            obj = json.loads(json_text)
            if isinstance(obj, dict):
                return obj
        except Exception:  # noqa: BLE001
            return None
        return None
