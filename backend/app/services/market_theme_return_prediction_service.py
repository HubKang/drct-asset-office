from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import logging
import math
import statistics
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.schemas.market_theme_return_prediction_schema import MarketThemeReturnPredictionResponse

logger = logging.getLogger(__name__)


class MarketThemeReturnPredictionService:
    """RULE_V1 prediction and validation using only durable aggregate fields."""

    STAGE = "PREMARKET"
    HORIZON = "NEXT_SELECTED_DATE"
    METHOD = "RULE"

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _round(value: float | None, digits: int = 4) -> float | None:
        return None if value is None or not math.isfinite(value) else round(value, digits)

    @staticmethod
    def _parse_date(value: str, field: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field}는 YYYY-MM-DD 형식이어야 합니다.") from exc

    @staticmethod
    def next_weekday(value: str) -> str:
        result = date.fromisoformat(value) + timedelta(days=1)
        while result.weekday() >= 5:
            result += timedelta(days=1)
        return result.isoformat()

    @staticmethod
    def _percentiles(values: dict[int, float | None], *, neutral: float | None = None) -> dict[int, float | None]:
        valid = sorted((float(value), key) for key, value in values.items() if value is not None and math.isfinite(float(value)))
        if not valid:
            return {key: neutral for key in values}
        if len(valid) == 1:
            return {key: (50.0 if value is not None else neutral) for key, value in values.items()}
        result: dict[int, float | None] = {key: neutral for key in values}
        index = 0
        while index < len(valid):
            end = index
            while end + 1 < len(valid) and valid[end + 1][0] == valid[index][0]:
                end += 1
            percentile = ((index + end) / 2) / (len(valid) - 1) * 100
            for _, key in valid[index : end + 1]:
                result[key] = round(percentile, 4)
            index = end + 1
        return result

    def _cutoff(self) -> tuple[str, str | None]:
        row = self.db.execute(text("""
            SELECT MAX(return_date) AS cutoff, MAX(last_refreshed_at) AS cutoff_at
              FROM market_theme_daily_returns WHERE avg_change_rate IS NOT NULL
        """)).mappings().one()
        if not row["cutoff"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="예측에 사용할 테마등락률 데이터가 없습니다.")
        return str(row["cutoff"]), str(row["cutoff_at"]) if row["cutoff_at"] else None

    def _parameters(self) -> tuple[str, dict[str, float]]:
        rows = self.db.execute(text("""
            SELECT rs.rule_version, p.parameter_code, p.parameter_value
              FROM market_theme_return_prediction_rule_sets rs
              JOIN market_theme_return_prediction_rule_parameters p ON p.rule_set_id=rs.id
             WHERE rs.is_active=1 AND rs.status='ACTIVE'
             ORDER BY rs.updated_at DESC, rs.id DESC
        """)).mappings().all()
        if not rows:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="활성 예측 규칙이 없습니다.")
        version = str(rows[0]["rule_version"])
        return version, {str(row["parameter_code"]): float(row["parameter_value"]) for row in rows if row["rule_version"] == version}

    def _validate_target(self, target_date: str, cutoff: str, *, allow_actual: bool = False) -> None:
        target = self._parse_date(target_date, "target_date")
        if target.weekday() >= 5:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="토요일과 일요일은 예측 대상일로 선택할 수 없습니다.")
        if target <= self._parse_date(cutoff, "data_cutoff_date"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="예측 대상일은 데이터 기준일보다 이후여야 합니다.")
        if not allow_actual:
            exists = self.db.execute(text("SELECT 1 FROM market_theme_daily_returns WHERE return_date=:day AND avg_change_rate IS NOT NULL LIMIT 1"), {"day": target_date}).scalar()
            if exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="실제 테마등락률이 이미 존재하는 날짜에는 공식 예측을 실행할 수 없습니다.")

    def _load_features(self, cutoff: str) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]], dict[int, list[dict[str, Any]]], dict[int, float]]:
        themes = [dict(row) for row in self.db.execute(text("""
            SELECT t.id AS theme_id, t.theme_name, t.parent_theme_id AS theme_group_id, p.theme_name AS theme_group_name,
                   t.sort_order
              FROM market_themes t LEFT JOIN market_themes p ON p.id=t.parent_theme_id
             WHERE t.is_active=1 AND COALESCE(t.theme_level, 'THEME') <> 'THEME_GROUP'
             ORDER BY t.sort_order, t.theme_name, t.id
        """)).mappings().all()]
        returns = self.db.execute(text("""
            SELECT r.theme_id, r.return_date, r.avg_change_rate, r.stock_count, r.success_stock_count,
                   r.rising_stock_count, r.falling_stock_count, r.total_trading_value_100m
              FROM market_theme_daily_returns r JOIN market_themes t ON t.id=r.theme_id
             WHERE t.is_active=1 AND r.return_date <= :cutoff AND r.avg_change_rate IS NOT NULL
             ORDER BY r.theme_id, r.return_date DESC
        """), {"cutoff": cutoff}).mappings().all()
        returns_by_theme: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in returns:
            bucket = returns_by_theme[int(row["theme_id"])]
            if len(bucket) < 20:
                bucket.append(dict(row))
        flows = self.db.execute(text("""
            SELECT mts.theme_id, f.flow_date,
                   SUM(CASE WHEN f.foreign_net_amount IS NULL OR f.institution_net_amount IS NULL THEN NULL ELSE f.foreign_net_amount + f.institution_net_amount END) AS joint_net,
                   SUM(f.program_net_amount) AS program_net,
                   SUM(CASE WHEN COALESCE(f.foreign_net_amount,0)+COALESCE(f.institution_net_amount,0)>0 THEN 1 ELSE 0 END) AS positive_count,
                   COUNT(CASE WHEN f.foreign_net_amount IS NOT NULL OR f.institution_net_amount IS NOT NULL THEN 1 END) AS flow_count,
                   COUNT(*) AS linked_count
              FROM market_theme_stocks mts JOIN market_themes t ON t.id=mts.theme_id
              JOIN stock_investor_flows f ON f.stock_id=mts.stock_id
             WHERE mts.is_active=1 AND t.is_active=1 AND f.flow_date<=:cutoff
             GROUP BY mts.theme_id, f.flow_date ORDER BY mts.theme_id, f.flow_date DESC
        """), {"cutoff": cutoff}).mappings().all()
        flows_by_theme: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in flows:
            bucket = flows_by_theme[int(row["theme_id"])]
            if len(bucket) < 5:
                bucket.append(dict(row))
        concentrations = {int(row["theme_id"]): float(row["ratio"] or 0) for row in self.db.execute(text("""
            SELECT theme_id, CASE WHEN SUM(COALESCE(trading_value,0))>0
                   THEN MAX(COALESCE(trading_value,0))*1.0/SUM(COALESCE(trading_value,0)) ELSE NULL END AS ratio
              FROM market_theme_stock_daily_returns WHERE return_date=:cutoff GROUP BY theme_id
        """), {"cutoff": cutoff}).mappings().all()}
        return themes, returns_by_theme, flows_by_theme, concentrations

    def _calculate(self, cutoff: str, parameters: dict[str, float]) -> list[dict[str, Any]]:
        themes, returns_by_theme, flows_by_theme, concentrations = self._load_features(cutoff)
        raw: dict[int, dict[str, Any]] = {}
        all_daily_means: dict[str, list[float]] = defaultdict(list)
        for rows in returns_by_theme.values():
            for row in rows:
                all_daily_means[str(row["return_date"])].append(float(row["avg_change_rate"]))
        daily_cross = [statistics.pstdev(values) for values in all_daily_means.values() if len(values) >= 2]
        recent_mean = statistics.mean(value for values in all_daily_means.values() for value in values) if all_daily_means else 0.0
        recent_volatility = statistics.mean(daily_cross) if daily_cross else 1.0
        recent_volatility = max(recent_volatility, 0.25)

        for theme in themes:
            theme_id = int(theme["theme_id"])
            rows = returns_by_theme.get(theme_id, [])
            chronological = list(reversed(rows))
            rates = [float(row["avg_change_rate"]) for row in chronological]
            latest = rows[0] if rows else None
            base = float(latest["avg_change_rate"]) if latest else None
            avg3 = statistics.mean(rates[-3:]) if len(rates) >= 3 else None
            avg5 = statistics.mean(rates[-5:]) if len(rates) >= 5 else None
            momentum10 = sum(rates[-10:]) if len(rates) >= 10 else None
            acceleration = avg3 - statistics.mean(rates[-6:-3]) if len(rates) >= 6 and avg3 is not None else None
            price_raw_values = [value for value in (base, avg3, avg5, (momentum10 / 10 if momentum10 is not None else None), acceleration) if value is not None]
            price_raw = statistics.mean(price_raw_values) if price_raw_values else None
            flow_rows = flows_by_theme.get(theme_id, [])
            joint_values = [float(row["joint_net"]) for row in flow_rows if row["joint_net"] is not None]
            program_values = [float(row["program_net"]) for row in flow_rows if row["program_net"] is not None]
            trading = float(latest["total_trading_value_100m"] or 0) * 100_000_000 if latest else 0
            flow_net = sum(joint_values) + (sum(program_values) * 0.25 if program_values else 0)
            flow_raw = flow_net / trading if joint_values and trading > 0 else None
            price_breadth = float(latest["rising_stock_count"] or 0) / int(latest["success_stock_count"] or 1) if latest and latest["success_stock_count"] else None
            flow_breadths = [float(row["positive_count"] or 0) / int(row["flow_count"] or 1) for row in flow_rows if row["flow_count"]]
            breadth_raw = statistics.mean([value for value in ([price_breadth] + flow_breadths) if value is not None]) if price_breadth is not None or flow_breadths else None
            coverage = float(latest["success_stock_count"] or 0) / int(latest["stock_count"] or 1) if latest and latest["stock_count"] else 0.0
            avg_liquidity = statistics.mean(float(row["total_trading_value_100m"] or 0) for row in rows[:5]) if rows else None
            liquidity_raw = (float(latest["total_trading_value_100m"] or 0) / avg_liquidity) if latest and avg_liquidity else None
            raw[theme_id] = {**theme, "base": base, "price_raw": price_raw, "flow_raw": flow_raw, "breadth_raw": breadth_raw,
                             "liquidity_raw": liquidity_raw, "coverage": coverage, "concentration": concentrations.get(theme_id), "rates": rates}

        price_pct = self._percentiles({key: row["price_raw"] for key, row in raw.items()})
        flow_pct = self._percentiles({key: row["flow_raw"] for key, row in raw.items()})
        breadth_pct = self._percentiles({key: row["breadth_raw"] for key, row in raw.items()})
        liquidity_pct = self._percentiles({key: row["liquidity_raw"] for key, row in raw.items()})
        result: list[dict[str, Any]] = []
        min_coverage = parameters.get("MIN_DATA_COVERAGE", 0.7)
        for theme_id, row in raw.items():
            price_score, flow_score = price_pct[theme_id], flow_pct[theme_id]
            breadth_score, liquidity_score = breadth_pct[theme_id], liquidity_pct[theme_id]
            if price_score is None or flow_score is None:
                alignment_score = None
            else:
                agreement = 100 - abs(price_score - flow_score)
                alignment_score = max(0.0, min(100.0, agreement + ((price_score + flow_score - 100) * 0.25)))
            penalty = 0.0
            base = row["base"]
            if base is not None and base > 5:
                penalty -= min(parameters.get("OVERHEAT_PENALTY_MAX", 15), (base - 5) * 1.5)
            concentration = row["concentration"]
            if concentration is not None and concentration > 0.4:
                penalty -= min(parameters.get("CONCENTRATION_PENALTY_MAX", 10), (concentration - 0.4) * 20)
            if row["coverage"] < min_coverage:
                penalty -= parameters.get("LOW_COVERAGE_PENALTY_MAX", 20) * (min_coverage - row["coverage"]) / max(min_coverage, 0.01)
            if price_score is not None and flow_score is not None and price_score >= 60 and flow_score <= 40:
                penalty -= parameters.get("FLOW_DIVERGENCE_PENALTY_MAX", 10) * (price_score - flow_score) / 100
            scores = {
                "price_score": price_score, "flow_score": flow_score, "breadth_score": breadth_score,
                "alignment_score": alignment_score, "liquidity_score": liquidity_score,
                "market_environment_score": 50.0,
            }
            weighted = 0.0
            used_weight = 0.0
            for code, key in (("PRICE_WEIGHT", "price_score"), ("FLOW_WEIGHT", "flow_score"), ("BREADTH_WEIGHT", "breadth_score"),
                              ("ALIGNMENT_WEIGHT", "alignment_score"), ("LIQUIDITY_WEIGHT", "liquidity_score"),
                              ("MARKET_ENVIRONMENT_WEIGHT", "market_environment_score")):
                if scores[key] is not None:
                    weight = parameters.get(code, 0)
                    weighted += float(scores[key]) * weight
                    used_weight += weight
            total_score = weighted / used_weight + penalty if used_weight else None
            predicted = None
            if total_score is not None:
                signal = max(-1.0, min(1.0, (total_score - 50) / 50))
                predicted = recent_mean + signal * recent_volatility * parameters.get("PREDICTION_SCALE", 1.0) + parameters.get("PREDICTION_BIAS", 0.0)
                predicted = max(parameters.get("PREDICTION_MIN", -20), min(parameters.get("PREDICTION_MAX", 20), predicted))
            result.append({**row, **scores, "penalty_score": self._round(penalty), "prediction_score": self._round(total_score),
                           "predicted_change_rate": self._round(predicted), "predicted_rank": None,
                           "evaluation_status": "NOT_EVALUABLE" if row["coverage"] < min_coverage or predicted is None else "NOT_EVALUATED"})
        ranked = sorted((row for row in result if row["evaluation_status"] != "NOT_EVALUABLE"),
                        key=lambda row: (-float(row["predicted_change_rate"]), -float(row["prediction_score"]), str(row["theme_name"]), int(row["theme_id"])))
        for rank, row in enumerate(ranked, 1):
            row["predicted_rank"] = rank
        return result

    def predict(self, target_date: str) -> MarketThemeReturnPredictionResponse:
        cutoff, cutoff_at = self._cutoff()
        existing = self.db.execute(text("""
            SELECT * FROM market_theme_return_prediction_runs
             WHERE target_date=:target AND prediction_stage=:stage AND prediction_horizon=:horizon
        """), {"target": target_date, "stage": self.STAGE, "horizon": self.HORIZON}).mappings().first()
        if existing and existing["status"] == "EVALUATED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="검증 완료된 예측은 수정할 수 없습니다.")
        self._validate_target(target_date, cutoff)
        version, parameters = self._parameters()
        items = self._calculate(cutoff, parameters)
        if not items:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="예측할 활성 테마가 없습니다.")
        timestamp = now_kst()
        try:
            self.db.execute(text("""
                INSERT INTO market_theme_return_prediction_runs
                (target_date,data_cutoff_date,data_cutoff_at,prediction_stage,prediction_horizon,official_method,status,
                 revision_count,rule_version,first_predicted_at,last_predicted_at,created_at,updated_at)
                VALUES (:target,:cutoff,:cutoff_at,:stage,:horizon,'RULE','PREDICTED',1,:version,:now,:now,:now,:now)
                ON CONFLICT(target_date,prediction_stage,prediction_horizon) DO UPDATE SET
                  data_cutoff_date=excluded.data_cutoff_date,data_cutoff_at=excluded.data_cutoff_at,status='PREDICTED',
                  revision_count=market_theme_return_prediction_runs.revision_count+1,rule_version=excluded.rule_version,
                  last_predicted_at=excluded.last_predicted_at,updated_at=excluded.updated_at
            """), {"target": target_date, "cutoff": cutoff, "cutoff_at": cutoff_at, "stage": self.STAGE, "horizon": self.HORIZON, "version": version, "now": timestamp})
            run_id = int(self.db.execute(text("""
                SELECT id FROM market_theme_return_prediction_runs WHERE target_date=:target AND prediction_stage=:stage AND prediction_horizon=:horizon
            """), {"target": target_date, "stage": self.STAGE, "horizon": self.HORIZON}).scalar_one())
            self.db.execute(text("DELETE FROM market_theme_return_prediction_items WHERE run_id=:run_id AND prediction_method='RULE'"), {"run_id": run_id})
            self.db.execute(text("""
                INSERT INTO market_theme_return_prediction_items
                (run_id,theme_id,prediction_method,is_official,base_change_rate,predicted_change_rate,prediction_score,predicted_rank,
                 price_score,flow_score,breadth_score,alignment_score,liquidity_score,market_environment_score,penalty_score,
                 data_coverage_rate,evaluation_status,created_at,updated_at)
                VALUES (:run_id,:theme_id,'RULE',1,:base,:predicted_change_rate,:prediction_score,:predicted_rank,:price_score,
                        :flow_score,:breadth_score,:alignment_score,:liquidity_score,:market_environment_score,:penalty_score,
                        :coverage,:evaluation_status,:now,:now)
            """), [{**row, "run_id": run_id, "now": timestamp} for row in items])
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        try:
            from backend.app.services.market_theme_return_ml_service import MarketThemeReturnMLService
            MarketThemeReturnMLService(self.db).predict_shadow(target_date, require_model=False)
        except Exception:
            logger.exception("ML shadow inference failed after official RULE prediction target_date=%s", target_date)
        return self.get(target_date)

    @staticmethod
    def _precision(predicted: list[int], actual: list[int], k: int) -> float | None:
        denominator = min(k, len(predicted), len(actual))
        return None if denominator == 0 else len(set(predicted[:denominator]) & set(actual[:denominator])) / denominator

    @staticmethod
    def _ndcg(predicted: list[int], actual: list[int], k: int = 5) -> float | None:
        if not predicted or not actual:
            return None
        actual_rank = {theme_id: rank for rank, theme_id in enumerate(actual, 1)}
        relevance = {theme_id: max(0, len(actual) - rank + 1) for theme_id, rank in actual_rank.items()}
        dcg = sum((2 ** relevance.get(theme_id, 0) - 1) / math.log2(index + 2) for index, theme_id in enumerate(predicted[:k]))
        ideal = sum((2 ** relevance[theme_id] - 1) / math.log2(index + 2) for index, theme_id in enumerate(actual[:k]))
        return dcg / ideal if ideal else None

    def validate(self, target_date: str) -> MarketThemeReturnPredictionResponse:
        run = self._run_row(target_date)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 대상일의 예측을 찾을 수 없습니다.")
        actual_rows = self.db.execute(text("""
            SELECT theme_id, avg_change_rate FROM market_theme_daily_returns
             WHERE return_date=:target AND avg_change_rate IS NOT NULL
        """), {"target": target_date}).mappings().all()
        if not actual_rows:
            self.db.execute(text("UPDATE market_theme_return_prediction_runs SET status='WAITING_ACTUAL',updated_at=:now WHERE id=:id"), {"now": now_kst(), "id": run["id"]})
            self.db.commit()
            response = self.get(target_date)
            response.status = "WAITING_ACTUAL"
            response.message = "선택한 대상일의 실제 테마등락률이 아직 수집되지 않았습니다."
            return response
        actual_sorted = sorted(((int(row["theme_id"]), float(row["avg_change_rate"])) for row in actual_rows), key=lambda item: (-item[1], item[0]))
        actual = {theme_id: value for theme_id, value in actual_sorted}
        actual_rank = {theme_id: rank for rank, (theme_id, _) in enumerate(actual_sorted, 1)}
        prediction_rows = self.db.execute(text("SELECT * FROM market_theme_return_prediction_items WHERE run_id=:run_id AND is_official=1"), {"run_id": run["id"]}).mappings().all()
        timestamp = now_kst()
        neutral_band = self._parameters()[1].get("DIRECTION_NEUTRAL_BAND", 0.5)
        evaluated: list[dict[str, Any]] = []
        for row in prediction_rows:
            theme_id = int(row["theme_id"])
            predicted = row["predicted_change_rate"]
            if theme_id not in actual or predicted is None or row["predicted_rank"] is None:
                self.db.execute(text("UPDATE market_theme_return_prediction_items SET evaluation_status='NOT_EVALUABLE',evaluated_at=:now,updated_at=:now WHERE id=:id"), {"now": timestamp, "id": row["id"]})
                continue
            predicted = float(predicted)
            actual_value = actual[theme_id]
            gap = actual_value - predicted
            absolute = abs(gap)
            baseline = abs(actual_value - float(row["base_change_rate"])) if row["base_change_rate"] is not None else None
            def direction(value: float) -> int:
                return 0 if abs(value) <= neutral_band else (1 if value > 0 else -1)
            payload = {"id": row["id"], "actual": actual_value, "actual_rank": actual_rank[theme_id], "gap": gap, "absolute": absolute,
                       "rank_gap": actual_rank[theme_id] - int(row["predicted_rank"]), "direction_hit": int(direction(predicted) == direction(actual_value)),
                       "baseline": baseline, "effect": baseline - absolute if baseline is not None else None, "now": timestamp,
                       "theme_id": theme_id, "predicted_rank": int(row["predicted_rank"])}
            evaluated.append(payload)
            self.db.execute(text("""
                UPDATE market_theme_return_prediction_items SET actual_change_rate=:actual,actual_rank=:actual_rank,signed_gap=:gap,
                absolute_gap=:absolute,rank_gap=:rank_gap,direction_hit=:direction_hit,baseline_absolute_error=:baseline,
                prediction_effect=:effect,evaluation_status='COMPLETE',evaluated_at=:now,updated_at=:now WHERE id=:id
            """), payload)
        if not evaluated:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="예측과 연결할 수 있는 실제 테마등락률이 없습니다.")
        predicted_order = [row["theme_id"] for row in sorted(evaluated, key=lambda row: row["predicted_rank"])]
        actual_order = [theme_id for theme_id, _ in actual_sorted if theme_id in set(predicted_order)]
        gaps = [row["gap"] for row in evaluated]
        absolutes = [row["absolute"] for row in evaluated]
        baselines = [row["baseline"] for row in evaluated if row["baseline"] is not None]
        n = len(evaluated)
        rank_d2 = sum((row["actual_rank"] - row["predicted_rank"]) ** 2 for row in evaluated)
        spearman = 1 - (6 * rank_d2) / (n * (n * n - 1)) if n > 1 else None
        base_by_theme = {int(row["theme_id"]): (float(row["base_change_rate"]) if row["base_change_rate"] is not None else None) for row in prediction_rows}
        baseline_order = [row["theme_id"] for row in sorted(
            evaluated,
            key=lambda row: (base_by_theme[row["theme_id"]] is None, -(base_by_theme[row["theme_id"]] or 0), row["theme_id"]),
        )]
        metrics = {
            "run_id": run["id"], "theme_count": len(prediction_rows), "evaluable_theme_count": n,
            "return_mae": statistics.mean(absolutes), "return_rmse": math.sqrt(statistics.mean(value * value for value in gaps)),
            "mean_signed_gap": statistics.mean(gaps), "mean_rank_error": statistics.mean(abs(row["rank_gap"]) for row in evaluated),
            "top1_hit": self._precision(predicted_order, actual_order, 1), "precision_at_3": self._precision(predicted_order, actual_order, 3),
            "precision_at_5": self._precision(predicted_order, actual_order, 5), "precision_at_10": self._precision(predicted_order, actual_order, 10),
            "direction_accuracy": statistics.mean(row["direction_hit"] for row in evaluated), "spearman": spearman,
            "ndcg": self._ndcg(predicted_order, actual_order), "baseline_mae": statistics.mean(baselines) if baselines else None,
            "mae_improvement": (statistics.mean(baselines) - statistics.mean(absolutes)) if baselines else None,
            "baseline_precision": self._precision(baseline_order, actual_order, 5),
            "improved": sum(1 for row in evaluated if row["effect"] is not None and row["effect"] > 0), "now": timestamp,
        }
        self.db.execute(text("""
            INSERT INTO market_theme_return_prediction_metrics
            (run_id,theme_count,evaluable_theme_count,return_mae,return_rmse,mean_signed_gap,mean_rank_error,top1_hit,
             precision_at_3,precision_at_5,precision_at_10,direction_accuracy,spearman_rank_correlation,ndcg_at_5,
             baseline_mae,mae_improvement,baseline_precision_at_5,improved_theme_count,evaluation_status,evaluated_at,created_at,updated_at)
            VALUES (:run_id,:theme_count,:evaluable_theme_count,:return_mae,:return_rmse,:mean_signed_gap,:mean_rank_error,:top1_hit,
             :precision_at_3,:precision_at_5,:precision_at_10,:direction_accuracy,:spearman,:ndcg,:baseline_mae,:mae_improvement,
             :baseline_precision,:improved,'COMPLETE',:now,:now,:now)
            ON CONFLICT(run_id) DO UPDATE SET theme_count=excluded.theme_count,evaluable_theme_count=excluded.evaluable_theme_count,
             return_mae=excluded.return_mae,return_rmse=excluded.return_rmse,mean_signed_gap=excluded.mean_signed_gap,
             mean_rank_error=excluded.mean_rank_error,top1_hit=excluded.top1_hit,precision_at_3=excluded.precision_at_3,
             precision_at_5=excluded.precision_at_5,precision_at_10=excluded.precision_at_10,direction_accuracy=excluded.direction_accuracy,
             spearman_rank_correlation=excluded.spearman_rank_correlation,ndcg_at_5=excluded.ndcg_at_5,baseline_mae=excluded.baseline_mae,
             mae_improvement=excluded.mae_improvement,baseline_precision_at_5=excluded.baseline_precision_at_5,
             improved_theme_count=excluded.improved_theme_count,evaluation_status='COMPLETE',evaluated_at=excluded.evaluated_at,updated_at=excluded.updated_at
        """), metrics)
        self.db.execute(text("UPDATE market_theme_return_prediction_runs SET status='EVALUATED',evaluated_at=:now,updated_at=:now WHERE id=:id"), {"now": timestamp, "id": run["id"]})
        self.db.commit()
        try:
            from backend.app.services.market_theme_return_ml_service import MarketThemeReturnMLService
            MarketThemeReturnMLService(self.db).validate_methods(target_date)
        except Exception:
            logger.exception("ML shadow validation failed without changing RULE result target_date=%s", target_date)
        return self.get(target_date)

    def _run_row(self, target_date: str) -> dict[str, Any] | None:
        row = self.db.execute(text("""
            SELECT * FROM market_theme_return_prediction_runs WHERE target_date=:target
             AND prediction_stage=:stage AND prediction_horizon=:horizon AND status<>'CANCELLED'
             ORDER BY last_predicted_at DESC,id DESC LIMIT 1
        """), {"target": target_date, "stage": self.STAGE, "horizon": self.HORIZON}).mappings().first()
        return dict(row) if row else None

    def _advice(self, metrics: dict[str, Any] | None, items: list[dict[str, Any]]) -> list[dict[str, str]]:
        if not metrics:
            return []
        advice: list[dict[str, str]] = []
        low = [row for row in items if float(row.get("data_coverage_rate") or 0) < 0.7]
        if low:
            advice.append({"code": "LOW_DATA_COVERAGE", "diagnosis": "데이터 완전성 부족", "impact": "높음", "evidence": f"기준 미달 테마 {len(low)}개",
                           "current_setting": "MIN_DATA_COVERAGE=0.70", "suggested_range": "0.75~0.85", "expected_effect": "저수집률 테마의 상위 진입과 오차 확대를 줄입니다.", "parameter_code": "MIN_DATA_COVERAGE"})
        signed = metrics.get("mean_signed_gap")
        if signed is not None and float(signed) <= -0.5:
            advice.append({"code": "OVER_PREDICTION", "diagnosis": "전체 과대예측", "impact": "중간", "evidence": f"평균 signed gap {float(signed):.2f}%p",
                           "current_setting": "PREDICTION_BIAS=0.00", "suggested_range": "-0.50~-0.10", "expected_effect": "예측 수준을 낮춰 평균 편향을 줄입니다.", "parameter_code": "PREDICTION_BIAS"})
        elif signed is not None and float(signed) >= 0.5:
            advice.append({"code": "UNDER_PREDICTION", "diagnosis": "전체 과소예측", "impact": "중간", "evidence": f"평균 signed gap +{float(signed):.2f}%p",
                           "current_setting": "PREDICTION_BIAS=0.00", "suggested_range": "+0.10~+0.50", "expected_effect": "예측 수준을 높여 평균 편향을 줄입니다.", "parameter_code": "PREDICTION_BIAS"})
        if metrics.get("precision_at_5") is not None and float(metrics["precision_at_5"]) < 0.4:
            advice.append({"code": "LOW_RANK_SEPARATION", "diagnosis": "순위 분리력 부족", "impact": "중간", "evidence": f"Precision@5 {float(metrics['precision_at_5'])*100:.0f}%",
                           "current_setting": "백분위 결합 순위", "suggested_range": "ALIGNMENT_WEIGHT 0.15~0.25", "expected_effect": "가격·수급 동조 테마의 순위 분리력을 높입니다.", "parameter_code": "ALIGNMENT_WEIGHT"})
        if metrics.get("mae_improvement") is not None and float(metrics["mae_improvement"]) < 0 and (metrics.get("precision_at_5") or 0) >= (metrics.get("baseline_precision_at_5") or 0):
            advice.append({"code": "EXCESSIVE_SCALE", "diagnosis": "순위는 양호하지만 등락률 폭이 과도", "impact": "중간", "evidence": f"기준 대비 MAE {abs(float(metrics['mae_improvement'])):.2f}%p 악화",
                           "current_setting": "PREDICTION_SCALE=1.00", "suggested_range": "0.70~0.95", "expected_effect": "순위를 유지하면서 예상 등락률 진폭을 줄입니다.", "parameter_code": "PREDICTION_SCALE"})
        return advice[:4]

    def get(self, target_date: str) -> MarketThemeReturnPredictionResponse:
        run = self._run_row(target_date)
        cutoff = None
        try:
            cutoff, _ = self._cutoff()
        except HTTPException:
            pass
        if not run:
            return MarketThemeReturnPredictionResponse(status="DRAFT", data_cutoff_date=cutoff,
                default_target_date=self.next_weekday(cutoff) if cutoff else None, message="저장된 예측이 없습니다.")
        items = [dict(row) for row in self.db.execute(text("""
            SELECT i.*,t.theme_name,t.parent_theme_id AS theme_group_id,p.theme_name AS theme_group_name
              FROM market_theme_return_prediction_items i JOIN market_themes t ON t.id=i.theme_id
              LEFT JOIN market_themes p ON p.id=t.parent_theme_id WHERE i.run_id=:run_id AND i.is_official=1
             ORDER BY i.predicted_rank IS NULL,i.predicted_rank,t.theme_name
        """), {"run_id": run["id"]}).mappings().all()]
        shadow_items = [dict(row) for row in self.db.execute(text("""
            SELECT i.*,t.theme_name,t.parent_theme_id AS theme_group_id,p.theme_name AS theme_group_name
              FROM market_theme_return_prediction_items i JOIN market_themes t ON t.id=i.theme_id
              LEFT JOIN market_themes p ON p.id=t.parent_theme_id WHERE i.run_id=:run_id AND i.prediction_method='ML' AND i.is_official=0
             ORDER BY i.predicted_rank IS NULL,i.predicted_rank,t.theme_name
        """), {"run_id": run["id"]}).mappings().all()]
        metrics_row = self.db.execute(text("SELECT * FROM market_theme_return_prediction_metrics WHERE run_id=:run_id"), {"run_id": run["id"]}).mappings().first()
        metrics = dict(metrics_row) if metrics_row else None
        method_metrics = [dict(row) for row in self.db.execute(text("""
            SELECT prediction_method,model_version,theme_count,evaluable_theme_count,return_mae,return_rmse,
                   mean_signed_gap,mean_rank_error,precision_at_5,direction_accuracy,ndcg_at_5
              FROM market_theme_return_prediction_method_metrics WHERE run_id=:run_id
             ORDER BY CASE prediction_method WHEN 'BASELINE' THEN 1 WHEN 'RULE' THEN 2 ELSE 3 END
        """), {"run_id": run["id"]}).mappings().all()]
        return MarketThemeReturnPredictionResponse(status=str(run["status"]), data_cutoff_date=str(run["data_cutoff_date"]),
            default_target_date=self.next_weekday(str(run["data_cutoff_date"])), run=run, items=items, shadow_items=shadow_items, metrics=metrics,
            recommendations=self._advice(metrics, items), method_metrics=method_metrics)

    def latest(self) -> MarketThemeReturnPredictionResponse:
        row = self.db.execute(text("""
            SELECT target_date FROM market_theme_return_prediction_runs WHERE status<>'CANCELLED'
             ORDER BY target_date DESC,last_predicted_at DESC,id DESC LIMIT 1
        """)).mappings().first()
        return self.get(str(row["target_date"])) if row else self.get("9999-12-31")

    def prediction_for_cutoff(self, cutoff: str) -> dict[str, Any]:
        row = self.db.execute(text("""
            SELECT * FROM market_theme_return_prediction_runs WHERE data_cutoff_date=:cutoff AND status<>'CANCELLED'
             ORDER BY last_predicted_at DESC,id DESC LIMIT 1
        """), {"cutoff": cutoff}).mappings().first()
        if not row:
            return {"run": None, "values": {}, "ranks": {}}
        values: dict[int, float | None] = {}
        ranks: dict[int, int | None] = {}
        for item in self.db.execute(text("SELECT theme_id,predicted_change_rate,predicted_rank FROM market_theme_return_prediction_items WHERE run_id=:run_id AND is_official=1"), {"run_id": row["id"]}).mappings().all():
            values[int(item["theme_id"])] = float(item["predicted_change_rate"]) if item["predicted_change_rate"] is not None else None
            ranks[int(item["theme_id"])] = int(item["predicted_rank"]) if item["predicted_rank"] is not None else None
        return {"run": dict(row), "values": values, "ranks": ranks}
