from __future__ import annotations

from collections import defaultdict
import math
import statistics
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from backend.app.schemas.market_theme_observation_schema import (
    MarketThemePriceFlowRadarAxisResult,
    MarketThemePriceFlowRadarProfile,
    MarketThemePriceFlowResearchResponse,
    MarketThemePriceFlowStageMetric,
)
from backend.app.services.market_theme_observation_feature_service import (
    PRICE_FLOW_FEATURE_VERSION,
    PRICE_FLOW_STAGE_VERSION,
    MarketThemeObservationFeatureService,
)


STAGE_LABELS = {
    "EARLY": "수급 선행",
    "CONFIRMED": "상승 확인",
    "MATURE": "상승 진행",
    "EXHAUSTED": "소진 주의",
}
RADAR_AXES = {
    "price_strength": "price_score",
    "flow_strength": "flow_score",
    "flow_acceleration": "flow_acceleration_percentile",
    "breadth": "breadth_score",
    "sustainability": "sustainability_score",
}


class MarketThemePriceFlowResearchService:
    """Leakage-safe, transient Phase 3 analysis over the shared dated feature set."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
        values = [float(row[key]) for row in rows if row.get(key) is not None and math.isfinite(float(row[key]))]
        return float(statistics.mean(values)) if values else None

    @staticmethod
    def _contiguous_folds(dates: list[str], count: int = 4) -> list[list[str]]:
        if not dates:
            return []
        size = max(1, math.ceil(len(dates) / count))
        return [dates[index:index + size] for index in range(0, len(dates), size)]

    @classmethod
    def _stage_metrics(
        cls,
        rows: list[dict[str, Any]],
        *,
        fold_rates: dict[str, list[float]] | None = None,
        fold_wins: dict[str, int] | None = None,
    ) -> list[MarketThemePriceFlowStageMetric]:
        total = max(1, len(rows))
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["stage_code"])].append(row)
        result: list[MarketThemePriceFlowStageMetric] = []
        for stage in STAGE_LABELS:
            values = grouped.get(stage, [])
            if not values:
                continue
            percentiles = [float(row["actual_percentile"]) for row in values]
            ranks = [float(row["label_rank"]) for row in values]
            rates = (fold_rates or {}).get(stage, [])
            result.append(MarketThemePriceFlowStageMetric(
                stage_code=stage,
                stage_label=STAGE_LABELS[stage],
                sample_count=len(values),
                sample_ratio=len(values) / total,
                top10_rate=sum(int(row["label_rank"]) <= 10 for row in values) / len(values),
                top20_rate=sum(int(row["label_top20"]) == 1 for row in values) / len(values),
                mean_actual_percentile=float(statistics.mean(percentiles)),
                median_actual_percentile=float(statistics.median(percentiles)),
                mean_actual_rank=float(statistics.mean(ranks)),
                median_actual_rank=float(statistics.median(ranks)),
                bottom_half_rate=sum(value < 50 for value in percentiles) / len(values),
                top5_rate=sum(int(row["label_rank"]) <= 5 for row in values) / len(values),
                fold_win_count=(fold_wins or {}).get(stage, 0),
                worst_fold_top20_rate=min(rates) if rates else None,
                fold_top20_std=float(np.std(rates)) if rates else None,
            ))
        return result

    @classmethod
    def _radar(cls, rows: list[dict[str, Any]]) -> MarketThemePriceFlowRadarProfile:
        return MarketThemePriceFlowRadarProfile(**{
            output: cls._mean(rows, source) for output, source in RADAR_AXES.items()
        })

    def analyze(self) -> MarketThemePriceFlowResearchResponse:
        dataset = MarketThemeObservationFeatureService(self.db).build_dataset()
        source = [row for row in dataset.rows if row.label_rank is not None and row.label_top20 is not None]
        by_date: dict[str, list[Any]] = defaultdict(list)
        for row in source:
            by_date[row.base_date].append(row)
        rows: list[dict[str, Any]] = []
        severe_failure_count = 0
        top5_count = 0
        for base_date, day_rows in by_date.items():
            count = len(day_rows)
            predicted_top5 = {
                row.theme_id for row in sorted(day_rows, key=lambda item: (-item.observation_rule_score, item.theme_id))[:5]
            }
            for row in day_rows:
                actual_percentile = 100.0 if count == 1 else 100.0 * (count - int(row.label_rank)) / (count - 1)
                values = dict(row.values)
                record = {
                    **values,
                    "base_date": base_date,
                    "target_date": row.target_date,
                    "theme_id": row.theme_id,
                    "label_rank": int(row.label_rank),
                    "label_top20": int(row.label_top20),
                    "actual_percentile": actual_percentile,
                    "stage_code": MarketThemeObservationFeatureService.signal_stage(values),
                }
                rows.append(record)
                if row.theme_id in predicted_top5:
                    top5_count += 1
                    severe_failure_count += int(actual_percentile < 50)
        dates = sorted(by_date)
        if not rows:
            return MarketThemePriceFlowResearchResponse(
                status="INSUFFICIENT_DATA",
                message="D+1 실제 결과가 연결된 가격·수급 연구 표본이 부족합니다.",
                stage_version=PRICE_FLOW_STAGE_VERSION,
                feature_version=PRICE_FLOW_FEATURE_VERSION,
            )

        fold_rates: dict[str, list[float]] = defaultdict(list)
        fold_wins: dict[str, int] = defaultdict(int)
        for fold_dates in self._contiguous_folds(dates):
            fold_set = set(fold_dates)
            fold_rows = [row for row in rows if row["base_date"] in fold_set]
            stage_rates: dict[str, float] = {}
            for stage in STAGE_LABELS:
                values = [row for row in fold_rows if row["stage_code"] == stage]
                if values:
                    rate = sum(int(row["label_top20"]) == 1 for row in values) / len(values)
                    fold_rates[stage].append(rate)
                    stage_rates[stage] = rate
            if stage_rates:
                best = max(stage_rates.values())
                for stage, rate in stage_rates.items():
                    fold_wins[stage] += int(rate == best)

        middle = max(1, len(dates) // 2)
        first_dates = set(dates[:middle])
        second_dates = set(dates[middle:])
        success_rows = [row for row in rows if float(row["actual_percentile"]) >= 80]
        failure_rows = [row for row in rows if float(row["actual_percentile"]) < 50]
        success_radar = self._radar(success_rows)
        failure_radar = self._radar(failure_rows)
        axis_results = []
        for axis in RADAR_AXES:
            success_value = getattr(success_radar, axis)
            failure_value = getattr(failure_radar, axis)
            axis_results.append(MarketThemePriceFlowRadarAxisResult(
                axis=axis,
                success_mean=success_value,
                failure_mean=failure_value,
                difference=None if success_value is None or failure_value is None else success_value - failure_value,
            ))
        return MarketThemePriceFlowResearchResponse(
            status="COMPLETED",
            message="Stage 성과와 성공·실패 Radar를 과거 D0 기준으로 재계산했습니다.",
            stage_version=PRICE_FLOW_STAGE_VERSION,
            feature_version=PRICE_FLOW_FEATURE_VERSION,
            data_start_date=dates[0],
            data_end_date=dates[-1],
            signal_start_date=min(str(row["target_date"]) for row in rows),
            signal_end_date=max(str(row["target_date"]) for row in rows),
            sample_count=len(rows),
            evaluated_dates=len(dates),
            stage_metrics=self._stage_metrics(rows, fold_rates=fold_rates, fold_wins=fold_wins),
            first_half_stage_metrics=self._stage_metrics([row for row in rows if row["base_date"] in first_dates]),
            second_half_stage_metrics=self._stage_metrics([row for row in rows if row["base_date"] in second_dates]),
            success_radar=success_radar,
            failure_radar=failure_radar,
            radar_axis_results=axis_results,
            rule_top5_bottom_half_rate=severe_failure_count / top5_count if top5_count else None,
            severe_failure_count=severe_failure_count,
        )
