from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import math
import statistics
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


FEATURE_VERSION = "THEME_RETURN_FEATURE_V1"
FEATURE_VERSION_V2 = "THEME_RETURN_FEATURE_V2"

FEATURE_NAMES = (
    "price_score", "flow_score", "breadth_score", "alignment_score", "liquidity_score",
    "market_environment_score", "penalty_score", "data_coverage_rate", "base_change_rate",
    "return_mean_3d", "return_mean_5d", "return_mean_10d", "return_volatility_5d",
    "return_volatility_10d", "return_momentum_delta", "base_return_percentile",
    "foreign_flow_strength", "institution_flow_strength", "joint_flow_strength", "program_flow_strength",
    "joint_flow_mean_3d", "joint_flow_mean_5d", "flow_acceleration", "joint_positive_streak",
    "actor_direction_alignment", "price_breadth", "joint_flow_breadth", "top1_concentration",
    "top3_concentration", "calendar_gap_days",
)

FEATURE_NAMES_V2 = FEATURE_NAMES + (
    "return_3d_percentile", "return_5d_percentile", "return_10d_percentile",
    "foreign_flow_percentile", "institution_flow_percentile", "combined_flow_percentile",
    "program_flow_percentile", "breadth_percentile", "liquidity_percentile",
    "concentration_inverse_percentile", "return_3d_minus_10d", "return_1d_minus_5d",
    "flow_3d_minus_5d", "breadth_short_change", "liquidity_short_change",
    "price_flow_interaction", "momentum_flow_interaction", "breadth_flow_interaction",
    "score_interaction", "alignment_breadth_interaction", "return_minus_cross_section_mean",
    "flow_minus_cross_section_mean", "liquidity_minus_cross_section_mean",
)


@dataclass(frozen=True)
class ThemeFeatureRow:
    base_date: str
    target_date: str | None
    theme_id: int
    theme_name: str
    values: dict[str, float | None]
    rule_prediction: float | None
    label: float | None = None


@dataclass(frozen=True)
class ThemeFeatureDataset:
    rows: list[ThemeFeatureRow]
    actual_dates: list[str]
    excluded_missing_label: int = 0
    excluded_low_coverage: int = 0


