from __future__ import annotations

from collections import Counter
import json
from html import unescape
import mimetypes
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, unquote

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.llm.lmstudio_client import LMStudioClient
from backend.app.services.image_file_service import ImageFileService
from backend.app.schemas.kms_schema import (
    IMPORTANCE_VALUES,
    LEARNING_STATUS_VALUES,
    KmsCategoryCreate,
    KmsCategoryResponse,
    KmsCategorySortOrderResponse,
    KmsCategorySortOrderUpdate,
    KmsCategorySummary,
    KmsCategoryUpdate,
    KmsHomeSummary,
    KmsKnowledgeItemCreate,
    KmsKnowledgeItemResponse,
    KmsKnowledgeItemTagResponse,
    KmsKnowledgeItemTagUpdate,
    KmsKnowledgeItemUpdate,
    KmsKnowledgeExtractionResponse,
    KmsSettingItemSummary,
    KmsLocalImageSelectResponse,
    KmsOverallSummary,
    KmsPostCreate,
    KmsPostSummary,
    KmsPostUpdate,
    KmsRecentPost,
    KmsSettingGroupResponse,
    KmsSettingItemActiveUpdate,
    KmsSettingItemCreate,
    KmsSettingItemResponse,
    KmsSettingItemSortOrderResponse,
    KmsSettingItemSortOrderUpdate,
    KmsSettingItemUpdate,
    KmsSummaryHelpApplyRequest,
    KmsSummaryHelpResponse,
    KmsTagCreate,
    KmsTagResponse,
    KmsTagUpdate,
)

KMS_ALLOWED_LOCAL_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
KMS_DEFAULT_ITEM_CODES = {
    "PARA_TYPE": "RESOURCE",
    "KNOWLEDGE_CATEGORY": "UNCATEGORIZED",
    "KNOWLEDGE_STATUS": "COLLECTED",
    "IMPORTANCE_LEVEL": "NORMAL",
    "TAG_TYPE": "CONCEPT",
    "USAGE_CONTEXT": "UNSPECIFIED",
    "SOURCE_TYPE": "MANUAL",
}
DEFAULT_KMS_CATEGORIES = ["시장", "재료", "수급", "차트", "재무", "기법", "심리", "리스크", "복기", "자료"]
HTML_TAG_RE = re.compile(r"<\s*/?\s*(?:p|br|div|span|h[1-6]|ul|ol|li|table|thead|tbody|tr|td|th|strong|b|em|i|a|blockquote|pre|code)\b|</", re.IGNORECASE)

def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        if key in row:
            return row[key]
    except (KeyError, TypeError):
        pass
    return default


def _looks_like_html(value: str | None) -> bool:
    return bool(value and HTML_TAG_RE.search(value))


def _strip_html_tags(value: str | None) -> str:
    text_value = unescape(str(value or ""))
    text_value = re.sub(r"(?i)<br\s*/?>", "\n", text_value)
    text_value = re.sub(r"(?i)</(?:p|div|h[1-6]|li|tr)>", "\n", text_value)
    text_value = re.sub(r"<[^>]+>", " ", text_value)
    return re.sub(r"[ \t\r\f\v]+", " ", text_value).strip()


def _plain_snippet(value: str | None, max_length: int = 180) -> str:
    text_value = _strip_html_tags(value)
    return f"{text_value[:max_length]}..." if len(text_value) > max_length else text_value


class KmsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_setting_groups(self, include_inactive: bool = False, include_items: bool = True) -> list[KmsSettingGroupResponse]:
        filters = [] if include_inactive else ["is_active = 1"]
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT id, group_code, group_name, description, sort_order, is_active, created_at, updated_at
                FROM kms_setting_groups
                {where}
                ORDER BY sort_order, id
                """
            )
        ).mappings().all()
        groups: list[KmsSettingGroupResponse] = []
        for row in rows:
            group = self._setting_group_response(row)
            if include_items:
                group.items = self.list_setting_items(group_code=group.group_code, include_inactive=include_inactive)
            groups.append(group)
        return groups

    def list_setting_items(self, group_code: str | None = None, include_inactive: bool = False) -> list[KmsSettingItemResponse]:
        filters = []
        params: dict[str, Any] = {}
        if group_code:
            filters.append("g.group_code = :group_code")
            params["group_code"] = group_code.strip().upper()
        if not include_inactive:
            filters.append("i.is_active = 1")
            filters.append("g.is_active = 1")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT i.*, g.group_code
                FROM kms_setting_items i
                JOIN kms_setting_groups g ON g.id = i.group_id
                {where}
                ORDER BY g.sort_order, i.sort_order, i.id
                """
            ),
            params,
        ).mappings().all()
        return [self._setting_item_response(row) for row in rows]

    def create_setting_item(self, payload: KmsSettingItemCreate) -> KmsSettingItemResponse:
        group = self._get_setting_group_by_code(payload.group_code)
        item_code = payload.item_code.strip().upper()
        item_name = payload.item_name.strip()
        if not item_code or not item_name:
            raise HTTPException(status_code=400, detail="item_code and item_name are required")
        duplicated = self.db.execute(
            text("SELECT id FROM kms_setting_items WHERE group_id = :group_id AND item_code = :item_code"),
            {"group_id": group["id"], "item_code": item_code},
        ).first()
        if duplicated:
            raise HTTPException(status_code=409, detail="same setting item code already exists")
        now = now_kst()
        if payload.is_default:
            self._clear_setting_group_default(int(group["id"]))
        result = self.db.execute(
            text(
                """
                INSERT INTO kms_setting_items
                (group_id, item_code, item_name, description, color, icon, sort_order, is_default, is_system, is_active, created_at, updated_at)
                VALUES (:group_id, :item_code, :item_name, :description, :color, :icon, :sort_order, :is_default, :is_system, :is_active, :now, :now)
                """
            ),
            {
                "group_id": int(group["id"]),
                "item_code": item_code,
                "item_name": item_name,
                "description": payload.description,
                "color": payload.color,
                "icon": payload.icon,
                "sort_order": payload.sort_order,
                "is_default": 1 if payload.is_default else 0,
                "is_system": 1 if payload.is_system else 0,
                "is_active": 1 if payload.is_active else 0,
                "now": now,
            },
        )
        self.db.commit()
        return self.get_setting_item(int(result.lastrowid))

    def get_setting_item(self, item_id: int) -> KmsSettingItemResponse:
        row = self.db.execute(
            text(
                """
                SELECT i.*, g.group_code
                FROM kms_setting_items i
                JOIN kms_setting_groups g ON g.id = i.group_id
                WHERE i.id = :item_id
                """
            ),
            {"item_id": item_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="setting item not found")
        return self._setting_item_response(row)

    def update_setting_item(self, item_id: int, payload: KmsSettingItemUpdate) -> KmsSettingItemResponse:
        current = self.get_setting_item(item_id)
        values = payload.model_dump(exclude_unset=True)
        if current.is_system and values.get("item_code") and values["item_code"] != current.item_code:
            raise HTTPException(status_code=409, detail="system setting item code cannot be changed")
        if "item_code" in values and values["item_code"] is not None:
            values["item_code"] = str(values["item_code"]).strip().upper()
        if "item_name" in values and values["item_name"] is not None:
            values["item_name"] = str(values["item_name"]).strip()
        if values.get("is_default"):
            self._clear_setting_group_default(current.group_id)
        for bool_key in ("is_default", "is_active"):
            if bool_key in values and values[bool_key] is not None:
                values[bool_key] = 1 if values[bool_key] else 0
        if values:
            values["updated_at"] = now_kst()
            values["item_id"] = item_id
            assignments = ", ".join(f"{key} = :{key}" for key in values)
            self.db.execute(text(f"UPDATE kms_setting_items SET {assignments} WHERE id = :item_id"), values)
            self.db.commit()
        return self.get_setting_item(item_id)

    def set_setting_item_active(self, item_id: int, payload: KmsSettingItemActiveUpdate) -> KmsSettingItemResponse:
        current = self.get_setting_item(item_id)
        if current.is_system and not payload.is_active:
            raise HTTPException(status_code=409, detail="system setting item cannot be deactivated")
        self.db.execute(
            text("UPDATE kms_setting_items SET is_active = :is_active, updated_at = :now WHERE id = :item_id"),
            {"item_id": item_id, "is_active": 1 if payload.is_active else 0, "now": now_kst()},
        )
        self.db.commit()
        return self.get_setting_item(item_id)

    def set_setting_item_default(self, item_id: int) -> KmsSettingItemResponse:
        current = self.get_setting_item(item_id)
        self._clear_setting_group_default(current.group_id)
        self.db.execute(
            text("UPDATE kms_setting_items SET is_default = 1, is_active = 1, updated_at = :now WHERE id = :item_id"),
            {"item_id": item_id, "now": now_kst()},
        )
        self.db.commit()
        return self.get_setting_item(item_id)

    def reorder_setting_items(self, payload: KmsSettingItemSortOrderUpdate) -> KmsSettingItemSortOrderResponse:
        if not payload.items:
            raise HTTPException(status_code=400, detail="items are required")
        now = now_kst()
        for item in payload.items:
            self.db.execute(
                text("UPDATE kms_setting_items SET sort_order = :sort_order, updated_at = :now WHERE id = :item_id"),
                {"item_id": item.id, "sort_order": item.sort_order, "now": now},
            )
        self.db.commit()
        return KmsSettingItemSortOrderResponse(success=True, updated_count=len(payload.items))

    def list_knowledge_items(
        self,
        keyword: str | None = None,
        para_type_id: int | None = None,
        category_id: int | None = None,
        status_id: int | None = None,
        importance_id: int | None = None,
        usage_context_id: int | None = None,
        source_type_id: int | None = None,
        tag_id: int | None = None,
        tag: str | None = None,
        is_active: bool | None = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KmsKnowledgeItemResponse]:
        self.sync_legacy_posts_to_knowledge_items()
        self.cleanup_knowledge_content_formats()
        filters = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if keyword:
            filters.append("(k.title LIKE :keyword OR k.summary LIKE :keyword OR k.content LIKE :keyword OR k.one_line_conclusion LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        for key, value in {
            "para_type_id": para_type_id,
            "category_id": category_id,
            "status_id": status_id,
            "importance_id": importance_id,
            "usage_context_id": usage_context_id,
            "source_type_id": source_type_id,
        }.items():
            if value:
                filters.append(f"k.{key} = :{key}")
                params[key] = value
        if tag_id:
            filters.append(
                """
                EXISTS (
                    SELECT 1
                    FROM kms_knowledge_item_tags kit
                    WHERE kit.knowledge_item_id = k.id AND kit.tag_id = :tag_id
                )
                """
            )
            params["tag_id"] = tag_id
        if tag:
            filters.append(
                """
                EXISTS (
                    SELECT 1
                    FROM kms_knowledge_item_tags kit
                    JOIN kms_tags t ON t.id = kit.tag_id
                    WHERE kit.knowledge_item_id = k.id AND t.name LIKE :tag
                )
                """
            )
            params["tag"] = f"%{tag.strip().lstrip('#')}%"
        if is_active is not None:
            filters.append("k.is_active = :is_active")
            params["is_active"] = 1 if is_active else 0
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT k.*
                FROM kms_knowledge_items k
                {where}
                ORDER BY k.updated_at DESC, k.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        return [self._knowledge_item_response(row) for row in rows]

    def get_knowledge_item(self, item_id: int) -> KmsKnowledgeItemResponse:
        self.sync_legacy_posts_to_knowledge_items()
        self.cleanup_knowledge_content_formats()
        row = self.db.execute(text("SELECT * FROM kms_knowledge_items WHERE id = :item_id"), {"item_id": item_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="knowledge item not found")
        return self._knowledge_item_response(row)

    def create_knowledge_item(self, payload: KmsKnowledgeItemCreate) -> KmsKnowledgeItemResponse:
        title = payload.title.strip()
        content = (payload.content or "").strip()
        if not title or not _strip_html_tags(content):
            raise HTTPException(status_code=400, detail="title and content are required")
        defaults = self._kms_setting_default_ids()
        now = now_kst()
        result = self.db.execute(
            text(
                """
                INSERT INTO kms_knowledge_items
                (legacy_post_id, legacy_source_type, legacy_source_id, title, content, content_format,
                 one_line_conclusion, summary, para_type_id, category_id, status_id,
                 importance_id, usage_context_id, source_type_id, source_url, source_title, ai_extract_status,
                 embedding_status, is_active, created_at, updated_at)
                VALUES
                (NULL, NULL, NULL, :title, :content, 'HTML',
                 :one_line_conclusion, :summary, :para_type_id, :category_id, :status_id,
                 :importance_id, :usage_context_id, :source_type_id, :source_url, :source_title, 'PENDING',
                 'PENDING', 1, :now, :now)
                """
            ),
            {
                "title": title,
                "content": content,
                "one_line_conclusion": payload.one_line_conclusion,
                "summary": payload.summary,
                "para_type_id": payload.para_type_id or defaults["PARA_TYPE"],
                "category_id": payload.category_id or defaults["KNOWLEDGE_CATEGORY"],
                "status_id": payload.status_id or defaults["KNOWLEDGE_STATUS"],
                "importance_id": payload.importance_id or defaults["IMPORTANCE_LEVEL"],
                "usage_context_id": payload.usage_context_id or defaults["USAGE_CONTEXT"],
                "source_type_id": payload.source_type_id or defaults["SOURCE_TYPE"],
                "source_url": payload.source_url,
                "source_title": payload.source_title,
                "now": now,
            },
        )
        item_id = int(result.lastrowid)
        self._replace_knowledge_item_tags(item_id, self._normalize_tags(payload.tags))
        self.db.commit()
        return self.get_knowledge_item(item_id)

    def replace_knowledge_item_tags(self, item_id: int, payload: KmsKnowledgeItemTagUpdate) -> KmsKnowledgeItemResponse:
        self.get_knowledge_item(item_id)
        self._sync_knowledge_item_confirmed_tags(item_id, self._normalize_tags(payload.tag_names), payload.tag_type_id)
        self.db.commit()
        return self.get_knowledge_item(item_id)

    def sync_knowledge_item_confirmed_tags(self, item_id: int, payload: KmsKnowledgeItemTagUpdate) -> KmsKnowledgeItemResponse:
        self.get_knowledge_item(item_id)
        self._sync_knowledge_item_confirmed_tags(item_id, self._normalize_tags(payload.tag_names), payload.tag_type_id)
        self.db.commit()
        return self.get_knowledge_item(item_id)

    def remove_knowledge_item_tag(self, item_id: int, tag_id: int) -> KmsKnowledgeItemResponse:
        self.get_knowledge_item(item_id)
        self.db.execute(
            text("DELETE FROM kms_knowledge_item_tags WHERE knowledge_item_id = :item_id AND tag_id = :tag_id"),
            {"item_id": item_id, "tag_id": tag_id},
        )
        self._refresh_tag_counts()
        self.db.commit()
        return self.get_knowledge_item(item_id)

    def update_knowledge_item(self, item_id: int, payload: KmsKnowledgeItemUpdate) -> KmsKnowledgeItemResponse:
        self.get_knowledge_item(item_id)
        values = payload.model_dump(exclude_unset=True)
        tags_value = values.pop("tags", None)
        values.pop("content_format", None)
        if "title" in values and values["title"] is not None:
            values["title"] = str(values["title"]).strip()
            if not values["title"]:
                raise HTTPException(status_code=400, detail="title is required")
        if "content" in values:
            content = str(values["content"] or "").strip()
            if not _strip_html_tags(content):
                raise HTTPException(status_code=400, detail="content is required")
            values["content"] = content
            values["content_format"] = "HTML"
        if "is_active" in values and values["is_active"] is not None:
            values["is_active"] = 1 if values["is_active"] else 0
        if values:
            values["updated_at"] = now_kst()
            assignments = ", ".join(f"{key} = :{key}" for key in values)
            self.db.execute(text(f"UPDATE kms_knowledge_items SET {assignments} WHERE id = :item_id"), {**values, "item_id": item_id})
        if tags_value is not None:
            self._sync_knowledge_item_confirmed_tags(item_id, self._normalize_tags(tags_value))
            self.db.execute(
                text("UPDATE kms_knowledge_items SET updated_at = :now WHERE id = :item_id"),
                {"item_id": item_id, "now": now_kst()},
            )
        self.db.commit()
        return self.get_knowledge_item(item_id)

    def set_knowledge_item_active(self, item_id: int, is_active: bool) -> KmsKnowledgeItemResponse:
        self.get_knowledge_item(item_id)
        self.db.execute(
            text("UPDATE kms_knowledge_items SET is_active = :is_active, updated_at = :now WHERE id = :item_id"),
            {"item_id": item_id, "is_active": 1 if is_active else 0, "now": now_kst()},
        )
        self.db.commit()
        return self.get_knowledge_item(item_id)

    def delete_knowledge_item(self, item_id: int) -> KmsKnowledgeItemResponse:
        current = self.get_knowledge_item(item_id)
        self.db.execute(text("DELETE FROM kms_knowledge_item_tags WHERE knowledge_item_id = :item_id"), {"item_id": item_id})
        self.db.execute(text("DELETE FROM kms_knowledge_extractions WHERE knowledge_item_id = :item_id"), {"item_id": item_id})
        self.db.execute(text("DELETE FROM kms_knowledge_items WHERE id = :item_id"), {"item_id": item_id})
        self._refresh_tag_counts()
        self.db.commit()
        return current

    def generate_knowledge_item_summary_help(self, item_id: int) -> KmsSummaryHelpResponse:
        item = self.get_knowledge_item(item_id)
        self.db.execute(
            text("UPDATE kms_knowledge_items SET ai_extract_status = 'RUNNING', updated_at = :now WHERE id = :item_id"),
            {"item_id": item_id, "now": now_kst()},
        )
        self.db.commit()
        try:
            payload = self._generate_summary_help_payload(item)
            self._store_summary_help_payload(item_id, payload)
            self.db.execute(
                text("UPDATE kms_knowledge_items SET ai_extract_status = 'DONE', updated_at = :now WHERE id = :item_id"),
                {"item_id": item_id, "now": now_kst()},
            )
            self.db.commit()
            return self._summary_help_response(item_id)
        except Exception as exc:  # noqa: BLE001
            error_text = str(exc)[:1000]
            self.db.execute(
                text("UPDATE kms_knowledge_items SET ai_extract_status = 'FAILED', updated_at = :now WHERE id = :item_id"),
                {"item_id": item_id, "now": now_kst()},
            )
            self._upsert_knowledge_extraction(item_id, "AI_ERROR", error_text, model_name="lmstudio")
            self.db.commit()
            return self._summary_help_response(item_id, error_message=error_text)

    def apply_knowledge_item_summary_help(self, item_id: int, payload: KmsSummaryHelpApplyRequest) -> KmsSummaryHelpResponse:
        item = self.get_knowledge_item(item_id)
        values: dict[str, Any] = {}
        summary = str(payload.summary or "").strip()
        if payload.apply_summary and summary:
            values["summary"] = summary
        if values:
            values["updated_at"] = now_kst()
            assignments = ", ".join(f"{key} = :{key}" for key in values)
            self.db.execute(text(f"UPDATE kms_knowledge_items SET {assignments} WHERE id = :item_id"), {**values, "item_id": item_id})
        if payload.add_keywords_as_tags:
            current_tags = [tag.tag_name for tag in item.tags if tag.is_confirmed]
            merged_tags = self._normalize_tags(current_tags + payload.keywords)
            self._sync_knowledge_item_confirmed_tags(item_id, merged_tags)
        self.db.commit()
        return self._summary_help_response(item_id)

    def _html_to_ai_plain_text(self, html_text: str, max_chars: int = 6000) -> str:
        text_value = str(html_text or "")
        text_value = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text_value)
        text_value = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text_value)
        text_value = re.sub(r"(?i)<br\s*/?>", "\n", text_value)
        text_value = re.sub(r"(?i)</(p|div|li|tr|h1|h2|h3|h4)\s*>", "\n", text_value)
        text_value = re.sub(r"(?is)<img[^>]*>", " ", text_value)
        text_value = re.sub(r"<[^>]+>", " ", text_value)
        text_value = unescape(text_value).replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text_value.splitlines()]
        text_value = "\n".join(line for line in lines if line)
        if len(text_value) <= max_chars:
            return text_value
        head = text_value[: max_chars // 2].strip()
        tail = text_value[-max_chars // 2 :].strip()
        return f"{head}\n\n...[중략]...\n\n{tail}"

    def _extract_json_object(self, text_value: str) -> dict[str, Any] | None:
        if not text_value:
            return None
        cleaned = str(text_value).strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _generate_summary_help_payload(self, item: KmsKnowledgeItemResponse) -> dict[str, Any]:
        client = LMStudioClient(timeout=45)
        plain_text = self._html_to_ai_plain_text(item.content, max_chars=1400)
        confirmed_tags = [tag.tag_name for tag in item.tags if tag.is_confirmed]
        prompt = f"""
아래 KMS 지식글을 보고 JSON 객체만 출력하세요.

규칙:
- summary는 1~2문장으로 짧게 작성합니다.
- keywords는 태그로 추가해도 좋은 핵심어 3~7개만 작성합니다.
- 매수/매도 추천, 목표가, 확정적 투자 판단은 쓰지 않습니다.
- 본문에 없는 내용을 만들지 않습니다.
- JSON 외 설명, markdown, 코드블록을 출력하지 않습니다.

응답 형식:
{{
  "summary": "2~3문장 요약",
  "keywords": ["키워드1", "키워드2", "키워드3"]
}}

제목: {item.title}
기존 요약: {item.summary or ""}
기존 확정 태그: {", ".join(confirmed_tags)}

본문:
{plain_text}
""".strip()
        raw = client.generate_text(
            prompt=prompt,
            temperature=0.0,
            max_tokens=1200,
            timeout=45,
            purpose="kms_summary_help",
            system_prompt="너는 한국 주식 리서치 지식관리 보조 AI이다. 내부 추론은 출력하지 말고 최종 JSON만 출력한다.",
            response_format={"type": "json_object"},
        )
        payload = self._extract_json_object(raw)
        if not payload:
            return self._fallback_summary_help_payload(item, plain_text)
        try:
            return self._normalize_summary_help_payload(payload)
        except RuntimeError:
            return self._fallback_summary_help_payload(item, plain_text)

    def _fallback_summary_help_payload(self, item: KmsKnowledgeItemResponse, plain_text: str) -> dict[str, Any]:
        source = re.sub(r"\s+", " ", plain_text or item.summary or item.title).strip()
        sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+|\n+", source) if part.strip()]
        summary_parts: list[str] = []
        for sentence in sentences:
            if len(" ".join(summary_parts + [sentence])) > 500:
                break
            summary_parts.append(sentence)
            if len(summary_parts) >= 2:
                break
        summary = " ".join(summary_parts).strip() or source[:500].strip() or item.title
        keywords = self._summary_help_keywords_from_text(
            " ".join([item.title or "", item.summary or "", plain_text or ""]),
            [tag.tag_name for tag in item.tags if tag.is_confirmed],
        )
        return {"summary": summary[:800], "keywords": keywords}

    def _summary_help_keywords_from_text(self, text_value: str, seed_tags: list[str] | None = None) -> list[str]:
        text_body = str(text_value or "")
        candidates: list[str] = []
        candidates.extend(seed_tags or [])
        keyword_rules = [
            "금",
            "금리",
            "달러",
            "달러인덱스",
            "중앙은행",
            "탈달러화",
            "외환보유",
            "지정학리스크",
            "인플레이션",
            "ETF",
            "유가",
            "환율",
            "수급",
            "반도체",
            "HBM",
            "AI",
            "기관",
            "개인투자자",
            "리스크",
        ]
        lowered = text_body.casefold()
        for keyword in keyword_rules:
            if keyword.casefold() in lowered:
                candidates.append(keyword)
        for match in re.findall(r"#\s*([0-9A-Za-z가-힣_+-]{2,20})", text_body):
            candidates.append(match)
        return self._normalize_tags(candidates)[:7]

    def _normalize_summary_help_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        summary = re.sub(r"\s+", " ", str(payload.get("summary") or "").strip())
        raw_keywords = payload.get("keywords")
        if not isinstance(raw_keywords, list):
            raw_keywords = []
        keywords = self._normalize_tags([str(value) for value in raw_keywords])[:7]
        if not summary:
            raise RuntimeError("요약 도움 응답에 summary가 없습니다.")
        return {"summary": summary[:800], "keywords": keywords}

    def _store_summary_help_payload(self, item_id: int, payload: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                DELETE FROM kms_knowledge_extractions
                WHERE knowledge_item_id = :item_id
                  AND source = 'AI'
                  AND extraction_type IN (
                    'FULL_AI_STRUCTURED', 'SUMMARY', 'KEY_POINTS', 'CATEGORY_SUGGESTION',
                    'USAGE_CONTEXT_SUGGESTION', 'TAG_SUGGESTION', 'STOCK_SUGGESTION',
                    'THEME_SUGGESTION', 'CHECKLIST', 'SUMMARY_HELP', 'AI_ERROR'
                  )
                """
            ),
            {"item_id": item_id},
        )
        self._upsert_knowledge_extraction(
            item_id,
            "SUMMARY_HELP",
            json.dumps(payload, ensure_ascii=False),
            model_name="lmstudio",
            confidence=1.0,
        )

    def _upsert_knowledge_extraction(self, item_id: int, extraction_type: str, text_value: str, model_name: str | None = None, confidence: float | None = None) -> None:
        if not str(text_value or "").strip():
            return
        now = now_kst()
        self.db.execute(
            text(
                """
                INSERT INTO kms_knowledge_extractions
                (knowledge_item_id, extraction_type, extraction_text, source, model_name, confidence_score, created_at, updated_at)
                VALUES (:item_id, :extraction_type, :text_value, 'AI', :model_name, :confidence, :now, :now)
                """
            ),
            {
                "item_id": item_id,
                "extraction_type": extraction_type,
                "text_value": text_value,
                "model_name": model_name,
                "confidence": confidence,
                "now": now,
            },
        )

    def _latest_summary_help_payload(self, item_id: int) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                SELECT extraction_text
                FROM kms_knowledge_extractions
                WHERE knowledge_item_id = :item_id
                  AND extraction_type = 'SUMMARY_HELP'
                  AND source = 'AI'
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"item_id": item_id},
        ).first()
        if not row:
            return {}
        try:
            payload = json.loads(str(row[0] or "{}"))
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _summary_help_response(self, item_id: int, error_message: str | None = None) -> KmsSummaryHelpResponse:
        item = self.get_knowledge_item(item_id)
        payload = self._latest_summary_help_payload(item_id)
        keywords = payload.get("keywords") if isinstance(payload.get("keywords"), list) else []
        return KmsSummaryHelpResponse(
            knowledge_item_id=item_id,
            status=item.ai_extract_status,
            summary=str(payload.get("summary") or "") or None,
            keywords=[str(value) for value in keywords if str(value).strip()],
            error_message=error_message,
            item=item,
        )

    def resolve_local_image(self, image_path: str) -> tuple[Path, str]:
        raw_path = str(image_path or "").strip().strip('"')
        if not raw_path:
            raise HTTPException(status_code=400, detail="local image path is required")
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            raise HTTPException(status_code=400, detail="absolute local image path is required")
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="local image file not found")
        if path.suffix.lower() not in KMS_ALLOWED_LOCAL_IMAGE_SUFFIXES:
            raise HTTPException(status_code=400, detail="PNG, JPG, GIF, WEBP image files only")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return path, media_type

    def select_local_image(self) -> KmsLocalImageSelectResponse:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"file picker unavailable: {exc}") from exc

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            selected = filedialog.askopenfilename(
                title="KMS image select",
                filetypes=[
                    ("Image files", "*.png *.jpg *.jpeg *.gif *.webp"),
                    ("All files", "*.*"),
                ],
            )
        finally:
            root.destroy()

        if not selected:
            return KmsLocalImageSelectResponse(selected=False)

        file_path, _media_type = self.resolve_local_image(selected)
        path_text = str(file_path)
        return KmsLocalImageSelectResponse(
            selected=True,
            path=path_text,
            url=f"/kms/local-image?path={quote(path_text, safe='')}",
        )

    def ensure_default_categories(self) -> None:
        now = now_kst()
        for index, name in enumerate(DEFAULT_KMS_CATEGORIES, start=1):
            exists = self.db.execute(
                text("SELECT id FROM kms_categories WHERE parent_id IS NULL AND name = :name LIMIT 1"),
                {"name": name},
            ).first()
            if exists:
                continue
            self.db.execute(
                text(
                    """
                    INSERT INTO kms_categories (parent_id, name, description, sort_order, is_active, created_at, updated_at)
                    VALUES (NULL, :name, NULL, :sort_order, 1, :now, :now)
                    """
                ),
                {"name": name, "sort_order": index * 10, "now": now},
            )
        self.db.commit()

    def list_categories(self, include_inactive: bool = False) -> list[KmsCategoryResponse]:
        self.ensure_default_categories()
        where = "" if include_inactive else "WHERE is_active = 1"
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    c.id,
                    c.parent_id,
                    c.name,
                    c.description,
                    c.sort_order,
                    c.is_active,
                    c.created_at,
                    c.updated_at,
                    (
                        SELECT COUNT(*)
                        FROM kms_posts p
                        JOIN kms_categories pc ON pc.id = p.category_id
                        WHERE p.is_active = 1
                          AND pc.name = c.name
                          AND COALESCE(pc.parent_id, -1) = COALESCE(c.parent_id, -1)
                    ) AS post_count,
                    (
                        SELECT COUNT(*)
                        FROM kms_posts p
                        JOIN kms_categories pc ON pc.id = p.category_id
                        WHERE pc.name = c.name
                          AND COALESCE(pc.parent_id, -1) = COALESCE(c.parent_id, -1)
                    ) AS total_post_count,
                    (
                        SELECT COUNT(*)
                        FROM kms_categories child
                        WHERE child.parent_id = c.id
                    ) AS child_count
                FROM kms_categories c
                {where}
                ORDER BY COALESCE(c.parent_id, 0), c.sort_order, c.id
                """
            )
        ).mappings()
        return [self._category_response(row) for row in rows]

    def create_category(self, payload: KmsCategoryCreate) -> KmsCategoryResponse:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="category name is required")
        self.ensure_default_categories()
        duplicated = self.db.execute(
            text(
                """
                SELECT id FROM kms_categories
                WHERE COALESCE(parent_id, -1) = COALESCE(:parent_id, -1) AND name = :name
                LIMIT 1
                """
            ),
            {"parent_id": payload.parent_id, "name": name},
        ).first()
        if duplicated:
            raise HTTPException(status_code=409, detail="same category already exists")
        now = now_kst()
        result = self.db.execute(
            text(
                """
                INSERT INTO kms_categories (parent_id, name, description, sort_order, is_active, created_at, updated_at)
                VALUES (:parent_id, :name, :description, :sort_order, :is_active, :now, :now)
                """
            ),
            {
                "parent_id": payload.parent_id,
                "name": name,
                "description": payload.description,
                "sort_order": payload.sort_order,
                "is_active": 1 if payload.is_active else 0,
                "now": now,
            },
        )
        self.db.commit()
        return self.get_category(int(result.lastrowid))

    def get_category(self, category_id: int) -> KmsCategoryResponse:
        row = self.db.execute(
            text(
                """
                SELECT
                    c.id,
                    c.parent_id,
                    c.name,
                    c.description,
                    c.sort_order,
                    c.is_active,
                    c.created_at,
                    c.updated_at,
                    (
                        SELECT COUNT(*)
                        FROM kms_posts p
                        JOIN kms_categories pc ON pc.id = p.category_id
                        WHERE p.is_active = 1
                          AND pc.name = c.name
                          AND COALESCE(pc.parent_id, -1) = COALESCE(c.parent_id, -1)
                    ) AS post_count,
                    (
                        SELECT COUNT(*)
                        FROM kms_posts p
                        JOIN kms_categories pc ON pc.id = p.category_id
                        WHERE pc.name = c.name
                          AND COALESCE(pc.parent_id, -1) = COALESCE(c.parent_id, -1)
                    ) AS total_post_count,
                    (
                        SELECT COUNT(*)
                        FROM kms_categories child
                        WHERE child.parent_id = c.id
                    ) AS child_count
                FROM kms_categories c
                WHERE c.id = :category_id
                """
            ),
            {"category_id": category_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="category not found")
        return self._category_response(row)

    def update_category(self, category_id: int, payload: KmsCategoryUpdate) -> KmsCategoryResponse:
        self.get_category(category_id)
        values = payload.model_dump(exclude_unset=True)
        if "name" in values and values["name"] is not None:
            values["name"] = values["name"].strip()
            if not values["name"]:
                raise HTTPException(status_code=400, detail="category name is required")
        if "is_active" in values:
            values["is_active"] = 1 if values["is_active"] else 0
        if not values:
            return self.get_category(category_id)
        values["updated_at"] = now_kst()
        assignments = ", ".join(f"{key} = :{key}" for key in values)
        values["category_id"] = category_id
        self.db.execute(text(f"UPDATE kms_categories SET {assignments} WHERE id = :category_id"), values)
        self.db.commit()
        return self.get_category(category_id)

    def set_category_active(self, category_id: int, is_active: bool) -> KmsCategoryResponse:
        self.get_category(category_id)
        self.db.execute(
            text("UPDATE kms_categories SET is_active = :is_active, updated_at = :now WHERE id = :category_id"),
            {"category_id": category_id, "is_active": 1 if is_active else 0, "now": now_kst()},
        )
        self.db.commit()
        return self.get_category(category_id)

    def deactivate_category(self, category_id: int) -> KmsCategoryResponse:
        return self.set_category_active(category_id, False)

    def delete_category(self, category_id: int) -> dict[str, bool]:
        self.get_category(category_id)
        post_count = int(
            self.db.execute(text("SELECT COUNT(*) FROM kms_posts WHERE category_id = :category_id"), {"category_id": category_id}).scalar() or 0
        )
        child_count = int(
            self.db.execute(text("SELECT COUNT(*) FROM kms_categories WHERE parent_id = :category_id"), {"category_id": category_id}).scalar() or 0
        )
        if post_count > 0:
            raise HTTPException(status_code=409, detail="??移댄뀒怨좊━???곌껐??寃뚯떆湲???덉뼱 ??젣?????놁뒿?덈떎. 鍮꾪솢?깊솕瑜??ъ슜??二쇱꽭??")
        if child_count > 0:
            raise HTTPException(status_code=409, detail="?섏쐞 移댄뀒怨좊━媛 ?덉뼱 ??젣?????놁뒿?덈떎. ?섏쐞 移댄뀒怨좊━瑜?癒쇱? ?뺣━??二쇱꽭??")
        self.db.execute(text("DELETE FROM kms_categories WHERE id = :category_id"), {"category_id": category_id})
        self.db.commit()
        return {"success": True}

    def update_category_sort_orders(self, payload: KmsCategorySortOrderUpdate) -> KmsCategorySortOrderResponse:
        if not payload.items:
            raise HTTPException(status_code=400, detail="??ν븷 移댄뀒怨좊━ ?쒖꽌媛 ?놁뒿?덈떎.")
        ids = [item.id for item in payload.items]
        if len(set(ids)) != len(ids):
            raise HTTPException(status_code=400, detail="以묐났??移댄뀒怨좊━媛 ?ы븿?섏뼱 ?덉뒿?덈떎.")
        orders = [item.sort_order for item in payload.items]
        if len(set(orders)) != len(orders):
            raise HTTPException(status_code=400, detail="?쒖떆 ?쒖꽌媛 以묐났?섏뿀?듬땲??")
        rows = self.db.execute(
            text("SELECT id FROM kms_categories WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": tuple(ids)},
        ).mappings().all()
        found_ids = {int(row["id"]) for row in rows}
        missing_ids = [category_id for category_id in ids if category_id not in found_ids]
        if missing_ids:
            raise HTTPException(status_code=404, detail=f"議댁옱?섏? ?딅뒗 移댄뀒怨좊━媛 ?ы븿?섏뼱 ?덉뒿?덈떎: {missing_ids[0]}")
        now = now_kst()
        for item in payload.items:
            self.db.execute(
                text("UPDATE kms_categories SET sort_order = :sort_order, updated_at = :now WHERE id = :category_id"),
                {"category_id": item.id, "sort_order": item.sort_order, "now": now},
            )
        self.db.commit()
        return KmsCategorySortOrderResponse(success=True, updated_count=len(payload.items))

    def list_posts(
        self,
        keyword: str | None = None,
        category_id: int | None = None,
        learning_status: str | None = None,
        importance: str | None = None,
        is_active: bool | None = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KmsPostSummary]:
        self.ensure_default_categories()
        filters = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if keyword:
            filters.append("(p.title LIKE :keyword OR p.summary LIKE :keyword OR p.content LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        if category_id:
            filters.append(
                """
                p.category_id IN (
                    SELECT sibling.id
                    FROM kms_categories sibling
                    JOIN kms_categories selected ON selected.id = :category_id
                    WHERE sibling.name = selected.name
                      AND COALESCE(sibling.parent_id, -1) = COALESCE(selected.parent_id, -1)
                )
                """
            )
            params["category_id"] = category_id
        if learning_status:
            filters.append("p.learning_status = :learning_status")
            params["learning_status"] = learning_status
        if importance:
            filters.append("p.importance = :importance")
            params["importance"] = importance
        if is_active is not None:
            filters.append("p.is_active = :is_active")
            params["is_active"] = 1 if is_active else 0
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT p.*, c.name AS category_name
                FROM kms_posts p
                LEFT JOIN kms_categories c ON c.id = p.category_id
                {where}
                ORDER BY p.is_pinned DESC, p.updated_at DESC, p.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        return [self._post_response(row) for row in rows]

    def get_post(self, post_id: int) -> KmsPostSummary:
        row = self.db.execute(
            text(
                """
                SELECT p.*, c.name AS category_name
                FROM kms_posts p
                LEFT JOIN kms_categories c ON c.id = p.category_id
                WHERE p.id = :post_id
                """
            ),
            {"post_id": post_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="post not found")
        return self._post_response(row)

    def create_post(self, payload: KmsPostCreate) -> KmsPostSummary:
        self._validate_post_payload(payload.category_id, payload.title, payload.content, payload.importance, payload.learning_status)
        now = now_kst()
        result = self.db.execute(
            text(
                """
                INSERT INTO kms_posts (
                    category_id, title, summary, content, source_url, importance, learning_status,
                    is_pinned, is_active, created_at, updated_at
                ) VALUES (
                    :category_id, :title, :summary, :content, :source_url, :importance, :learning_status,
                    :is_pinned, :is_active, :now, :now
                )
                """
            ),
            {
                "category_id": payload.category_id,
                "title": payload.title.strip(),
                "summary": payload.summary,
                "content": payload.content,
                "source_url": payload.source_url,
                "importance": payload.importance,
                "learning_status": payload.learning_status,
                "is_pinned": 1 if payload.is_pinned else 0,
                "is_active": 1 if payload.is_active else 0,
                "now": now,
            },
        )
        post_id = int(result.lastrowid)
        self._replace_post_tags(post_id, self._normalize_tags(payload.tags))
        self._link_content_images_to_post(post_id, payload.content)
        self.db.commit()
        return self.get_post(post_id)

    def update_post(self, post_id: int, payload: KmsPostUpdate) -> KmsPostSummary:
        current = self.get_post(post_id)
        values = payload.model_dump(exclude_unset=True)
        tags_value = values.pop("tags", None)
        merged_category_id = values.get("category_id", current.category_id)
        merged_title = values.get("title", current.title)
        merged_content = values.get("content", current.content)
        merged_importance = values.get("importance", current.importance)
        merged_learning_status = values.get("learning_status", current.learning_status)
        self._validate_post_payload(merged_category_id, merged_title, merged_content, merged_importance, merged_learning_status)
        if "title" in values and values["title"] is not None:
            values["title"] = values["title"].strip()
        for bool_key in ("is_pinned", "is_active"):
            if bool_key in values:
                values[bool_key] = 1 if values[bool_key] else 0
        if values:
            values["updated_at"] = now_kst()
            assignments = ", ".join(f"{key} = :{key}" for key in values)
            values["post_id"] = post_id
            self.db.execute(text(f"UPDATE kms_posts SET {assignments} WHERE id = :post_id"), values)
        if tags_value is not None:
            self._replace_post_tags(post_id, self._normalize_tags(tags_value))
        if "content" in values:
            self._link_content_images_to_post(post_id, merged_content)
        self.db.commit()
        return self.get_post(post_id)

    def delete_post(self, post_id: int) -> KmsPostSummary:
        current = self.get_post(post_id)
        self._delete_post_images(post_id, current.content)
        self.db.execute(text("DELETE FROM kms_post_tags WHERE post_id = :post_id"), {"post_id": post_id})
        self.db.execute(
            text("DELETE FROM kms_posts WHERE id = :post_id"),
            {"post_id": post_id},
        )
        self._refresh_tag_counts()
        self.db.commit()
        return current

    def deactivate_post(self, post_id: int) -> KmsPostSummary:
        return self.delete_post(post_id)

    def list_tags(self, keyword: str | None = None, sort: str = "popular", limit: int = 100) -> list[KmsTagResponse]:
        filters = ["is_active = 1"]
        params: dict[str, Any] = {"limit": limit}
        if keyword:
            filters.append("name LIKE :keyword")
            params["keyword"] = f"%{keyword.strip().lstrip('#')}%"
        order_by = "use_count DESC, name ASC" if sort != "name" else "name ASC"
        rows = self.db.execute(
            text(
                f"""
                SELECT id, name, description, use_count, is_active, created_at, updated_at
                FROM kms_tags
                WHERE {' AND '.join(filters)}
                ORDER BY {order_by}
                LIMIT :limit
                """
            ),
            params,
        ).mappings()
        return [self._tag_response(row) for row in rows]

    def create_tag(self, payload: KmsTagCreate) -> KmsTagResponse:
        name = payload.tag_name.strip().lstrip("#")
        if not name:
            raise HTTPException(status_code=400, detail="tag_name is required")
        duplicated = self.db.execute(text("SELECT id FROM kms_tags WHERE name = :name"), {"name": name}).first()
        if duplicated:
            raise HTTPException(status_code=409, detail="same tag already exists")
        now = now_kst()
        result = self.db.execute(
            text(
                """
                INSERT INTO kms_tags
                (name, description, use_count, is_active, tag_type_id, color, entity_type, entity_id, created_at, updated_at)
                VALUES (:name, :description, 0, :is_active, :tag_type_id, :color, :entity_type, :entity_id, :now, :now)
                """
            ),
            {
                "name": name,
                "description": payload.description,
                "is_active": 1 if payload.is_active else 0,
                "tag_type_id": payload.tag_type_id or self._kms_setting_default_ids().get("TAG_TYPE"),
                "color": payload.color,
                "entity_type": payload.entity_type,
                "entity_id": payload.entity_id,
                "now": now,
            },
        )
        self.db.commit()
        return self._get_tag_response(int(result.lastrowid))

    def update_tag(self, tag_id: int, payload: KmsTagUpdate) -> KmsTagResponse:
        self._get_tag_response(tag_id)
        values = payload.model_dump(exclude_unset=True)
        if "tag_name" in values:
            values["name"] = str(values.pop("tag_name") or "").strip().lstrip("#")
            if not values["name"]:
                raise HTTPException(status_code=400, detail="tag_name is required")
        if "is_active" in values and values["is_active"] is not None:
            values["is_active"] = 1 if values["is_active"] else 0
        if values:
            values["updated_at"] = now_kst()
            values["tag_id"] = tag_id
            assignments = ", ".join(f"{key} = :{key}" for key in values)
            self.db.execute(text(f"UPDATE kms_tags SET {assignments} WHERE id = :tag_id"), values)
            self.db.commit()
        return self._get_tag_response(tag_id)

    def search_by_tags(
        self,
        tag_names: list[str] | str,
        match_mode: str = "AND",
        category_id: int | None = None,
        learning_status: str | None = None,
        importance: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KmsPostSummary]:
        tags = self._normalize_tags(tag_names)
        if not tags:
            return []
        mode = match_mode.upper()
        if mode not in {"AND", "OR"}:
            raise HTTPException(status_code=400, detail="match_mode must be AND or OR")
        filters = ["p.is_active = 1", "t.name IN :tag_names"]
        params: dict[str, Any] = {"tag_names": tuple(tags), "limit": limit, "offset": offset}
        if category_id:
            filters.append("p.category_id = :category_id")
            params["category_id"] = category_id
        if learning_status:
            filters.append("p.learning_status = :learning_status")
            params["learning_status"] = learning_status
        if importance:
            filters.append("p.importance = :importance")
            params["importance"] = importance
        having = "HAVING COUNT(DISTINCT t.name) = :tag_count" if mode == "AND" else ""
        if mode == "AND":
            params["tag_count"] = len(tags)
        rows = self.db.execute(
            text(
                f"""
                SELECT p.*, c.name AS category_name
                FROM kms_posts p
                JOIN kms_post_tags pt ON pt.post_id = p.id
                JOIN kms_tags t ON t.id = pt.tag_id
                LEFT JOIN kms_categories c ON c.id = p.category_id
                WHERE {' AND '.join(filters)}
                GROUP BY p.id
                {having}
                ORDER BY p.is_pinned DESC, p.updated_at DESC, p.id DESC
                LIMIT :limit OFFSET :offset
                """
            ).bindparams(bindparam("tag_names", expanding=True)),
            params,
        ).mappings().all()
        return [self._post_response(row) for row in rows]

    def get_home_summary(self) -> KmsHomeSummary:
        self.ensure_default_categories()
        overall_row = self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_posts,
                    SUM(CASE WHEN learning_status = '蹂듭뒿 ?꾩슂' THEN 1 ELSE 0 END) AS review_needed_count,
                    SUM(CASE WHEN learning_status = '?ㅼ쟾 ?곸슜 ?꾨낫' THEN 1 ELSE 0 END) AS practice_candidate_count,
                    SUM(CASE WHEN importance = '?듭떖' THEN 1 ELSE 0 END) AS core_count,
                    SUM(CASE WHEN updated_at >= datetime('now', '-7 days', 'localtime') THEN 1 ELSE 0 END) AS recent_7d_count
                FROM kms_posts
                WHERE is_active = 1
                """
            )
        ).mappings().first()
        categories = self._category_summaries()
        popular_tags = self.list_tags(sort="popular", limit=12)
        recent_posts = self._recent_posts()
        review_needed_posts = self._recent_posts("蹂듭뒿 ?꾩슂")
        practice_candidate_posts = self._recent_posts("?ㅼ쟾 ?곸슜 ?꾨낫")
        return KmsHomeSummary(
            overall=KmsOverallSummary(
                total_posts=int(overall_row["total_posts"] or 0),
                review_needed_count=int(overall_row["review_needed_count"] or 0),
                practice_candidate_count=int(overall_row["practice_candidate_count"] or 0),
                core_count=int(overall_row["core_count"] or 0),
                recent_7d_count=int(overall_row["recent_7d_count"] or 0),
            ),
            categories=categories,
            popular_tags=popular_tags,
            recent_posts=recent_posts,
            review_needed_posts=review_needed_posts,
            practice_candidate_posts=practice_candidate_posts,
        )

    def _extract_kms_image_refs(self, content: str | None) -> tuple[set[str], set[str]]:
        file_urls: set[str] = set()
        relative_paths: set[str] = set()
        for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', str(content or ""), flags=re.IGNORECASE):
            marker = "/static/kms_images/"
            marker_index = src.find(marker)
            if marker_index < 0:
                continue
            file_url = src[marker_index:].split("#", 1)[0].split("?", 1)[0]
            if not file_url:
                continue
            file_urls.add(file_url)
            decoded_file_url = unquote(file_url)
            file_urls.add(decoded_file_url)
            relative_paths.add("data/" + file_url.removeprefix("/static/"))
            relative_paths.add("data/" + decoded_file_url.removeprefix("/static/"))
        return file_urls, relative_paths

    def _find_kms_image_ids(self, post_id: int, content: str | None) -> set[int]:
        image_ids: set[int] = set()
        rows = self.db.execute(
            text(
                """
                SELECT id
                FROM app_images
                WHERE domain = 'kms'
                  AND owner_type = 'kms_post'
                  AND owner_id = :post_id
                """
            ),
            {"post_id": post_id},
        ).mappings().all()
        image_ids.update(int(row["id"]) for row in rows)

        file_urls, relative_paths = self._extract_kms_image_refs(content)
        for file_url in file_urls:
            row = self.db.execute(
                text("SELECT id FROM app_images WHERE domain = 'kms' AND file_url = :file_url"),
                {"file_url": file_url},
            ).mappings().first()
            if row:
                image_ids.add(int(row["id"]))
        for relative_path in relative_paths:
            row = self.db.execute(
                text("SELECT id FROM app_images WHERE domain = 'kms' AND relative_path = :relative_path"),
                {"relative_path": relative_path},
            ).mappings().first()
            if row:
                image_ids.add(int(row["id"]))
        return image_ids

    def _link_content_images_to_post(self, post_id: int, content: str | None) -> None:
        image_ids = self._find_kms_image_ids(post_id, content)
        for image_id in image_ids:
            self.db.execute(
                text(
                    """
                    UPDATE app_images
                    SET owner_type = 'kms_post', owner_id = :post_id, updated_at = :now
                    WHERE id = :image_id
                      AND domain = 'kms'
                      AND (owner_id IS NULL OR owner_id = :post_id)
                    """
                ),
                {"image_id": image_id, "post_id": post_id, "now": now_kst()},
            )

    def _delete_post_images(self, post_id: int, content: str | None) -> None:
        image_ids = self._find_kms_image_ids(post_id, content)
        image_service = ImageFileService(self.db)
        for image_id in sorted(image_ids):
            row = self.db.execute(
                text("SELECT relative_path FROM app_images WHERE id = :image_id"),
                {"image_id": image_id},
            ).mappings().first()
            if not row:
                continue
            image_service.delete_physical_file(str(row["relative_path"]))
            self.db.execute(text("DELETE FROM app_images WHERE id = :image_id"), {"image_id": image_id})

    def _validate_post_payload(self, category_id: int, title: str, content: str, importance: str, learning_status: str) -> None:
        if not str(title or "").strip():
            raise HTTPException(status_code=400, detail="title is required")
        if not str(content or "").strip():
            raise HTTPException(status_code=400, detail="content is required")
        if importance not in IMPORTANCE_VALUES and not self._setting_item_id_by_name_or_code("IMPORTANCE_LEVEL", importance):
            raise HTTPException(status_code=400, detail="invalid importance")
        if learning_status not in LEARNING_STATUS_VALUES and not self._setting_item_id_by_name_or_code("KNOWLEDGE_STATUS", learning_status):
            raise HTTPException(status_code=400, detail="invalid learning_status")
        self.get_category(category_id)

    def _replace_post_tags(self, post_id: int, tag_names: list[str]) -> None:
        self.db.execute(text("DELETE FROM kms_post_tags WHERE post_id = :post_id"), {"post_id": post_id})
        now = now_kst()
        for name in tag_names:
            row = self.db.execute(text("SELECT id FROM kms_tags WHERE name = :name"), {"name": name}).first()
            if row:
                tag_id = int(row[0])
                self.db.execute(text("UPDATE kms_tags SET is_active = 1, updated_at = :now WHERE id = :tag_id"), {"tag_id": tag_id, "now": now})
            else:
                result = self.db.execute(
                    text(
                        """
                        INSERT INTO kms_tags (name, description, use_count, is_active, created_at, updated_at)
                        VALUES (:name, NULL, 0, 1, :now, :now)
                        """
                    ),
                    {"name": name, "now": now},
                )
                tag_id = int(result.lastrowid)
            self.db.execute(text("INSERT OR IGNORE INTO kms_post_tags (post_id, tag_id) VALUES (:post_id, :tag_id)"), {"post_id": post_id, "tag_id": tag_id})
        self._refresh_tag_counts()

    def _refresh_tag_counts(self) -> None:
        self.db.execute(text("UPDATE kms_tags SET use_count = 0"))
        self.db.execute(
            text(
                """
                UPDATE kms_tags
                SET use_count = (
                    SELECT COUNT(*)
                    FROM kms_post_tags pt
                    JOIN kms_posts p ON p.id = pt.post_id AND p.is_active = 1
                    WHERE pt.tag_id = kms_tags.id
                )
                """
            )
        )

    def _normalize_tags(self, tags: list[str] | str | None) -> list[str]:
        if tags is None:
            return []
        raw_values = tags.split(",") if isinstance(tags, str) else [part for raw in tags for part in str(raw).split(",")]
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in raw_values:
            name = re.sub(r"\s+", " ", str(raw).strip().lstrip("#").strip())
            key = name.casefold()
            if not name or key in seen:
                continue
            seen.add(key)
            normalized.append(name)
        return normalized

    def _post_response(self, row: Any) -> KmsPostSummary:
        tags = self._tags_for_post(int(row["id"]))
        return KmsPostSummary(
            id=int(row["id"]),
            category_id=int(row["category_id"]),
            category_name=row["category_name"],
            title=row["title"],
            summary=row["summary"],
            content=row["content"],
            source_url=row["source_url"],
            importance=row["importance"],
            learning_status=row["learning_status"],
            is_pinned=bool(row["is_pinned"]),
            is_active=bool(row["is_active"]),
            tags=tags,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            post_count=int(row["post_count"] or 0) if "post_count" in row else 0,
            total_post_count=int(row["total_post_count"] or 0) if "total_post_count" in row else 0,
            child_count=int(row["child_count"] or 0) if "child_count" in row else 0,
        )

    def _tags_for_post(self, post_id: int) -> list[str]:
        rows = self.db.execute(
            text(
                """
                SELECT t.name
                FROM kms_tags t
                JOIN kms_post_tags pt ON pt.tag_id = t.id
                WHERE pt.post_id = :post_id AND t.is_active = 1
                ORDER BY t.name
                """
            ),
            {"post_id": post_id},
        )
        return [str(row[0]) for row in rows]

    def _category_response(self, row: Any) -> KmsCategoryResponse:
        return KmsCategoryResponse(
            id=int(row["id"]),
            parent_id=row["parent_id"],
            name=row["name"],
            description=row["description"],
            sort_order=int(row["sort_order"] or 0),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _tag_response(self, row: Any) -> KmsTagResponse:
        return KmsTagResponse(
            id=int(row["id"]),
            name=row["name"],
            description=row["description"],
            use_count=int(row["use_count"] or 0),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _get_tag_response(self, tag_id: int) -> KmsTagResponse:
        row = self.db.execute(
            text("SELECT id, name, description, use_count, is_active, created_at, updated_at FROM kms_tags WHERE id = :tag_id"),
            {"tag_id": tag_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="tag not found")
        return self._tag_response(row)

    def _setting_group_response(self, row: Any) -> KmsSettingGroupResponse:
        return KmsSettingGroupResponse(
            id=int(row["id"]),
            group_code=str(row["group_code"]),
            group_name=str(row["group_name"]),
            description=row["description"],
            sort_order=int(row["sort_order"] or 0),
            is_active=bool(row["is_active"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            items=[],
        )

    def _setting_item_response(self, row: Any) -> KmsSettingItemResponse:
        return KmsSettingItemResponse(
            id=int(row["id"]),
            group_id=int(row["group_id"]),
            group_code=str(row["group_code"]) if "group_code" in row and row["group_code"] is not None else None,
            item_code=str(row["item_code"]),
            item_name=str(row["item_name"]),
            description=row["description"],
            color=row["color"],
            icon=row["icon"],
            sort_order=int(row["sort_order"] or 0),
            is_default=bool(row["is_default"]),
            is_system=bool(row["is_system"]),
            is_active=bool(row["is_active"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def cleanup_knowledge_content_formats(self) -> None:
        markdown_rows = self.db.execute(
            text("SELECT id FROM kms_knowledge_items WHERE UPPER(COALESCE(content_format, '')) = 'MARKDOWN'")
        ).all()
        for row in markdown_rows:
            item_id = int(row[0])
            self.db.execute(text("DELETE FROM kms_knowledge_item_tags WHERE knowledge_item_id = :item_id"), {"item_id": item_id})
            self.db.execute(text("DELETE FROM kms_knowledge_extractions WHERE knowledge_item_id = :item_id"), {"item_id": item_id})
            self.db.execute(text("DELETE FROM kms_knowledge_items WHERE id = :item_id"), {"item_id": item_id})
        rows = self.db.execute(
            text(
                """
                SELECT id, content, content_format
                FROM kms_knowledge_items
                WHERE content_format IS NULL OR UPPER(content_format) <> 'HTML'
                """
            )
        ).mappings().all()
        if not rows and not markdown_rows:
            return
        for row in rows:
            self.db.execute(
                text(
                    """
                    UPDATE kms_knowledge_items
                    SET content_format = 'HTML'
                    WHERE id = :item_id
                    """
                ),
                {"item_id": int(row["id"])},
            )
        self.db.commit()

    def _knowledge_item_response(self, row: Any) -> KmsKnowledgeItemResponse:
        item_id = int(row["id"])
        raw_content = str(row["content"] or "")
        snippet_source = row["summary"] or raw_content
        return KmsKnowledgeItemResponse(
            id=item_id,
            legacy_post_id=int(row["legacy_post_id"]) if row["legacy_post_id"] is not None else None,
            legacy_source_type=_row_get(row, "legacy_source_type"),
            legacy_source_id=int(_row_get(row, "legacy_source_id")) if _row_get(row, "legacy_source_id") is not None else None,
            title=str(row["title"]),
            content=raw_content,
            content_format="HTML",
            plain_text_snippet=_plain_snippet(snippet_source),
            one_line_conclusion=row["one_line_conclusion"],
            summary=row["summary"],
            para_type_id=int(row["para_type_id"]) if row["para_type_id"] is not None else None,
            category_id=int(row["category_id"]) if row["category_id"] is not None else None,
            status_id=int(row["status_id"]) if row["status_id"] is not None else None,
            importance_id=int(row["importance_id"]) if row["importance_id"] is not None else None,
            usage_context_id=int(row["usage_context_id"]) if row["usage_context_id"] is not None else None,
            source_type_id=int(row["source_type_id"]) if row["source_type_id"] is not None else None,
            source_url=row["source_url"],
            source_title=row["source_title"],
            ai_extract_status=str(row["ai_extract_status"] or "PENDING"),
            embedding_status=str(row["embedding_status"] or "PENDING"),
            is_active=bool(row["is_active"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            para_type=self._setting_item_summary(row["para_type_id"]),
            category=self._setting_item_summary(row["category_id"]),
            status=self._setting_item_summary(row["status_id"]),
            importance=self._setting_item_summary(row["importance_id"]),
            usage_context=self._setting_item_summary(row["usage_context_id"]),
            source_type=self._setting_item_summary(row["source_type_id"]),
            tags=self._knowledge_tags_for_item(item_id),
            extractions=self._knowledge_extractions_for_item(item_id),
        )

    def _setting_item_summary(self, item_id: object) -> KmsSettingItemSummary | None:
        if item_id is None:
            return None
        row = self.db.execute(
            text("SELECT id, item_code, item_name, color, icon FROM kms_setting_items WHERE id = :item_id"),
            {"item_id": int(item_id)},
        ).mappings().first()
        if not row:
            return None
        return KmsSettingItemSummary(
            id=int(row["id"]),
            item_code=str(row["item_code"]),
            item_name=str(row["item_name"]),
            color=row["color"],
            icon=row["icon"],
        )

    def _knowledge_extractions_for_item(self, item_id: int) -> list[KmsKnowledgeExtractionResponse]:
        rows = self.db.execute(
            text(
                """
                SELECT id, extraction_type, extraction_text, source, model_name, confidence_score, created_at, updated_at
                FROM kms_knowledge_extractions
                WHERE knowledge_item_id = :item_id
                ORDER BY created_at DESC, id DESC
                """
            ),
            {"item_id": item_id},
        ).mappings().all()
        return [
            KmsKnowledgeExtractionResponse(
                id=int(row["id"]),
                extraction_type=str(row["extraction_type"]),
                extraction_text=str(row["extraction_text"]),
                source=str(row["source"] or "USER"),
                model_name=row["model_name"],
                confidence_score=float(row["confidence_score"]) if row["confidence_score"] is not None else None,
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def _knowledge_tags_for_item(self, item_id: int) -> list[KmsKnowledgeItemTagResponse]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    kit.id,
                    kit.tag_id,
                    t.name AS tag_name,
                    t.tag_type_id,
                    type_item.item_name AS tag_type_name,
                    kit.weight,
                    kit.source,
                    kit.is_confirmed
                FROM kms_knowledge_item_tags kit
                JOIN kms_tags t ON t.id = kit.tag_id
                LEFT JOIN kms_setting_items type_item ON type_item.id = t.tag_type_id
                WHERE kit.knowledge_item_id = :item_id
                  AND COALESCE(t.is_active, 1) = 1
                ORDER BY kit.is_confirmed DESC, t.name
                """
            ),
            {"item_id": item_id},
        ).mappings().all()
        return [
            KmsKnowledgeItemTagResponse(
                id=int(row["id"]),
                tag_id=int(row["tag_id"]),
                tag_name=str(row["tag_name"]),
                tag_type_id=int(row["tag_type_id"]) if row["tag_type_id"] is not None else None,
                tag_type_name=str(row["tag_type_name"]) if row["tag_type_name"] is not None else None,
                weight=float(row["weight"] or 1),
                source=str(row["source"] or "USER"),
                is_confirmed=bool(row["is_confirmed"]),
            )
            for row in rows
        ]

    def _get_setting_group_by_code(self, group_code: str) -> Any:
        row = self.db.execute(
            text("SELECT * FROM kms_setting_groups WHERE group_code = :group_code"),
            {"group_code": group_code.strip().upper()},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="setting group not found")
        return row

    def _clear_setting_group_default(self, group_id: int) -> None:
        self.db.execute(text("UPDATE kms_setting_items SET is_default = 0 WHERE group_id = :group_id"), {"group_id": group_id})

    def _kms_setting_default_ids(self) -> dict[str, int | None]:
        defaults: dict[str, int | None] = {}
        for group_code, fallback_code in KMS_DEFAULT_ITEM_CODES.items():
            row = self.db.execute(
                text(
                    """
                    SELECT i.id
                    FROM kms_setting_items i
                    JOIN kms_setting_groups g ON g.id = i.group_id
                    WHERE g.group_code = :group_code
                      AND i.is_active = 1
                    ORDER BY i.is_default DESC, CASE WHEN i.item_code = :fallback_code THEN 0 ELSE 1 END, i.sort_order, i.id
                    LIMIT 1
                    """
                ),
                {"group_code": group_code, "fallback_code": fallback_code},
            ).first()
            defaults[group_code] = int(row[0]) if row else None
        return defaults

    def _setting_item_id_by_name_or_code(self, group_code: str, value: str | None) -> int | None:
        if not value:
            return self._kms_setting_default_ids().get(group_code)
        row = self.db.execute(
            text(
                """
                SELECT i.id
                FROM kms_setting_items i
                JOIN kms_setting_groups g ON g.id = i.group_id
                WHERE g.group_code = :group_code
                  AND (i.item_name = :value OR i.item_code = :code_value)
                ORDER BY i.is_active DESC, i.sort_order
                LIMIT 1
                """
            ),
            {"group_code": group_code, "value": value, "code_value": value.strip().upper()},
        ).first()
        return int(row[0]) if row else self._kms_setting_default_ids().get(group_code)

    def sync_legacy_posts_to_knowledge_items(self) -> None:
        defaults = self._kms_setting_default_ids()
        rows = self.db.execute(
            text(
                """
                SELECT p.*, c.name AS category_name
                FROM kms_posts p
                LEFT JOIN kms_categories c ON c.id = p.category_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM kms_knowledge_items k WHERE k.legacy_post_id = p.id
                       OR (k.legacy_source_type = 'kms_posts' AND k.legacy_source_id = p.id)
                )
                """
            )
        ).mappings().all()
        if not rows:
            return
        now = now_kst()
        for row in rows:
            raw_content = str(row["content"] or "")
            result = self.db.execute(
                text(
                    """
                    INSERT INTO kms_knowledge_items
                    (legacy_post_id, legacy_source_type, legacy_source_id, title, content, content_format,
                     one_line_conclusion, summary, para_type_id, category_id, status_id,
                     importance_id, usage_context_id, source_type_id, source_url, source_title, ai_extract_status,
                     embedding_status, is_active, created_at, updated_at)
                    VALUES
                    (:legacy_post_id, 'kms_posts', :legacy_post_id, :title, :content, 'HTML',
                     :one_line_conclusion, :summary, :para_type_id, :category_id, :status_id,
                     :importance_id, :usage_context_id, :source_type_id, :source_url, :source_title, 'PENDING',
                     'PENDING', :is_active, :created_at, :updated_at)
                    """
                ),
                {
                    "legacy_post_id": int(row["id"]),
                    "title": row["title"],
                    "content": raw_content,
                    "one_line_conclusion": row["one_line_conclusion"] if "one_line_conclusion" in row else None,
                    "summary": row["summary"],
                    "para_type_id": row["para_type_id"] if "para_type_id" in row and row["para_type_id"] is not None else defaults["PARA_TYPE"],
                    "category_id": row["knowledge_category_id"] if "knowledge_category_id" in row and row["knowledge_category_id"] is not None else self._setting_item_id_by_name_or_code("KNOWLEDGE_CATEGORY", row["category_name"]),
                    "status_id": row["status_id"] if "status_id" in row and row["status_id"] is not None else self._setting_item_id_by_name_or_code("KNOWLEDGE_STATUS", row["learning_status"]),
                    "importance_id": row["importance_id"] if "importance_id" in row and row["importance_id"] is not None else self._setting_item_id_by_name_or_code("IMPORTANCE_LEVEL", row["importance"]),
                    "usage_context_id": row["usage_context_id"] if "usage_context_id" in row and row["usage_context_id"] is not None else defaults["USAGE_CONTEXT"],
                    "source_type_id": row["source_type_id"] if "source_type_id" in row and row["source_type_id"] is not None else defaults["SOURCE_TYPE"],
                    "source_url": row["source_url"],
                    "source_title": row["source_title"] if "source_title" in row else None,
                    "is_active": int(row["is_active"] or 0),
                    "created_at": row["created_at"] or now,
                    "updated_at": row["updated_at"] or now,
                },
            )
            knowledge_item_id = int(result.lastrowid)
            for tag_name in self._tags_for_post(int(row["id"])):
                tag_id = self._ensure_kms_tag(tag_name)
                self.db.execute(
                    text(
                        """
                        INSERT OR IGNORE INTO kms_knowledge_item_tags
                        (knowledge_item_id, tag_id, weight, source, is_confirmed, created_at)
                        VALUES (:knowledge_item_id, :tag_id, 1.0, 'USER', 1, :now)
                        """
                    ),
                    {"knowledge_item_id": knowledge_item_id, "tag_id": tag_id, "now": now},
                )
        self.db.commit()

    def _ensure_kms_tag(self, tag_name: str, tag_type_id: int | None = None) -> int:
        name = tag_name.strip().lstrip("#")
        row = self.db.execute(text("SELECT id FROM kms_tags WHERE name = :name"), {"name": name}).first()
        if row:
            tag_id = int(row[0])
            if tag_type_id:
                self.db.execute(text("UPDATE kms_tags SET tag_type_id = COALESCE(tag_type_id, :tag_type_id) WHERE id = :tag_id"), {"tag_id": tag_id, "tag_type_id": tag_type_id})
            return tag_id
        defaults = self._kms_setting_default_ids()
        result = self.db.execute(
            text(
                """
                INSERT INTO kms_tags (name, description, use_count, is_active, tag_type_id, created_at, updated_at)
                VALUES (:name, NULL, 0, 1, :tag_type_id, :now, :now)
                """
            ),
            {"name": name, "tag_type_id": tag_type_id or defaults["TAG_TYPE"], "now": now_kst()},
        )
        return int(result.lastrowid)

    def _replace_knowledge_item_tags(self, item_id: int, tag_names: list[str]) -> None:
        self._sync_knowledge_item_confirmed_tags(item_id, tag_names)

    def _sync_knowledge_item_confirmed_tags(self, item_id: int, tag_names: list[str], tag_type_id: int | None = None) -> None:
        self.db.execute(
            text(
                """
                DELETE FROM kms_knowledge_item_tags
                WHERE knowledge_item_id = :item_id
                  AND is_confirmed = 1
                """
            ),
            {"item_id": item_id},
        )
        now = now_kst()
        for tag_name in tag_names:
            tag_id = self._ensure_kms_tag(tag_name, tag_type_id)
            self.db.execute(
                text(
                    """
                    INSERT INTO kms_knowledge_item_tags
                    (knowledge_item_id, tag_id, weight, source, is_confirmed, created_at)
                    VALUES (:item_id, :tag_id, 1.0, 'USER', 1, :now)
                    ON CONFLICT(knowledge_item_id, tag_id) DO UPDATE SET
                        weight = 1.0,
                        source = 'USER',
                        is_confirmed = 1
                    """
                ),
                {"item_id": item_id, "tag_id": tag_id, "now": now},
            )
        self.db.execute(
            text("UPDATE kms_knowledge_items SET updated_at = :now WHERE id = :item_id"),
            {"item_id": item_id, "now": now},
        )
        self._refresh_tag_counts()

    def _category_summaries(self) -> list[KmsCategorySummary]:
        categories = self.list_categories()
        summaries: list[KmsCategorySummary] = []
        for category in categories:
            rows = self.db.execute(
                text(
                    """
                    SELECT p.id, p.importance, p.learning_status, p.updated_at, t.name AS tag_name
                    FROM kms_posts p
                    LEFT JOIN kms_post_tags pt ON pt.post_id = p.id
                    LEFT JOIN kms_tags t ON t.id = pt.tag_id AND t.is_active = 1
                    WHERE p.is_active = 1 AND p.category_id = :category_id
                    """
                ),
                {"category_id": category.id},
            ).mappings().all()
            post_ids = {int(row["id"]) for row in rows}
            tag_counts = Counter(str(row["tag_name"]) for row in rows if row["tag_name"])
            latest = max((str(row["updated_at"]) for row in rows if row["updated_at"]), default=None)
            summaries.append(
                KmsCategorySummary(
                    category_id=category.id,
                    category_name=category.name,
                    total_posts=len(post_ids),
                    core_count=len({int(row["id"]) for row in rows if row["importance"] == "?듭떖"}),
                    review_needed_count=len({int(row["id"]) for row in rows if row["learning_status"] == "蹂듭뒿 ?꾩슂"}),
                    practice_candidate_count=len({int(row["id"]) for row in rows if row["learning_status"] == "?ㅼ쟾 ?곸슜 ?꾨낫"}),
                    recent_7d_count=len(
                        {
                            int(row["id"])
                            for row in rows
                            if row["updated_at"]
                            and self.db.execute(
                                text("SELECT CASE WHEN :updated_at >= datetime('now', '-7 days', 'localtime') THEN 1 ELSE 0 END"),
                                {"updated_at": row["updated_at"]},
                            ).scalar()
                        }
                    ),
                    top_tags=[name for name, _ in tag_counts.most_common(5)],
                    last_updated_at=latest,
                )
            )
        return summaries

    def _recent_posts(self, learning_status: str | None = None, limit: int = 6) -> list[KmsRecentPost]:
        params: dict[str, Any] = {"limit": limit}
        status_filter = ""
        if learning_status:
            status_filter = "AND p.learning_status = :learning_status"
            params["learning_status"] = learning_status
        rows = self.db.execute(
            text(
                f"""
                SELECT p.id, p.title, c.name AS category_name, p.learning_status, p.importance, p.updated_at
                FROM kms_posts p
                LEFT JOIN kms_categories c ON c.id = p.category_id
                WHERE p.is_active = 1 {status_filter}
                ORDER BY p.updated_at DESC, p.id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings()
        return [
            KmsRecentPost(
                post_id=int(row["id"]),
                title=row["title"],
                category_name=row["category_name"],
                learning_status=row["learning_status"],
                importance=row["importance"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
