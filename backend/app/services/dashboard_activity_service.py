from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.services.trade_training_service import TradeTrainingService


KST = ZoneInfo("Asia/Seoul")


class DashboardActivityService:
    """Build a transient compact feed from existing durable feature records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _kst_iso(value: Any, *, naive_is_utc: bool = False) -> str | None:
        if not value:
            return None
        raw = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc if naive_is_utc else KST)
        return parsed.astimezone(KST).isoformat(timespec="seconds")

    def recent(self, *, days: int = 30, limit: int = 5) -> dict[str, Any]:
        now = datetime.now(KST)
        cutoff = now - timedelta(days=max(1, days))
        items: list[dict[str, Any]] = []

        months = {now.strftime("%Y-%m"), cutoff.strftime("%Y-%m")}
        training_service = TradeTrainingService(self.db)
        for month in months:
            try:
                calendar = training_service.get_training_calendar(month)
            except Exception:  # A malformed legacy training must not block other dashboard activities.
                continue
            for day in calendar.get("days", []):
                for training in day.get("items", []):
                    event_at = self._kst_iso(training.get("completed_at"), naive_is_utc=True)
                    if not event_at or datetime.fromisoformat(event_at) < cutoff:
                        continue
                    training_type = "계좌관리 매매훈련" if training.get("training_type") == "ACCOUNT" else "종목매매훈련"
                    items.append({
                        "type": "TRAINING_COMPLETED",
                        "event_at": event_at,
                        "title": "매매훈련 완료",
                        "summary": f"{training.get('stock_name') or '종목 미상'} · {training_type}",
                        "route": "/trade-training-calendar",
                    })

        journal_rows = self.db.execute(text("""
            SELECT id,stock_name,created_at FROM trade_journals
             WHERE created_at IS NOT NULL ORDER BY created_at DESC,id DESC LIMIT 20
        """)).mappings().all()
        for row in journal_rows:
            event_at = self._kst_iso(row["created_at"])
            if event_at and datetime.fromisoformat(event_at) >= cutoff:
                items.append({"type": "TRADE_JOURNAL", "event_at": event_at, "title": "매매일지 작성",
                              "summary": str(row["stock_name"] or "종목 미상"), "route": "/trade-journals"})

        marker_rows = self.db.execute(text("""
            SELECT e.id,e.created_at,s.stock_name,m.name marker_name
              FROM chart_marker_events e JOIN stocks s ON s.id=e.stock_id
              JOIN chart_markers m ON m.id=e.marker_id
             WHERE e.created_at IS NOT NULL ORDER BY e.created_at DESC,e.id DESC LIMIT 20
        """)).mappings().all()
        for row in marker_rows:
            event_at = self._kst_iso(row["created_at"])
            if event_at and datetime.fromisoformat(event_at) >= cutoff:
                items.append({"type": "CHART_MARKER", "event_at": event_at, "title": "차트마커 등록",
                              "summary": f"{row['stock_name']} · {row['marker_name']}", "route": "/trading/chart-markers"})

        observation_rows = self.db.execute(text("""
            SELECT r.id,r.calculated_at,r.evaluated_at,
                   (SELECT COUNT(*) FROM market_theme_observation_items i WHERE i.run_id=r.id) theme_count,
                   (SELECT t.theme_name FROM market_theme_observation_items i
                     JOIN market_themes t ON t.id=i.theme_id WHERE i.run_id=r.id
                     ORDER BY i.observation_rank IS NULL,i.observation_rank LIMIT 1) top_theme
              FROM market_theme_observation_runs r
             ORDER BY COALESCE(r.evaluated_at,r.calculated_at) DESC,r.id DESC LIMIT 20
        """)).mappings().all()
        for row in observation_rows:
            calculated_at = self._kst_iso(row["calculated_at"])
            if calculated_at and datetime.fromisoformat(calculated_at) >= cutoff:
                items.append({"type": "OBSERVATION_CALCULATION", "event_at": calculated_at,
                              "title": "관찰우선순위 계산",
                              "summary": f"{int(row['theme_count'] or 0)}개 테마 · {row['top_theme'] or '1위 확인 중'} 1위",
                              "route": "/market-themes?view=prediction"})
            evaluated_at = self._kst_iso(row["evaluated_at"])
            if evaluated_at and datetime.fromisoformat(evaluated_at) >= cutoff:
                items.append({"type": "OBSERVATION_VALIDATION", "event_at": evaluated_at,
                              "title": "관찰순위 검증", "summary": f"{int(row['theme_count'] or 0)}개 테마 실전검증",
                              "route": "/market-themes?view=prediction"})

        items.sort(key=lambda item: str(item["event_at"]), reverse=True)
        return {
            "period_start": cutoff.date().isoformat(),
            "period_end": now.date().isoformat(),
            "items": items[: max(1, min(limit, 20))],
        }
