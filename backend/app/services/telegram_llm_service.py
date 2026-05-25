from __future__ import annotations

import json
import re
from typing import Any

from backend.app.core.config import (
    TELEGRAM_LLM_ENABLED,
    TELEGRAM_LLM_MAX_TOKENS,
    TELEGRAM_LLM_MODEL,
    TELEGRAM_LLM_TEMPERATURE,
)
from backend.app.entities.classification_rule import ClassificationRule
from backend.app.llm.lmstudio_client import LMStudioClient
from backend.app.services.analysis_classifier import AnalysisClassifier


class TelegramLLMService:
    FALLBACK_SUMMARY_TEXT = "확인 필요: 원문 기반 추가 검토가 필요합니다."
    DEFAULT_RESULT = {
        "message_type": "unknown",
        "item_category": "기타",
        "summary_text": "",
        "key_points": [],
        "tag": "기타",
        "score": 50,
        "sentiment": "neutral",
        "risk_level": "unknown",
        "event_type": "기타",
        "related_stock_name": "",
        "related_stock_code": "",
        "related_theme": "",
        "risk_points": ["비공식 채널 정보로 사실관계 확인 필요"],
        "check_points": ["공시/공식뉴스 교차검증 필요"],
    }

    def __init__(self) -> None:
        self.client = LMStudioClient()
        self.classifier = AnalysisClassifier()

    def summarize_and_classify(self, text: str, rules: list[ClassificationRule]) -> dict[str, Any]:
        llm_obj = self._generate_llm_json(text)
        merged = {**self.DEFAULT_RESULT, **llm_obj}
        merged = self._normalize_alias_fields(merged)
        merged = self._sanitize_structured_result(merged)
        merged["key_points"] = self._normalize_list(merged.get("key_points"))
        merged["risk_points"] = self._normalize_list(merged.get("risk_points"))
        merged["check_points"] = self._normalize_list(merged.get("check_points"))

        # 1순위: 기존 classification_rules(뉴스 기준) -> 2순위 LLM -> 3순위 기본값
        rule_result = self.classifier.classify_news(title=text[:120], summary=text, ai_summary=merged.get("summary_text"), rules=rules)
        rule_tags = str(rule_result.get("ai_tags") or "").split(",")
        cleaned_rule_tags = [tag.strip() for tag in rule_tags if tag.strip()]

        if cleaned_rule_tags:
            merged["tag"] = cleaned_rule_tags[0]
        merged["sentiment"] = str(rule_result.get("ai_sentiment") or merged.get("sentiment") or "neutral")
        merged["score"] = int(rule_result.get("ai_importance_score") or merged.get("score") or 50)

        if merged.get("event_type") in {None, "", "기타"}:
            merged["event_type"] = self._guess_event_type(text)
        if merged.get("message_type") in {None, "", "unknown"}:
            merged["message_type"] = self._guess_message_type(text)
        if merged.get("item_category") in {None, "", "기타"}:
            merged["item_category"] = self._map_item_category(str(merged.get("message_type") or "unknown"))

        summary_text = str(merged.get("summary_text") or "").strip()
        key_points = self._normalize_list(merged.get("key_points"))
        is_fallback = self._is_fallback_summary(summary_text=summary_text, key_points=key_points)
        summary_error = str(merged.get("summary_error_message") or "").strip()
        summary_text = summary_text if not is_fallback else ""
        if self._looks_like_json_object(summary_text):
            summary_text = ""
            is_fallback = True
            if not summary_error:
                summary_error = "JSON_LIKE_SUMMARY_BLOCKED"
        merged["summary_text"] = summary_text
        merged["key_points"] = key_points if not is_fallback else []
        merged["summary_has_content"] = 1 if len(summary_text) >= 20 and not is_fallback else 0
        merged["fallback_used"] = 1 if is_fallback else 0
        merged["summary_error_message"] = summary_error or None
        if merged["summary_has_content"] == 0 and not merged["summary_error_message"]:
            merged["summary_error_message"] = "FALLBACK_TEXT_BLOCKED" if is_fallback else "SUMMARY_TOO_SHORT"
        return merged

    def _sanitize_structured_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(payload)
        summary_text = str(result.get("summary_text") or "").strip()

        # Some models wrap JSON again inside summary_text.
        if ("```" in summary_text) or (summary_text.startswith("{") and summary_text.endswith("}")):
            nested, _, _ = self._parse_json(summary_text)
            if nested:
                nested = self._normalize_alias_fields(nested)
                if nested.get("summary_text"):
                    result["summary_text"] = str(nested.get("summary_text") or "").strip()
                if nested.get("key_points"):
                    result["key_points"] = nested.get("key_points")
                for key in ("message_type", "item_category", "tag", "score", "sentiment", "risk_level", "event_type", "related_stock_name", "related_stock_code", "related_theme"):
                    if nested.get(key):
                        result[key] = nested.get(key)

        key_points = self._normalize_list(result.get("key_points"))
        filtered_points = []
        for point in key_points:
            p = point.strip()
            if not p:
                continue
            if p in {"```json", "```", "{", "}"}:
                continue
            if p.startswith("\"") and p.endswith("\""):
                p = p.strip("\"")
            if any(token in p for token in ["message_type", "item_category", "summary_text", "key_points"]):
                continue
            filtered_points.append(p)
        result["key_points"] = filtered_points
        return result

    def _generate_llm_json(self, text: str) -> dict[str, Any]:
        if not TELEGRAM_LLM_ENABLED:
            return {"summary_error_message": "TELEGRAM_LLM_DISABLED"}

        prompt = self._build_primary_prompt(text)
        retry_prompt = self._build_retry_prompt(text)
        model_name = TELEGRAM_LLM_MODEL or None
        retry_used = False
        fallback_used = False

        try:
            raw = self.client.generate_text(
                prompt=prompt,
                temperature=TELEGRAM_LLM_TEMPERATURE,
                max_tokens=TELEGRAM_LLM_MAX_TOKENS,
                model=model_name,
                purpose="telegram_item_summary_primary",
            )
            parsed, parse_error, extracted_json_len = self._parse_json(raw)
            content_source = "content"

            if not parsed:
                retry_used = True
                retry_raw = self.client.generate_text(
                    prompt=retry_prompt,
                    temperature=TELEGRAM_LLM_TEMPERATURE,
                    max_tokens=TELEGRAM_LLM_MAX_TOKENS,
                    model=model_name,
                    purpose="telegram_item_summary_retry",
                )
                retry_parsed, retry_error, retry_json_len = self._parse_json(retry_raw)
                if retry_parsed:
                    raw = retry_raw
                    parsed = retry_parsed
                    parse_error = None
                    extracted_json_len = retry_json_len
                else:
                    parse_error = f"primary={parse_error or 'unknown'}; retry={retry_error or 'unknown'}"
                    natural_summary = self._extract_natural_summary(retry_raw) or self._extract_natural_summary(raw)
                    if natural_summary:
                        parsed = {
                            "summary_text": natural_summary,
                            "key_points": self._extract_points_from_text(natural_summary),
                            "summary_error_message": "NATURAL_LANGUAGE_FALLBACK",
                        }
                        fallback_used = True
                        content_source = "fallback"

            if not parsed:
                parsed = {"summary_error_message": "JSON_PARSE_FAILED"}
            elif parse_error and not parsed.get("summary_error_message"):
                parsed["summary_error_message"] = parse_error

            summary_preview = str(parsed.get("summary_text") or "") if parsed else ""
            key_points_count = len(parsed.get("key_points") or []) if isinstance(parsed.get("key_points"), list) else 0
            final_status = "summarized" if len(summary_preview.strip()) >= 20 else "failed"
            failure_reason = parsed.get("summary_error_message") if final_status == "failed" else "none"
            print(
                f"[TELEGRAM LLM] model={model_name or self.client.model} raw_len={len(raw or '')} content_len={len(raw or '')} "
                f"reasoning_content_len=0 content_source={content_source} parse_ok={1 if parsed and parsed.get('summary_error_message') != 'JSON_PARSE_FAILED' else 0} "
                f"parse_error={parse_error or 'none'} extracted_json_len={extracted_json_len} fallback_used={1 if fallback_used else 0} "
                f"retry_used={1 if retry_used else 0} summary_len={len(summary_preview.strip())} key_points_count={key_points_count} "
                f"final_status={final_status} failure_reason={failure_reason}"
            )
            print(f"[TELEGRAM LLM] raw_preview={(raw or '')[:300].replace(chr(10), ' ')}")
            print(f"[TELEGRAM LLM] final_summary_preview={summary_preview[:200]}")
            return parsed
        except Exception as exc:
            print(f"[TELEGRAM LLM] generate_error={exc}")
            return {"summary_error_message": "LMSTUDIO_REQUEST_FAILED"}

    def _build_primary_prompt(self, text: str) -> str:
        return (
            "아래 텔레그램 메시지를 JSON으로만 요약/분류하세요.\n"
            "반드시 JSON 객체 하나만 반환하세요. 설명문, markdown, 코드블록, 주석 금지.\n"
            "응답 첫 글자는 { 마지막 글자는 } 여야 합니다.\n"
            "summary_text는 한국어 평문 2문장 이상으로 작성하세요.\n"
            "key_points는 한국어 핵심 포인트 2~4개 배열로 작성하세요.\n"
            "{\"summary_text\":\"\",\"key_points\":[],\"message_type\":\"unknown\",\"item_category\":\"기타\",\"tag\":\"기타\",\"score\":50,\"sentiment\":\"neutral\",\"risk_level\":\"unknown\",\"event_type\":\"기타\"}\n"
            f"메시지:\n{text[:5000]}"
        )

    def _build_retry_prompt(self, text: str) -> str:
        return (
            "직전 응답 형식이 잘못되었습니다. JSON 객체 하나만 다시 반환하세요.\n"
            "아래 스키마 키만 사용하세요: summary_text, key_points, message_type, item_category, tag, score, sentiment, risk_level, event_type\n"
            "{\"summary_text\":\"\",\"key_points\":[],\"message_type\":\"unknown\",\"item_category\":\"기타\",\"tag\":\"기타\",\"score\":50,\"sentiment\":\"neutral\",\"risk_level\":\"unknown\",\"event_type\":\"기타\"}\n"
            f"메시지:\n{text[:5000]}"
        )

    def _parse_json(self, raw: str) -> tuple[dict[str, Any], str | None, int]:
        cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
        if not cleaned:
            return {}, "empty_response", 0

        fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw or "", flags=re.IGNORECASE)
        if fenced_match:
            fenced_body = fenced_match.group(1).strip()
            try:
                fenced_obj = json.loads(fenced_body)
                if isinstance(fenced_obj, dict):
                    return fenced_obj, None, len(fenced_body)
            except Exception:
                pass

        try:
            direct = json.loads(cleaned)
            if isinstance(direct, dict):
                return direct, None, len(cleaned)
        except Exception:
            pass

        candidate = self._extract_first_json_object(cleaned)
        if not candidate:
            return {}, "json_block_not_found", 0

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed, None, len(candidate)
        except Exception as exc:
            normalized = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                reparsed = json.loads(normalized)
                if isinstance(reparsed, dict):
                    return reparsed, None, len(normalized)
            except Exception:
                return {}, str(exc), len(candidate)

        return {}, "unknown_parse_failure", len(candidate)

    @staticmethod
    def _extract_first_json_object(text: str) -> str:
        start = text.find("{")
        if start < 0:
            return ""
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]
        return ""

    @staticmethod
    def _normalize_alias_fields(payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(payload)
        alias_map = {
            "summary_text": ["summary", "overall_summary", "요약", "요약문"],
            "key_points": ["points", "bullet_points", "핵심포인트", "핵심_포인트"],
            "message_type": ["type", "분류유형"],
            "item_category": ["category", "카테고리"],
            "risk_points": ["risks", "risk_point_list"],
            "check_points": ["checks", "checklist", "확인포인트"],
        }
        for canonical, aliases in alias_map.items():
            if result.get(canonical):
                continue
            for alias in aliases:
                if alias in result and result.get(alias):
                    result[canonical] = result.get(alias)
                    break
        return result

    @staticmethod
    def _extract_natural_summary(raw: str) -> str:
        if not raw:
            return ""
        text = raw.strip()
        text = re.sub(r"^(요약|summary)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
        if text.startswith("{") or text.startswith("["):
            return ""
        if "```" in text:
            return ""
        if "{" in text and "}" in text:
            return ""
        if len(text) < 20:
            return ""
        return text[:1200]

    @staticmethod
    def _looks_like_json_object(text: str) -> bool:
        stripped = (text or "").strip()
        return stripped.startswith("{") and stripped.endswith("}")

    @staticmethod
    def _extract_points_from_text(text: str) -> list[str]:
        lines = [ln.strip(" -•\t") for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2:
            return lines[:5]
        if not lines:
            return []
        chunks = [seg.strip() for seg in re.split(r"[.。]\s*", lines[0]) if seg.strip()]
        return chunks[:5]

    @staticmethod
    def _normalize_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _is_fallback_summary(self, summary_text: str, key_points: list[str]) -> bool:
        normalized = summary_text.strip()
        if not normalized:
            return True
        if normalized == self.FALLBACK_SUMMARY_TEXT:
            return True
        if key_points == ["확인 필요"]:
            return True
        if normalized.startswith("확인 필요:"):
            return True
        return False

    @staticmethod
    def _guess_message_type(text: str) -> str:
        lowered = text.lower()
        if any(k in lowered for k in ["광고", "이벤트", "가입", "유료방"]):
            return "advertisement"
        if any(k in lowered for k in ["공지", "안내", "점검", "운영"]):
            return "channel_notice"
        if any(k in lowered for k in ["실적", "공급", "수주", "계약", "종목"]):
            return "stock_news"
        if any(k in lowered for k in ["테마", "관련주", "순환매"]):
            return "theme_issue"
        if any(k in lowered for k in ["시장", "지수", "수급", "환율", "금리"]):
            return "market_commentary"
        if any(k in lowered for k in ["정책", "규제", "정부", "국회"]):
            return "policy_issue"
        if any(k in lowered for k in ["리스크", "악재", "소송", "제재"]):
            return "risk_issue"
        return "unknown"

    @staticmethod
    def _map_item_category(message_type: str) -> str:
        mapping = {
            "economic_news": "경제",
            "stock_news": "종목",
            "theme_issue": "테마",
            "market_commentary": "시장흐름",
            "policy_issue": "정책",
            "disclosure_like": "투자",
            "risk_issue": "리스크",
            "investment_opinion": "투자",
            "channel_notice": "공지",
            "advertisement": "광고",
            "etc": "기타",
            "unknown": "기타",
        }
        return mapping.get(message_type, "기타")

    @staticmethod
    def _guess_event_type(text: str) -> str:
        lowered = text.lower()
        if "실적" in lowered:
            return "실적"
        if any(k in lowered for k in ["수주", "계약"]):
            return "수주"
        if any(k in lowered for k in ["정책", "규제"]):
            return "정책"
        if any(k in lowered for k in ["리스크", "소송", "악재"]):
            return "리스크"
        if "테마" in lowered:
            return "테마확산"
        return "기타"
