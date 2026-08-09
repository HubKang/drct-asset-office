from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend.app.services.market_theme_return_feature_service import (
    FEATURE_NAMES_V2,
    MarketThemeReturnFeatureService,
)


OBSERVATION_FEATURE_VERSION = "THEME_OBSERVATION_FEATURE_V1"
MIN_UNIVERSE_THEMES = 10
MIN_ACTIVE_THEME_COVERAGE = 0.50
MACRO_CODES = ("US_NASDAQ", "US_SP500", "US_SOX", "US_DOW", "US_10Y", "US_2Y", "USD_KRW", "US_BROAD_DOLLAR", "WTI")
OBSERVATION_FEATURE_NAMES = FEATURE_NAMES_V2 + tuple(
    f"macro_{code.lower()}_{window}" for code in MACRO_CODES for window in ("1d", "5d")
) + ("market_kospi_1d", "market_kosdaq_1d", "market_gold_1d", "technical_score", "observation_rule_score")


@dataclass(frozen=True)
class ObservationFeatureRow:
    base_date: str
    target_date: str
    theme_id: int
    theme_name: str
    values: dict[str, float | None]
    observation_rule_score: float
    status_code: str
    confidence_level: str
    data_coverage_rate: float
    label_return: float | None
    label_top20: int | None
    label_rank: int | None


@dataclass(frozen=True)
class ObservationFeatureDataset:
    rows: list[ObservationFeatureRow]
    qualified_dates: list[str]
    excluded_universe_dates: int
    minimum_universe_size: int


