from __future__ import annotations

import math
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.advisory_package_schema import AdvisoryEvidencePackageResponse
from backend.app.services.stock_market_metric_service import StockMarketMetricService
from backend.app.services.stock_price_service import StockPriceService


@dataclass
class EvidencePackageOptions:
    price_source: str = "pykrx"
    market_metrics_source: str = "marcap"
    include_candle_reference: bool = False
    lookback_days: int = 252
    recent_candle_limit: int = 60
    include_raw_candles: bool = False
    pattern_window: int = 20
    similar_case_limit: int = 5
    strategy_horizon: str = "both"
    include_scenario_questions: bool = True


class AdvisoryEvidencePackageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.price_repo = StockPriceRepository(db)
        self.price_service = StockPriceService(db)
        self.market_metrics_service = StockMarketMetricService(db)

    @staticmethod
    def _normalize_options(options: EvidencePackageOptions) -> EvidencePackageOptions:
        horizon = (options.strategy_horizon or "both").lower()
        if horizon not in {"swing", "long_term", "both"}:
            horizon = "both"
        return EvidencePackageOptions(
            price_source=options.price_source or "pykrx",
            market_metrics_source=options.market_metrics_source or "marcap",
            include_candle_reference=bool(options.include_candle_reference),
            lookback_days=max(20, min(int(options.lookback_days or 252), 252)),
            recent_candle_limit=max(5, min(int(options.recent_candle_limit or 60), 252)),
            include_raw_candles=bool(options.include_raw_candles),
            pattern_window=max(5, min(int(options.pattern_window or 20), 120)),
            similar_case_limit=max(
                0,
                min(int(options.similar_case_limit if options.similar_case_limit is not None else 5), 10),
            ),
            strategy_horizon=horizon,
            include_scenario_questions=bool(options.include_scenario_questions),
        )

    @staticmethod
    def _change_rate(start_price: float | None, end_price: float | None) -> float | None:
        if start_price in (None, 0) or end_price is None:
            return None
        return round(((float(end_price) - float(start_price)) / float(start_price)) * 100, 4)

    @staticmethod
    def _round_similarity(score: float) -> float:
        return round(score, 4)

    def _build_timeframe_summary(self, label: str, rows: list) -> dict:
        if not rows:
            return {
                "label": label,
                "start_trade_date": None,
                "end_trade_date": None,
                "change_rate": None,
                "highest_price": None,
                "lowest_price": None,
            }
        start_row = rows[-1]
        end_row = rows[0]
        highs = [float(row.high_price) for row in rows if row.high_price is not None]
        lows = [float(row.low_price) for row in rows if row.low_price is not None]
        return {
            "label": label,
            "start_trade_date": start_row.trade_date,
            "end_trade_date": end_row.trade_date,
            "change_rate": self._change_rate(start_row.close_price, end_row.close_price),
            "highest_price": None if not highs else round(max(highs), 4),
            "lowest_price": None if not lows else round(min(lows), 4),
        }

    def _build_recent_candles(self, rows: list, limit: int) -> list[dict]:
        return [
            {
                "trade_date": row.trade_date,
                "open_price": row.open_price,
                "high_price": row.high_price,
                "low_price": row.low_price,
                "close_price": row.close_price,
                "change_rate": row.change_rate,
                "volume": row.volume,
            }
            for row in rows[:limit]
        ]

    @staticmethod
    def _window_vector(rows: list) -> list[float] | None:
        if any(row.close_price is None for row in rows):
            return None
        closes = [float(row.close_price) for row in rows]
        base = closes[0]
        if base == 0:
            return None
        return [((value / base) - 1.0) * 100 for value in closes]

    @staticmethod
    def _euclidean_distance(a: list[float], b: list[float]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def _build_similar_pattern_cases(self, rows_desc: list, pattern_window: int, similar_case_limit: int) -> list[dict]:
        if similar_case_limit <= 0:
            return []
        rows = list(reversed(rows_desc))
        if len(rows) < pattern_window * 3:
            return []

        reference_window = rows[-pattern_window:]
        reference_vector = self._window_vector(reference_window)
        if reference_vector is None:
            return []

        cases: list[dict] = []
        max_start = len(rows) - pattern_window - 20
        for start_idx in range(0, max_start):
            window = rows[start_idx : start_idx + pattern_window]
            vector = self._window_vector(window)
            if vector is None:
                continue
            distance = self._euclidean_distance(reference_vector, vector)
            similarity = max(0.0, 100.0 - distance)

            next_5_idx = start_idx + pattern_window + 4
            next_20_idx = start_idx + pattern_window + 19
            window_end_close = window[-1].close_price
            next_5_close = rows[next_5_idx].close_price if next_5_idx < len(rows) else None
            next_20_close = rows[next_20_idx].close_price if next_20_idx < len(rows) else None

            cases.append(
                {
                    "case_id": f"pattern_case_{start_idx + 1}",
                    "reference_end_trade_date": reference_window[-1].trade_date,
                    "comparison_start_trade_date": window[0].trade_date,
                    "comparison_end_trade_date": window[-1].trade_date,
                    "similarity_score": self._round_similarity(similarity),
                    "historical_next_5d_change_rate": self._change_rate(window_end_close, next_5_close),
                    "historical_next_20d_change_rate": self._change_rate(window_end_close, next_20_close),
                    "note": "과거 유사 패턴은 참고 사례일 뿐이며 향후 주가 움직임을 보장하지 않습니다.",
                }
            )

        cases.sort(key=lambda item: item["similarity_score"], reverse=True)
        return cases[:similar_case_limit]

    def _build_candle_reference(self, stock_id: int, source: str, options: EvidencePackageOptions) -> dict | None:
        if not options.include_candle_reference:
            return None

        rows = self.price_repo.list_recent_rows(stock_id=stock_id, source=source, limit=options.lookback_days)
        if not rows:
            return {
                "included": True,
                "lookback_days": options.lookback_days,
                "recent_candle_limit": options.recent_candle_limit,
                "include_raw_candles": options.include_raw_candles,
                "pattern_window": options.pattern_window,
                "similar_case_limit": options.similar_case_limit,
                "row_count": 0,
                "start_trade_date": None,
                "end_trade_date": None,
                "timeframe_summaries": [],
                "recent_candles": [],
                "similar_pattern_cases": [],
                "caution_note": "요청한 source 기준으로 캔들 참조 데이터가 없습니다.",
            }

        rows_desc = rows
        rows_5 = rows_desc[:5]
        rows_20 = rows_desc[:20]
        rows_60 = rows_desc[:60]
        rows_252 = rows_desc[: min(len(rows_desc), 252)]

        recent_candles = self._build_recent_candles(rows_desc, options.recent_candle_limit) if options.include_raw_candles else []
        similar_pattern_cases = self._build_similar_pattern_cases(
            rows_desc=rows_desc,
            pattern_window=options.pattern_window,
            similar_case_limit=options.similar_case_limit,
        )

        return {
            "included": True,
            "lookback_days": options.lookback_days,
            "recent_candle_limit": options.recent_candle_limit,
            "include_raw_candles": options.include_raw_candles,
            "pattern_window": options.pattern_window,
            "similar_case_limit": options.similar_case_limit,
            "row_count": len(rows_desc),
            "start_trade_date": rows_desc[-1].trade_date,
            "end_trade_date": rows_desc[0].trade_date,
            "timeframe_summaries": [
                self._build_timeframe_summary("5d", rows_5),
                self._build_timeframe_summary("20d", rows_20),
                self._build_timeframe_summary("60d", rows_60),
                self._build_timeframe_summary("252d", rows_252),
            ],
            "recent_candles": recent_candles,
            "similar_pattern_cases": similar_pattern_cases,
            "caution_note": (
                "과거 유사 패턴은 참고 사례일 뿐입니다. 유사 패턴 이후 실제 수익률은 예측값이 아니며 자동 매수·매도 신호로 해석하면 안 됩니다."
            ),
        }

    @staticmethod
    def _build_strategy_horizon_context(strategy_horizon: str) -> tuple[dict, dict]:
        notes_map = {
            "swing": [
                "최근 가격 흐름, 이동평균, 단기 캔들 흐름, 거래량 변화를 우선 참고합니다.",
                "과거 유사 패턴은 단기 시나리오 검토용 참고 사례로만 해석합니다.",
            ],
            "long_term": [
                "장기 가격 추세, 중장기 이동평균, 구조적 변화 가능성을 우선 참고합니다.",
                "단기 가격 변동은 장기 판단의 보조 자료로만 해석합니다.",
            ],
            "both": [
                "단기 가격 흐름과 장기 구조 요인을 함께 검토합니다.",
                "스윙 관점과 장기 관점에서 각각 다른 확인 포인트를 구분합니다.",
            ],
        }
        weights_map = {
            "swing": {"swing_weight": 0.8, "long_term_weight": 0.2},
            "long_term": {"swing_weight": 0.2, "long_term_weight": 0.8},
            "both": {"swing_weight": 0.5, "long_term_weight": 0.5},
        }
        return {
            "selected_horizon": strategy_horizon,
            "horizon_notes": notes_map[strategy_horizon],
        }, weights_map[strategy_horizon]

    @staticmethod
    def _localize_market_metrics_note(note: str | None) -> str | None:
        if not note:
            return note
        if note.startswith("Market metrics are based on "):
            parts = note.replace("Market metrics are based on ", "").split(" and are older than the latest price data date ")
            if len(parts) == 2:
                metrics_date = parts[0].strip()
                price_date = parts[1].strip().rstrip(".")
                return f"시장지표는 {metrics_date} 기준이며 최신 가격 데이터 기준일 {price_date}보다 오래되었습니다."
        return note

    @staticmethod
    def _build_scenario_questions(options: EvidencePackageOptions) -> list[str]:
        if not options.include_scenario_questions:
            return []
        questions = [
            "최근 가격 요약을 바탕으로 현재 주가 위치와 단기 흐름을 설명해 주세요.",
            "자동 매수·매도 판단 없이, 사용자가 직접 판단할 수 있도록 근거 중심으로 정리해 주세요.",
        ]
        if options.include_candle_reference:
            questions.append("과거 유사 패턴이 제공된 경우, 이를 예측이 아니라 참고 사례로만 해석해 주세요.")
        if options.strategy_horizon in {"swing", "both"}:
            questions.append("스윙 관점에서 상승·횡보·하락 시나리오별 확인 포인트를 구분해 주세요.")
        if options.strategy_horizon in {"long_term", "both"}:
            questions.append("장기 관점에서 추가로 확인해야 할 구조 요인과 리스크 요인을 구분해 주세요.")
        return questions

    def get_evidence_package(
        self,
        stock_id: int,
        options: EvidencePackageOptions | None = None,
    ) -> AdvisoryEvidencePackageResponse:
        resolved = self._normalize_options(options or EvidencePackageOptions())
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        price_summary = self.price_service.get_summary(stock_id=stock_id, source=resolved.price_source)

        market_metrics_summary = None
        data_quality_notes: list[str] = []
        try:
            market_metrics_summary = self.market_metrics_service.get_summary(
                stock_id=stock_id,
                source=resolved.market_metrics_source,
            )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND or exc.detail != "market metrics not found":
                raise
            data_quality_notes.append(
                f"시장지표 요약 데이터가 없습니다. source={resolved.market_metrics_source} 기준 데이터를 추가 확인해야 합니다."
            )

        if market_metrics_summary:
            if market_metrics_summary.get("is_stale"):
                data_quality_notes.append(
                    "시장지표 데이터가 최신 가격 데이터보다 오래되었습니다. 현재 수급 판단에는 최신성 차이를 반드시 고려해야 합니다."
                )
            if market_metrics_summary.get("data_note"):
                data_quality_notes.append(
                    str(self._localize_market_metrics_note(market_metrics_summary["data_note"]))
                )

        candle_reference = self._build_candle_reference(
            stock_id=stock_id,
            source=resolved.price_source,
            options=resolved,
        )
        if candle_reference and candle_reference["similar_pattern_cases"]:
            data_quality_notes.append("과거 유사 패턴은 참고 사례일 뿐이며 향후 주가 움직임을 보장하지 않습니다.")
            data_quality_notes.append("유사 패턴 이후 실제 수익률은 예측값이 아니라 시나리오 검토용 참고 정보입니다.")

        strategy_horizon_context, analysis_horizon_weights = self._build_strategy_horizon_context(
            resolved.strategy_horizon
        )
        scenario_questions = self._build_scenario_questions(resolved)

        instruction_guardrails = [
            "이 패키지는 GPT 자문을 위한 사실형 근거 자료로만 사용해야 합니다.",
            "이 패키지만으로 자동 매수, 매도, 목표가 결론을 생성하지 마십시오.",
            "시장지표가 오래되었거나 누락된 경우, 해석 전에 그 한계를 먼저 명시하십시오.",
            "과거 유사 패턴은 예측이 아니라 참고 사례로만 다루십시오.",
        ]

        return AdvisoryEvidencePackageResponse(
            stock={
                "stock_id": stock.id,
                "stock_code": stock.stock_code,
                "stock_name": stock.stock_name,
            },
            price_summary={
                "latest_trade_date": price_summary.get("latest_trade_date"),
                "latest_close_price": price_summary.get("latest_close_price"),
                "latest_ma5": price_summary.get("latest_ma5"),
                "latest_ma20": price_summary.get("latest_ma20"),
                "latest_ma60": price_summary.get("latest_ma60"),
                "recent_5d_change_rate": price_summary.get("recent_5d_change_rate"),
                "avg_volume_20d": price_summary.get("avg_volume_20d"),
                "high_52w": price_summary.get("high_52w"),
                "high_52w_date": price_summary.get("high_52w_date"),
                "price_position_vs_52w_high": price_summary.get("price_position_vs_52w_high"),
                "price_count": price_summary["price_count"],
                "source": price_summary["source"],
            },
            market_metrics_summary=(
                None
                if market_metrics_summary is None
                else {
                    "latest_market_metrics_date": market_metrics_summary["latest_market_metrics_date"],
                    "latest_price_trade_date": market_metrics_summary.get("latest_price_trade_date"),
                    "is_stale": market_metrics_summary["is_stale"],
                    "stale_days": market_metrics_summary.get("stale_days"),
                    "staleness_level": market_metrics_summary["staleness_level"],
                    "market": market_metrics_summary.get("market"),
                    "trading_value": market_metrics_summary.get("trading_value"),
                    "market_cap": market_metrics_summary.get("market_cap"),
                    "listed_shares": market_metrics_summary.get("listed_shares"),
                    "trading_volume": market_metrics_summary.get("trading_volume"),
                    "trading_value_rank": market_metrics_summary.get("trading_value_rank"),
                    "market_trading_value_rank": market_metrics_summary.get("market_trading_value_rank"),
                    "trading_value_percentile": market_metrics_summary.get("trading_value_percentile"),
                    "market_trading_value_percentile": market_metrics_summary.get("market_trading_value_percentile"),
                    "source": market_metrics_summary["source"],
                    "data_note": self._localize_market_metrics_note(market_metrics_summary["data_note"]),
                }
            ),
            price_candle_reference=candle_reference,
            strategy_horizon_context=strategy_horizon_context,
            analysis_horizon_weights=analysis_horizon_weights,
            scenario_questions_for_gpt=scenario_questions,
            news_summary=None,
            disclosure_summary=None,
            risk_summary=None,
            theme_summary=None,
            telegram_theme_summary=None,
            data_quality_notes=data_quality_notes,
            instruction_guardrails=instruction_guardrails,
            generated_at=now_kst(),
        )
