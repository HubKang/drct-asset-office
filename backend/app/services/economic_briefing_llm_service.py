from __future__ import annotations

import json
from typing import Any

from backend.app.core.config import (
    ECONOMIC_BRIEFING_CHUNK_MAX_TOKENS,
    ECONOMIC_BRIEFING_CHUNK_RETRY_MAX_TOKENS,
    ECONOMIC_BRIEFING_LLM_MODEL,
    ECONOMIC_BRIEFING_LLM_TIMEOUT_SECONDS,
    ECONOMIC_BRIEFING_OVERALL_MAX_TOKENS,
    ECONOMIC_BRIEFING_TEMPERATURE,
)
from backend.app.llm.lmstudio_client import LMStudioClient


class EconomicBriefingLLMService:
    def __init__(self) -> None:
        self.client = LMStudioClient(timeout=ECONOMIC_BRIEFING_LLM_TIMEOUT_SECONDS)
        self.model_name = ECONOMIC_BRIEFING_LLM_MODEL or None

    def summarize_chunk(self, chunk_text: str, chunk_index: int, total_chunks: int) -> dict[str, Any]:
        system_prompt = (
            "너는 경제 브리핑 자막을 요약하는 분석 보조자입니다. "
            "투자 추천, 매수/매도 판단, 목표가 제시는 금지합니다. "
            "사고 과정을 쓰지 말고 최종 JSON만 출력하세요."
        )
        prompt = self._build_chunk_prompt(chunk_text=chunk_text, chunk_index=chunk_index, total_chunks=total_chunks)
        try:
            raw = self.client.generate_text(
                prompt=prompt,
                temperature=ECONOMIC_BRIEFING_TEMPERATURE,
                max_tokens=ECONOMIC_BRIEFING_CHUNK_MAX_TOKENS,
                model=self.model_name,
                purpose=f"economic_briefing_chunk:{chunk_index}",
                system_prompt=system_prompt,
            )
            if not raw.strip():
                raise RuntimeError("empty content")
            parsed = self._parse_json_or_fallback(raw, fallback_key="summary")
            parsed["_raw_response_length"] = len(raw.strip())
            return parsed
        except Exception:
            short_text = chunk_text[:2000]
            retry_prompt = self._build_chunk_retry_prompt(short_text=short_text)
            raw_retry = self.client.generate_text(
                prompt=retry_prompt,
                temperature=ECONOMIC_BRIEFING_TEMPERATURE,
                max_tokens=ECONOMIC_BRIEFING_CHUNK_RETRY_MAX_TOKENS,
                model=self.model_name,
                purpose=f"economic_briefing_chunk_retry:{chunk_index}",
                system_prompt=system_prompt,
            )
            if not raw_retry.strip():
                raise RuntimeError("empty content after retry")
            parsed_retry = self._parse_json_or_fallback(raw_retry, fallback_key="summary")
            parsed_retry["_raw_response_length"] = len(raw_retry.strip())
            return parsed_retry

    def summarize_overall(self, chunk_summaries: list[dict[str, Any]]) -> dict[str, Any]:
        packed = json.dumps(chunk_summaries, ensure_ascii=False)
        prompt = (
            "아래 chunk 요약을 통합해 영상 전체 경제 브리핑 요약을 만드세요.\n"
            "반드시 JSON만 출력하세요. 사고 과정/마크다운 금지.\n"
            '{"overall_summary":"...","key_points":["..."],"topics":[{"topic_name":"...","summary":"..."}],'
            '"theme_mentions":["..."],"stock_mentions":["..."],"risk_points":["..."],"observation_points":["..."]}\n\n'
            f"{packed}"
        )
        system_prompt = "사고 과정을 쓰지 말고 최종 JSON만 출력하세요."
        try:
            raw = self.client.generate_text(
                prompt=prompt,
                temperature=ECONOMIC_BRIEFING_TEMPERATURE,
                max_tokens=ECONOMIC_BRIEFING_OVERALL_MAX_TOKENS,
                model=self.model_name,
                purpose="economic_briefing_overall",
                system_prompt=system_prompt,
            )
            if not raw.strip():
                raise RuntimeError("empty content")
            parsed = self._parse_json_or_fallback(raw, fallback_key="overall_summary")
            parsed["_raw_response_length"] = len(raw.strip())
            return parsed
        except Exception:
            short = packed[:4000]
            retry_prompt = (
                "다음 데이터를 5문장 이내로 통합 요약하고 JSON만 출력하세요.\n"
                '{"overall_summary":"...","key_points":[],"topics":[],"theme_mentions":[],"stock_mentions":[],"risk_points":[],"observation_points":[]}\n'
                f"{short}"
            )
            raw_retry = self.client.generate_text(
                prompt=retry_prompt,
                temperature=ECONOMIC_BRIEFING_TEMPERATURE,
                max_tokens=max(ECONOMIC_BRIEFING_OVERALL_MAX_TOKENS + 600, 2800),
                model=self.model_name,
                purpose="economic_briefing_overall_retry",
                system_prompt=system_prompt,
            )
            if not raw_retry.strip():
                raise RuntimeError("empty content after retry")
            parsed_retry = self._parse_json_or_fallback(raw_retry, fallback_key="overall_summary")
            parsed_retry["_raw_response_length"] = len(raw_retry.strip())
            return parsed_retry

    def extract_structured_fields(self, source_text: str, overall_summary: str) -> dict[str, Any]:
        prompt = (
            "Extract structured investment-briefing fields from the input.\n"
            "Return JSON only.\n"
            "Required keys: key_points, topics, theme_mentions, stock_mentions, risk_points.\n"
            "Rules:\n"
            "- key_points: 3~7 concise bullets\n"
            "- topics: 2~5 items, each with topic_name and summary\n"
            "- theme_mentions: 3~10 terms\n"
            "- stock_mentions: 1~10 stock/company names from the input only\n"
            "- risk_points: 2~5 items\n"
            "- If uncertain, use '확인 필요' item instead of leaving all fields empty.\n"
            '{"key_points":[],"topics":[{"topic_name":"","summary":""}],"theme_mentions":[],"stock_mentions":[],"risk_points":[]}\n\n'
            f"OVERALL_SUMMARY:\n{overall_summary[:3000]}\n\n"
            f"SOURCE_TEXT:\n{source_text[:8000]}"
        )
        raw = self.client.generate_text(
            prompt=prompt,
            temperature=ECONOMIC_BRIEFING_TEMPERATURE,
            max_tokens=max(ECONOMIC_BRIEFING_OVERALL_MAX_TOKENS, 2200),
            model=self.model_name,
            purpose="economic_briefing_structured_retry",
            system_prompt="Output valid JSON only.",
        )
        if not raw.strip():
            raise RuntimeError("empty content on structured retry")
        parsed = self._parse_json_or_fallback(raw, fallback_key="overall_summary")
        parsed["_raw_response_length"] = len(raw.strip())
        return parsed

    def _parse_json_or_fallback(self, raw: str, fallback_key: str) -> dict[str, Any]:
        text = (raw or "").strip().replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
        return {
            fallback_key: text[:4000],
            "key_points": [],
            "topics": [],
            "theme_mentions": [],
            "stock_mentions": [],
            "risk_points": [],
            "observation_points": [],
        }

    @staticmethod
    def _build_chunk_prompt(chunk_text: str, chunk_index: int, total_chunks: int) -> str:
        return (
            f"아래 자막 일부를 5문장 이내로 요약하세요. 현재 청크: {chunk_index}/{total_chunks}\n"
            "반드시 JSON만 출력하세요. 마크다운/설명문/사고 과정 금지.\n"
            '{'
            '"summary":"5문장 이내 요약",'
            '"themes":["테마"],'
            '"stocks":["종목"],'
            '"risks":["리스크"]'
            '}\n'
            f"자막:\n{chunk_text}"
        )

    @staticmethod
    def _build_chunk_retry_prompt(short_text: str) -> str:
        return (
            "다음 텍스트를 5문장 이내로 요약하세요.\n"
            "반드시 JSON만 출력하세요. 사고 과정 금지.\n"
            '{"summary":"...","themes":[],"stocks":[],"risks":[]}\n'
            f"텍스트:\n{short_text}"
        )
