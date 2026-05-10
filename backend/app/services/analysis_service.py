from __future__ import annotations

import json
import logging
from typing import Any

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
        rules = self.classification_rule_repo.list_active_by_target("news")
        self._warn_if_no_active_rules(target_type="news", active_rule_count=len(rules))
        item_system_prompt = (
            "너는 투자 뉴스와 공시를 짧게 요약하는 보조 AI이다. "
            "내부 사고 과정, Thinking Process, Analysis, Reasoning을 절대 출력하지 마라. "
            "JSON을 출력하지 마라. 완성된 한국어 요약문만 출력하라."
        )

        for item in items:
            processed_at = now_kst()
            base_prompt = self._build_news_item_prompt(item)
            attempts = max(1, LLM_ITEM_SUMMARY_RETRY_COUNT + 1)
            saved = False
            last_error = ""

            for attempt in range(attempts):
                prompt = base_prompt
                if attempt > 0:
                    prompt += "\n\n이전 응답이 형식을 지키지 않았거나 중간에 끊겼습니다. JSON 없이 완성된 한국어 요약문만 3문장으로 다시 작성하세요."
                try:
                    raw = self.llm_client.generate_text(
                        prompt=prompt,
                        temperature=0.1,
                        max_tokens=LLM_ITEM_SUMMARY_MAX_OUTPUT_TOKENS,
                        timeout=LLM_ITEM_SUMMARY_TIMEOUT_SECONDS,
                        purpose=f"news_ai_summary:{item.id}:attempt{attempt + 1}",
                        system_prompt=item_system_prompt,
                    )
                    cleaned = self._clean_item_summary_text(raw)
                    if not self._is_valid_item_summary(cleaned):
                        last_error = "invalid or incomplete item summary"
                        continue

                    classified = self.classifier.classify_news(
                        title=item.title,
                        summary=item.summary,
                        ai_summary=cleaned,
                        rules=rules,
                    )
                    self.news_repo.update_ai_summary(
                        news_id=item.id,
                        ai_summary=cleaned,
                        ai_sentiment=str(classified.get("ai_sentiment", "neutral")),
                        ai_importance_score=int(classified.get("ai_importance_score", 50)),
                        ai_tags=str(classified.get("ai_tags", "뉴스")),
                        ai_processed_at=processed_at,
                        ai_summary_error=None,
                    )
                    success_count += 1
                    saved = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)

            if not saved:
                failed_count += 1
                error_message = last_error or "invalid or empty summary response"
                self.news_repo.mark_ai_summary_failed(
                    news_id=item.id,
                    error_message=error_message,
                    ai_processed_at=processed_at,
                )

        return AiSummarizeResponse(
            status="success",
            target="news",
            processed_count=len(items),
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            message=self._message_with_active_rules("news ai summary completed", len(rules)),
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
        rules = self.classification_rule_repo.list_active_by_target("disclosure")
        self._warn_if_no_active_rules(target_type="disclosure", active_rule_count=len(rules))
        item_system_prompt = (
            "너는 투자 뉴스와 공시를 짧게 요약하는 보조 AI이다. "
            "내부 사고 과정, Thinking Process, Analysis, Reasoning을 절대 출력하지 마라. "
            "JSON을 출력하지 마라. 완성된 한국어 요약문만 출력하라."
        )

        for item in items:
            processed_at = now_kst()
            base_prompt = self._build_disclosure_item_prompt(item)
            attempts = max(1, LLM_ITEM_SUMMARY_RETRY_COUNT + 1)
            saved = False
            last_error = ""

            for attempt in range(attempts):
                prompt = base_prompt
                if attempt > 0:
                    prompt += "\n\n이전 응답이 형식을 지키지 않았거나 중간에 끊겼습니다. JSON 없이 완성된 한국어 요약문만 3문장으로 다시 작성하세요."
                try:
                    raw = self.llm_client.generate_text(
                        prompt=prompt,
                        temperature=0.1,
                        max_tokens=LLM_ITEM_SUMMARY_MAX_OUTPUT_TOKENS,
                        timeout=LLM_ITEM_SUMMARY_TIMEOUT_SECONDS,
                        purpose=f"disclosure_ai_summary:{item.id}:attempt{attempt + 1}",
                        system_prompt=item_system_prompt,
                    )
                    cleaned = self._clean_item_summary_text(raw)
                    if not self._is_valid_item_summary(cleaned):
                        last_error = "invalid or incomplete item summary"
                        continue

                    classified = self.classifier.classify_disclosure(
                        disclosure_title=item.disclosure_title,
                        disclosure_type=item.disclosure_type,
                        ai_summary=cleaned,
                        rules=rules,
                    )
                    self.disclosure_repo.update_ai_summary(
                        disclosure_id=item.id,
                        ai_summary=cleaned,
                        ai_importance_score=int(classified.get("ai_importance_score", 50)),
                        ai_tags=str(classified.get("ai_tags", "공시")),
                        ai_risk_level=str(classified.get("ai_risk_level", "unknown")),
                        ai_event_type=str(classified.get("ai_event_type", "기타")),
                        ai_processed_at=processed_at,
                        ai_summary_error=None,
                    )
                    success_count += 1
                    saved = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)

            if not saved:
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
            message=self._message_with_active_rules("disclosure ai summary completed", len(rules)),
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
        template_path = PROJECT_ROOT / "prompts" / "lmstudio_news_item_summary_template.md"
        template = template_path.read_text(encoding="utf-8")
        return (
            template.replace("{{title}}", self._truncate_text(item.title, 200))
            .replace("{{published_at}}", item.published_at or "정보 없음")
            .replace("{{summary}}", self._truncate_text(item.summary, LLM_MAX_ITEM_SUMMARY_CHARS) or "정보 없음")
            .replace("{{source}}", item.source or "정보 없음")
        )

    def _build_disclosure_item_prompt(self, item: Any) -> str:
        template_path = PROJECT_ROOT / "prompts" / "lmstudio_disclosure_item_summary_template.md"
        template = template_path.read_text(encoding="utf-8")
        return (
            template.replace("{{disclosure_title}}", self._truncate_text(item.disclosure_title, 220))
            .replace("{{disclosure_type}}", item.disclosure_type or "정보 없음")
            .replace("{{disclosed_at}}", item.disclosed_at or "정보 없음")
        )

    def _build_chunk_prompt(self, source_label: str, items_text: str) -> str:
        template_path = PROJECT_ROOT / "prompts" / "lmstudio_chunk_summary_template.md"
        template = template_path.read_text(encoding="utf-8")
        return template.replace("{{source_label}}", source_label).replace("{{items}}", items_text)

    def _build_final_prompt(
        self,
        stock_name: str,
        stock_code: str,
        analysis_date: str,
        news_summary: str,
        disclosure_summary: str,
    ) -> str:
        template_path = PROJECT_ROOT / "prompts" / "lmstudio_summary_template.md"
        template = template_path.read_text(encoding="utf-8")
        return (
            template.replace("{{stock_name}}", stock_name)
            .replace("{{stock_code}}", stock_code)
            .replace("{{analysis_date}}", analysis_date)
            .replace("{{news_summary}}", news_summary)
            .replace("{{disclosure_summary}}", disclosure_summary)
        )

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
        cleaned = text.strip()
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        cleaned = cleaned.replace("\r\n", "\n").strip()

        if cleaned.startswith("{") or '"ai_summary"' in cleaned:
            return ""

        prefixes = ["출력:", "요약:", "투자 관점 요약:", "최종 답변:"]
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
        return cleaned

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
