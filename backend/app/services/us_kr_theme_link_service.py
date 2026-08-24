from __future__ import annotations

from fastapi import HTTPException, status
import math
from bisect import bisect_right
from datetime import date
from statistics import mean, median

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from backend.app.core.config import now_kst
from backend.app.entities.market_theme import MarketTheme
from backend.app.entities.us_kr_theme_link import UsKrThemeLink
from backend.app.entities.us_market_theme import UsTheme, UsThemeGroup
from backend.app.schemas.us_kr_theme_link_schema import (
    ThemeLinkOption,
    UsKrLeadAnalysisResponse,
    UsKrLeadMetrics,
    UsKrLeadPair,
    UsKrLeadThreshold,
    UsKrThemeLinkInput,
    UsKrThemeLinkOverview,
    UsKrThemeLinkResponse,
    UsKrThemeLinkSummary,
    UsKrThemeLinkUpdate,
    UsKrTodayObservationItem,
    UsKrTodayObservationResponse,
    UsKrTodayObservationSummary,
)


class UsKrThemeLinkService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _validate(self, us_theme_id: int, kr_theme_id: int) -> tuple[UsTheme, MarketTheme]:
        us_theme = self.db.get(UsTheme, us_theme_id)
        if us_theme is None:
            raise HTTPException(status_code=404, detail="미국 테마를 찾을 수 없습니다.")
        if not us_theme.active:
            raise HTTPException(status_code=400, detail="활성 미국 테마만 연결할 수 있습니다.")
        kr_theme = self.db.get(MarketTheme, kr_theme_id)
        if kr_theme is None:
            raise HTTPException(status_code=404, detail="국내 테마를 찾을 수 없습니다.")
        if not kr_theme.is_active or kr_theme.theme_level != "THEME":
            raise HTTPException(status_code=400, detail="활성 국내 테마만 연결할 수 있습니다.")
        return us_theme, kr_theme

    def _response(self, link: UsKrThemeLink) -> UsKrThemeLinkResponse:
        us_theme = self.db.get(UsTheme, link.us_theme_id)
        kr_theme = self.db.get(MarketTheme, link.kr_theme_id)
        us_group = self.db.get(UsThemeGroup, us_theme.theme_group_id) if us_theme else None
        kr_group = self.db.get(MarketTheme, kr_theme.parent_theme_id) if kr_theme and kr_theme.parent_theme_id else None
        return UsKrThemeLinkResponse(
            id=link.id, us_theme_id=link.us_theme_id,
            us_group_name=us_group.name if us_group else "미지정", us_theme_name=us_theme.name if us_theme else "-",
            kr_theme_id=link.kr_theme_id,
            kr_group_name=kr_group.theme_name if kr_group else "미지정", kr_theme_name=kr_theme.theme_name if kr_theme else "-",
            memo=link.memo, active=link.active, created_at=link.created_at, updated_at=link.updated_at,
        )

    def overview(self) -> UsKrThemeLinkOverview:
        links = self.db.scalars(select(UsKrThemeLink).order_by(UsKrThemeLink.id.desc())).all()
        linked_us = {row.us_theme_id for row in links if row.active}
        linked_kr = {row.kr_theme_id for row in links if row.active}
        us_rows = self.db.execute(
            select(UsTheme, UsThemeGroup.name).join(UsThemeGroup, UsTheme.theme_group_id == UsThemeGroup.id)
            .where(UsTheme.active == 1).order_by(UsThemeGroup.sort_order, UsTheme.sort_order, UsTheme.name)
        ).all()
        parent = aliased(MarketTheme)
        kr_rows = self.db.execute(
            select(MarketTheme, parent.theme_name).outerjoin(parent, MarketTheme.parent_theme_id == parent.id)
            .where(MarketTheme.is_active == 1, MarketTheme.theme_level == "THEME")
            .order_by(func.coalesce(parent.sort_order, 9999), MarketTheme.sort_order, MarketTheme.theme_name)
        ).all()
        us_options = [ThemeLinkOption(id=row.id, group_name=group, theme_name=row.name, active=row.active, linked=row.id in linked_us) for row, group in us_rows]
        kr_options = [ThemeLinkOption(id=row.id, group_name=group or "미지정", theme_name=row.theme_name, active=row.is_active, linked=row.id in linked_kr) for row, group in kr_rows]
        return UsKrThemeLinkOverview(
            summary=UsKrThemeLinkSummary(
                us_active_themes=len(us_options), kr_active_themes=len(kr_options), linked_themes=len(linked_us),
                unlinked_us_themes=len(us_options) - len(linked_us), unlinked_kr_themes=len(kr_options) - len(linked_kr),
            ),
            links=[self._response(row) for row in links], us_themes=us_options, kr_themes=kr_options,
        )

    def create(self, payload: UsKrThemeLinkInput) -> UsKrThemeLinkResponse:
        self._validate(payload.us_theme_id, payload.kr_theme_id)
        now = now_kst()
        link = UsKrThemeLink(us_theme_id=payload.us_theme_id, kr_theme_id=payload.kr_theme_id, memo=(payload.memo or "").strip() or None, active=1, created_at=now, updated_at=now)
        self.db.add(link)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 연결된 미국 또는 국내 테마입니다.") from exc
        self.db.refresh(link)
        return self._response(link)

    def update(self, link_id: int, payload: UsKrThemeLinkUpdate) -> UsKrThemeLinkResponse:
        link = self.db.get(UsKrThemeLink, link_id)
        if link is None:
            raise HTTPException(status_code=404, detail="테마 연결을 찾을 수 없습니다.")
        values = payload.model_dump(exclude_unset=True)
        us_id = int(values.get("us_theme_id", link.us_theme_id))
        kr_id = int(values.get("kr_theme_id", link.kr_theme_id))
        self._validate(us_id, kr_id)
        link.us_theme_id, link.kr_theme_id = us_id, kr_id
        if "memo" in values:
            link.memo = (values["memo"] or "").strip() or None
        link.updated_at = now_kst()
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="이미 연결된 미국 또는 국내 테마입니다.") from exc
        self.db.refresh(link)
        return self._response(link)

    def delete(self, link_id: int) -> UsKrThemeLinkResponse:
        link = self.db.get(UsKrThemeLink, link_id)
        if link is None:
            raise HTTPException(status_code=404, detail="테마 연결을 찾을 수 없습니다.")
        response = self._response(link)
        self.db.delete(link)
        self.db.commit()
        return response

    @staticmethod
    def _pearson(xs: list[float], ys: list[float]) -> float | None:
        if len(xs) < 2 or len(xs) != len(ys):
            return None
        x_mean, y_mean = mean(xs), mean(ys)
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        x_sum = sum((x - x_mean) ** 2 for x in xs)
        y_sum = sum((y - y_mean) ** 2 for y in ys)
        denominator = math.sqrt(x_sum * y_sum)
        return numerator / denominator if denominator > 0 else None

    @staticmethod
    def _rank(values: list[float]) -> list[float]:
        ordered = sorted(enumerate(values), key=lambda item: item[1])
        ranks = [0.0] * len(values)
        cursor = 0
        while cursor < len(ordered):
            end = cursor + 1
            while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
                end += 1
            average_rank = (cursor + 1 + end) / 2
            for index in range(cursor, end):
                ranks[ordered[index][0]] = average_rank
            cursor = end
        return ranks

    @classmethod
    def _spearman(cls, xs: list[float], ys: list[float]) -> float | None:
        return cls._pearson(cls._rank(xs), cls._rank(ys)) if len(xs) >= 2 else None

    @staticmethod
    def _rounded(value: float | None, digits: int = 4) -> float | None:
        return round(value, digits) if value is not None and math.isfinite(value) else None

    @staticmethod
    def _sample_guidance(sample_count: int) -> str:
        if sample_count < 20:
            return "표본 부족"
        if sample_count < 60:
            return "참고"
        return "분석 가능"

    def build_us_kr_lead_pairs(
        self,
        us_theme_id: int,
        kr_theme_id: int,
        us_metric: str,
        window: int,
        max_gap_days: int = 7,
    ) -> tuple[list[dict[str, object]], int, int]:
        metric_column = "theme_strength" if us_metric == "theme_strength" else "simple_return"
        us_rows = self.db.execute(text(f"""
            SELECT trade_date, {metric_column} AS us_value
            FROM us_theme_daily_returns
            WHERE theme_id=:theme_id
            ORDER BY trade_date ASC
        """), {"theme_id": us_theme_id}).mappings().all()
        kr_rows = self.db.execute(text("""
            SELECT return_date, avg_change_rate AS kr_return
            FROM market_theme_daily_returns
            WHERE theme_id=:theme_id
            ORDER BY return_date ASC
        """), {"theme_id": kr_theme_id}).mappings().all()

        return self._build_pairs_from_rows(us_rows, kr_rows, window, max_gap_days)

    @staticmethod
    def _build_pairs_from_rows(
        us_rows: list[object],
        kr_rows: list[object],
        window: int,
        max_gap_days: int = 7,
    ) -> tuple[list[dict[str, object]], int, int]:
        clean_kr: list[tuple[str, date, float]] = []
        for row in kr_rows:
            try:
                value = float(row["kr_return"])
                parsed = date.fromisoformat(str(row["return_date"])[:10])
                if math.isfinite(value):
                    clean_kr.append((str(row["return_date"])[:10], parsed, value))
            except (TypeError, ValueError):
                continue
        kr_dates = [item[1] for item in clean_kr]
        candidates: list[tuple[str, date, float]] = []
        invalid_us_count = 0
        for row in us_rows:
            try:
                value = float(row["us_value"])
                parsed = date.fromisoformat(str(row["trade_date"])[:10])
                if not math.isfinite(value):
                    raise ValueError
                candidates.append((str(row["trade_date"])[:10], parsed, value))
            except (TypeError, ValueError):
                invalid_us_count += 1

        valid: list[dict[str, object]] = []
        excluded_dates: list[date] = []
        for us_date_text, us_date, us_value in candidates:
            match_index = bisect_right(kr_dates, us_date)
            if match_index >= len(clean_kr):
                excluded_dates.append(us_date)
                continue
            kr_date_text, kr_date, kr_return = clean_kr[match_index]
            gap = (kr_date - us_date).days
            if gap > max_gap_days:
                excluded_dates.append(us_date)
                continue
            direction_match = None if us_value == 0 or kr_return == 0 else (us_value > 0) == (kr_return > 0)
            valid.append({
                "us_trade_date": us_date_text, "us_date": us_date, "us_value": us_value,
                "kr_trade_date": kr_date_text, "kr_return": kr_return,
                "calendar_gap_days": gap, "direction_match": direction_match,
            })

        selected = valid if window == 0 else valid[-window:]
        if selected and (window == 0 or len(valid) <= window):
            candidate_count = len(candidates) + invalid_us_count
            excluded_count = len(excluded_dates) + invalid_us_count
        elif selected:
            earliest = selected[0]["us_date"]
            candidate_count = sum(1 for _, row_date, _ in candidates if row_date >= earliest)
            excluded_count = sum(1 for row_date in excluded_dates if row_date >= earliest)
        else:
            candidate_count = len(candidates) + invalid_us_count
            excluded_count = candidate_count
        return selected, candidate_count, excluded_count

    @staticmethod
    def _current_threshold(value: float) -> tuple[str, float] | None:
        if value > 0:
            return "UP", 3.0 if value >= 3 else 2.0 if value >= 2 else 1.0 if value >= 1 else 0.0
        if value < 0:
            return "DOWN", -3.0 if value <= -3 else -2.0 if value <= -2 else -1.0 if value <= -1 else 0.0
        return None

    def today_observation(self, window: int = 120, us_metric: str = "theme_strength") -> UsKrTodayObservationResponse:
        metric_column = "theme_strength" if us_metric == "theme_strength" else "simple_return"
        link_rows = self.db.execute(text("""
            SELECT l.id AS link_id,l.us_theme_id,l.kr_theme_id,
                   ut.name AS us_theme_name,ug.name AS us_group_name,
                   kt.theme_name AS kr_theme_name,COALESCE(kg.theme_name,'미지정') AS kr_group_name
            FROM us_kr_theme_links l
            JOIN us_themes ut ON ut.id=l.us_theme_id AND ut.active=1
            JOIN us_theme_groups ug ON ug.id=ut.theme_group_id
            JOIN market_themes kt ON kt.id=l.kr_theme_id AND kt.is_active=1 AND kt.theme_level='THEME'
            LEFT JOIN market_themes kg ON kg.id=kt.parent_theme_id
            WHERE l.active=1
            ORDER BY l.id
        """)).mappings().all()
        latest_us_date = self.db.scalar(text("SELECT MAX(trade_date) FROM us_theme_daily_returns"))
        latest_us_date = str(latest_us_date)[:10] if latest_us_date else None
        kr_target_date = None
        if latest_us_date:
            candidate_kr_date = self.db.scalar(text("""
                SELECT MIN(return_date) FROM market_theme_daily_returns
                WHERE return_date > :latest_us_date
            """), {"latest_us_date": latest_us_date})
            if candidate_kr_date:
                parsed_gap = (date.fromisoformat(str(candidate_kr_date)[:10]) - date.fromisoformat(latest_us_date)).days
                if parsed_gap <= 7:
                    kr_target_date = str(candidate_kr_date)[:10]
        if not link_rows or not latest_us_date:
            linked_count = len(link_rows)
            return UsKrTodayObservationResponse(
                window=window or None, us_metric=us_metric,
                us_metric_label="미국 테마강도" if us_metric == "theme_strength" else "미국 단순등락률",
                latest_us_date=latest_us_date, previous_us_date=None, kr_target_date=kr_target_date,
                max_calendar_gap_days=7,
                summary=UsKrTodayObservationSummary(linked_count=linked_count, available_count=0, missing_count=linked_count, up_count=0, down_count=0),
                items=[],
            )

        us_ids = sorted({int(row["us_theme_id"]) for row in link_rows})
        kr_ids = sorted({int(row["kr_theme_id"]) for row in link_rows})
        us_rows = self.db.execute(text(f"""
            SELECT theme_id,trade_date,{metric_column} AS us_value,breadth_ratio,valid_stock_count,up_count,down_count
            FROM us_theme_daily_returns
            WHERE theme_id IN :theme_ids
            ORDER BY theme_id,trade_date
        """).bindparams(bindparam("theme_ids", expanding=True)), {"theme_ids": us_ids}).mappings().all()
        kr_rows = self.db.execute(text("""
            SELECT theme_id,return_date,avg_change_rate AS kr_return
            FROM market_theme_daily_returns
            WHERE theme_id IN :theme_ids
            ORDER BY theme_id,return_date
        """).bindparams(bindparam("theme_ids", expanding=True)), {"theme_ids": kr_ids}).mappings().all()
        us_by_theme: dict[int, list[object]] = {}
        kr_by_theme: dict[int, list[object]] = {}
        for row in us_rows:
            us_by_theme.setdefault(int(row["theme_id"]), []).append(row)
        for row in kr_rows:
            kr_by_theme.setdefault(int(row["theme_id"]), []).append(row)
        previous_dates = sorted({str(row["trade_date"])[:10] for row in us_rows if str(row["trade_date"])[:10] < latest_us_date})
        global_previous_date = previous_dates[-1] if previous_dates else None

        raw_items: list[dict[str, object]] = []
        for link in link_rows:
            theme_us_rows = us_by_theme.get(int(link["us_theme_id"]), [])
            theme_kr_rows = kr_by_theme.get(int(link["kr_theme_id"]), [])
            pairs, _, _ = self._build_pairs_from_rows(theme_us_rows, theme_kr_rows, window, 7)
            clean_latest = []
            for row in theme_us_rows:
                try:
                    value = float(row["us_value"])
                    if math.isfinite(value):
                        clean_latest.append((str(row["trade_date"])[:10], value, row))
                except (TypeError, ValueError):
                    continue
            latest = next((row for row in reversed(clean_latest) if row[0] == latest_us_date), None)
            previous = next((row for row in reversed(clean_latest) if row[0] < latest_us_date), None)
            threshold_row = None
            current = self._current_threshold(latest[1]) if latest else None
            if current:
                threshold_row = next((row for row in self._thresholds(pairs) if row.direction == current[0] and row.threshold == current[1]), None)
            latest_source = latest[2] if latest else None
            # A zero latest value is valid observation data even though it has no
            # matching directional threshold bucket. Only a missing latest value
            # should be pushed into the unavailable group.
            available = latest is not None
            raw_items.append({
                "link": link, "available": available, "latest": latest, "previous": previous,
                "source": latest_source, "current": current, "threshold_row": threshold_row,
                "missing_reason": None if available else "최신 미국 테마 지표가 없습니다.",
            })

        def sort_key(item: dict[str, object]) -> tuple[object, ...]:
            latest = item["latest"]
            threshold_row = item["threshold_row"]
            value = float(latest[1]) if latest else 0.0
            response = float(threshold_row.response_rate) if threshold_row and threshold_row.response_rate is not None else -1.0
            sample = int(threshold_row.sample_count) if threshold_row else 0
            return (0 if item["available"] else 1, -abs(value), -response, -sample)
        raw_items.sort(key=sort_key)
        items: list[UsKrTodayObservationItem] = []
        for index, item in enumerate(raw_items, start=1):
            link = item["link"]
            latest = item["latest"]
            previous = item["previous"]
            source = item["source"]
            current = item["current"]
            threshold_row = item["threshold_row"]
            items.append(UsKrTodayObservationItem(
                rank=index, link_id=int(link["link_id"]), us_theme_id=int(link["us_theme_id"]), us_group_name=str(link["us_group_name"]), us_theme_name=str(link["us_theme_name"]),
                kr_theme_id=int(link["kr_theme_id"]), kr_group_name=str(link["kr_group_name"]), kr_theme_name=str(link["kr_theme_name"]),
                available=bool(item["available"]), latest_us_date=latest[0] if latest else None, previous_us_date=previous[0] if previous else None,
                kr_target_date=kr_target_date, latest_value=self._rounded(latest[1]) if latest else None,
                previous_value=self._rounded(previous[1]) if previous else None,
                delta=self._rounded(latest[1] - previous[1]) if latest and previous else None,
                breadth_ratio=self._rounded(float(source["breadth_ratio"])) if source and source["breadth_ratio"] is not None else None,
                valid_stock_count=int(source["valid_stock_count"] or 0) if source else 0, up_count=int(source["up_count"] or 0) if source else 0, down_count=int(source["down_count"] or 0) if source else 0,
                threshold_direction=current[0] if current else None, threshold_condition=threshold_row.condition if threshold_row else None,
                threshold=current[1] if current else None, sample_count=threshold_row.sample_count if threshold_row else 0,
                response_rate=threshold_row.response_rate if threshold_row else None, avg_kr_return=threshold_row.avg_kr_return if threshold_row else None,
                sample_guidance=self._sample_guidance(threshold_row.sample_count if threshold_row else 0), missing_reason=item["missing_reason"],
            ))
        available_items = [row for row in items if row.available]
        return UsKrTodayObservationResponse(
            window=window or None, us_metric=us_metric,
            us_metric_label="미국 테마강도" if us_metric == "theme_strength" else "미국 단순등락률",
            latest_us_date=latest_us_date, previous_us_date=global_previous_date, kr_target_date=kr_target_date, max_calendar_gap_days=7,
            summary=UsKrTodayObservationSummary(linked_count=len(items), available_count=len(available_items), missing_count=len(items) - len(available_items), up_count=sum(1 for row in available_items if (row.latest_value or 0) > 0), down_count=sum(1 for row in available_items if (row.latest_value or 0) < 0)),
            items=items,
        )

    def _thresholds(self, pairs: list[dict[str, object]]) -> list[UsKrLeadThreshold]:
        result: list[UsKrLeadThreshold] = []
        for direction, threshold in [("UP", 0.0), ("UP", 1.0), ("UP", 2.0), ("UP", 3.0), ("DOWN", 0.0), ("DOWN", -1.0), ("DOWN", -2.0), ("DOWN", -3.0)]:
            if direction == "UP":
                rows = [row for row in pairs if float(row["us_value"]) > 0] if threshold == 0 else [row for row in pairs if float(row["us_value"]) >= threshold]
                responses = [float(row["kr_return"]) > 0 for row in rows]
                condition = "US > 0%" if threshold == 0 else f"US ≥ +{int(threshold)}%"
            else:
                rows = [row for row in pairs if float(row["us_value"]) < 0] if threshold == 0 else [row for row in pairs if float(row["us_value"]) <= threshold]
                responses = [float(row["kr_return"]) < 0 for row in rows]
                condition = "US < 0%" if threshold == 0 else f"US ≤ {int(threshold)}%"
            kr_values = [float(row["kr_return"]) for row in rows]
            result.append(UsKrLeadThreshold(
                direction=direction, condition=condition, threshold=threshold, sample_count=len(rows),
                response_rate=self._rounded(100 * sum(responses) / len(responses), 2) if responses else None,
                avg_kr_return=self._rounded(mean(kr_values)) if kr_values else None,
                median_kr_return=self._rounded(median(kr_values)) if kr_values else None,
            ))
        return result

    def lead_analysis(self, link_id: int, window: int = 120, us_metric: str = "theme_strength") -> UsKrLeadAnalysisResponse:
        link = self.db.get(UsKrThemeLink, link_id)
        if link is None or not link.active:
            raise HTTPException(status_code=404, detail="활성 한미 테마 연결을 찾을 수 없습니다.")
        pairs, candidate_count, excluded_count = self.build_us_kr_lead_pairs(link.us_theme_id, link.kr_theme_id, us_metric, window)
        xs = [float(row["us_value"]) for row in pairs]
        ys = [float(row["kr_return"]) for row in pairs]
        directional = [row for row in pairs if row["direction_match"] is not None]
        us_up = [row for row in pairs if float(row["us_value"]) > 0]
        us_down = [row for row in pairs if float(row["us_value"]) < 0]
        pearson = self._pearson(xs, ys)
        x_mean, y_mean = (mean(xs), mean(ys)) if pairs else (0.0, 0.0)
        x_variance = sum((value - x_mean) ** 2 for value in xs)
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / x_variance if x_variance > 0 else None
        intercept = y_mean - slope * x_mean if slope is not None else None
        metrics = UsKrLeadMetrics(
            candidate_count=candidate_count, sample_count=len(pairs), excluded_count=excluded_count,
            direction_sample_count=len(directional),
            direction_match_rate=self._rounded(100 * sum(bool(row["direction_match"]) for row in directional) / len(directional), 2) if directional else None,
            us_up_kr_up_rate=self._rounded(100 * sum(float(row["kr_return"]) > 0 for row in us_up) / len(us_up), 2) if us_up else None,
            us_down_kr_down_rate=self._rounded(100 * sum(float(row["kr_return"]) < 0 for row in us_down) / len(us_down), 2) if us_down else None,
            avg_kr_return=self._rounded(mean(ys)) if ys else None,
            median_kr_return=self._rounded(median(ys)) if ys else None,
            pearson_correlation=self._rounded(pearson), spearman_correlation=self._rounded(self._spearman(xs, ys)),
            regression_slope=self._rounded(slope), regression_intercept=self._rounded(intercept),
            sample_guidance=self._sample_guidance(len(pairs)),
        )
        public_pairs = [UsKrLeadPair(**{key: value for key, value in row.items() if key != "us_date"}) for row in reversed(pairs)]
        return UsKrLeadAnalysisResponse(
            link=self._response(link), window=window or None, us_metric=us_metric,
            us_metric_label="미국 테마강도" if us_metric == "theme_strength" else "미국 단순등락률",
            kr_metric_label="국내 일별 테마등락률",
            latest_us_date=max((pair.us_trade_date for pair in public_pairs), default=None),
            latest_kr_date=max((pair.kr_trade_date for pair in public_pairs), default=None),
            max_calendar_gap_days=7, metrics=metrics, thresholds=self._thresholds(pairs), pairs=public_pairs,
        )
