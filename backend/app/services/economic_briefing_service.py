from __future__ import annotations

import json
import logging
import re
import time
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import (
    ECONOMIC_BRIEFING_CHUNK_MAX_CHARS,
    ECONOMIC_BRIEFING_CHUNK_OVERLAP_CHARS,
    ECONOMIC_BRIEFING_LLM_ENABLED,
    ECONOMIC_BRIEFING_LLM_PROVIDER,
    ECONOMIC_BRIEFING_SKIP_IF_SUMMARIZED,
    ECONOMIC_BRIEFING_SUMMARY_SKIP_IF_EXISTS,
    ECONOMIC_BRIEFING_LLM_TIMEOUT_SECONDS,
    YOUTUBE_PLAYLIST_REFRESH_DEFAULT_LIMIT,
    now_kst,
)
from backend.app.core.database import SessionLocal
from backend.app.schemas.economic_briefing_schema import (
    BriefingSummaryJobCreateResponse,
    BriefingSummaryJobItem,
    BriefingSummaryJobResponse,
    BriefingSummaryDetailResponse,
    BriefingTopicItem,
    BriefingVideoSummarizeResponse,
    BriefingTranscriptCheckResponse,
    BriefingTranscriptChunkPreview,
    BriefingSourceCreate,
    BriefingSourceItem,
    BriefingSourceListResponse,
    BriefingSourceMutationResponse,
    BriefingSourceUpdate,
    BriefingSummaryItem,
    BriefingSummaryListResponse,
    BriefingVideoItem,
    BriefingVideoListResponse,
    BriefingVideoManualCreate,
    BriefingVideoMutationResponse,
    BriefingVideoStatusUpdate,
)
from backend.app.services.economic_briefing_llm_service import EconomicBriefingLLMService
from backend.app.services.youtube_metadata_service import YouTubeMetadataError, YouTubeMetadataService, YouTubeVideoMetadata
from backend.app.services.youtube_transcript_service import (
    TranscriptFetchError,
    TranscriptProviderFailure,
    TranscriptUnavailableError,
    YouTubeTranscriptService,
)

logger = logging.getLogger(__name__)


class EconomicBriefingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sources(self, status_filter: str = "all", include_deleted: bool = False) -> BriefingSourceListResponse:
        if status_filter not in {"all", "active", "inactive"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status는 all/active/inactive 중 하나여야 합니다.")
        clauses = []
        # 30-D-2 보강: source 삭제 상태를 include_deleted 옵션으로 제어한다.
        clauses.append("1=1")
        if status_filter == "active":
            clauses.append("is_active=1")
        elif status_filter == "inactive":
            clauses.append("is_active=0")
        rows = self.db.execute(
            text(
                f"""
                SELECT id, source_type, source_name, source_url, channel_id, playlist_id,
                       is_default, is_active, last_checked_at, deleted_at, created_at, updated_at
                FROM briefing_sources
                WHERE {' AND '.join(clauses)}
                ORDER BY is_default DESC, is_active DESC, id DESC
                """
            )
        ).mappings().all()
        items = [BriefingSourceItem(**dict(r)) for r in rows]
        return BriefingSourceListResponse(success=True, count=len(items), items=items)

    def create_source(self, payload: BriefingSourceCreate) -> BriefingSourceMutationResponse:
        if payload.source_type not in {"channel", "playlist"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_type은 channel 또는 playlist여야 합니다.")
        now = now_kst()
        self.db.execute(
            text(
                """
                INSERT INTO briefing_sources
                (source_type, source_name, source_url, channel_id, playlist_id, is_default, is_active, deleted_at, created_at, updated_at)
                VALUES
                (:source_type, :source_name, :source_url, :channel_id, :playlist_id, :is_default, :is_active, NULL, :created_at, :updated_at)
                """
            ),
            {
                "source_type": payload.source_type,
                "source_name": payload.source_name.strip(),
                "source_url": payload.source_url.strip(),
                "channel_id": payload.channel_id.strip() if payload.channel_id else None,
                "playlist_id": payload.playlist_id.strip() if payload.playlist_id else self.extract_playlist_id(payload.source_url),
                "is_default": int(payload.is_default or 0),
                "is_active": int(payload.is_active if payload.is_active is not None else 1),
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        row = self.db.execute(
            text(
                """
                SELECT id, source_type, source_name, source_url, channel_id, playlist_id,
                       is_default, is_active, last_checked_at, deleted_at, created_at, updated_at
                FROM briefing_sources
                ORDER BY id DESC LIMIT 1
                """
            )
        ).mappings().first()
        return BriefingSourceMutationResponse(success=True, message="source가 등록되었습니다.", inserted_count=1, item=BriefingSourceItem(**dict(row)))

    def update_source(self, source_id: int, payload: BriefingSourceUpdate) -> BriefingSourceMutationResponse:
        existing = self.db.execute(text("SELECT * FROM briefing_sources WHERE id=:id"), {"id": source_id}).mappings().first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source를 찾을 수 없습니다.")
        updates = {"id": source_id, "updated_at": now_kst()}
        set_clauses = ["updated_at=:updated_at"]
        for key in ["source_name", "source_url", "channel_id", "playlist_id", "is_default", "is_active"]:
            value = getattr(payload, key)
            if value is None:
                continue
            updates[key] = value
            set_clauses.append(f"{key}=:{key}")
        self.db.execute(text(f"UPDATE briefing_sources SET {', '.join(set_clauses)} WHERE id=:id"), updates)
        self.db.commit()
        row = self.db.execute(
            text(
                """
                SELECT id, source_type, source_name, source_url, channel_id, playlist_id,
                       is_default, is_active, last_checked_at, deleted_at, created_at, updated_at
                FROM briefing_sources WHERE id=:id
                """
            ),
            {"id": source_id},
        ).mappings().first()
        return BriefingSourceMutationResponse(success=True, message="source가 수정되었습니다.", updated_count=1, item=BriefingSourceItem(**dict(row)))

    def deactivate_source(self, source_id: int) -> BriefingSourceMutationResponse:
        found = self.db.execute(text("SELECT id FROM briefing_sources WHERE id=:id"), {"id": source_id}).mappings().first()
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source를 찾을 수 없습니다.")
        self.db.execute(
            text("UPDATE briefing_sources SET is_active=0, updated_at=:updated_at WHERE id=:id"),
            {"id": source_id, "updated_at": now_kst()},
        )
        self.db.commit()
        row = self.db.execute(
            text(
                """
                SELECT id, source_type, source_name, source_url, channel_id, playlist_id,
                       is_default, is_active, last_checked_at, deleted_at, created_at, updated_at
                FROM briefing_sources WHERE id=:id
                """
            ),
            {"id": source_id},
        ).mappings().first()
        return BriefingSourceMutationResponse(success=True, message="source가 비활성화되었습니다.", updated_count=1, item=BriefingSourceItem(**dict(row)))

    def activate_source(self, source_id: int) -> BriefingSourceMutationResponse:
        found = self.db.execute(text("SELECT id FROM briefing_sources WHERE id=:id"), {"id": source_id}).mappings().first()
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source를 찾을 수 없습니다.")
        self.db.execute(
            text("UPDATE briefing_sources SET is_active=1, deleted_at=NULL, updated_at=:updated_at WHERE id=:id"),
            {"id": source_id, "updated_at": now_kst()},
        )
        self.db.commit()
        row = self.db.execute(
            text(
                """
                SELECT id, source_type, source_name, source_url, channel_id, playlist_id,
                       is_default, is_active, last_checked_at, deleted_at, created_at, updated_at
                FROM briefing_sources WHERE id=:id
                """
            ),
            {"id": source_id},
        ).mappings().first()
        return BriefingSourceMutationResponse(success=True, message="source가 다시 활성화되었습니다.", updated_count=1, item=BriefingSourceItem(**dict(row)))

    def soft_delete_source(self, source_id: int) -> BriefingSourceMutationResponse:
        found = self.db.execute(text("SELECT id FROM briefing_sources WHERE id=:id"), {"id": source_id}).mappings().first()
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source를 찾을 수 없습니다.")
        now = now_kst()
        # 30-D-2 보강: source 삭제 시 연결 영상은 유지하고 source_id만 NULL로 정리한다.
        self.db.execute(
            text("UPDATE briefing_videos SET source_id=NULL, updated_at=:updated_at WHERE source_id=:source_id"),
            {"source_id": source_id, "updated_at": now},
        )
        self.db.execute(
            text("DELETE FROM briefing_sources WHERE id=:id"),
            {"id": source_id},
        )
        self.db.commit()
        return BriefingSourceMutationResponse(
            success=True,
            message="source가 삭제되었습니다. 연결된 영상은 유지하고 source 연결만 해제했습니다.",
            updated_count=1,
            item=None,
        )

    def refresh_source_videos(self, source_id: int, max_results: int | None = None) -> BriefingSourceMutationResponse:
        row = self.db.execute(text("SELECT * FROM briefing_sources WHERE id=:id"), {"id": source_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source를 찾을 수 없습니다.")
        if row.get("deleted_at"):
            return BriefingSourceMutationResponse(success=False, message="비활성 source의 영상은 새로고침할 수 없습니다.")
        if int(row.get("is_active") or 0) != 1:
            return BriefingSourceMutationResponse(success=False, message="삭제된 source의 영상은 새로고침할 수 없습니다.")
        if str(row.get("source_type") or "") != "playlist":
            return BriefingSourceMutationResponse(success=False, message="playlist source만 영상 새로고침을 지원합니다.")
        if not row.get("playlist_id"):
            return BriefingSourceMutationResponse(success=False, message="playlist_id가 없어 영상 새로고침을 할 수 없습니다.")
        limit = int(max_results or YOUTUBE_PLAYLIST_REFRESH_DEFAULT_LIMIT)
        limit = max(1, min(limit, 100))
        service = YouTubeMetadataService()
        try:
            self.repair_orphan_briefing_video_source_ids()
            video_ids = service.fetch_playlist_video_ids(str(row.get("playlist_id")), max_results=limit)
            metadata_items = service.fetch_video_metadata(video_ids)
        except YouTubeMetadataError as exc:
            return BriefingSourceMutationResponse(success=False, message=str(exc))

        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        now = now_kst()
        source_id_value = int(row["id"])
        try:
            for item in metadata_items:
                result = self._upsert_briefing_video_from_metadata(source_id_value=source_id_value, item=item, now=now)
                if result == "inserted":
                    inserted_count += 1
                elif result == "updated":
                    updated_count += 1
                else:
                    skipped_count += 1
        except RuntimeError as exc:
            self.db.rollback()
            return BriefingSourceMutationResponse(success=False, message=str(exc))
        except IntegrityError:
            self.db.rollback()
            return BriefingSourceMutationResponse(
                success=False,
                message="영상 메타데이터를 가져왔지만 source 연결 처리 중 오류가 발생했습니다. source 상태를 확인해 주세요.",
            )

        self.db.execute(
            text("UPDATE briefing_sources SET last_checked_at=:last_checked_at, updated_at=:updated_at WHERE id=:id"),
            {"id": source_id_value, "last_checked_at": now, "updated_at": now},
        )
        self.db.commit()
        return BriefingSourceMutationResponse(
            success=True,
            source_id=source_id_value,
            source_name=str(row.get("source_name") or ""),
            playlist_id=str(row.get("playlist_id") or ""),
            fetched_count=len(video_ids),
            inserted_count=inserted_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            message="영상 목록을 새로고침했습니다.",
        )

    def list_videos(
        self,
        source_id: int | None = None,
        manual_only: bool = False,
        analysis_status: str | None = None,
        transcript_status: str | None = None,
        limit: int = 200,
    ) -> BriefingVideoListResponse:
        self.repair_empty_summarized_videos()
        clauses = ["1=1"]
        params: dict[str, object] = {"limit": limit}
        if manual_only:
            clauses.append("source_id IS NULL")
        if source_id is not None:
            clauses.append("source_id=:source_id")
            params["source_id"] = source_id
        if analysis_status:
            clauses.append("analysis_status=:analysis_status")
            params["analysis_status"] = analysis_status
        if transcript_status:
            clauses.append("transcript_status=:transcript_status")
            params["transcript_status"] = transcript_status
        rows = self.db.execute(
            text(
                f"""
                SELECT id, source_id, video_id, video_url, title, channel_name, published_at, duration_seconds,
                       thumbnail_url, description_summary, transcript_status, transcript_language, transcript_source,
                       transcript_checked_at, transcript_text_length, transcript_chunk_count,
                       llm_response_length, llm_timeout_seconds,
                       analysis_status,
                       (
                           SELECT bs.id
                           FROM briefing_summaries bs
                           WHERE bs.video_id = briefing_videos.id
                             AND bs.summary_type = 'full'
                           ORDER BY bs.id DESC
                           LIMIT 1
                       ) AS summary_id,
                       EXISTS(
                           SELECT 1
                           FROM briefing_summaries bs
                           WHERE bs.video_id = briefing_videos.id
                             AND bs.summary_type = 'full'
                       ) AS summary_exists,
                       EXISTS(
                           SELECT 1
                           FROM (
                               SELECT 1
                               FROM briefing_summaries bs
                               WHERE bs.video_id = briefing_videos.id
                                 AND bs.summary_type = 'full'
                                 AND (
                                     IFNULL(TRIM(bs.summary_text), '') <> ''
                                     OR IFNULL(TRIM(bs.key_points_json), '') NOT IN ('', '[]', '{{}}', 'null')
                                     OR IFNULL(TRIM(bs.topic_json), '') NOT IN ('', '[]', '{{}}', 'null')
                                     OR IFNULL(TRIM(bs.theme_mentions_json), '') NOT IN ('', '[]', '{{}}', 'null')
                                     OR IFNULL(TRIM(bs.stock_mentions_json), '') NOT IN ('', '[]', '{{}}', 'null')
                                     OR IFNULL(TRIM(bs.risk_points_json), '') NOT IN ('', '[]', '{{}}', 'null')
                                 )
                               UNION ALL
                               SELECT 1
                               FROM briefing_topic_items bti
                               WHERE bti.video_id = briefing_videos.id
                               LIMIT 1
                           )
                       ) AS summary_has_content,
                       (
                           SELECT COUNT(1)
                           FROM briefing_topic_items bti
                           WHERE bti.video_id = briefing_videos.id
                       ) AS topic_count,
                       last_analyzed_at, error_message, created_at, updated_at
                FROM briefing_videos
                WHERE {' AND '.join(clauses)}
                ORDER BY COALESCE(published_at, '') DESC, id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        items = [BriefingVideoItem(**dict(r)) for r in rows]
        return BriefingVideoListResponse(success=True, count=len(items), items=items)

    def create_manual_video(self, payload: BriefingVideoManualCreate) -> BriefingVideoMutationResponse:
        video_id = self.extract_video_id(payload.video_url)
        if not video_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효한 YouTube 영상 URL을 입력해 주세요.")
        if payload.source_id is not None and not self._source_exists(payload.source_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="선택한 source가 유효하지 않습니다.")
        existing = self.db.execute(
            text(
                """
                SELECT id, source_id, video_id, video_url, title, channel_name, published_at, duration_seconds,
                       thumbnail_url, description_summary, transcript_status, transcript_language, transcript_source,
                       transcript_checked_at, transcript_text_length, transcript_chunk_count,
                       llm_response_length, llm_timeout_seconds,
                       analysis_status, last_analyzed_at, error_message, created_at, updated_at
                FROM briefing_videos
                WHERE video_id=:video_id
                LIMIT 1
                """
            ),
            {"video_id": video_id},
        ).mappings().first()
        if existing:
            update_count = 0
            if payload.source_id is not None and existing.get("source_id") != payload.source_id:
                now = now_kst()
                self.db.execute(
                    text(
                        """
                        UPDATE briefing_videos
                        SET source_id=:source_id, updated_at=:updated_at
                        WHERE id=:id
                        """
                    ),
                    {
                        "source_id": payload.source_id,
                        "updated_at": now,
                        "id": existing["id"],
                    },
                )
                self.db.commit()
                update_count = 1
                existing = self.db.execute(
                    text(
                        """
                        SELECT id, source_id, video_id, video_url, title, channel_name, published_at, duration_seconds,
                               thumbnail_url, description_summary, transcript_status, transcript_language, transcript_source,
                               transcript_checked_at, transcript_text_length, transcript_chunk_count,
                               llm_response_length, llm_timeout_seconds,
                               analysis_status, last_analyzed_at, error_message, created_at, updated_at
                        FROM briefing_videos
                        WHERE id=:id
                        LIMIT 1
                        """
                    ),
                    {"id": existing["id"]},
                ).mappings().first()
            return BriefingVideoMutationResponse(
                success=True,
                message="이미 등록된 영상입니다." if update_count == 0 else "이미 등록된 영상입니다. 선택한 source 연결만 갱신했습니다.",
                updated_count=update_count,
                skipped_count=1,
                item=BriefingVideoItem(**dict(existing)),
            )
        now = now_kst()
        clean_url = f"https://www.youtube.com/watch?v={video_id}"
        self.db.execute(
            text(
                """
                INSERT INTO briefing_videos
                (source_id, video_id, video_url, title, transcript_status, transcript_source, analysis_status, created_at, updated_at)
                VALUES
                (:source_id, :video_id, :video_url, :title, 'unknown', 'none', 'pending', :created_at, :updated_at)
                """
            ),
            {
                "source_id": payload.source_id,
                "video_id": video_id,
                "video_url": clean_url,
                "title": f"수동 등록 영상 ({video_id})",
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        row = self.db.execute(
            text(
                """
                SELECT id, source_id, video_id, video_url, title, channel_name, published_at, duration_seconds,
                       thumbnail_url, description_summary, transcript_status, transcript_language, transcript_source,
                       transcript_checked_at, transcript_text_length, transcript_chunk_count,
                       llm_response_length, llm_timeout_seconds,
                       analysis_status, last_analyzed_at, error_message, created_at, updated_at
                FROM briefing_videos
                WHERE video_id=:video_id
                LIMIT 1
                """
            ),
            {"video_id": video_id},
        ).mappings().first()
        return BriefingVideoMutationResponse(success=True, message="단일 영상 URL이 등록되었습니다.", inserted_count=1, item=BriefingVideoItem(**dict(row)))

    def mark_video_status(self, briefing_video_id: int, payload: BriefingVideoStatusUpdate) -> BriefingVideoMutationResponse:
        existing = self.db.execute(text("SELECT id FROM briefing_videos WHERE id=:id"), {"id": briefing_video_id}).mappings().first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상을 찾을 수 없습니다.")
        updates = {"id": briefing_video_id, "updated_at": now_kst()}
        set_clauses = ["updated_at=:updated_at"]
        for key in ["transcript_status", "transcript_language", "transcript_source", "analysis_status", "error_message"]:
            value = getattr(payload, key)
            if value is None:
                continue
            updates[key] = value
            set_clauses.append(f"{key}=:{key}")
        if payload.analysis_status == "summarized":
            updates["last_analyzed_at"] = now_kst()
            set_clauses.append("last_analyzed_at=:last_analyzed_at")
        self.db.execute(text(f"UPDATE briefing_videos SET {', '.join(set_clauses)} WHERE id=:id"), updates)
        self.db.commit()
        row = self.db.execute(
            text(
                """
                SELECT id, source_id, video_id, video_url, title, channel_name, published_at, duration_seconds,
                       thumbnail_url, description_summary, transcript_status, transcript_language, transcript_source,
                       transcript_checked_at, transcript_text_length, transcript_chunk_count,
                       llm_response_length, llm_timeout_seconds,
                       analysis_status, last_analyzed_at, error_message, created_at, updated_at
                FROM briefing_videos
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": briefing_video_id},
        ).mappings().first()
        return BriefingVideoMutationResponse(success=True, message="영상 상태가 수정되었습니다.", updated_count=1, item=BriefingVideoItem(**dict(row)))

    def refresh_video_metadata(self, video_id: str) -> BriefingVideoMutationResponse:
        row = self.db.execute(
            text("SELECT * FROM briefing_videos WHERE video_id=:video_id LIMIT 1"),
            {"video_id": video_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상을 찾을 수 없습니다.")
        service = YouTubeMetadataService()
        try:
            items = service.fetch_video_metadata([video_id])
        except YouTubeMetadataError as exc:
            return BriefingVideoMutationResponse(success=False, message=str(exc))
        if not items:
            return BriefingVideoMutationResponse(success=False, message="YouTube에서 영상 메타데이터를 찾을 수 없습니다.")
        now = now_kst()
        try:
            result = self._upsert_briefing_video_from_metadata(
                source_id_value=row.get("source_id"),
                item=items[0],
                now=now,
            )
        except RuntimeError as exc:
            self.db.rollback()
            return BriefingVideoMutationResponse(success=False, message=str(exc))
        except IntegrityError:
            self.db.rollback()
            return BriefingVideoMutationResponse(
                success=False,
                message="영상 메타데이터를 가져왔지만 source 연결 처리 중 오류가 발생했습니다. source 상태를 확인해 주세요.",
            )
        self.db.commit()
        refreshed = self.db.execute(
            text(
                """
                SELECT id, source_id, video_id, video_url, title, channel_name, published_at, duration_seconds,
                       thumbnail_url, description_summary, transcript_status, transcript_language, transcript_source,
                       transcript_checked_at, transcript_text_length, transcript_chunk_count,
                       llm_response_length, llm_timeout_seconds,
                       analysis_status, last_analyzed_at, error_message, created_at, updated_at
                FROM briefing_videos
                WHERE video_id=:video_id
                LIMIT 1
                """
            ),
            {"video_id": video_id},
        ).mappings().first()
        return BriefingVideoMutationResponse(
            success=True,
            message="영상 메타데이터를 갱신했습니다.",
            inserted_count=1 if result == "inserted" else 0,
            updated_count=1 if result == "updated" else 0,
            skipped_count=1 if result == "skipped" else 0,
            item=BriefingVideoItem(**dict(refreshed)) if refreshed else None,
        )

    def list_video_summaries(self, briefing_video_id: int) -> BriefingSummaryListResponse:
        rows = self.db.execute(
            text(
                """
                SELECT id, video_id, summary_type, model_name, summary_text, key_points_json, topic_json,
                       stock_mentions_json, theme_mentions_json, risk_points_json, quality_meta_json, elapsed_seconds, chunk_count, created_at, updated_at
                FROM briefing_summaries
                WHERE video_id=:video_id
                ORDER BY id DESC
                """
            ),
            {"video_id": briefing_video_id},
        ).mappings().all()
        items = [BriefingSummaryItem(**dict(r)) for r in rows]
        return BriefingSummaryListResponse(success=True, count=len(items), items=items)

    def summarize_video(self, video_id: str, force: bool = False) -> BriefingVideoSummarizeResponse:
        row = self.db.execute(
            text("SELECT * FROM briefing_videos WHERE video_id=:video_id LIMIT 1"),
            {"video_id": video_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상을 찾을 수 없습니다.")
        if (ECONOMIC_BRIEFING_SKIP_IF_SUMMARIZED or ECONOMIC_BRIEFING_SUMMARY_SKIP_IF_EXISTS) and not force:
            existing_summary = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM briefing_summaries
                    WHERE video_id=:video_pk AND summary_type='full'
                      AND (
                        IFNULL(TRIM(summary_text), '') <> ''
                        OR IFNULL(TRIM(key_points_json), '') NOT IN ('', '[]', '{}', 'null')
                        OR IFNULL(TRIM(topic_json), '') NOT IN ('', '[]', '{}', 'null')
                        OR IFNULL(TRIM(theme_mentions_json), '') NOT IN ('', '[]', '{}', 'null')
                        OR IFNULL(TRIM(stock_mentions_json), '') NOT IN ('', '[]', '{}', 'null')
                        OR IFNULL(TRIM(risk_points_json), '') NOT IN ('', '[]', '{}', 'null')
                      )
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"video_pk": int(row["id"])},
            ).mappings().first()
            if existing_summary:
                return BriefingVideoSummarizeResponse(
                    success=True,
                    video_id=video_id,
                    analysis_status=str(row.get("analysis_status") or "summarized"),
                    summary_id=int(existing_summary["id"]),
                    topic_count=0,
                    theme_mentions=[],
                    stock_mentions=[],
                    message="이미 요약된 영상입니다. 다시 요약하려면 force=true로 요청해 주세요.",
                    error=None,
                )
        total_started = time.perf_counter()
        if not ECONOMIC_BRIEFING_LLM_ENABLED or ECONOMIC_BRIEFING_LLM_PROVIDER != "local_lmstudio":
            return BriefingVideoSummarizeResponse(
                success=False,
                video_id=video_id,
                analysis_status="failed",
                message="LLM 요약 기능이 비활성화되어 있습니다.",
                error="llm_disabled",
            )

        now = now_kst()
        llm_timeout_seconds = int(ECONOMIC_BRIEFING_LLM_TIMEOUT_SECONDS)
        llm_response_length = 0
        transcript_service = YouTubeTranscriptService()
        logger.info(
            "[EconomicBriefing] summarize_start video_id=%s transcript_status=%s analysis_status=%s checked_at=%s",
            video_id,
            row.get("transcript_status"),
            row.get("analysis_status"),
            row.get("transcript_checked_at"),
        )
        try:
            t0 = time.perf_counter()
            text_all, language, source = transcript_service.fetch_transcript_text(video_id, caller="summarize")
            print(f"[ECON_BRIEFING_TIMING] video_id={video_id} step=transcript_fetch elapsed={time.perf_counter()-t0:.1f}s")
            t1 = time.perf_counter()
            chunks = transcript_service.split_text_into_chunks_for_llm(
                text_all,
                max_chars=ECONOMIC_BRIEFING_CHUNK_MAX_CHARS,
                overlap_chars=ECONOMIC_BRIEFING_CHUNK_OVERLAP_CHARS,
            )
            print(f"[ECON_BRIEFING_TIMING] video_id={video_id} step=chunk_split elapsed={time.perf_counter()-t1:.1f}s chunk_count={len(chunks)}")
            if not str(text_all or "").strip():
                self._mark_analysis_failed(int(row["id"]), "transcript empty", now, llm_response_length=0, llm_timeout_seconds=llm_timeout_seconds)
                return BriefingVideoSummarizeResponse(
                    success=False,
                    video_id=video_id,
                    analysis_status="failed",
                    summary_id=None,
                    topic_count=0,
                    theme_mentions=[],
                    stock_mentions=[],
                    message="요약 생성에 실패했습니다.",
                    error="empty_transcript",
                )
            if len(chunks) == 0:
                self._mark_analysis_failed(int(row["id"]), "transcript chunk split empty", now, llm_response_length=0, llm_timeout_seconds=llm_timeout_seconds)
                return BriefingVideoSummarizeResponse(
                    success=False,
                    video_id=video_id,
                    analysis_status="failed",
                    summary_id=None,
                    topic_count=0,
                    theme_mentions=[],
                    stock_mentions=[],
                    message="요약 생성에 실패했습니다.",
                    error="empty_chunks",
                )
        except TranscriptUnavailableError as exc:
            logger.warning("[EconomicBriefing] summarize_transcript_unavailable video_id=%s error=%s", video_id, str(exc)[:200])
            self._mark_analysis_failed(int(row["id"]), str(exc)[:300], now, llm_response_length=0, llm_timeout_seconds=llm_timeout_seconds)
            return BriefingVideoSummarizeResponse(
                success=False,
                video_id=video_id,
                analysis_status="failed",
                summary_id=None,
                topic_count=0,
                theme_mentions=[],
                stock_mentions=[],
                message="요약 생성에 실패했습니다.",
                error=str(exc)[:300],
            )
        except TranscriptProviderFailure as exc:
            error_text = f"transcript_source_failed:{exc.normalized_error_type}"[:300]
            self._mark_analysis_failed(int(row["id"]), error_text, now, llm_response_length=0, llm_timeout_seconds=llm_timeout_seconds)
            return BriefingVideoSummarizeResponse(
                success=False,
                video_id=video_id,
                analysis_status="failed",
                summary_id=None,
                topic_count=0,
                theme_mentions=[],
                stock_mentions=[],
                message="요약 생성에 실패했습니다.",
                error=error_text,
            )
        except Exception as exc:
            reason = exc.__class__.__name__
            detail = str(exc).strip().replace("\n", " ")
            logger.warning("[EconomicBriefing] summarize_transcript_failed video_id=%s error_type=%s detail=%s", video_id, reason, detail[:200])
            error_text = f"transcript fetch failed: {reason}: {detail}"[:300] if detail else f"transcript fetch failed: {reason}"[:300]
            self._mark_analysis_failed(int(row["id"]), error_text, now, llm_response_length=0, llm_timeout_seconds=llm_timeout_seconds)
            return BriefingVideoSummarizeResponse(
                success=False,
                video_id=video_id,
                analysis_status="failed",
                summary_id=None,
                topic_count=0,
                theme_mentions=[],
                stock_mentions=[],
                message="요약 생성에 실패했습니다.",
                error=error_text,
            )

        llm = EconomicBriefingLLMService()
        failed_chunk_indices: list[int] = []
        try:
            chunk_summaries: list[dict[str, object]] = []
            for c in chunks:
                try:
                    c_started = time.perf_counter()
                    chunk_result = llm.summarize_chunk(c.text, c.index, len(chunks))
                    llm_response_length += int(chunk_result.get("_raw_response_length") or 0)
                    chunk_summaries.append(chunk_result)
                    print(f"[ECON_BRIEFING_TIMING] video_id={video_id} step=chunk_summary chunk={c.index}/{len(chunks)} elapsed={time.perf_counter()-c_started:.1f}s")
                except Exception:
                    failed_chunk_indices.append(c.index)
                    chunk_summaries.append(
                        {
                            "summary": "일부 구간의 LLM 요약 생성에 실패했습니다.",
                            "themes": [],
                            "stocks": [],
                            "risks": ["LLM 구간 요약 실패"],
                        }
                    )
            if failed_chunk_indices and len(failed_chunk_indices) >= len(chunks):
                self._mark_analysis_failed(int(row["id"]), "llm failed: all chunks failed", now, llm_response_length=llm_response_length, llm_timeout_seconds=llm_timeout_seconds)
                return BriefingVideoSummarizeResponse(
                    success=False,
                    video_id=video_id,
                    analysis_status="failed",
                    summary_id=None,
                    topic_count=0,
                    theme_mentions=[],
                    stock_mentions=[],
                    message="요약 생성에 실패했습니다.",
                    error="all_chunks_failed",
                )
            try:
                o_started = time.perf_counter()
                overall = llm.summarize_overall(chunk_summaries)
                llm_response_length += int(overall.get("_raw_response_length") or 0)
                print(f"[ECON_BRIEFING_TIMING] video_id={video_id} step=overall_summary elapsed={time.perf_counter()-o_started:.1f}s")
            except Exception:
                # 전체 요약 생성이 실패하면 chunk 요약 결과를 합쳐 fallback 요약으로 사용한다.
                overall = self._build_overall_fallback_from_chunks(chunk_summaries)
        except Exception as exc:
            err_txt = str(exc)[:200]
            user_msg = "요약 생성에 실패했습니다."
            if "empty content" in err_txt.lower():
                user_msg = "LM Studio 요약 요청에 실패했습니다. 서버 연결과 모델 상태를 확인해 주세요."
            self._mark_analysis_failed(int(row["id"]), f"llm failed: {err_txt}", now, llm_response_length=llm_response_length, llm_timeout_seconds=llm_timeout_seconds)
            return BriefingVideoSummarizeResponse(
                success=False,
                video_id=video_id,
                analysis_status="failed",
                summary_id=None,
                topic_count=0,
                theme_mentions=[],
                stock_mentions=[],
                message=user_msg,
                error="llm_failed",
            )

        summary_text = str(overall.get("overall_summary") or overall.get("summary_text") or overall.get("chunk_summary") or "")[:12000]
        key_points = self._to_str_list(overall.get("key_points"))
        topics = self._to_topic_list(overall.get("topics"))
        theme_mentions = self._to_str_list(overall.get("theme_mentions"))
        stock_mentions = self._to_str_list(overall.get("stock_mentions"))
        risk_points = self._to_str_list(overall.get("risk_points"))
        observation_points = self._to_str_list(overall.get("observation_points"))
        if observation_points:
            key_points.extend([f"관찰 포인트: {x}" for x in observation_points[:3]])
        summary_text = self._normalize_summary_text(summary_text)
        quality_status, quality_message, quality_meta = self._evaluate_summary_quality(
            summary_text=summary_text,
            key_points=key_points,
            topics=topics,
            theme_mentions=theme_mentions,
            stock_mentions=stock_mentions,
            risk_points=risk_points,
            retry_count=0,
        )
        if quality_status == "partial_failed":
            try:
                source_for_retry = "\n".join([str(c.get("summary") or "") for c in chunk_summaries if isinstance(c, dict)])
                structured_retry = llm.extract_structured_fields(source_text=source_for_retry, overall_summary=summary_text)
                llm_response_length += int(structured_retry.get("_raw_response_length") or 0)
                key_points = self._merge_str_lists(key_points, self._to_str_list(structured_retry.get("key_points")))
                topics = self._merge_topic_lists(topics, self._to_topic_list(structured_retry.get("topics")))
                theme_mentions = self._merge_str_lists(theme_mentions, self._to_str_list(structured_retry.get("theme_mentions")))
                stock_mentions = self._merge_str_lists(stock_mentions, self._to_str_list(structured_retry.get("stock_mentions")))
                risk_points = self._merge_str_lists(risk_points, self._to_str_list(structured_retry.get("risk_points")))
                quality_status, quality_message, quality_meta = self._evaluate_summary_quality(
                    summary_text=summary_text,
                    key_points=key_points,
                    topics=topics,
                    theme_mentions=theme_mentions,
                    stock_mentions=stock_mentions,
                    risk_points=risk_points,
                    retry_count=1,
                )
            except Exception as exc:
                quality_status = "partial_failed"
                quality_message = f"structured retry failed: {str(exc)[:120]}"
                quality_meta["retry_count"] = 1
        if quality_status == "failed":
            self._mark_analysis_failed(
                int(row["id"]),
                quality_message or "summary quality failed",
                now,
                llm_response_length=llm_response_length,
                llm_timeout_seconds=llm_timeout_seconds,
            )
            return BriefingVideoSummarizeResponse(
                success=False,
                video_id=video_id,
                analysis_status="failed",
                summary_id=None,
                topic_count=0,
                theme_mentions=[],
                stock_mentions=[],
                message="요약 생성에 실패했습니다.",
                error="summary_quality_failed",
            )

        if llm_response_length <= 0:
            self._mark_analysis_failed(int(row["id"]), "LLM response empty", now, llm_response_length=0, llm_timeout_seconds=llm_timeout_seconds)
            return BriefingVideoSummarizeResponse(
                success=False,
                video_id=video_id,
                analysis_status="failed",
                summary_id=None,
                topic_count=0,
                theme_mentions=[],
                stock_mentions=[],
                message="요약 생성에 실패했습니다.",
                error="empty_llm_response",
            )

        db_started = time.perf_counter()
        elapsed_seconds = int(max(1, round(time.perf_counter() - total_started)))
        summary_id = self._upsert_full_summary(
            video_pk=int(row["id"]),
            model_name="local_lmstudio",
            summary_text=summary_text,
            key_points=key_points,
            topics=topics,
            stock_mentions=stock_mentions,
            theme_mentions=theme_mentions,
            risk_points=risk_points,
            quality_meta=quality_meta,
            elapsed_seconds=elapsed_seconds,
            chunk_count=len(chunks),
            now=now,
        )
        topic_count = self._replace_topic_items(int(row["id"]), topics, now)
        analysis_status_value = "summarized" if quality_status == "ok" else "partial_failed"
        message_text = quality_message if quality_status != "ok" else (
            f"일부 구간 요약 실패: {','.join(str(i) for i in failed_chunk_indices)}" if failed_chunk_indices else None
        )
        self.db.execute(
            text(
                """
                UPDATE briefing_videos
                SET transcript_status='available',
                    transcript_language=:transcript_language,
                    transcript_source=:transcript_source,
                    transcript_checked_at=:transcript_checked_at,
                    transcript_text_length=:transcript_text_length,
                    transcript_chunk_count=:transcript_chunk_count,
                    llm_response_length=:llm_response_length,
                    llm_timeout_seconds=:llm_timeout_seconds,
                    analysis_status=:analysis_status,
                    last_analyzed_at=:last_analyzed_at,
                    error_message=:error_message,
                    updated_at=:updated_at
                WHERE id=:id
                """
            ),
            {
                "id": int(row["id"]),
                "transcript_language": language,
                "transcript_source": source,
                "transcript_checked_at": now,
                "transcript_text_length": len(text_all),
                "transcript_chunk_count": len(chunks),
                "llm_response_length": llm_response_length,
                "llm_timeout_seconds": llm_timeout_seconds,
                "analysis_status": analysis_status_value,
                "last_analyzed_at": now,
                "error_message": message_text,
                "updated_at": now,
            },
        )
        self.db.commit()
        print(f"[ECON_BRIEFING_TIMING] video_id={video_id} step=db_save elapsed={time.perf_counter()-db_started:.1f}s")
        print(f"[ECON_BRIEFING_TIMING] video_id={video_id} step=total elapsed={time.perf_counter()-total_started:.1f}s")
        return BriefingVideoSummarizeResponse(
            success=quality_status == "ok",
            video_id=video_id,
            analysis_status=analysis_status_value,
            summary_id=summary_id,
            topic_count=topic_count,
            theme_mentions=theme_mentions[:20],
            stock_mentions=stock_mentions[:20],
            message="요약이 정상적으로 완료되었습니다." if quality_status == "ok" else "구조화 요약 일부가 생성되지 않았습니다. 재요약을 권장합니다.",
            error=None if quality_status == "ok" else "structured_summary_partial_failed",
        )

    def get_summary_detail(self, video_id: str) -> BriefingSummaryDetailResponse:
        video = self.db.execute(
            text(
                """
                SELECT id, video_id, transcript_text_length, transcript_chunk_count, llm_response_length, llm_timeout_seconds, error_message
                FROM briefing_videos
                WHERE video_id=:video_id
                LIMIT 1
                """
            ),
            {"video_id": video_id},
        ).mappings().first()
        if not video:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상을 찾을 수 없습니다.")
        summary_row = self.db.execute(
            text(
                """
                SELECT id, video_id, summary_type, model_name, summary_text, key_points_json, topic_json,
                       stock_mentions_json, theme_mentions_json, risk_points_json, quality_meta_json, elapsed_seconds, chunk_count, created_at, updated_at
                FROM briefing_summaries
                WHERE video_id=:video_pk AND summary_type='full'
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"video_pk": int(video["id"])},
        ).mappings().first()
        topics_rows = self.db.execute(
            text(
                """
                SELECT id, video_id, topic_name, summary, importance_score, related_themes_json, related_stocks_json, created_at, updated_at
                FROM briefing_topic_items
                WHERE video_id=:video_pk
                ORDER BY id ASC
                """
            ),
            {"video_pk": int(video["id"])},
        ).mappings().all()
        parsed_summary = {
            "id": None,
            "summary_type": "full",
            "model_name": None,
            "summary_text": None,
            "key_points": [],
            "topics": [],
            "stock_mentions": [],
            "theme_mentions": [],
            "risk_points": [],
            "elapsed_seconds": None,
            "chunk_count": None,
            "source_text_length": video.get("transcript_text_length"),
            "source_chunk_count": video.get("transcript_chunk_count"),
            "llm_response_length": video.get("llm_response_length"),
            "llm_timeout_seconds": video.get("llm_timeout_seconds"),
            "error_message": video.get("error_message"),
            "structured_sections_count": 0,
            "key_points_count": 0,
            "topic_summaries_count": 0,
            "mentioned_themes_count": 0,
            "mentioned_stocks_count": 0,
            "risk_points_count": 0,
            "summary_quality_status": "failed",
            "summary_quality_message": "",
            "retry_count": 0,
            "created_at": None,
            "updated_at": None,
        }
        has_content = len(topics_rows) > 0
        if summary_row:
            summary_text = self._normalize_summary_text(str(summary_row["summary_text"] or ""))
            key_points = self._json_to_list(summary_row["key_points_json"])
            topics = self._json_to_list(summary_row["topic_json"])
            stock_mentions = self._json_to_list(summary_row["stock_mentions_json"])
            theme_mentions = self._json_to_list(summary_row["theme_mentions_json"])
            risk_points = self._json_to_list(summary_row["risk_points_json"])
            quality_meta = {}
            try:
                quality_meta = json.loads(str(summary_row.get("quality_meta_json") or "{}"))
                if not isinstance(quality_meta, dict):
                    quality_meta = {}
            except Exception:
                quality_meta = {}
            has_content = self._has_valid_summary_content(
                summary_text=summary_text,
                key_points=key_points if isinstance(key_points, list) else [],
                topics=topics if isinstance(topics, list) else [],
                theme_mentions=theme_mentions if isinstance(theme_mentions, list) else [],
                stock_mentions=stock_mentions if isinstance(stock_mentions, list) else [],
                risk_points=risk_points if isinstance(risk_points, list) else [],
            ) or len(topics_rows) > 0
            parsed_summary = {
                "id": int(summary_row["id"]),
                "summary_type": str(summary_row["summary_type"]),
                "model_name": summary_row["model_name"],
                "summary_text": summary_text,
                "key_points": key_points,
                "topics": topics,
                "stock_mentions": stock_mentions,
                "theme_mentions": theme_mentions,
                "risk_points": risk_points,
                "elapsed_seconds": summary_row.get("elapsed_seconds"),
                "chunk_count": summary_row.get("chunk_count"),
                "source_text_length": video.get("transcript_text_length"),
                "source_chunk_count": video.get("transcript_chunk_count"),
                "llm_response_length": video.get("llm_response_length"),
                "llm_timeout_seconds": video.get("llm_timeout_seconds"),
                "error_message": video.get("error_message"),
                "structured_sections_count": int(quality_meta.get("structured_sections_count") or 0),
                "key_points_count": int(quality_meta.get("key_points_count") or len(key_points)),
                "topic_summaries_count": int(quality_meta.get("topic_summaries_count") or len(topics)),
                "mentioned_themes_count": int(quality_meta.get("mentioned_themes_count") or len(theme_mentions)),
                "mentioned_stocks_count": int(quality_meta.get("mentioned_stocks_count") or len(stock_mentions)),
                "risk_points_count": int(quality_meta.get("risk_points_count") or len(risk_points)),
                "summary_quality_status": str(quality_meta.get("summary_quality_status") or "ok"),
                "summary_quality_message": str(quality_meta.get("summary_quality_message") or ""),
                "retry_count": int(quality_meta.get("retry_count") or 0),
                "created_at": summary_row["created_at"],
                "updated_at": summary_row["updated_at"],
            }
        return BriefingSummaryDetailResponse(
            success=True,
            video_id=video_id,
            has_content=has_content,
            summary=parsed_summary,
            topics=[BriefingTopicItem(**dict(r)) for r in topics_rows],
        )

    def _upsert_full_summary(
        self,
        video_pk: int,
        model_name: str,
        summary_text: str,
        key_points: list[str],
        topics: list[dict[str, str]],
        stock_mentions: list[str],
        theme_mentions: list[str],
        risk_points: list[str],
        quality_meta: dict[str, object],
        elapsed_seconds: int,
        chunk_count: int,
        now: str,
    ) -> int:
        existing = self.db.execute(
            text("SELECT id FROM briefing_summaries WHERE video_id=:video_id AND summary_type='full' LIMIT 1"),
            {"video_id": video_pk},
        ).mappings().first()
        payload = {
            "video_id": video_pk,
            "summary_type": "full",
            "model_name": model_name,
            "summary_text": summary_text,
            "key_points_json": json.dumps(key_points, ensure_ascii=False),
            "topic_json": json.dumps(topics, ensure_ascii=False),
            "stock_mentions_json": json.dumps(stock_mentions, ensure_ascii=False),
            "theme_mentions_json": json.dumps(theme_mentions, ensure_ascii=False),
            "risk_points_json": json.dumps(risk_points, ensure_ascii=False),
            "quality_meta_json": json.dumps(quality_meta, ensure_ascii=False),
            "elapsed_seconds": elapsed_seconds,
            "chunk_count": chunk_count,
            "updated_at": now,
        }
        if existing:
            payload["id"] = int(existing["id"])
            self.db.execute(
                text(
                    """
                    UPDATE briefing_summaries
                    SET model_name=:model_name,
                        summary_text=:summary_text,
                        key_points_json=:key_points_json,
                        topic_json=:topic_json,
                        stock_mentions_json=:stock_mentions_json,
                        theme_mentions_json=:theme_mentions_json,
                        risk_points_json=:risk_points_json,
                        quality_meta_json=:quality_meta_json,
                        elapsed_seconds=:elapsed_seconds,
                        chunk_count=:chunk_count,
                        updated_at=:updated_at
                    WHERE id=:id
                    """
                ),
                payload,
            )
            return int(existing["id"])
        payload["created_at"] = now
        self.db.execute(
            text(
                """
                INSERT INTO briefing_summaries
                (video_id, summary_type, model_name, summary_text, key_points_json, topic_json, stock_mentions_json, theme_mentions_json, risk_points_json, quality_meta_json, elapsed_seconds, chunk_count, created_at, updated_at)
                VALUES
                (:video_id, :summary_type, :model_name, :summary_text, :key_points_json, :topic_json, :stock_mentions_json, :theme_mentions_json, :risk_points_json, :quality_meta_json, :elapsed_seconds, :chunk_count, :created_at, :updated_at)
                """
            ),
            payload,
        )
        row = self.db.execute(text("SELECT id FROM briefing_summaries WHERE video_id=:video_id AND summary_type='full' ORDER BY id DESC LIMIT 1"), {"video_id": video_pk}).mappings().first()
        return int(row["id"])

    def _replace_topic_items(self, video_pk: int, topics: list[dict[str, str]], now: str) -> int:
        self.db.execute(text("DELETE FROM briefing_topic_items WHERE video_id=:video_id"), {"video_id": video_pk})
        count = 0
        for t in topics:
            name = (t.get("topic_name") or "").strip()
            if not name:
                continue
            self.db.execute(
                text(
                    """
                    INSERT INTO briefing_topic_items
                    (video_id, topic_name, summary, importance_score, related_themes_json, related_stocks_json, created_at, updated_at)
                    VALUES
                    (:video_id, :topic_name, :summary, :importance_score, :related_themes_json, :related_stocks_json, :created_at, :updated_at)
                    """
                ),
                {
                    "video_id": video_pk,
                    "topic_name": name[:100],
                    "summary": (t.get("summary") or "")[:1500],
                    "importance_score": None,
                    "related_themes_json": "[]",
                    "related_stocks_json": "[]",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            count += 1
        return count

    def _mark_analysis_failed(
        self,
        video_pk: int,
        error_message: str,
        now: str,
        llm_response_length: int | None = None,
        llm_timeout_seconds: int | None = None,
    ) -> None:
        self.db.execute(
            text(
                """
                UPDATE briefing_videos
                SET analysis_status='failed',
                    error_message=:error_message,
                    llm_response_length=:llm_response_length,
                    llm_timeout_seconds=:llm_timeout_seconds,
                    updated_at=:updated_at
                WHERE id=:id
                """
            ),
            {
                "id": video_pk,
                "error_message": error_message[:300],
                "llm_response_length": llm_response_length,
                "llm_timeout_seconds": llm_timeout_seconds,
                "updated_at": now,
            },
        )
        self.db.commit()

    @staticmethod
    def _to_str_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for x in value:
            s = str(x).strip()
            if s:
                out.append(s[:200])
        seen = set()
        dedup = []
        for x in out:
            if x in seen:
                continue
            seen.add(x)
            dedup.append(x)
        return dedup[:50]

    @staticmethod
    def _to_topic_list(value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        out: list[dict[str, str]] = []
        for x in value:
            if not isinstance(x, dict):
                continue
            topic_name = str(x.get("topic_name") or "").strip()
            summary = str(x.get("summary") or "").strip()
            if not topic_name:
                continue
            out.append({"topic_name": topic_name[:100], "summary": summary[:1500]})
        return out[:30]

    @staticmethod
    def _json_to_list(raw: object) -> list[object]:
        if raw is None:
            return []
        try:
            parsed = json.loads(str(raw))
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
        return []

    @staticmethod
    def _normalize_summary_text(summary_text: str) -> str:
        text = (summary_text or "").strip()
        if not text:
            return ""
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                overall = str(parsed.get("overall_summary") or parsed.get("summary_text") or parsed.get("chunk_summary") or "").strip()
                return overall or text
        except Exception:
            overall_matches = re.findall(r'"overall_summary"\s*:\s*"([^"]*)"', text)
            chunk_matches = re.findall(r'"chunk_summary"\s*:\s*"([^"]*)"', text)
            extracted = [x.strip() for x in (overall_matches or chunk_matches) if x.strip()]
            if extracted:
                return "\n\n".join(extracted[:8])
        return text

    @staticmethod
    def _has_valid_summary_content(
        summary_text: str,
        key_points: list[str] | list[object],
        topics: list[dict[str, str]] | list[object],
        theme_mentions: list[str] | list[object],
        stock_mentions: list[str] | list[object],
        risk_points: list[str] | list[object],
    ) -> bool:
        text = (summary_text or "").strip()
        invalid_markers = [
            "일부 구간의 LLM 요약 생성에 실패했습니다.",
            "일부 구간 요약만 생성되었습니다. 전체 요약을 다시 실행해 주세요.",
        ]
        looks_like_json = text.startswith("{") or text.startswith("[") or '"chunk_summary"' in text or '"overall_summary"' in text
        if text and text not in invalid_markers and not looks_like_json:
            return True
        if any(EconomicBriefingService._is_meaningful_summary_text(str(x)) for x in key_points):
            return True
        if any(
            isinstance(x, dict)
            and (
                EconomicBriefingService._is_meaningful_summary_text(str(x.get("topic_name") or ""))
                or EconomicBriefingService._is_meaningful_summary_text(str(x.get("summary") or ""))
            )
            for x in topics
        ):  # type: ignore[union-attr]
            return True
        if any(EconomicBriefingService._is_meaningful_summary_text(str(x)) for x in theme_mentions):
            return True
        if any(EconomicBriefingService._is_meaningful_summary_text(str(x)) for x in stock_mentions):
            return True
        if any(EconomicBriefingService._is_meaningful_summary_text(str(x)) for x in risk_points):
            return True
        return False

    def _evaluate_summary_quality(
        self,
        summary_text: str,
        key_points: list[str],
        topics: list[dict[str, str]],
        theme_mentions: list[str],
        stock_mentions: list[str],
        risk_points: list[str],
        retry_count: int,
    ) -> tuple[str, str, dict[str, object]]:
        overall_len = len((summary_text or "").strip())
        non_empty_structured = sum(
            [
                1 if key_points else 0,
                1 if topics else 0,
                1 if theme_mentions else 0,
                1 if stock_mentions else 0,
                1 if risk_points else 0,
            ]
        )
        status = "ok"
        message = ""
        if overall_len < 100:
            status = "failed"
            message = "전체 요약이 너무 짧습니다."
        elif non_empty_structured < 2:
            status = "partial_failed"
            message = "구조화 요약 필드가 부족합니다."
        meta = {
            "structured_sections_count": non_empty_structured,
            "key_points_count": len(key_points),
            "topic_summaries_count": len(topics),
            "mentioned_themes_count": len(theme_mentions),
            "mentioned_stocks_count": len(stock_mentions),
            "risk_points_count": len(risk_points),
            "summary_quality_status": status,
            "summary_quality_message": message,
            "retry_count": retry_count,
            "overall_summary_length": overall_len,
        }
        return status, message, meta

    @staticmethod
    def _merge_str_lists(base: list[str], extra: list[str], limit: int = 50) -> list[str]:
        merged = [x.strip() for x in base if x and x.strip()]
        for item in extra:
            s = item.strip()
            if s and s not in merged:
                merged.append(s)
            if len(merged) >= limit:
                break
        return merged

    @staticmethod
    def _merge_topic_lists(base: list[dict[str, str]], extra: list[dict[str, str]], limit: int = 30) -> list[dict[str, str]]:
        merged = [x for x in base if (x.get("topic_name") or "").strip() or (x.get("summary") or "").strip()]
        existing_keys = {(x.get("topic_name") or "", x.get("summary") or "") for x in merged}
        for item in extra:
            key = (item.get("topic_name") or "", item.get("summary") or "")
            if key in existing_keys:
                continue
            if not (key[0].strip() or key[1].strip()):
                continue
            merged.append(item)
            existing_keys.add(key)
            if len(merged) >= limit:
                break
        return merged

    @staticmethod
    def _is_meaningful_summary_text(text: str) -> bool:
        s = (text or "").strip()
        if not s:
            return False
        blocked_tokens = [
            "llm chunk",
            "요약 생성 실패",
            "empty content",
            "fallback",
        ]
        low = s.lower()
        return not any(token in low for token in blocked_tokens)

    def repair_empty_summarized_videos(self) -> int:
        now = now_kst()
        result = self.db.execute(
            text(
                """
                UPDATE briefing_videos
                SET analysis_status='failed',
                    error_message='요약 결과가 없어 완료 처리할 수 없습니다. 다시 요약을 실행해 주세요.',
                    updated_at=:updated_at
                WHERE analysis_status='summarized'
                  AND id IN (
                    SELECT v.id
                    FROM briefing_videos v
                    LEFT JOIN briefing_summaries s
                      ON s.video_id = v.id
                     AND s.summary_type='full'
                    WHERE v.analysis_status='summarized'
                      AND (
                        s.id IS NULL OR (
                          IFNULL(TRIM(s.summary_text), '') = ''
                          AND IFNULL(TRIM(s.key_points_json), '') IN ('', '[]', '{}', 'null')
                          AND IFNULL(TRIM(s.topic_json), '') IN ('', '[]', '{}', 'null')
                          AND IFNULL(TRIM(s.theme_mentions_json), '') IN ('', '[]', '{}', 'null')
                          AND IFNULL(TRIM(s.stock_mentions_json), '') IN ('', '[]', '{}', 'null')
                          AND IFNULL(TRIM(s.risk_points_json), '') IN ('', '[]', '{}', 'null')
                          AND (
                            SELECT COUNT(1) FROM briefing_topic_items bti WHERE bti.video_id = v.id
                          ) = 0
                        )
                      )
                  )
                """
            ),
            {"updated_at": now},
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def check_video_transcript(self, video_id: str) -> BriefingTranscriptCheckResponse:
        row = self.db.execute(
            text("SELECT id, video_id FROM briefing_videos WHERE video_id=:video_id LIMIT 1"),
            {"video_id": video_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="영상을 찾을 수 없습니다.")
        now = now_kst()
        service = None
        current_status_row = self.db.execute(
            text("SELECT transcript_status, analysis_status, transcript_checked_at FROM briefing_videos WHERE id=:id"),
            {"id": int(row["id"])},
        ).mappings().first()
        logger.info(
            "[EconomicBriefing] transcript_check_start video_id=%s caller=transcript_check transcript_status=%s analysis_status=%s checked_at=%s",
            video_id,
            (current_status_row or {}).get("transcript_status"),
            (current_status_row or {}).get("analysis_status"),
            (current_status_row or {}).get("transcript_checked_at"),
        )
        try:
            service = YouTubeTranscriptService()
            text_all, language, source = service.fetch_transcript_text(video_id=video_id, caller="transcript_check")
            chunks = service.split_text_into_chunks(text_all, max_chars=4000, overlap_chars=300)
            text_length = len(text_all)
            chunk_count = len(chunks)
            previews = [
                BriefingTranscriptChunkPreview(index=c.index, text_length=len(c.text), preview=c.text[:200])
                for c in chunks[:10]
            ]
            self.db.execute(
                text(
                    """
                    UPDATE briefing_videos
                    SET transcript_status='available',
                        transcript_language=:transcript_language,
                        transcript_source=:transcript_source,
                        transcript_checked_at=:transcript_checked_at,
                        transcript_text_length=:transcript_text_length,
                        transcript_chunk_count=:transcript_chunk_count,
                        error_message=NULL,
                        updated_at=:updated_at
                    WHERE id=:id
                    """
                ),
                {
                    "id": int(row["id"]),
                    "transcript_language": language,
                    "transcript_source": source,
                    "transcript_checked_at": now,
                    "transcript_text_length": text_length,
                    "transcript_chunk_count": chunk_count,
                    "updated_at": now,
                },
            )
            self.db.commit()
            logger.info(
                "[EconomicBriefing] transcript_check_success video_id=%s text_length=%s chunk_count=%s",
                video_id,
                text_length,
                chunk_count,
            )
            return BriefingTranscriptCheckResponse(
                success=True,
                video_id=video_id,
                transcript_status="available",
                transcript_language=language,
                transcript_source=source,
                text_length=text_length,
                chunk_count=chunk_count,
                chunk_previews=previews,
                message="자막 상태를 확인했습니다.",
                error=None,
                failure_reason=None,
                error_type=None,
                attempts=getattr(service, "last_attempts", []),
                selected_provider=source,
                provider_results={"selected": {"success": True, "provider": source}},
                normalized_error_type=None,
                is_retryable=None,
                retry_after_minutes=None,
            )
        except TranscriptUnavailableError as exc:
            logger.warning("[EconomicBriefing] transcript_check_unavailable video_id=%s error=%s", video_id, str(exc)[:200])
            self._save_transcript_failure(int(row["id"]), now, "unavailable", str(exc)[:300])
            return BriefingTranscriptCheckResponse(
                success=False,
                video_id=video_id,
                transcript_status="unavailable",
                transcript_language=None,
                transcript_source="transcript_api" if service is not None else None,
                text_length=0,
                chunk_count=0,
                chunk_previews=[],
                message="자막을 찾을 수 없습니다.",
                error=str(exc)[:300],
                failure_reason="fetch_and_legacy_failed",
                error_type=exc.__class__.__name__,
                attempts=getattr(service, "last_attempts", []),
                selected_provider="all_failed",
                provider_results={},
                normalized_error_type="transcript_unavailable",
                is_retryable=False,
                retry_after_minutes=None,
            )
        except TranscriptProviderFailure as exc:
            error_msg = str(exc)[:500]
            self._save_transcript_failure(int(row["id"]), now, "failed", error_msg)
            return BriefingTranscriptCheckResponse(
                success=False,
                video_id=video_id,
                transcript_status="failed",
                transcript_language=None,
                transcript_source="transcript_api" if service is not None else None,
                text_length=0,
                chunk_count=0,
                chunk_previews=[],
                message="자막 상태 확인에 실패했습니다.",
                error=error_msg,
                failure_reason="provider_fallback_failed",
                error_type=exc.normalized_error_type,
                attempts=getattr(service, "last_attempts", []),
                selected_provider=exc.selected_provider,
                provider_results=exc.provider_results,
                normalized_error_type=exc.normalized_error_type,
                is_retryable=exc.is_retryable,
                retry_after_minutes=exc.retry_after_minutes,
            )
        except TranscriptFetchError as exc:
            logger.warning("[EconomicBriefing] transcript_check_failed video_id=%s error=%s", video_id, str(exc)[:200])
            self._save_transcript_failure(int(row["id"]), now, "failed", str(exc)[:300])
            return BriefingTranscriptCheckResponse(
                success=False,
                video_id=video_id,
                transcript_status="failed",
                transcript_language=None,
                transcript_source="transcript_api" if service is not None else None,
                text_length=0,
                chunk_count=0,
                chunk_previews=[],
                message="자막 상태 확인에 실패했습니다.",
                error=str(exc)[:300],
                failure_reason="fetch_and_legacy_failed",
                error_type=exc.__class__.__name__,
                attempts=getattr(service, "last_attempts", []),
                selected_provider="all_failed",
                provider_results={},
                normalized_error_type="unknown",
                is_retryable=True,
                retry_after_minutes=60,
            )
        except Exception:
            err = "자막 조회 중 오류가 발생했습니다."
            logger.exception("[EconomicBriefing] transcript_check_exception video_id=%s", video_id)
            self._save_transcript_failure(int(row["id"]), now, "failed", err)
            return BriefingTranscriptCheckResponse(
                success=False,
                video_id=video_id,
                transcript_status="failed",
                transcript_language=None,
                transcript_source=None,
                text_length=0,
                chunk_count=0,
                chunk_previews=[],
                message="자막 상태 확인에 실패했습니다.",
                error=err,
                failure_reason="unexpected_error",
                error_type="Exception",
                attempts=getattr(service, "last_attempts", []),
                selected_provider="all_failed",
                provider_results={},
                normalized_error_type="unknown",
                is_retryable=True,
                retry_after_minutes=60,
            )

    def _save_transcript_failure(self, briefing_video_id: int, checked_at: str, status_value: str, error_message: str) -> None:
        self.db.execute(
            text(
                """
                UPDATE briefing_videos
                SET transcript_status=:transcript_status,
                    transcript_source='transcript_api',
                    transcript_checked_at=:transcript_checked_at,
                    transcript_text_length=NULL,
                    transcript_chunk_count=NULL,
                    error_message=:error_message,
                    updated_at=:updated_at
                WHERE id=:id
                """
            ),
            {
                "id": briefing_video_id,
                "transcript_status": status_value,
                "transcript_checked_at": checked_at,
                "error_message": error_message[:300],
                "updated_at": checked_at,
            },
        )
        self.db.commit()

    @staticmethod
    def extract_video_id(url: str) -> str | None:
        try:
            parsed = urlparse(url.strip())
        except Exception:
            return None
        host = (parsed.netloc or "").lower()
        path = parsed.path or ""
        if "youtu.be" in host:
            segment = path.strip("/").split("/")
            return segment[0] if segment and segment[0] else None
        if "youtube.com" in host or "m.youtube.com" in host:
            if path.startswith("/watch"):
                query = parse_qs(parsed.query)
                v = query.get("v", [None])[0]
                return v
            if path.startswith("/shorts/"):
                segment = path.split("/")
                return segment[2] if len(segment) > 2 else None
            if path.startswith("/embed/"):
                segment = path.split("/")
                return segment[2] if len(segment) > 2 else None
        return None

    @staticmethod
    def extract_playlist_id(url: str) -> str | None:
        try:
            parsed = urlparse(url.strip())
            query = parse_qs(parsed.query)
            return query.get("list", [None])[0]
        except Exception:
            return None

    def _upsert_briefing_video_from_metadata(
        self,
        source_id_value: int | None,
        item: YouTubeVideoMetadata,
        now: str,
    ) -> str:
        if source_id_value is not None and not self._source_exists(int(source_id_value)):
            raise RuntimeError("영상 새로고침 중 연결된 source가 유효하지 않습니다. source 목록을 먼저 확인해 주세요.")
        existing = self.db.execute(
            text("SELECT id, analysis_status, source_id FROM briefing_videos WHERE video_id=:video_id LIMIT 1"),
            {"video_id": item.video_id},
        ).mappings().first()
        if existing:
            resolved_source_id = self._resolve_video_source_id(
                current_source_id=existing.get("source_id"),
                refresh_source_id=source_id_value,
            )
            update_sql = """
                UPDATE briefing_videos
                SET source_id=:source_id,
                    video_url=:video_url,
                    title=:title,
                    channel_name=:channel_name,
                    published_at=:published_at,
                    duration_seconds=:duration_seconds,
                    thumbnail_url=NULL,
                    description_summary=:description_summary,
                    updated_at=:updated_at
                WHERE id=:id
            """
            self.db.execute(
                text(update_sql),
                {
                    "id": int(existing["id"]),
                    "source_id": resolved_source_id,
                    "video_url": f"https://www.youtube.com/watch?v={item.video_id}",
                    "title": item.title,
                    "channel_name": item.channel_name,
                    "published_at": item.published_at,
                    "duration_seconds": item.duration_seconds,
                    "description_summary": item.description_summary,
                    "updated_at": now,
                },
            )
            return "updated"
        self.db.execute(
            text(
                """
                INSERT INTO briefing_videos
                (source_id, video_id, video_url, title, channel_name, published_at, duration_seconds, thumbnail_url, description_summary,
                 transcript_status, transcript_source, analysis_status, created_at, updated_at)
                VALUES
                (:source_id, :video_id, :video_url, :title, :channel_name, :published_at, :duration_seconds, NULL, :description_summary,
                 'unknown', 'none', 'pending', :created_at, :updated_at)
                """
            ),
            {
                "source_id": source_id_value,
                "video_id": item.video_id,
                "video_url": f"https://www.youtube.com/watch?v={item.video_id}",
                "title": item.title,
                "channel_name": item.channel_name,
                "published_at": item.published_at,
                "duration_seconds": item.duration_seconds,
                "description_summary": item.description_summary,
                "created_at": now,
                "updated_at": now,
            },
        )
        return "inserted"

    def repair_orphan_briefing_video_source_ids(self) -> int:
        now = now_kst()
        result = self.db.execute(
            text(
                """
                UPDATE briefing_videos
                SET source_id = NULL,
                    updated_at = :updated_at
                WHERE source_id IS NOT NULL
                  AND source_id NOT IN (SELECT id FROM briefing_sources)
                """
            ),
            {"updated_at": now},
        )
        return int(result.rowcount or 0)

    def _build_overall_fallback_from_chunks(self, chunk_summaries: list[dict[str, object]]) -> dict[str, object]:
        summary_lines: list[str] = []
        key_points: list[str] = []
        topics: list[dict[str, str]] = []
        theme_mentions: list[str] = []
        stock_mentions: list[str] = []
        risk_points: list[str] = []
        for idx, chunk in enumerate(chunk_summaries, start=1):
            csum = str(chunk.get("summary") or chunk.get("chunk_summary") or "").strip()
            if csum:
                summary_lines.append(f"{idx}. {csum}")
            for x in chunk.get("themes", []) if isinstance(chunk.get("themes"), list) else []:
                sx = str(x).strip()
                if sx:
                    theme_mentions.append(sx)
            for x in chunk.get("stocks", []) if isinstance(chunk.get("stocks"), list) else []:
                sx = str(x).strip()
                if sx:
                    stock_mentions.append(sx)
            for x in chunk.get("risks", []) if isinstance(chunk.get("risks"), list) else []:
                sx = str(x).strip()
                if sx:
                    risk_points.append(sx)
        return {
            "overall_summary": "\n".join(summary_lines)[:8000] or "일부 구간 요약만 생성되었습니다. 전체 요약을 다시 실행해 주세요.",
            "key_points": key_points[:20],
            "topics": topics[:30],
            "theme_mentions": list(dict.fromkeys(theme_mentions))[:30],
            "stock_mentions": list(dict.fromkeys(stock_mentions))[:30],
            "risk_points": list(dict.fromkeys(risk_points))[:30],
            "observation_points": [],
        }

    def _source_exists(self, source_id: int) -> bool:
        row = self.db.execute(
            text("SELECT 1 FROM briefing_sources WHERE id=:id LIMIT 1"),
            {"id": source_id},
        ).first()
        return row is not None

    def _resolve_video_source_id(self, current_source_id: object, refresh_source_id: int | None) -> int | None:
        current_id = int(current_source_id) if isinstance(current_source_id, int) else None
        if current_id is None:
            return refresh_source_id
        if self._source_exists(current_id):
            return current_id
        return refresh_source_id


