from __future__ import annotations

from collections import Counter
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
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
    KmsLocalImageSelectResponse,
    KmsOverallSummary,
    KmsPostCreate,
    KmsPostSummary,
    KmsPostUpdate,
    KmsRecentPost,
    KmsTagResponse,
)

KMS_ALLOWED_LOCAL_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
DEFAULT_KMS_CATEGORIES = ["시장", "재료", "수급", "차트", "재무", "기법", "심리", "리스크", "복기", "자료"]


class KmsService:
    def __init__(self, db: Session) -> None:
        self.db = db

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
                        WHERE p.category_id = c.id AND p.is_active = 1
                    ) AS post_count,
                    (
                        SELECT COUNT(*)
                        FROM kms_posts p
                        WHERE p.category_id = c.id
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
                        WHERE p.category_id = c.id AND p.is_active = 1
                    ) AS post_count,
                    (
                        SELECT COUNT(*)
                        FROM kms_posts p
                        WHERE p.category_id = c.id
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
            raise HTTPException(status_code=409, detail="이 카테고리에 연결된 게시글이 있어 삭제할 수 없습니다. 비활성화를 사용해 주세요.")
        if child_count > 0:
            raise HTTPException(status_code=409, detail="하위 카테고리가 있어 삭제할 수 없습니다. 하위 카테고리를 먼저 정리해 주세요.")
        self.db.execute(text("DELETE FROM kms_categories WHERE id = :category_id"), {"category_id": category_id})
        self.db.commit()
        return {"success": True}

    def update_category_sort_orders(self, payload: KmsCategorySortOrderUpdate) -> KmsCategorySortOrderResponse:
        if not payload.items:
            raise HTTPException(status_code=400, detail="저장할 카테고리 순서가 없습니다.")
        ids = [item.id for item in payload.items]
        if len(set(ids)) != len(ids):
            raise HTTPException(status_code=400, detail="중복된 카테고리가 포함되어 있습니다.")
        orders = [item.sort_order for item in payload.items]
        if len(set(orders)) != len(orders):
            raise HTTPException(status_code=400, detail="표시 순서가 중복되었습니다.")
        rows = self.db.execute(
            text("SELECT id FROM kms_categories WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": tuple(ids)},
        ).mappings().all()
        found_ids = {int(row["id"]) for row in rows}
        missing_ids = [category_id for category_id in ids if category_id not in found_ids]
        if missing_ids:
            raise HTTPException(status_code=404, detail=f"존재하지 않는 카테고리가 포함되어 있습니다: {missing_ids[0]}")
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
            filters.append("p.category_id = :category_id")
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
        self.db.commit()
        return self.get_post(post_id)

    def deactivate_post(self, post_id: int) -> KmsPostSummary:
        self.get_post(post_id)
        self.db.execute(
            text("UPDATE kms_posts SET is_active = 0, updated_at = :now WHERE id = :post_id"),
            {"post_id": post_id, "now": now_kst()},
        )
        self.db.commit()
        return self.get_post(post_id)

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
                    SUM(CASE WHEN learning_status = '복습 필요' THEN 1 ELSE 0 END) AS review_needed_count,
                    SUM(CASE WHEN learning_status = '실전 적용 후보' THEN 1 ELSE 0 END) AS practice_candidate_count,
                    SUM(CASE WHEN importance = '핵심' THEN 1 ELSE 0 END) AS core_count,
                    SUM(CASE WHEN updated_at >= datetime('now', '-7 days', 'localtime') THEN 1 ELSE 0 END) AS recent_7d_count
                FROM kms_posts
                WHERE is_active = 1
                """
            )
        ).mappings().first()
        categories = self._category_summaries()
        popular_tags = self.list_tags(sort="popular", limit=12)
        recent_posts = self._recent_posts()
        review_needed_posts = self._recent_posts("복습 필요")
        practice_candidate_posts = self._recent_posts("실전 적용 후보")
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

    def _validate_post_payload(self, category_id: int, title: str, content: str, importance: str, learning_status: str) -> None:
        if not str(title or "").strip():
            raise HTTPException(status_code=400, detail="title is required")
        if not str(content or "").strip():
            raise HTTPException(status_code=400, detail="content is required")
        if importance not in IMPORTANCE_VALUES:
            raise HTTPException(status_code=400, detail="invalid importance")
        if learning_status not in LEARNING_STATUS_VALUES:
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
        raw_values = tags.split(",") if isinstance(tags, str) else tags
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in raw_values:
            name = str(raw).strip().lstrip("#").strip()
            if not name or name in seen:
                continue
            seen.add(name)
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
                    core_count=len({int(row["id"]) for row in rows if row["importance"] == "핵심"}),
                    review_needed_count=len({int(row["id"]) for row in rows if row["learning_status"] == "복습 필요"}),
                    practice_candidate_count=len({int(row["id"]) for row in rows if row["learning_status"] == "실전 적용 후보"}),
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
