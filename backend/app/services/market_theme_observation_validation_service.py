from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from statistics import mean
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.schemas.market_theme_observation_schema import (
    MarketThemeObservationDiagnosticMessage,
    MarketThemeObservationDiagnosticsResponse,
    MarketThemeObservationDiagnosticMetricSummary,
    MarketThemeObservationDiagnosticPairedSummary,
    MarketThemeObservationDiagnosticPeriod,
    MarketThemeObservationDiagnosticScoreBucket,
    MarketThemeObservationDiagnosticStatusPerformance,
)


OBSERVATION_RULE_VERSION = "OBSERVATION_RULE_V1"
OBSERVATION_METRIC_VERSION = "THEME_OBSERVATION_METRIC_V1"
MIN_EVALUABLE_THEMES = 10
MIN_EVALUATION_COVERAGE_RATE = 0.50
AUTO_VALIDATION_MAX_PENDING_DAYS = 20


class MarketThemeObservationValidationService:
    """Persist and aggregate only compact scalar validation results."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def snapshot(
        self,
        target_date: str,
        calculation_mode: str,
        rows: list[dict[str, Any]],
        *,
        model_version: str | None = None,
        rule_version: str = OBSERVATION_RULE_VERSION,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        payloads = [{
            "target": target_date,
            "theme_id": int(row["theme_id"]),
            "mode": calculation_mode,
            "rule": rule_version,
            "model": model_version or "",
            "metric": OBSERVATION_METRIC_VERSION,
            "score": row.get("score"),
            "rank": int(row["rank"]),
            "status": row.get("status"),
            "coverage": row.get("coverage"),
            "now": now,
        } for row in rows]
        self.db.execute(text("""
            INSERT INTO market_theme_observation_validation_samples
            (target_date,theme_id,calculation_mode,observation_rule_version,model_version,metric_version,
             observation_score,observation_rank,status_code,data_coverage_rate,evaluation_status,created_at,updated_at)
            VALUES (:target,:theme_id,:mode,:rule,:model,:metric,:score,:rank,:status,:coverage,'PENDING',:now,:now)
            ON CONFLICT(target_date,theme_id,calculation_mode,observation_rule_version,model_version) DO UPDATE SET
              metric_version=excluded.metric_version,observation_score=excluded.observation_score,
              observation_rank=excluded.observation_rank,status_code=excluded.status_code,
              data_coverage_rate=excluded.data_coverage_rate,actual_rank=NULL,actual_top20=NULL,
              rank_error=NULL,rank_gap=NULL,top20_hit=NULL,refresh_score_delta=NULL,
              refresh_rank_improvement=NULL,refresh_effect=NULL,evaluation_status='PENDING',
              evaluated_at=NULL,updated_at=excluded.updated_at
        """), payloads)

    @staticmethod
    def metric_values(rows: list[dict[str, Any]], actual_top_ids: set[int], top_count: int) -> dict[str, Any]:
        ordered = sorted(rows, key=lambda row: (int(row["observation_rank"]), int(row["theme_id"])))
        predicted_top = {int(row["theme_id"]) for row in ordered[:top_count]}
        hits = len(predicted_top & actual_top_ids)
        precision = hits / len(predicted_top) if predicted_top else None
        recall = hits / len(actual_top_ids) if actual_top_ids else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else 0.0
        top5 = ordered[:5]
        top5_hits = len({int(row["theme_id"]) for row in top5} & actual_top_ids)
        precision_at_5 = top5_hits / len(top5) if top5 else None
        dcg = sum((1 if int(row["theme_id"]) in actual_top_ids else 0) / math.log2(index + 2) for index, row in enumerate(top5))
        idcg = sum(1 / math.log2(index + 2) for index in range(min(5, len(actual_top_ids))))
        n = len(ordered)
        spearman = None
        if n > 1:
            spearman = 1 - 6 * sum((int(row["observation_rank"]) - int(row["actual_rank"])) ** 2 for row in ordered) / (n * (n * n - 1))
        return {
            "precision": precision, "recall": recall, "f1": f1, "p5": precision_at_5,
            "ndcg": dcg / idcg if idcg else None, "spearman": spearman,
            "rank_error": mean(float(row["rank_error"]) for row in ordered) if ordered else None,
            "top5_hits": top5_hits,
        }

    def evaluate(self, target_date: str) -> str:
        samples = [dict(row) for row in self.db.execute(text("""
            SELECT * FROM market_theme_observation_validation_samples
             WHERE target_date=:target ORDER BY calculation_mode,observation_rank,theme_id
        """), {"target": target_date}).mappings().all()]
        actual_rows = [dict(row) for row in self.db.execute(text("""
            SELECT theme_id,avg_change_rate FROM market_theme_daily_returns
             WHERE return_date=:target AND avg_change_rate IS NOT NULL
             ORDER BY avg_change_rate DESC,theme_id ASC
        """), {"target": target_date}).mappings().all()]
        if not actual_rows:
            return "WAITING_ACTUAL"
        if not samples:
            return "NO_SNAPSHOT"

        actual_rank = {int(row["theme_id"]): index + 1 for index, row in enumerate(actual_rows)}
        actual_top_count = max(1, math.ceil(len(actual_rows) * .20))
        actual_top_ids = {theme_id for theme_id, rank in actual_rank.items() if rank <= actual_top_count}
        now = datetime.now().isoformat(timespec="seconds")
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for sample in samples:
            groups[(str(sample["calculation_mode"]), str(sample["observation_rule_version"]), str(sample["model_version"] or ""))].append(sample)

        qualified = 0
        for (mode, rule, model), group in groups.items():
            evaluated: list[dict[str, Any]] = []
            for sample in group:
                theme_id = int(sample["theme_id"])
                rank = actual_rank.get(theme_id)
                if rank is None:
                    self.db.execute(text("""
                        UPDATE market_theme_observation_validation_samples SET actual_rank=NULL,actual_top20=NULL,
                          rank_error=NULL,rank_gap=NULL,top20_hit=NULL,evaluation_status='MISSING_ACTUAL',evaluated_at=:now,updated_at=:now
                         WHERE id=:id
                    """), {"id": sample["id"], "now": now})
                    continue
                rank_error = abs(rank - int(sample["observation_rank"]))
                sample.update(actual_rank=rank, rank_error=rank_error)
                evaluated.append(sample)
                observation_top20 = int(sample["observation_rank"]) <= actual_top_count
                self.db.execute(text("""
                    UPDATE market_theme_observation_validation_samples SET actual_rank=:actual_rank,actual_top20=:actual_top20,
                      rank_error=:rank_error,rank_gap=:rank_gap,top20_hit=:hit,evaluation_status='EVALUATED',
                      evaluated_at=:now,updated_at=:now WHERE id=:id
                """), {"actual_rank": rank, "actual_top20": int(theme_id in actual_top_ids), "rank_error": rank_error,
                         "rank_gap": rank - int(sample["observation_rank"]),
                         "hit": int(observation_top20 and theme_id in actual_top_ids), "now": now, "id": sample["id"]})
            coverage = len(evaluated) / len(group) if group else 0.0
            status = "QUALIFIED" if len(evaluated) >= MIN_EVALUABLE_THEMES and coverage >= MIN_EVALUATION_COVERAGE_RATE else "INSUFFICIENT_UNIVERSE"
            qualified += int(status == "QUALIFIED")
            values = self.metric_values(evaluated, actual_top_ids, actual_top_count)
            self.db.execute(text("""
                INSERT INTO market_theme_observation_validation_metrics
                (target_date,calculation_mode,observation_rule_version,model_version,metric_version,total_theme_count,
                 evaluable_theme_count,evaluation_coverage_rate,precision_top20,recall_top20,f1_top20,precision_at_5,
                 ndcg_at_5,spearman,mean_rank_error,top5_actual_top20_count,evaluation_status,evaluated_at,created_at,updated_at)
                VALUES (:target,:mode,:rule,:model,:metric,:total,:evaluable,:coverage,:precision,:recall,:f1,:p5,
                        :ndcg,:spearman,:rank_error,:top5_hits,:status,:now,:now,:now)
                ON CONFLICT(target_date,calculation_mode,observation_rule_version,model_version) DO UPDATE SET
                  metric_version=excluded.metric_version,total_theme_count=excluded.total_theme_count,
                  evaluable_theme_count=excluded.evaluable_theme_count,evaluation_coverage_rate=excluded.evaluation_coverage_rate,
                  precision_top20=excluded.precision_top20,recall_top20=excluded.recall_top20,f1_top20=excluded.f1_top20,
                  precision_at_5=excluded.precision_at_5,ndcg_at_5=excluded.ndcg_at_5,spearman=excluded.spearman,
                  mean_rank_error=excluded.mean_rank_error,top5_actual_top20_count=excluded.top5_actual_top20_count,
                  evaluation_status=excluded.evaluation_status,evaluated_at=excluded.evaluated_at,updated_at=excluded.updated_at
            """), {"target": target_date, "mode": mode, "rule": rule, "model": model, "metric": OBSERVATION_METRIC_VERSION,
                     "total": len(group), "evaluable": len(evaluated), "coverage": coverage, "status": status, "now": now, **values})

        self._evaluate_refresh_effect(target_date, actual_rank, now)
        self.db.commit()
        return "EVALUATED" if qualified else "INSUFFICIENT_UNIVERSE"

    def auto_validate_latest_actual(self) -> dict[str, Any]:
        """Validate a bounded set of finished actual dates before a new D+1 calculation."""
        active_theme_count = int(self.db.execute(text("""
            SELECT COUNT(*) FROM market_themes WHERE is_active=1 AND theme_level='THEME'
        """)).scalar() or 0)
        actual_dates = [dict(row) for row in self.db.execute(text("""
            SELECT return_date,COUNT(*) actual_count,MAX(updated_at) actual_updated_at
              FROM market_theme_daily_returns
             WHERE avg_change_rate IS NOT NULL
             GROUP BY return_date ORDER BY return_date DESC LIMIT :limit
        """), {"limit": AUTO_VALIDATION_MAX_PENDING_DAYS * 3}).mappings().all()]
        eligible_dates = [row for row in actual_dates
                          if int(row["actual_count"] or 0) >= MIN_EVALUABLE_THEMES
                          and (int(row["actual_count"] or 0) / max(1, active_theme_count)) >= MIN_EVALUATION_COVERAGE_RATE]
        if not eligible_dates:
            diagnostics = self.diagnostics()
            return {"status": "AUTO_VALIDATION_WAITING_ACTUAL", "target_date": None, "modes": [],
                    "quality_status": None,
                    "message": "검증 가능한 최신 테마 실측 데이터가 아직 없습니다. D+1 관찰순위 계산은 계속 진행합니다.",
                    "diagnostic_status": diagnostics.diagnostic_status}

        latest_actual = str(eligible_dates[0]["return_date"])
        latest_snapshot_modes = [str(value) for value in self.db.execute(text("""
            SELECT DISTINCT calculation_mode FROM market_theme_observation_validation_samples
             WHERE target_date=:target ORDER BY calculation_mode
        """), {"target": latest_actual}).scalars().all()]
        pending_dates = [str(value) for value in self.db.execute(text("""
            SELECT s.target_date
              FROM market_theme_observation_validation_samples s
              JOIN market_theme_daily_returns r
                ON r.return_date=s.target_date AND r.theme_id=s.theme_id AND r.avg_change_rate IS NOT NULL
             WHERE s.target_date<=:latest
             GROUP BY s.target_date
            HAVING SUM(CASE WHEN s.evaluation_status!='EVALUATED' THEN 1 ELSE 0 END)>0
                OR MAX(COALESCE(r.updated_at,''))>COALESCE(MAX(s.evaluated_at),'')
             ORDER BY s.target_date ASC LIMIT :limit
        """), {"latest": latest_actual, "limit": AUTO_VALIDATION_MAX_PENDING_DAYS}).scalars().all()]

        if not pending_dates:
            diagnostics = self.diagnostics()
            if latest_snapshot_modes:
                return {"status": "AUTO_VALIDATION_UP_TO_DATE", "target_date": latest_actual,
                        "modes": latest_snapshot_modes, "quality_status": "UP_TO_DATE",
                        "message": f"{latest_actual} 관찰결과는 최신 실측 기준으로 이미 검증되어 있습니다.",
                        "diagnostic_status": diagnostics.diagnostic_status}
            return {"status": "AUTO_VALIDATION_SKIPPED_NO_OBSERVATION", "target_date": latest_actual,
                    "modes": [], "quality_status": None,
                    "message": "최신 실측 데이터는 확인됐지만 비교할 기존 관찰결과가 없어 자동검증을 건너뛰었습니다.",
                    "diagnostic_status": diagnostics.diagnostic_status}

        modes: set[str] = set()
        quality_statuses: list[str] = []
        last_target: str | None = None
        try:
            for pending_date in pending_dates:
                result = self.evaluate(pending_date)
                last_target = pending_date
                quality_statuses.append(result)
                modes.update(str(value) for value in self.db.execute(text("""
                    SELECT DISTINCT calculation_mode FROM market_theme_observation_validation_samples
                     WHERE target_date=:target ORDER BY calculation_mode
                """), {"target": pending_date}).scalars().all())
            diagnostics = self.diagnostics()
        except Exception:
            self.db.rollback()
            diagnostics = self.diagnostics()
            return {"status": "AUTO_VALIDATION_FAILED", "target_date": last_target or latest_actual,
                    "modes": sorted(modes), "quality_status": None,
                    "message": "최근 관찰결과 자동검증에 실패했습니다. D+1 관찰순위는 계속 계산하지만 검증 상태를 확인해 주세요.",
                    "diagnostic_status": diagnostics.diagnostic_status}

        quality = "INSUFFICIENT_UNIVERSE" if "INSUFFICIENT_UNIVERSE" in quality_statuses else "QUALIFIED"
        mode_label = "/".join(mode.replace("_MARKET_DATA", "") for mode in sorted(modes))
        if quality == "INSUFFICIENT_UNIVERSE":
            message = f"{last_target} 검증은 완료됐지만 평가 Universe가 부족해 장기 성능 집계에서는 제외됩니다."
        else:
            message = f"{last_target} {mode_label} 관찰결과를 실측으로 검증했습니다."
        return {"status": "SUCCESS", "target_date": last_target, "modes": sorted(modes),
                "quality_status": quality, "message": message,
                "diagnostic_status": diagnostics.diagnostic_status}

    def _evaluate_refresh_effect(self, target_date: str, actual_rank: dict[int, int], now: str) -> None:
        rows = [dict(row) for row in self.db.execute(text("""
            SELECT c.theme_id,c.observation_score AS current_score,c.observation_rank AS current_rank,
                   r.id AS refreshed_id,r.observation_score AS refreshed_score,r.observation_rank AS refreshed_rank,
                   c.observation_rule_version,c.model_version
              FROM market_theme_observation_validation_samples c
              JOIN market_theme_observation_validation_samples r
                ON r.target_date=c.target_date AND r.theme_id=c.theme_id
               AND r.observation_rule_version=c.observation_rule_version AND r.model_version=c.model_version
             WHERE c.target_date=:target AND c.calculation_mode='CURRENT_MARKET_DATA'
               AND r.calculation_mode='REFRESHED_MARKET_DATA'
        """), {"target": target_date}).mappings().all()]
        effects: list[int] = []
        for row in rows:
            actual = actual_rank.get(int(row["theme_id"]))
            effect = None if actual is None else abs(actual - int(row["current_rank"])) - abs(actual - int(row["refreshed_rank"]))
            if effect is not None:
                effects.append(effect)
            self.db.execute(text("""
                UPDATE market_theme_observation_validation_samples SET refresh_score_delta=:score_delta,
                  refresh_rank_improvement=:rank_improvement,refresh_effect=:effect,updated_at=:now WHERE id=:id
            """), {"score_delta": None if row["current_score"] is None or row["refreshed_score"] is None else float(row["refreshed_score"]) - float(row["current_score"]),
                     "rank_improvement": int(row["current_rank"]) - int(row["refreshed_rank"]),
                     "effect": effect, "now": now, "id": row["refreshed_id"]})
        current = self.db.execute(text("""SELECT * FROM market_theme_observation_validation_metrics
            WHERE target_date=:target AND calculation_mode='CURRENT_MARKET_DATA' AND model_version=''"""), {"target": target_date}).mappings().first()
        refreshed = self.db.execute(text("""SELECT * FROM market_theme_observation_validation_metrics
            WHERE target_date=:target AND calculation_mode='REFRESHED_MARKET_DATA' AND model_version=''"""), {"target": target_date}).mappings().first()
        if current and refreshed and effects:
            self.db.execute(text("""
                UPDATE market_theme_observation_validation_metrics SET improved_theme_count=:improved,
                  worsened_theme_count=:worsened,unchanged_theme_count=:unchanged,
                  mean_rank_error_current=:current_error,mean_rank_error_refreshed=:refreshed_error,
                  mean_refresh_effect=:mean_effect,current_precision_top20=:current_precision,
                  refreshed_precision_top20=:refreshed_precision,current_ndcg_at_5=:current_ndcg,
                  refreshed_ndcg_at_5=:refreshed_ndcg,updated_at=:now WHERE id=:id
            """), {"improved": sum(value > 0 for value in effects), "worsened": sum(value < 0 for value in effects),
                     "unchanged": sum(value == 0 for value in effects), "current_error": current["mean_rank_error"],
                     "refreshed_error": refreshed["mean_rank_error"], "mean_effect": mean(effects),
                     "current_precision": current["precision_top20"], "refreshed_precision": refreshed["precision_top20"],
                     "current_ndcg": current["ndcg_at_5"], "refreshed_ndcg": refreshed["ndcg_at_5"],
                     "now": now, "id": refreshed["id"]})

    @staticmethod
    def _summary(rows: list[dict[str, Any]]) -> MarketThemeObservationDiagnosticMetricSummary:
        def avg(key: str) -> float | None:
            values = [float(row[key]) for row in rows if row.get(key) is not None]
            return mean(values) if values else None
        return MarketThemeObservationDiagnosticMetricSummary(
            evaluated_days=len({str(row["target_date"]) for row in rows}), precision_top20=avg("precision_top20"),
            precision_at_5=avg("precision_at_5"), ndcg_at_5=avg("ndcg_at_5"),
            spearman=avg("spearman"), mean_rank_error=avg("mean_rank_error"),
        )

    def diagnostics(self) -> MarketThemeObservationDiagnosticsResponse:
        metrics = [dict(row) for row in self.db.execute(text("""
            SELECT * FROM market_theme_observation_validation_metrics
             WHERE evaluation_status='QUALIFIED' ORDER BY target_date DESC
        """)).mappings().all()]
        quality_dates = sorted({str(row["target_date"]) for row in metrics if not row["model_version"]}, reverse=True)

        def period(limit: int | None) -> MarketThemeObservationDiagnosticPeriod:
            dates = set(quality_dates[:limit] if limit else quality_dates)
            selected = [row for row in metrics if str(row["target_date"]) in dates and not row["model_version"]]
            return MarketThemeObservationDiagnosticPeriod(
                quality_days=len(dates),
                current=self._summary([row for row in selected if row["calculation_mode"] == "CURRENT_MARKET_DATA"]),
                refreshed=self._summary([row for row in selected if row["calculation_mode"] == "REFRESHED_MARKET_DATA"]),
            )

        paired_rows = [row for row in metrics if row["calculation_mode"] == "REFRESHED_MARKET_DATA" and row.get("mean_refresh_effect") is not None and not row["model_version"]]
        paired_recent = paired_rows[:20]
        def avg_paired(key: str) -> float | None:
            values = [float(row[key]) for row in paired_recent if row.get(key) is not None]
            return mean(values) if values else None
        paired = MarketThemeObservationDiagnosticPairedSummary(
            paired_days=len(paired_recent), mean_rank_error_current=avg_paired("mean_rank_error_current"),
            mean_rank_error_refreshed=avg_paired("mean_rank_error_refreshed"), mean_refresh_effect=avg_paired("mean_refresh_effect"),
            improved_theme_count=sum(int(row.get("improved_theme_count") or 0) for row in paired_recent),
            worsened_theme_count=sum(int(row.get("worsened_theme_count") or 0) for row in paired_recent),
            unchanged_theme_count=sum(int(row.get("unchanged_theme_count") or 0) for row in paired_recent),
        )
        status_rows = [dict(row) for row in self.db.execute(text("""
            SELECT s.status_code,COUNT(*) sample_count,AVG(s.actual_top20) top20_hit_rate,
                   AVG(s.actual_rank) mean_actual_rank,AVG(s.rank_error) mean_rank_error
              FROM market_theme_observation_validation_samples s
              JOIN market_theme_observation_validation_metrics m
                ON m.target_date=s.target_date AND m.calculation_mode=s.calculation_mode
               AND m.observation_rule_version=s.observation_rule_version AND m.model_version=s.model_version
             WHERE s.evaluation_status='EVALUATED' AND m.evaluation_status='QUALIFIED'
             GROUP BY s.status_code ORDER BY s.status_code
        """)).mappings().all()]
        bucket_rows = [dict(row) for row in self.db.execute(text("""
            SELECT CASE WHEN s.observation_score>=80 THEN '80~100' WHEN s.observation_score>=70 THEN '70~80'
                        WHEN s.observation_score>=60 THEN '60~70' WHEN s.observation_score>=50 THEN '50~60' ELSE '0~50' END score_bucket,
                   COUNT(*) sample_count,AVG(s.actual_top20) top20_entry_rate,
                   AVG(CAST(s.actual_rank AS REAL)/m.evaluable_theme_count) mean_actual_rank_percentile
              FROM market_theme_observation_validation_samples s
              JOIN market_theme_observation_validation_metrics m
                ON m.target_date=s.target_date AND m.calculation_mode=s.calculation_mode
               AND m.observation_rule_version=s.observation_rule_version AND m.model_version=s.model_version
             WHERE s.evaluation_status='EVALUATED' AND m.evaluation_status='QUALIFIED' AND s.observation_score IS NOT NULL
             GROUP BY score_bucket
             ORDER BY MIN(s.observation_score) DESC
        """)).mappings().all()]

        messages: list[MarketThemeObservationDiagnosticMessage] = []
        diagnostic_status = "HEALTHY"
        if len(quality_dates) < 10:
            diagnostic_status = "INSUFFICIENT_DATA"
            messages.append(MarketThemeObservationDiagnosticMessage(code="INSUFFICIENT_DATA", severity="INFO",
                title="데이터 축적 중", message="아직 로직 변경을 판단하기에는 품질 검증 데이터가 부족합니다."))
        elif len(quality_dates) < 20:
            diagnostic_status = "WATCH"
            messages.append(MarketThemeObservationDiagnosticMessage(code="WATCH", severity="INFO",
                title="관찰 로직 추적 중", message="20개 품질 검증일까지 결과를 더 축적합니다."))
        else:
            recent = period(20)
            baseline = period(None)
            r = recent.current
            b = baseline.current
            degraded = ((r.precision_top20 is not None and b.precision_top20 is not None and r.precision_top20 < b.precision_top20 - .05)
                        or (r.ndcg_at_5 is not None and b.ndcg_at_5 is not None and r.ndcg_at_5 < b.ndcg_at_5 - .05)
                        or (r.mean_rank_error is not None and b.mean_rank_error is not None and r.mean_rank_error > b.mean_rank_error + 1))
            if degraded:
                diagnostic_status = "RULE_REVIEW_RECOMMENDED"
                messages.append(MarketThemeObservationDiagnosticMessage(code="RULE_REVIEW_RECOMMENDED", severity="WARNING",
                    title="관찰 로직 개선 검토 필요", message="최근 상위 테마 선별력이 장기 기준보다 낮아 Observation RULE 검토가 필요합니다."))
        if paired.paired_days >= 20 and ((paired.mean_refresh_effect or 0) <= 0 or
                ((paired.mean_rank_error_refreshed or 0) > (paired.mean_rank_error_current or 0))):
            diagnostic_status = "MARKET_ADJUSTMENT_REVIEW"
            messages.append(MarketThemeObservationDiagnosticMessage(code="MARKET_ADJUSTMENT_REVIEW", severity="WARNING",
                title="시장지표 보정 로직 검토 필요",
                message="최근 실전 검증에서 시장지표 보정이 관찰순위를 안정적으로 개선하지 못하고 있습니다."))

        trained_at = self.db.execute(text("""
            SELECT trained_at FROM market_theme_return_prediction_models
             WHERE target_type='TOP20_RELATIVE_STRENGTH' ORDER BY trained_at DESC LIMIT 1
        """)).scalar()
        days_after_training = 0
        if trained_at:
            trained_date = str(trained_at)[:10]
            days_after_training = len({row["target_date"] for row in metrics if row["target_date"] > trained_date})
            if days_after_training >= 20:
                messages.append(MarketThemeObservationDiagnosticMessage(code="ML_RETRAIN_RECOMMENDED", severity="INFO",
                    title="ML 재학습 검토 가능", message=f"마지막 학습 이후 {days_after_training}개 품질 검증일이 추가되었습니다."))
        return MarketThemeObservationDiagnosticsResponse(
            quality_evaluated_days=len(quality_dates), recent_5=period(5), recent_20=period(20), all=period(None),
            paired_correction=paired,
            status_performance=[MarketThemeObservationDiagnosticStatusPerformance(**row) for row in status_rows],
            score_bucket_performance=[MarketThemeObservationDiagnosticScoreBucket(**row) for row in bucket_rows],
            diagnostic_status=diagnostic_status, messages=messages, ml_quality_days_since_training=days_after_training,
        )