class MarketThemeReturnFeatureService:
    """Builds leakage-safe in-memory features from dated snapshots only."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _percentiles(values: dict[int, float | None]) -> dict[int, float | None]:
        valid = sorted((float(value), key) for key, value in values.items() if value is not None and math.isfinite(float(value)))
        result: dict[int, float | None] = {key: None for key in values}
        if not valid:
            return result
        if len(valid) == 1:
            result[valid[0][1]] = 50.0
            return result
        index = 0
        while index < len(valid):
            end = index
            while end + 1 < len(valid) and valid[end + 1][0] == valid[index][0]:
                end += 1
            percentile = ((index + end) / 2) / (len(valid) - 1) * 100
            for _, key in valid[index : end + 1]:
                result[key] = percentile
            index = end + 1
        return result

    @staticmethod
    def _mean(values: list[float | None]) -> float | None:
        valid = [float(value) for value in values if value is not None and math.isfinite(float(value))]
        return statistics.mean(valid) if valid else None

    @staticmethod
    def _stdev(values: list[float]) -> float | None:
        return statistics.pstdev(values) if len(values) >= 2 else None

    @staticmethod
    def _ratio(numerator: Any, denominator: Any) -> float | None:
        if numerator is None or denominator is None or float(denominator) == 0:
            return None
        return float(numerator) / float(denominator)

    def _load(self, through_date: str | None = None) -> tuple[list[str], dict[tuple[str, int], dict[str, Any]], dict[tuple[str, int], dict[str, Any]], dict[int, str]]:
        date_filter = "AND r.return_date<=:through_date" if through_date else ""
        params = {"through_date": through_date} if through_date else {}
        return_rows = self.db.execute(text(f"""
            SELECT r.theme_id,r.return_date,r.avg_change_rate,r.stock_count,r.success_stock_count,
                   r.rising_stock_count,r.falling_stock_count,r.flat_stock_count,r.total_trading_value_100m,
                   t.theme_name
              FROM market_theme_daily_returns r JOIN market_themes t ON t.id=r.theme_id
             WHERE r.avg_change_rate IS NOT NULL {date_filter}
             ORDER BY r.return_date,r.theme_id
        """), params).mappings().all()
        snapshots = self.db.execute(text(f"""
            WITH ranked_snapshots AS (
                SELECT s.*,ROW_NUMBER() OVER (PARTITION BY s.theme_id,s.return_date ORDER BY COALESCE(s.trading_value,0) DESC,s.stock_id) AS trading_rank,
                       SUM(COALESCE(s.trading_value,0)) OVER (PARTITION BY s.theme_id,s.return_date) AS theme_trading_value
                  FROM market_theme_stock_daily_returns s WHERE 1=1 {date_filter.replace('r.return_date', 's.return_date')}
            )
            SELECT s.theme_id,s.return_date,
                   CASE WHEN MAX(s.theme_trading_value)>0 THEN MAX(CASE WHEN s.trading_rank=1 THEN COALESCE(s.trading_value,0) END)*1.0/MAX(s.theme_trading_value) END AS top1_concentration,
                   CASE WHEN MAX(s.theme_trading_value)>0 THEN SUM(CASE WHEN s.trading_rank<=3 THEN COALESCE(s.trading_value,0) ELSE 0 END)*1.0/MAX(s.theme_trading_value) END AS top3_concentration,
                   SUM(CASE WHEN f.foreign_net_amount IS NOT NULL THEN f.foreign_net_amount END) AS foreign_net,
                   SUM(CASE WHEN f.institution_net_amount IS NOT NULL THEN f.institution_net_amount END) AS institution_net,
                   SUM(CASE WHEN f.program_net_amount IS NOT NULL THEN f.program_net_amount END) AS program_net,
                   SUM(CASE WHEN f.foreign_net_amount IS NOT NULL OR f.institution_net_amount IS NOT NULL THEN 1 ELSE 0 END) AS flow_count,
                   SUM(CASE WHEN COALESCE(f.foreign_net_amount,0)+COALESCE(f.institution_net_amount,0)>0 THEN 1 ELSE 0 END) AS joint_positive_count,
                   SUM(CASE WHEN f.foreign_net_amount>0 AND f.institution_net_amount>0 THEN 1 ELSE 0 END) AS both_positive_count,
                   SUM(COALESCE(s.trading_value,0)) AS snapshot_trading_value
              FROM ranked_snapshots s
              LEFT JOIN stock_investor_flows f ON f.stock_id=s.stock_id AND f.flow_date=s.return_date
             GROUP BY s.theme_id,s.return_date ORDER BY s.return_date,s.theme_id
        """), params).mappings().all()
        actual_dates = sorted({str(row["return_date"]) for row in return_rows})
        returns = {(str(row["return_date"]), int(row["theme_id"])): dict(row) for row in return_rows}
        snapshot_map = {(str(row["return_date"]), int(row["theme_id"])): dict(row) for row in snapshots}
        names = {int(row["theme_id"]): str(row["theme_name"]) for row in return_rows}
        return actual_dates, returns, snapshot_map, names

    def build_dataset(
        self,
        *,
        min_coverage: float = 0.70,
        through_date: str | None = None,
        inference_target_date: str | None = None,
    ) -> ThemeFeatureDataset:
        actual_dates, returns, snapshots, names = self._load(through_date)
        histories: dict[int, list[dict[str, Any]]] = defaultdict(list)
        flow_histories: dict[int, list[dict[str, Any]]] = defaultdict(list)
        rows: list[ThemeFeatureRow] = []
        excluded_missing_label = 0
        excluded_low_coverage = 0
        for date_index, base_date in enumerate(actual_dates):
            is_inference_row = date_index + 1 == len(actual_dates) and inference_target_date is not None
            target_date = actual_dates[date_index + 1] if date_index + 1 < len(actual_dates) else inference_target_date
            day_rows = {theme_id: row for (day, theme_id), row in returns.items() if day == base_date}
            raw: dict[int, dict[str, Any]] = {}
            for theme_id, current in day_rows.items():
                history = histories[theme_id]
                rates = [float(row["avg_change_rate"]) for row in history[-9:]] + [float(current["avg_change_rate"])]
                snapshot = snapshots.get((base_date, theme_id))
                trading_value = float(current["total_trading_value_100m"] or 0) * 100_000_000
                foreign_strength = self._ratio(snapshot.get("foreign_net") if snapshot else None, trading_value)
                institution_strength = self._ratio(snapshot.get("institution_net") if snapshot else None, trading_value)
                program_strength = self._ratio(snapshot.get("program_net") if snapshot else None, trading_value)
                joint_strength = None if foreign_strength is None or institution_strength is None else foreign_strength + institution_strength
                past_flows = flow_histories[theme_id]
                joint_series = [row["joint"] for row in past_flows[-4:] if row["joint"] is not None] + ([joint_strength] if joint_strength is not None else [])
                mean3 = self._mean(joint_series[-3:])
                previous3 = self._mean(joint_series[-6:-3]) if len(joint_series) >= 6 else None
                flow_acceleration = mean3 - previous3 if mean3 is not None and previous3 is not None else None
                streak = 0
                for value in reversed(joint_series):
                    if value == 0 or (streak > 0 and value < 0) or (streak < 0 and value > 0):
                        break
                    streak += 1 if value > 0 else -1
                coverage = float(current["success_stock_count"] or 0) / int(current["stock_count"] or 1) if current["stock_count"] else 0.0
                price_breadth = self._ratio(current["rising_stock_count"], current["success_stock_count"])
                joint_breadth = self._ratio(snapshot.get("joint_positive_count") if snapshot else None, snapshot.get("flow_count") if snapshot else None)
                actor_alignment = None
                if foreign_strength is not None and institution_strength is not None:
                    actor_alignment = 1.0 if (foreign_strength >= 0) == (institution_strength >= 0) else 0.0
                raw[theme_id] = {
                    "base": float(current["avg_change_rate"]), "mean3": self._mean(rates[-3:]), "mean5": self._mean(rates[-5:]),
                    "mean10": self._mean(rates[-10:]), "vol5": self._stdev(rates[-5:]), "vol10": self._stdev(rates[-10:]),
                    "momentum_delta": (self._mean(rates[-3:]) - self._mean(rates[-6:-3])) if len(rates) >= 6 else None,
                    "foreign": foreign_strength, "institution": institution_strength, "joint": joint_strength, "program": program_strength,
                    "joint3": mean3, "joint5": self._mean(joint_series[-5:]), "flow_acceleration": flow_acceleration,
                    "streak": float(streak), "actor_alignment": actor_alignment, "price_breadth": price_breadth,
                    "joint_breadth": joint_breadth, "top1": float(snapshot["top1_concentration"]) if snapshot and snapshot["top1_concentration"] is not None else None,
                    "top3": float(snapshot["top3_concentration"]) if snapshot and snapshot["top3_concentration"] is not None else None,
                    "liquidity": trading_value, "coverage": coverage,
                }
            base_percentile = self._percentiles({key: value["base"] for key, value in raw.items()})
            price_pct = self._percentiles({key: self._mean([value["base"], value["mean3"], value["mean5"], value["mean10"], value["momentum_delta"]]) for key, value in raw.items()})
            flow_pct = self._percentiles({key: self._mean([value["joint"], value["joint3"], value["joint5"], value["flow_acceleration"]]) for key, value in raw.items()})
            breadth_pct = self._percentiles({key: self._mean([value["price_breadth"], value["joint_breadth"]]) for key, value in raw.items()})
            liquidity_pct = self._percentiles({key: value["liquidity"] for key, value in raw.items()})
            return3_pct = self._percentiles({key: value["mean3"] for key, value in raw.items()})
            return5_pct = self._percentiles({key: value["mean5"] for key, value in raw.items()})
            return10_pct = self._percentiles({key: value["mean10"] for key, value in raw.items()})
            foreign_pct = self._percentiles({key: value["foreign"] for key, value in raw.items()})
            institution_pct = self._percentiles({key: value["institution"] for key, value in raw.items()})
            combined_pct = self._percentiles({key: value["joint"] for key, value in raw.items()})
            program_pct = self._percentiles({key: value["program"] for key, value in raw.items()})
            concentration_inverse_pct = self._percentiles({key: None if value["top1"] is None else -value["top1"] for key, value in raw.items()})
            return_cross_mean = self._mean([value["base"] for value in raw.values()])
            flow_cross_mean = self._mean([value["joint"] for value in raw.values()])
            liquidity_cross_mean = self._mean([value["liquidity"] for value in raw.values()])
            recent_market_dates = set(actual_dates[max(0, date_index - 19) : date_index + 1])
            past_return_values = [float(row["avg_change_rate"]) for (day, _), row in returns.items() if day in recent_market_dates]
            market_mean = statistics.mean(past_return_values) if past_return_values else 0.0
            day_cross_stdevs: list[float] = []
            for historic_day in actual_dates[max(0, date_index - 19) : date_index + 1]:
                values = [float(row["avg_change_rate"]) for (day, _), row in returns.items() if day == historic_day]
                if len(values) >= 2:
                    day_cross_stdevs.append(statistics.pstdev(values))
            market_volatility = max(statistics.mean(day_cross_stdevs), 0.25) if day_cross_stdevs else 1.0
            for theme_id, value in raw.items():
                price_score, flow_score = price_pct[theme_id], flow_pct[theme_id]
                alignment_score = None if price_score is None or flow_score is None else max(0.0, min(100.0, 100 - abs(price_score - flow_score) + (price_score + flow_score - 100) * 0.25))
                penalty = 0.0
                if value["base"] > 5:
                    penalty -= min(15.0, (value["base"] - 5) * 1.5)
                if value["top1"] is not None and value["top1"] > .4:
                    penalty -= min(10.0, (value["top1"] - .4) * 20)
                if value["coverage"] < min_coverage:
                    penalty -= 20 * (min_coverage - value["coverage"]) / min_coverage
                if price_score is not None and flow_score is not None and price_score >= 60 and flow_score <= 40:
                    penalty -= 10 * (price_score - flow_score) / 100
                components = ((price_score, .25), (flow_score, .25), (breadth_pct[theme_id], .15),
                              (alignment_score, .15), (liquidity_pct[theme_id], .10), (50.0, .10))
                available = [(score, weight) for score, weight in components if score is not None]
                total_score = sum(float(score) * weight for score, weight in available) / sum(weight for _, weight in available) + penalty if available else None
                rule_prediction = None if total_score is None else market_mean + max(-1.0, min(1.0, (total_score - 50) / 50)) * market_volatility
                calendar_gap = float((date.fromisoformat(target_date) - date.fromisoformat(base_date)).days) if target_date else None
                feature_values = {
                    "price_score": price_score, "flow_score": flow_score, "breadth_score": breadth_pct[theme_id],
                    "alignment_score": alignment_score, "liquidity_score": liquidity_pct[theme_id], "market_environment_score": 50.0,
                    "penalty_score": penalty, "data_coverage_rate": value["coverage"], "base_change_rate": value["base"],
                    "return_mean_3d": value["mean3"], "return_mean_5d": value["mean5"], "return_mean_10d": value["mean10"],
                    "return_volatility_5d": value["vol5"], "return_volatility_10d": value["vol10"],
                    "return_momentum_delta": value["momentum_delta"], "base_return_percentile": base_percentile[theme_id],
                    "foreign_flow_strength": value["foreign"], "institution_flow_strength": value["institution"],
                    "joint_flow_strength": value["joint"], "program_flow_strength": value["program"],
                    "joint_flow_mean_3d": value["joint3"], "joint_flow_mean_5d": value["joint5"],
                    "flow_acceleration": value["flow_acceleration"], "joint_positive_streak": value["streak"],
                    "actor_direction_alignment": value["actor_alignment"], "price_breadth": value["price_breadth"],
                    "joint_flow_breadth": value["joint_breadth"], "top1_concentration": value["top1"],
                    "top3_concentration": value["top3"], "calendar_gap_days": calendar_gap,
                    "return_3d_percentile": return3_pct[theme_id], "return_5d_percentile": return5_pct[theme_id],
                    "return_10d_percentile": return10_pct[theme_id], "foreign_flow_percentile": foreign_pct[theme_id],
                    "institution_flow_percentile": institution_pct[theme_id], "combined_flow_percentile": combined_pct[theme_id],
                    "program_flow_percentile": program_pct[theme_id], "breadth_percentile": breadth_pct[theme_id],
                    "liquidity_percentile": liquidity_pct[theme_id], "concentration_inverse_percentile": concentration_inverse_pct[theme_id],
                    "return_3d_minus_10d": None if value["mean3"] is None or value["mean10"] is None else value["mean3"] - value["mean10"],
                    "return_1d_minus_5d": None if value["mean5"] is None else value["base"] - value["mean5"],
                    "flow_3d_minus_5d": None if value["joint3"] is None or value["joint5"] is None else value["joint3"] - value["joint5"],
                    "breadth_short_change": None if value["price_breadth"] is None or value["joint_breadth"] is None else value["price_breadth"] - value["joint_breadth"],
                    "liquidity_short_change": None if liquidity_cross_mean is None else value["liquidity"] - liquidity_cross_mean,
                    "price_flow_interaction": None if price_score is None or combined_pct[theme_id] is None else price_score * combined_pct[theme_id] / 100,
                    "momentum_flow_interaction": None if value["momentum_delta"] is None or value["flow_acceleration"] is None else value["momentum_delta"] * value["flow_acceleration"],
                    "breadth_flow_interaction": None if breadth_pct[theme_id] is None or flow_score is None else breadth_pct[theme_id] * flow_score / 100,
                    "score_interaction": None if price_score is None or flow_score is None else price_score * flow_score / 100,
                    "alignment_breadth_interaction": None if alignment_score is None or breadth_pct[theme_id] is None else alignment_score * breadth_pct[theme_id] / 100,
                    "return_minus_cross_section_mean": None if return_cross_mean is None else value["base"] - return_cross_mean,
                    "flow_minus_cross_section_mean": None if value["joint"] is None or flow_cross_mean is None else value["joint"] - flow_cross_mean,
                    "liquidity_minus_cross_section_mean": None if liquidity_cross_mean is None else value["liquidity"] - liquidity_cross_mean,
                }
                label_row = returns.get((target_date, theme_id)) if target_date else None
                label = float(label_row["avg_change_rate"]) if label_row else None
                if target_date is not None:
                    if is_inference_row and value["coverage"] >= min_coverage:
                        rows.append(ThemeFeatureRow(base_date, target_date, theme_id, names[theme_id], feature_values, rule_prediction, None))
                    elif label is None:
                        excluded_missing_label += 1
                    elif value["coverage"] < min_coverage:
                        excluded_low_coverage += 1
                    else:
                        rows.append(ThemeFeatureRow(base_date, target_date, theme_id, names[theme_id], feature_values, rule_prediction, label))
                histories[theme_id].append(current)
                flow_histories[theme_id].append({"date": base_date, "joint": value["joint"]})
        return ThemeFeatureDataset(rows, actual_dates, excluded_missing_label, excluded_low_coverage)

    def build_for_date(self, as_of_date: str, target_date: str, *, min_coverage: float = .70) -> list[ThemeFeatureRow]:
        dataset = self.build_dataset(
            min_coverage=min_coverage,
            through_date=as_of_date,
            inference_target_date=target_date,
        )
        return [row for row in dataset.rows if row.base_date == as_of_date and row.target_date == target_date]
