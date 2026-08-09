from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.schemas.market_theme_observation_schema import MarketThemeObservationResponse
from backend.app.services.market_theme_observation_feature_service import (
    OBSERVATION_FEATURE_VERSION,
    MarketThemeObservationFeatureService,
)
from backend.app.services.market_data_collection_service import MarketDataCollectionService
from backend.app.services.market_theme_observation_validation_service import (
    MarketThemeObservationValidationService,
    OBSERVATION_RULE_VERSION,
)


class MarketThemeObservationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def next_weekday(value: str) -> str:
        current = date.fromisoformat(value) + timedelta(days=1)
        while current.weekday() >= 5:
            current += timedelta(days=1)
        return current.isoformat()

    def _cutoff(self) -> str:
        value = self.db.execute(text("SELECT MAX(return_date) FROM market_theme_daily_returns")).scalar()
        if not value:
            raise HTTPException(status_code=409, detail="테마 등락 데이터가 없어 관찰 순위를 계산할 수 없습니다.")
        return str(value)

    def _run(self, target_date: str) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM market_theme_observation_runs WHERE target_date=:target_date"), {"target_date": target_date}).mappings().first()
        return dict(row) if row else None

    def _latest_market_refresh_at(self) -> str | None:
        value = self.db.execute(text("""
            SELECT finished_at FROM market_data_collection_runs
             WHERE run_type='INCREMENTAL_ALL' AND status IN ('SUCCESS','PARTIAL_SUCCESS') AND finished_at IS NOT NULL
             ORDER BY id DESC LIMIT 1
        """)).scalar()
        return self._sqlite_utc_to_local(value)

    def _market_data_asof_at(self) -> str | None:
        value = self.db.execute(text("""
            SELECT MAX(value) FROM (
                SELECT MAX(collected_at) AS value FROM market_indicator_values
                UNION ALL SELECT MAX(collected_at) AS value FROM market_index_daily_prices
            )
        """)).scalar()
        return self._sqlite_utc_to_local(value)

    @staticmethod
    def actual_relative_strength(actual_rank: int | None, universe_count: int | None) -> float | None:
        if actual_rank is None or universe_count is None or universe_count < 1 or actual_rank < 1 or actual_rank > universe_count:
            return None
        if universe_count == 1:
            return 100.0
        return round(100 * (universe_count - actual_rank) / (universe_count - 1), 4)

    @staticmethod
    def relative_strength_gap(predicted_score: float | None, actual_strength: float | None) -> float | None:
        if predicted_score is None or actual_strength is None:
            return None
        return round(actual_strength - predicted_score, 4)

    def get(self, target_date: str) -> MarketThemeObservationResponse:
        run = self._run(target_date)
        cutoff = self._cutoff()
        if not run:
            return MarketThemeObservationResponse(status="DRAFT", data_cutoff_date=cutoff, default_target_date=self.next_weekday(cutoff), message="저장된 관찰 우선순위가 없습니다.", market_indicator_latest_refreshed_at=self._latest_market_refresh_at())
        items = [dict(row) for row in self.db.execute(text("""
            SELECT i.*,t.theme_name,t.parent_theme_id AS theme_group_id,p.theme_name AS theme_group_name
              FROM market_theme_observation_items i JOIN market_themes t ON t.id=i.theme_id
              LEFT JOIN market_themes p ON p.id=t.parent_theme_id WHERE i.run_id=:run_id
             ORDER BY i.observation_rank IS NULL,i.observation_rank,t.theme_name
        """), {"run_id": run["id"]}).mappings().all()]
        validation_rows = [dict(row) for row in self.db.execute(text("""
            SELECT theme_id,calculation_mode,observation_score,actual_rank
              FROM market_theme_observation_validation_samples
             WHERE target_date=:target_date
        """), {"target_date": target_date}).mappings().all()]
        validation_by_theme: dict[int, dict[str, dict[str, Any]]] = {}
        for validation_row in validation_rows:
            validation_by_theme.setdefault(int(validation_row["theme_id"]), {})[str(validation_row["calculation_mode"])] = validation_row
        actual_universe_count = int(self.db.execute(text("""
            SELECT COUNT(*) FROM market_theme_daily_returns
             WHERE return_date=:target_date AND avg_change_rate IS NOT NULL
        """), {"target_date": target_date}).scalar() or 0)
        official_mode = str(run.get("calculation_mode") or "CURRENT_MARKET_DATA")
        for item in items:
            samples = validation_by_theme.get(int(item["theme_id"]), {})
            official_sample = samples.get(official_mode)
            actual_rank = item.get("actual_rank")
            if actual_rank is None and official_sample is not None:
                actual_rank = official_sample.get("actual_rank")
            actual_strength = self.actual_relative_strength(int(actual_rank) if actual_rank is not None else None, actual_universe_count)
            predicted_score = item.get("relative_strength_score")
            item["actual_rank"] = actual_rank
            item["actual_relative_strength"] = actual_strength
            item["relative_strength_gap"] = self.relative_strength_gap(float(predicted_score) if predicted_score is not None else None, actual_strength)
            item["current_score"] = samples.get("CURRENT_MARKET_DATA", {}).get("observation_score")
            item["refreshed_score"] = samples.get("REFRESHED_MARKET_DATA", {}).get("observation_score")
        metrics_row = self.db.execute(text("SELECT * FROM market_theme_observation_metrics WHERE run_id=:run_id"), {"run_id": run["id"]}).mappings().first()
        return MarketThemeObservationResponse(
            status=str(run["status"]), data_cutoff_date=str(run["data_cutoff_date"]),
            default_target_date=self.next_weekday(str(run["data_cutoff_date"])), run=run, items=items,
            metrics=dict(metrics_row) if metrics_row else None, actual_universe_count=actual_universe_count or None,
            market_indicator_latest_refreshed_at=self._latest_market_refresh_at(),
        )

    def latest(self) -> MarketThemeObservationResponse:
        target = self.db.execute(text("SELECT target_date FROM market_theme_observation_runs ORDER BY target_date DESC,calculated_at DESC LIMIT 1")).scalar()
        if target:
            return self.get(str(target))
        cutoff = self._cutoff()
        return MarketThemeObservationResponse(status="DRAFT", data_cutoff_date=cutoff, default_target_date=self.next_weekday(cutoff), market_indicator_latest_refreshed_at=self._latest_market_refresh_at())

    def calculate(
        self,
        target_date: str,
        *,
        calculation_mode: str = "CURRENT_MARKET_DATA",
        market_refresh_requested: bool = False,
        market_refresh_status: str = "NOT_REQUESTED",
        market_indicator_refreshed_at: str | None = None,
        market_indicator_updated_count: int | None = None,
        market_indicator_failed_count: int | None = None,
        market_collection_run_id: int | None = None,
    ) -> MarketThemeObservationResponse:
        cutoff = self._cutoff()
        if date.fromisoformat(target_date) <= date.fromisoformat(cutoff) or date.fromisoformat(target_date).weekday() >= 5:
            raise HTTPException(status_code=422, detail="예측 대상일은 데이터 기준일 이후의 평일이어야 합니다.")
        calculated_at = datetime.now().isoformat(timespec="seconds")
        self.db.expire_all()
        rows = MarketThemeObservationFeatureService(self.db).build_for_date(cutoff, target_date, operational_asof_at=calculated_at)
        if not rows:
            raise HTTPException(status_code=409, detail="관찰 유니버스 품질 Gate를 통과한 테마가 없습니다.")
        now = calculated_at
        market_data_asof_at = self._market_data_asof_at()
        existing = self._run(target_date)
        if existing:
            run_id = int(existing["id"])
            self.db.execute(text("""
                UPDATE market_theme_observation_runs SET data_cutoff_date=:cutoff,status='PREDICTED',method='OBSERVATION_RULE',
                       model_version=NULL,feature_version=:feature,display_mode='SCORE',calculated_at=:now,evaluated_at=NULL,
                       calculation_mode=:mode,market_refresh_requested=:requested,market_refresh_status=:refresh_status,
                       market_indicator_refreshed_at=:refreshed_at,market_indicator_data_asof_at=:data_asof,
                       market_indicator_updated_count=:updated_count,market_indicator_failed_count=:failed_count,
                       market_collection_run_id=:collection_run_id,revision_count=revision_count+1,updated_at=:now
                 WHERE id=:id
            """), {"cutoff": cutoff, "feature": OBSERVATION_FEATURE_VERSION, "now": now, "id": run_id,
                    "mode": calculation_mode, "requested": int(market_refresh_requested), "refresh_status": market_refresh_status,
                    "refreshed_at": market_indicator_refreshed_at, "data_asof": market_data_asof_at,
                    "updated_count": market_indicator_updated_count, "failed_count": market_indicator_failed_count,
                    "collection_run_id": market_collection_run_id})
            self.db.execute(text("DELETE FROM market_theme_observation_metrics WHERE run_id=:id"), {"id": run_id})
            self.db.execute(text("DELETE FROM market_theme_observation_items WHERE run_id=:id"), {"id": run_id})
        else:
            result = self.db.execute(text("""
                INSERT INTO market_theme_observation_runs
                (target_date,data_cutoff_date,status,method,model_version,feature_version,display_mode,calculated_at,evaluated_at,
                 calculation_mode,market_refresh_requested,market_refresh_status,market_indicator_refreshed_at,
                 market_indicator_data_asof_at,market_indicator_updated_count,market_indicator_failed_count,market_collection_run_id,
                 revision_count,created_at,updated_at)
                VALUES (:target,:cutoff,'PREDICTED','OBSERVATION_RULE',NULL,:feature,'SCORE',:now,NULL,:mode,:requested,
                        :refresh_status,:refreshed_at,:data_asof,:updated_count,:failed_count,:collection_run_id,0,:now,:now)
            """), {"target": target_date, "cutoff": cutoff, "feature": OBSERVATION_FEATURE_VERSION, "now": now,
                    "mode": calculation_mode, "requested": int(market_refresh_requested), "refresh_status": market_refresh_status,
                    "refreshed_at": market_indicator_refreshed_at, "data_asof": market_data_asof_at,
                    "updated_count": market_indicator_updated_count, "failed_count": market_indicator_failed_count,
                    "collection_run_id": market_collection_run_id})
            run_id = int(result.lastrowid or 0)
        ranked = sorted(rows, key=lambda row: (-row.observation_rule_score, row.theme_name))
        payloads = []
        for rank, row in enumerate(ranked, 1):
            value = row.values
            payloads.append({
                "run_id": run_id, "theme_id": row.theme_id, "rank": rank, "score": round(row.observation_rule_score, 4),
                "status": row.status_code, "confidence": row.confidence_level, "coverage": row.data_coverage_rate,
                "base": value.get("base_change_rate"), "price": value.get("price_score"), "flow": value.get("flow_score"),
                "breadth": value.get("breadth_score"), "liquidity": value.get("liquidity_score"),
                "technical": value.get("technical_score"), "market": value.get("market_environment_score"),
                "penalty": value.get("penalty_score") or 0, "now": now,
            })
        self.db.execute(text("""
            INSERT INTO market_theme_observation_items
            (run_id,theme_id,observation_rank,relative_strength_probability,relative_strength_score,top20_probability,
             status_code,confidence_level,data_coverage_rate,base_change_rate,price_score,flow_score,breadth_score,
             liquidity_score,technical_score,market_environment_score,penalty_score,evaluation_status,created_at,updated_at)
            VALUES (:run_id,:theme_id,:rank,NULL,:score,NULL,:status,:confidence,:coverage,:base,:price,:flow,:breadth,
                    :liquidity,:technical,:market,:penalty,'PENDING',:now,:now)
        """), payloads)
        MarketThemeObservationValidationService(self.db).snapshot(
            target_date,
            calculation_mode,
            payloads,
            model_version=None,
            rule_version=OBSERVATION_RULE_VERSION,
        )
        self.db.commit()
        return self.get(target_date)

    def calculate_with_market_option(self, target_date: str, *, refresh_market_indicators: bool = False) -> MarketThemeObservationResponse:
        validation_service = MarketThemeObservationValidationService(self.db)
        try:
            pre_validation = validation_service.auto_validate_latest_actual()
        except Exception:
            self.db.rollback()
            pre_validation = {
                "status": "AUTO_VALIDATION_FAILED", "target_date": None, "modes": [], "quality_status": None,
                "message": "최근 관찰결과 자동검증에 실패했습니다. D+1 관찰순위는 계속 계산하지만 검증 상태를 확인해 주세요.",
                "diagnostic_status": None,
            }
        if not refresh_market_indicators:
            response = self.calculate(target_date, calculation_mode="CURRENT_MARKET_DATA")
            return self._attach_pre_validation(response, pre_validation)
        refresh_result = MarketDataCollectionService(self.db).collect(SimpleNamespace(
            mode="INCREMENTAL_ALL", items=None, start_date=None, end_date=None,
            triggered_by="THEME_OBSERVATION_PHASE5",
        ))
        refresh_status = str(refresh_result.get("status") or "FAILED")
        if refresh_status == "FAILED":
            raise HTTPException(status_code=502, detail={
                "code": "MARKET_REFRESH_FAILED",
                "message": "시장지표 갱신에 실패하여 보정관찰 계산을 중단했습니다.",
                "collection_run_id": refresh_result.get("run_id"),
            })
        normalized_status = "SUCCESS" if refresh_status == "SUCCESS" else "PARTIAL"
        refresh_at = self.db.execute(text("SELECT finished_at FROM market_data_collection_runs WHERE id=:id"), {"id": refresh_result["run_id"]}).scalar()
        try:
            response = self.calculate(
                target_date, calculation_mode="REFRESHED_MARKET_DATA", market_refresh_requested=True,
                market_refresh_status=normalized_status, market_indicator_refreshed_at=self._sqlite_utc_to_local(refresh_at) or datetime.now().isoformat(timespec="seconds"),
                market_indicator_updated_count=int(refresh_result.get("inserted_count") or 0) + int(refresh_result.get("updated_count") or 0),
                market_indicator_failed_count=int(refresh_result.get("failed_count") or 0), market_collection_run_id=int(refresh_result["run_id"]),
            )
        except Exception as exc:
            self.db.rollback()
            if isinstance(exc, HTTPException):
                reason = exc.detail
            else:
                reason = str(exc)
            raise HTTPException(status_code=500, detail={
                "code": "OBSERVATION_FAILED_AFTER_MARKET_REFRESH",
                "message": "시장지표 갱신은 완료됐지만 관찰순위 계산에 실패했습니다.",
                "collection_run_id": refresh_result.get("run_id"), "reason": reason,
            }) from exc
        if normalized_status == "PARTIAL":
            response.message = "시장지표 일부 갱신 실패 · 기존값을 포함해 관찰순위를 계산했습니다."
        else:
            response.message = "시장지표 보정관찰 계산을 완료했습니다."
        return self._attach_pre_validation(response, pre_validation)

    @staticmethod
    def _attach_pre_validation(response: MarketThemeObservationResponse, summary: dict[str, Any]) -> MarketThemeObservationResponse:
        if isinstance(response, dict):
            response.update({
                "pre_validation_status": summary.get("status"),
                "pre_validation_target_date": summary.get("target_date"),
                "pre_validation_modes": list(summary.get("modes") or []),
                "pre_validation_quality_status": summary.get("quality_status"),
                "pre_validation_message": summary.get("message"),
                "diagnostic_status": summary.get("diagnostic_status"),
            })
            return response  # type: ignore[return-value]
        response.pre_validation_status = summary.get("status")
        response.pre_validation_target_date = summary.get("target_date")
        response.pre_validation_modes = list(summary.get("modes") or [])
        response.pre_validation_quality_status = summary.get("quality_status")
        response.pre_validation_message = summary.get("message")
        response.diagnostic_status = summary.get("diagnostic_status")
        return response

    @staticmethod
    def _spearman(predicted: list[int], actual: list[int]) -> float | None:
        if len(predicted) < 2:
            return None
        n = len(predicted)
        return 1 - 6 * sum((p - a) ** 2 for p, a in zip(predicted, actual)) / (n * (n * n - 1))

    def validate(self, target_date: str) -> MarketThemeObservationResponse:
        run = self._run(target_date)
        if not run:
            raise HTTPException(status_code=404, detail="검증할 관찰 우선순위가 없습니다.")
        validation_status = MarketThemeObservationValidationService(self.db).evaluate(target_date)
        if validation_status == "WAITING_ACTUAL":
            response = self.get(target_date)
            response.message = "대상일의 실제 테마등락률이 아직 없어 검증을 대기합니다. 가짜 검증 결과는 생성하지 않았습니다."
            return response
        if validation_status == "NO_SNAPSHOT":
            raise HTTPException(status_code=409, detail="Phase5.5 적용 이후 생성된 검증용 관찰 스냅샷이 없습니다.")
        actual = [dict(row) for row in self.db.execute(text("""
            SELECT theme_id,avg_change_rate FROM market_theme_daily_returns
             WHERE return_date=:target AND avg_change_rate IS NOT NULL ORDER BY avg_change_rate DESC,theme_id ASC
        """), {"target": target_date}).mappings().all()]
        if not actual:
            raise HTTPException(status_code=409, detail="대상일 실적 데이터가 아직 없어 검증할 수 없습니다.")
        actual_rank = {int(row["theme_id"]): index + 1 for index, row in enumerate(actual)}
        actual_return = {int(row["theme_id"]): float(row["avg_change_rate"]) for row in actual}
        top_count = max(1, math.ceil(len(actual) * .20))
        items = [dict(row) for row in self.db.execute(text("SELECT * FROM market_theme_observation_items WHERE run_id=:id ORDER BY observation_rank"), {"id": run["id"]}).mappings().all()]
        evaluated = [item for item in items if int(item["theme_id"]) in actual_rank]
        predicted_top = {int(item["theme_id"]) for item in evaluated[:top_count]}
        actual_top = {theme_id for theme_id, rank in actual_rank.items() if rank <= top_count}
        hits = len(predicted_top & actual_top)
        precision = hits / len(predicted_top) if predicted_top else None
        recall = hits / len(actual_top) if actual_top else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else 0.0
        p5_ids = {int(item["theme_id"]) for item in evaluated[:5]}
        p5 = len(p5_ids & actual_top) / len(p5_ids) if p5_ids else None
        dcg = sum((1 if int(item["theme_id"]) in actual_top else 0) / math.log2(index + 2) for index, item in enumerate(evaluated[:5]))
        idcg = sum(1 / math.log2(index + 2) for index in range(min(5, len(actual_top))))
        ndcg = dcg / idcg if idcg else None
        predicted_ranks, actual_ranks, rank_errors = [], [], []
        for item in evaluated:
            theme_id = int(item["theme_id"]); p_rank = int(item["observation_rank"]); a_rank = actual_rank[theme_id]
            predicted_ranks.append(p_rank); actual_ranks.append(a_rank); rank_errors.append(abs(p_rank - a_rank))
            probability = item["relative_strength_probability"]
            self.db.execute(text("""
                UPDATE market_theme_observation_items SET actual_change_rate=:actual_return,actual_rank=:actual_rank,
                       actual_top20=:actual_top,rank_gap=:rank_gap,probability_error=:probability_error,
                       evaluation_status='EVALUATED',updated_at=CURRENT_TIMESTAMP WHERE id=:id
            """), {"actual_return": actual_return[theme_id], "actual_rank": a_rank, "actual_top": int(theme_id in actual_top),
                    "rank_gap": p_rank - a_rank, "probability_error": None if probability is None else float(probability) / 100 - int(theme_id in actual_top), "id": item["id"]})
        now = datetime.now().isoformat(timespec="seconds")
        self.db.execute(text("DELETE FROM market_theme_observation_metrics WHERE run_id=:id"), {"id": run["id"]})
        self.db.execute(text("""
            INSERT INTO market_theme_observation_metrics
            (run_id,theme_count,evaluable_theme_count,precision_top20,recall_top20,f1_top20,precision_at_5,ndcg_at_5,
             spearman_rank_correlation,mean_rank_error,brier_score,log_loss,calibration_error,evaluation_status,evaluated_at,created_at,updated_at)
            VALUES (:run_id,:theme_count,:evaluated,:precision,:recall,:f1,:p5,:ndcg,:spearman,:rank_error,NULL,NULL,NULL,:evaluation_status,:now,:now,:now)
        """), {"run_id": run["id"], "theme_count": len(items), "evaluated": len(evaluated), "precision": precision,
                "recall": recall, "f1": f1, "p5": p5, "ndcg": ndcg, "spearman": self._spearman(predicted_ranks, actual_ranks),
                "rank_error": sum(rank_errors) / len(rank_errors) if rank_errors else None,
                "evaluation_status": "QUALIFIED" if validation_status == "EVALUATED" else validation_status, "now": now})
        self.db.execute(text("UPDATE market_theme_observation_runs SET status='EVALUATED',evaluated_at=:now,updated_at=:now WHERE id=:id"), {"now": now, "id": run["id"]})
        self.db.commit()
        return self.get(target_date)

    def prediction_for_cutoff(self, cutoff: str) -> dict[str, Any]:
        run = self.db.execute(text("""
            SELECT * FROM market_theme_observation_runs WHERE data_cutoff_date=:cutoff
             ORDER BY calculated_at DESC,id DESC LIMIT 1
        """), {"cutoff": cutoff}).mappings().first()
        if not run:
            return {"run": None, "values": {}, "ranks": {}, "mode": None, "method": None, "feature_version": None, "calculated_at": None}
        values: dict[int, float | None] = {}; ranks: dict[int, int | None] = {}
        for item in self.db.execute(text("SELECT theme_id,observation_rank,relative_strength_probability,relative_strength_score FROM market_theme_observation_items WHERE run_id=:id"), {"id": run["id"]}).mappings().all():
            theme_id = int(item["theme_id"]); ranks[theme_id] = int(item["observation_rank"]) if item["observation_rank"] is not None else None
            raw = item["relative_strength_probability"] if run["display_mode"] == "PROBABILITY" else item["relative_strength_score"]
            values[theme_id] = float(raw) if raw is not None else None
        return {"run": dict(run), "values": values, "ranks": ranks, "mode": str(run["display_mode"]),
                "method": str(run["method"]), "feature_version": str(run["feature_version"]), "calculated_at": str(run["calculated_at"])}
    @staticmethod
    def _sqlite_utc_to_local(value: Any) -> str | None:
        if not value:
            return None
        raw = str(value)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone().replace(tzinfo=None).isoformat(timespec="seconds")
            return (parsed + timedelta(hours=9)).isoformat(timespec="seconds")
        except ValueError:
            return raw