class MarketThemeObservationFeatureService:
    """Phase4 dated, leakage-safe observation features. Detail remains transient."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _change(values: list[float], window: int) -> float | None:
        if len(values) <= window or values[-window - 1] == 0:
            return None
        return (values[-1] / values[-window - 1] - 1) * 100

    def _macro_by_date(self, through_date: str | None, *, operational_base_date: str | None = None, operational_asof_date: str | None = None) -> dict[str, dict[str, float | None]]:
        params: dict[str, Any] = {"codes": MACRO_CODES}
        effective_through = operational_asof_date or through_date
        date_clause = "AND value_date<=:through_date" if effective_through else ""
        if effective_through:
            params["through_date"] = effective_through
        statement = text(f"""
            SELECT indicator_code,value_date,value FROM market_indicator_values
             WHERE indicator_code IN :codes AND value IS NOT NULL {date_clause}
             ORDER BY indicator_code,value_date
        """).bindparams(bindparam("codes", expanding=True))
        rows = self.db.execute(statement, params).mappings().all()
        by_code: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for row in rows:
            by_code[str(row["indicator_code"])].append((str(row["value_date"]), float(row["value"])))
        result: dict[str, dict[str, float | None]] = {}
        base_dates = [str(row[0]) for row in self.db.execute(text(
            "SELECT DISTINCT return_date FROM market_theme_daily_returns " + ("WHERE return_date<=:through_date " if through_date else "") + "ORDER BY return_date"
        ), {"through_date": through_date} if through_date else {}).all()]
        for base_date in base_dates:
            features: dict[str, float | None] = {}
            for code in MACRO_CODES:
                # Historical rows remain strictly lagged. Only the live inference row may use values
                # that were actually available by its calculation timestamp.
                if operational_base_date == base_date and operational_asof_date:
                    history = [value for day, value in by_code.get(code, []) if day <= operational_asof_date]
                else:
                    history = [value for day, value in by_code.get(code, []) if day < base_date]
                features[f"macro_{code.lower()}_1d"] = self._change(history, 1)
                features[f"macro_{code.lower()}_5d"] = self._change(history, 5)
            result[base_date] = features
        return result

    def _market_by_date(self, through_date: str | None, *, operational_base_date: str | None = None, operational_asof_date: str | None = None) -> dict[str, dict[str, float | None]]:
        effective_through = operational_asof_date or through_date
        clause = "AND price_date<=:through_date" if effective_through else ""
        rows = self.db.execute(text(f"""
            WITH priced AS (
                SELECT index_code,price_date,change_rate,close_price,
                       LAG(close_price) OVER (PARTITION BY index_code ORDER BY price_date) AS previous_close
                  FROM market_index_daily_prices
                 WHERE index_code IN ('KOSPI','KOSDAQ','GOLD_KRX')
            )
            SELECT index_code,price_date,
                   COALESCE(change_rate,CASE WHEN previous_close IS NOT NULL AND previous_close<>0 THEN (close_price/previous_close-1)*100 END) AS change_rate
              FROM priced WHERE 1=1 {clause}
        """), {"through_date": effective_through} if effective_through else {}).mappings().all()
        key = {"KOSPI": "market_kospi_1d", "KOSDAQ": "market_kosdaq_1d", "GOLD_KRX": "market_gold_1d"}
        result: dict[str, dict[str, float | None]] = defaultdict(dict)
        for row in rows:
            result[str(row["price_date"])][key[str(row["index_code"])]] = float(row["change_rate"]) if row["change_rate"] is not None else None
        if operational_base_date and operational_asof_date:
            latest: dict[str, tuple[str, float | None]] = {}
            for row in rows:
                code = str(row["index_code"]); day = str(row["price_date"])
                if day <= operational_asof_date and (code not in latest or day > latest[code][0]):
                    latest[code] = (day, float(row["change_rate"]) if row["change_rate"] is not None else None)
            result[operational_base_date].update({key[code]: value for code, (_, value) in latest.items()})
        return result

    @staticmethod
    def _market_environment(values: dict[str, float | None]) -> float | None:
        directions = {
            "market_kospi_1d": 1.0, "market_kosdaq_1d": 1.0, "macro_us_nasdaq_1d": 1.0,
            "macro_us_sp500_1d": 1.0, "macro_us_sox_1d": 1.0, "macro_us_dow_1d": .5,
            "macro_us_10y_1d": -1.0, "macro_us_2y_1d": -.7, "macro_usd_krw_1d": -.7,
            "macro_us_broad_dollar_1d": -.5, "macro_wti_1d": -.2,
        }
        parts = [(float(values[name]), weight) for name, weight in directions.items() if values.get(name) is not None]
        if not parts:
            return None
        weighted_change = sum(change * weight for change, weight in parts) / sum(abs(weight) for _, weight in parts)
        return max(0.0, min(100.0, 50.0 + weighted_change * 10.0))

    @staticmethod
    def _score(values: dict[str, float | None]) -> tuple[float, str, str]:
        components = [
            (values.get("price_score"), .25), (values.get("flow_score"), .25),
            (values.get("breadth_score"), .15), (values.get("liquidity_score"), .10),
            (values.get("alignment_score"), .10), (values.get("technical_score"), .10),
            (values.get("market_environment_score"), .05),
        ]
        available = [(float(value), weight) for value, weight in components if value is not None and math.isfinite(float(value))]
        score = sum(value * weight for value, weight in available) / sum(weight for _, weight in available) if available else 50.0
        score += float(values.get("penalty_score") or 0)
        score = max(0.0, min(100.0, score))
        price, flow = values.get("price_score"), values.get("flow_score")
        base = float(values.get("base_change_rate") or 0)
        if base >= 8 or float(values.get("penalty_score") or 0) <= -12:
            state = "OVERHEAT_RISK"
        elif price is not None and flow is not None and price >= 65 and flow >= 65:
            state = "STRONG_CONTINUATION"
        elif flow is not None and flow >= 70 and (price is None or price < 60):
            state = "FLOW_LEADING"
        elif flow is not None and flow <= 25 and price is not None and price >= 55:
            state = "FLOW_EXIT"
        elif price is not None and price <= 35 and flow is not None and flow >= 55:
            state = "REVERSAL_WATCH"
        else:
            state = "NEUTRAL"
        coverage = float(values.get("data_coverage_rate") or 0)
        confidence = "HIGH" if coverage >= .85 and len(available) >= 6 else "MEDIUM" if coverage >= .65 and len(available) >= 4 else "LOW"
        return score, state, confidence

    def build_dataset(self, *, through_date: str | None = None, inference_target_date: str | None = None, operational_asof_at: str | None = None) -> ObservationFeatureDataset:
        source = MarketThemeReturnFeatureService(self.db).build_dataset(
            min_coverage=MIN_ACTIVE_THEME_COVERAGE, through_date=through_date, inference_target_date=inference_target_date
        )
        active_count = int(self.db.execute(text("""
            SELECT COUNT(*) FROM market_themes
             WHERE is_active=1 AND (theme_level='THEME' OR theme_level IS NULL)
        """)).scalar() or 0)
        minimum = max(MIN_UNIVERSE_THEMES, math.ceil(active_count * MIN_ACTIVE_THEME_COVERAGE))
        grouped: dict[str, list[Any]] = defaultdict(list)
        for row in source.rows:
            if row.target_date:
                grouped[row.target_date].append(row)
        qualified = {day for day, rows in grouped.items() if len(rows) >= minimum}
        operational_date = operational_asof_at[:10] if operational_asof_at else None
        inference_base_date = through_date if inference_target_date and operational_asof_at else None
        macro = self._macro_by_date(through_date, operational_base_date=inference_base_date, operational_asof_date=operational_date)
        market = self._market_by_date(through_date, operational_base_date=inference_base_date, operational_asof_date=operational_date)
        result: list[ObservationFeatureRow] = []
        for target_date, day_rows in grouped.items():
            if target_date not in qualified:
                continue
            labeled = sorted((row for row in day_rows if row.label is not None), key=lambda row: float(row.label), reverse=True)
            ranks = {row.theme_id: index + 1 for index, row in enumerate(labeled)}
            top_count = max(1, math.ceil(len(labeled) * .20))
            for row in day_rows:
                values = dict(row.values)
                values.update(macro.get(row.base_date, {}))
                values.update(market.get(row.base_date, {}))
                environment_score = self._market_environment(values)
                if environment_score is not None:
                    values["market_environment_score"] = environment_score
                tech_parts = [values.get("return_3d_percentile"), values.get("return_10d_percentile"), values.get("concentration_inverse_percentile")]
                tech_valid = [float(value) for value in tech_parts if value is not None]
                values["technical_score"] = sum(tech_valid) / len(tech_valid) if tech_valid else None
                score, state, confidence = self._score(values)
                values["observation_rule_score"] = score
                rank = ranks.get(row.theme_id)
                result.append(ObservationFeatureRow(
                    row.base_date, target_date, row.theme_id, row.theme_name, values, score, state, confidence,
                    float(values.get("data_coverage_rate") or 0), row.label, None if rank is None else int(rank <= top_count), rank,
                ))
        return ObservationFeatureDataset(result, sorted(qualified), len(grouped) - len(qualified), minimum)

    def build_for_date(self, as_of_date: str, target_date: str, *, operational_asof_at: str | None = None) -> list[ObservationFeatureRow]:
        dataset = self.build_dataset(through_date=as_of_date, inference_target_date=target_date, operational_asof_at=operational_asof_at)
        return [row for row in dataset.rows if row.base_date == as_of_date and row.target_date == target_date]
