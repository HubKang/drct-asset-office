from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.app.core.config import (
    TELEGRAM_LLM_ENABLED, TELEGRAM_LLM_MAX_TOKENS, TELEGRAM_LLM_MODEL, TELEGRAM_LLM_TEMPERATURE,
)
from backend.app.llm.lmstudio_client import LMStudioClient


logger = logging.getLogger(__name__)


class TelegramLLMService:
    """Summarizes selected article text without persisting prompts or model output."""

    def __init__(self) -> None:
        self.client = LMStudioClient()

    def summarize_article(self, article_text: str, article_title: str | None = None) -> dict[str, Any]:
        text = (article_text or "").strip()
        title = re.sub(r"\s+", " ", article_title or "").strip()
        if not TELEGRAM_LLM_ENABLED:
            return {"success": False, "error": "TELEGRAM_LLM_DISABLED"}
        if len(text) < 200:
            return {"success": False, "error": "ARTICLE_TEXT_TOO_SHORT"}
        try:
            raw = self.client.generate_text(
                prompt=(
                    "다음 기사 본문을 핵심 사실 중심의 한국어 2~3문장으로 요약하세요. "
                    "제목을 그대로 반복하지 말고 투자 추천이나 원문에 없는 추론을 추가하지 마세요. "
                    "숫자, 기업명, 일정 등 핵심 사실을 보존하고 불필요한 서론을 쓰지 마세요. "
                    "아래 제목의 단일 기사만 요약하고, 본문에 섞인 다른 기사 제목이나 추천 목록은 무시하세요. "
                    "JSON 객체 하나만 반환하며 summary 키만 사용하세요.\n"
                    '{"summary":""}\n기사 제목:\n' + title[:500] + "\n기사 본문:\n" + text[:15_000]
                ),
                temperature=TELEGRAM_LLM_TEMPERATURE,
                max_tokens=TELEGRAM_LLM_MAX_TOKENS,
                model=TELEGRAM_LLM_MODEL or None,
                purpose="telegram_article_summary",
            )
            summary = re.sub(r"\s+", " ", str(self._parse_json(raw).get("summary") or "")).strip(" \t\r\n\"'")
            if len(summary) < 40:
                return {"success": False, "error": "SUMMARY_TOO_SHORT"}
            return {"success": True, "summary": summary[:1200]}
        except Exception as exc:
            logger.warning("Selected article summary failed: %s", exc)
            return {"success": False, "error": "LLM_PROCESSING_FAILED"}

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
        try:
            value = json.loads(cleaned)
            return value if isinstance(value, dict) else {}
        except Exception:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                return {}
            try:
                value = json.loads(match.group(0))
                return value if isinstance(value, dict) else {}
            except Exception:
                return {}
