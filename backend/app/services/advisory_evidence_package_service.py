from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.repositories.disclosure_repository import DisclosureRepository
from backend.app.repositories.news_repository import NewsRepository
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.advisory_package_schema import AdvisoryEvidencePackageResponse
from backend.app.services.stock_market_metric_service import StockMarketMetricService
from backend.app.services.stock_price_service import StockPriceService
from backend.app.services.technical_indicator_service import TechnicalIndicatorService


@dataclass
class EvidencePackageOptions:
    price_source: str = "pykrx"
    market_metrics_source: str = "auto"
    include_candle_reference: bool = False
    lookback_days: int = 252
    recent_candle_limit: int = 60
    include_raw_candles: bool = False
    include_similar_patterns: bool = False
    pattern_window: int = 20
    similar_case_limit: int = 5
    pattern_ma: int = 20
    search_trading_days: int = 252
    strategy_horizon: str = "both"
    include_scenario_questions: bool = True
    include_news_disclosures_risk: bool = True
    include_technical_indicators: bool = True


class AdvisoryEvidencePackageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.price_repo = StockPriceRepository(db)
        self.news_repo = NewsRepository(db)
        self.disclosure_repo = DisclosureRepository(db)
        self.price_service = StockPriceService(db)
        self.market_metrics_service = StockMarketMetricService(db)
        self.technical_indicator_service = TechnicalIndicatorService(db)

    @staticmethod
    def _normalize_options(options: EvidencePackageOptions) -> EvidencePackageOptions:
        horizon = (options.strategy_horizon or "both").lower()
        if horizon not in {"swing", "long_term", "both"}:
            horizon = "both"
        pattern_ma = int(options.pattern_ma or 20)
        if pattern_ma not in {5, 10, 20, 60, 120, 240}:
            pattern_ma = 20
        return EvidencePackageOptions(
            price_source=options.price_source or "pykrx",
            market_metrics_source=options.market_metrics_source or "auto",
            include_candle_reference=bool(options.include_candle_reference),
            lookback_days=max(20, min(int(options.lookback_days or 252), 252)),
            recent_candle_limit=max(5, min(int(options.recent_candle_limit or 60), 252)),
            include_raw_candles=bool(options.include_raw_candles),
            include_similar_patterns=bool(options.include_similar_patterns),
            pattern_window=max(5, min(int(options.pattern_window or 20), 60)),
            similar_case_limit=max(1, min(int(options.similar_case_limit or 5), 20)),
            pattern_ma=pattern_ma,
            search_trading_days=max(60, min(int(options.search_trading_days or 252), 252)),
            strategy_horizon=horizon,
            include_scenario_questions=bool(options.include_scenario_questions),
            include_news_disclosures_risk=bool(options.include_news_disclosures_risk),
            include_technical_indicators=bool(options.include_technical_indicators),
        )

    @staticmethod
    def _change_rate(start_price: float | None, end_price: float | None) -> float | None:
        if start_price in (None, 0) or end_price is None:
            return None
        return round(((float(end_price) - float(start_price)) / float(start_price)) * 100, 2)

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
            "highest_price": None if not highs else round(max(highs), 2),
            "lowest_price": None if not lows else round(min(lows), 2),
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
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:19] if fmt.endswith("%S") else text[:10], fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    @staticmethod
    def _normalize_risk_level(value: str | None) -> str:
        normalized = (value or "").strip().lower()
        return normalized if normalized in {"high", "medium", "low"} else "unknown"

    @staticmethod
    def _normalize_sentiment(value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().lower()
        return text or None

    @staticmethod
    def _empty_risk_counts() -> dict[str, int]:
        return {"high": 0, "medium": 0, "low": 0, "unknown": 0}

    @staticmethod
    def _ma_attr_name(pattern_ma: int) -> str:
        return f"ma{pattern_ma}"

    @staticmethod
    def _mean_abs_distance(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 999.0
        return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

    @staticmethod
    def _to_similarity(distance: float, scale: float) -> float:
        if scale <= 0:
            return 0.0
        return round(max(0.0, min(100.0, 100.0 - (distance / scale) * 100.0)), 2)

    @staticmethod
    def _normalized_close(window: list) -> list[float] | None:
        closes = [float(row.close_price) for row in window if row.close_price is not None]
        if len(closes) != len(window) or closes[0] == 0:
            return None
        base = closes[0]
        return [value / base - 1.0 for value in closes]

    @staticmethod
    def _normalized_ma_gap(window: list, pattern_ma: int) -> list[float] | None:
        attr = AdvisoryEvidencePackageService._ma_attr_name(pattern_ma)
        result: list[float] = []
        for row in window:
            close = row.close_price
            ma_value = getattr(row, attr, None)
            if close is None or ma_value in (None, 0):
                return None
            result.append((float(close) - float(ma_value)) / float(ma_value))
        return result

    @staticmethod
    def _normalized_volume(window: list) -> list[float] | None:
        volumes = [float(row.volume) for row in window if row.volume is not None and float(row.volume) >= 0]
        if len(volumes) != len(window):
            return None
        base = volumes[0] if volumes[0] > 0 else (sum(volumes) / len(volumes) if sum(volumes) > 0 else 0.0)
        if base == 0:
            return None
        return [v / base - 1.0 for v in volumes]

    @staticmethod
    def _future_return(rows: list, end_idx: int, offset: int) -> float | None:
        target = end_idx + offset
        if target >= len(rows):
            return None
        start_close = rows[end_idx].close_price
        end_close = rows[target].close_price
        if start_close in (None, 0) or end_close is None:
            return None
        return round(((float(end_close) / float(start_close)) - 1.0) * 100.0, 2)

    @staticmethod
    def _future_max_min_return(rows: list, end_idx: int, horizon: int = 20) -> tuple[float | None, float | None]:
        start_close = rows[end_idx].close_price
        if start_close in (None, 0):
            return None, None
        future_slice = rows[end_idx + 1 : end_idx + 1 + horizon]
        closes = [float(r.close_price) for r in future_slice if r.close_price is not None]
        if not closes:
            return None, None
        max_ret = max(((c / float(start_close)) - 1.0) * 100.0 for c in closes)
        min_ret = min(((c / float(start_close)) - 1.0) * 100.0 for c in closes)
        return round(max_ret, 2), round(min_ret, 2)

    def _build_similar_pattern_cases(self, rows_desc: list, options: EvidencePackageOptions) -> dict:
        result = {
            "included": bool(options.include_similar_patterns),
            "method": "price_ma_volume_weighted_similarity",
            "search_trading_days": options.search_trading_days,
            "pattern_window": options.pattern_window,
            "pattern_ma": options.pattern_ma,
            "requested_limit": options.similar_case_limit,
            "returned_count": 0,
            "weight": {"price_flow": 0.5, "ma_position": 0.3, "volume_change": 0.2},
            "base_pattern": None,
            "cases": [],
            "data_quality_notes": [],
        }
        if not options.include_similar_patterns:
            return result

        rows = list(reversed(rows_desc[: options.search_trading_days]))
        if len(rows) < options.pattern_window * 2:
            result["data_quality_notes"].append("유사 패턴 분석에 필요한 가격 데이터가 부족합니다.")
            return result

        base = rows[-options.pattern_window :]
        base_close = self._normalized_close(base)
        base_ma = self._normalized_ma_gap(base, options.pattern_ma)
        base_volume = self._normalized_volume(base)
        if base_close is None:
            result["data_quality_notes"].append("기준 패턴 종가 데이터가 부족해 유사도 계산을 진행할 수 없습니다.")
            return result
        if base_ma is None:
            result["data_quality_notes"].append("선택한 패턴 기준 이평선 값이 일부 구간에서 누락되어 비교가 제한됩니다.")
        if base_volume is None:
            result["data_quality_notes"].append("거래량 데이터가 일부 누락되어 거래량 유사도 신뢰도가 낮을 수 있습니다.")

        ma_attr = self._ma_attr_name(options.pattern_ma)
        result["base_pattern"] = {
            "start_date": base[0].trade_date,
            "end_date": base[-1].trade_date,
            "trading_days": len(base),
            "latest_close": base[-1].close_price,
            "selected_ma_value": getattr(base[-1], ma_attr, None),
            "summary_ko": "가격 흐름, 이평선 위치, 거래량 변화를 함께 비교한 과거 참고 패턴입니다.",
        }

        base_start_idx = len(rows) - options.pattern_window
        candidates: list[dict] = []
        for start_idx in range(0, max(0, base_start_idx - options.pattern_window + 1)):
            end_idx = start_idx + options.pattern_window - 1
            if end_idx >= base_start_idx:
                continue
            window = rows[start_idx : start_idx + options.pattern_window]
            cand_close = self._normalized_close(window)
            if cand_close is None:
                continue
            cand_ma = self._normalized_ma_gap(window, options.pattern_ma)
            cand_volume = self._normalized_volume(window)

            price_score = self._to_similarity(self._mean_abs_distance(base_close, cand_close), 0.2)
            ma_score = self._to_similarity(self._mean_abs_distance(base_ma, cand_ma), 0.15) if (base_ma and cand_ma) else 0.0
            volume_score = self._to_similarity(self._mean_abs_distance(base_volume, cand_volume), 0.5) if (base_volume and cand_volume) else 0.0
            overall = round(price_score * 0.5 + ma_score * 0.3 + volume_score * 0.2, 2)

            start_close = window[0].close_price
            end_close = window[-1].close_price
            max_ret, min_ret = self._future_max_min_return(rows, end_idx, horizon=20)
            candidates.append(
                {
                    "start_date": window[0].trade_date,
                    "end_date": window[-1].trade_date,
                    "trading_days": len(window),
                    "overall_similarity_score": overall,
                    "price_similarity_score": price_score,
                    "ma_position_similarity_score": round(ma_score, 2),
                    "volume_similarity_score": round(volume_score, 2),
                    "start_close": start_close,
                    "end_close": end_close,
                    "return_rate": self._change_rate(start_close, end_close),
                    "max_return_after_pattern": max_ret,
                    "min_return_after_pattern": min_ret,
                    "after_5d_return": self._future_return(rows, end_idx, 5),
                    "after_10d_return": self._future_return(rows, end_idx, 10),
                    "after_20d_return": self._future_return(rows, end_idx, 20),
                    "gpt_note_ko": "이 사례는 과거 참고 사례입니다. 이후 수익률은 예측이 아니라 과거 참고값입니다.",
                }
            )

        candidates.sort(key=lambda x: x["overall_similarity_score"], reverse=True)
        selected = candidates[: options.similar_case_limit]
        for idx, item in enumerate(selected, start=1):
            item["rank"] = idx
        result["cases"] = selected
        result["returned_count"] = len(selected)
        if not selected:
            result["data_quality_notes"].append("유효한 후보 패턴이 부족하여 결과가 비어 있습니다.")
        if any(case["after_20d_return"] is None for case in selected):
            result["data_quality_notes"].append("일부 사례는 이후 데이터 부족으로 20거래일 수익률이 null입니다.")
        result["data_quality_notes"].append("거래대금은 현재 유사도 계산에 포함하지 않았습니다. KRX Open API 승인 후 반영 예정입니다.")
        return result

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
                "similar_pattern_cases": self._build_similar_pattern_cases([], options),
                "caution_note": "요청한 source 기준 가격 데이터가 없습니다.",
            }

        rows_5 = rows[:5]
        rows_20 = rows[:20]
        rows_60 = rows[:60]
        rows_252 = rows[: min(len(rows), 252)]
        recent_candles = self._build_recent_candles(rows, options.recent_candle_limit) if options.include_raw_candles else []
        similar_pattern_cases = self._build_similar_pattern_cases(rows, options)
        return {
            "included": True,
            "lookback_days": options.lookback_days,
            "recent_candle_limit": options.recent_candle_limit,
            "include_raw_candles": options.include_raw_candles,
            "pattern_window": options.pattern_window,
            "similar_case_limit": options.similar_case_limit,
            "row_count": len(rows),
            "start_trade_date": rows[-1].trade_date,
            "end_trade_date": rows[0].trade_date,
            "timeframe_summaries": [
                self._build_timeframe_summary("5d", rows_5),
                self._build_timeframe_summary("20d", rows_20),
                self._build_timeframe_summary("60d", rows_60),
                self._build_timeframe_summary("252d", rows_252),
            ],
            "recent_candles": recent_candles,
            "similar_pattern_cases": similar_pattern_cases,
            "caution_note": "과거 유사 패턴은 예측이 아니라 참고 사례입니다.",
        }

    @staticmethod
    def _build_strategy_horizon_context(strategy_horizon: str) -> tuple[dict, dict]:
        notes_map = {
            "swing": [
                "최근 가격 흐름, 이동평균, 단기 캔들 흐름을 우선 참고합니다.",
                "과거 유사 패턴은 단기 시나리오 검토용 참고 정보로만 해석합니다.",
            ],
            "long_term": [
                "중장기 가격 추세와 구조적 변화 가능성을 우선 참고합니다.",
                "단기 변동은 장기 판단의 보조 자료로만 해석합니다.",
            ],
            "both": [
                "단기 가격 흐름과 장기 구조 요인을 함께 검토합니다.",
                "스윙 관점과 장기 관점의 해석 차이를 구분합니다.",
            ],
        }
        weights_map = {
            "swing": {"swing_weight": 0.8, "long_term_weight": 0.2},
            "long_term": {"swing_weight": 0.2, "long_term_weight": 0.8},
            "both": {"swing_weight": 0.5, "long_term_weight": 0.5},
        }
        return {"selected_horizon": strategy_horizon, "horizon_notes": notes_map[strategy_horizon]}, weights_map[strategy_horizon]

    @staticmethod
    def _localize_market_metrics_note(note: str | None) -> str | None:
        if not note:
            return note
        if note.startswith("Market metrics are based on "):
            parts = note.replace("Market metrics are based on ", "").split(" and are older than the latest price data date ")
            if len(parts) == 2:
                metrics_date = parts[0].strip()
                price_date = parts[1].strip().rstrip(".")
                return f"시장지표는 {metrics_date} 기준이며 최신 가격 기준일 {price_date}보다 오래되었습니다."
        return note

    @staticmethod
    def _build_scenario_questions(options: EvidencePackageOptions) -> list[str]:
        if not options.include_scenario_questions:
            return []
        questions = [
            "현재 가격 위치와 단기 흐름을 사실 중심으로 정리해 주세요.",
            "자동 매수/매도 판단 없이, 사용자가 직접 판단할 수 있게 근거 중심으로 설명해 주세요.",
        ]
        if options.include_candle_reference:
            questions.append("유사 패턴 이후 수익률은 예측이 아니라 참고값임을 명시해 주세요.")
        return questions

    def _build_news_disclosure_blocks(self, stock_id: int, lookback_days: int = 30, max_items: int = 5) -> dict:
        now_dt = self._parse_date(now_kst()) or datetime.now()
        threshold = now_dt - timedelta(days=lookback_days)
        raw_news = self.news_repo.list_recent_by_stock(stock_id=stock_id, limit=100)
        raw_disclosures = self.disclosure_repo.list_recent_by_stock(stock_id=stock_id, limit=100)

        news_rows = []
        for item in raw_news:
            dt = self._parse_date(item.published_at) or self._parse_date(item.collected_at) or self._parse_date(item.created_at)
            if dt and dt >= threshold:
                news_rows.append((dt, item))
        news_rows.sort(key=lambda x: x[0], reverse=True)

        disclosure_rows = []
        for item in raw_disclosures:
            dt = self._parse_date(item.disclosed_at) or self._parse_date(item.created_at)
            if dt and dt >= threshold:
                disclosure_rows.append((dt, item))
        disclosure_rows.sort(key=lambda x: x[0], reverse=True)

        news_counts = self._empty_risk_counts()
        disclosure_counts = self._empty_risk_counts()
        timeline = []
        missing_ai_summary_count = 0
        unknown_risk_count = 0

        news_items = []
        for dt, item in news_rows[:max_items]:
            risk_level = "unknown"
            sentiment = self._normalize_sentiment(item.ai_sentiment or item.sentiment)
            news_counts[risk_level] += 1
            unknown_risk_count += 1
            if not item.ai_summary:
                missing_ai_summary_count += 1
            summary_text = item.ai_summary or item.summary or item.title
            note = "AI 요약이 있더라도 원문 제목/출처를 함께 확인해 주세요." if item.ai_summary else "AI 요약 누락으로 신뢰도가 낮아 원문 확인이 필요합니다."
            news_items.append(
                {
                    "news_id": item.id,
                    "title": item.title,
                    "published_at": item.published_at or item.collected_at or item.created_at,
                    "source": item.source,
                    "url": item.url,
                    "summary": item.summary,
                    "ai_summary": item.ai_summary,
                    "tag": item.ai_tags,
                    "score": item.ai_importance_score if item.ai_importance_score is not None else item.importance_score,
                    "sentiment": sentiment,
                    "risk_level": risk_level,
                    "event_type": None,
                    "gpt_note_ko": note,
                }
            )
            timeline.append(
                {
                    "event_date": item.published_at or item.collected_at or item.created_at,
                    "event_sort_dt": dt,
                    "source_type": "news",
                    "title": item.title,
                    "summary": summary_text,
                    "risk_level": risk_level,
                    "sentiment": sentiment,
                    "event_type": None,
                    "score": item.ai_importance_score if item.ai_importance_score is not None else item.importance_score,
                    "gpt_note_ko": note,
                }
            )

        disclosure_items = []
        for dt, item in disclosure_rows[:max_items]:
            risk_level = self._normalize_risk_level(item.ai_risk_level)
            disclosure_counts[risk_level] += 1
            if risk_level == "unknown":
                unknown_risk_count += 1
            if not item.ai_summary:
                missing_ai_summary_count += 1
            summary_text = item.ai_summary or item.summary or item.disclosure_title
            note = "공시 이벤트의 실제 사업 영향 기간과 일회성 여부를 분리해서 검토해 주세요." if item.ai_summary else "AI 요약 누락으로 공시 원문 확인이 필요합니다."
            disclosure_items.append(
                {
                    "disclosure_id": item.id,
                    "title": item.disclosure_title,
                    "disclosed_at": item.disclosed_at or item.created_at,
                    "report_name": item.disclosure_type,
                    "disclosure_url": item.url,
                    "ai_summary": summary_text,
                    "tag": item.ai_tags,
                    "score": item.ai_importance_score if item.ai_importance_score is not None else item.importance_score,
                    "sentiment": None,
                    "risk_level": risk_level,
                    "event_type": item.ai_event_type,
                    "gpt_note_ko": note,
                }
            )
            timeline.append(
                {
                    "event_date": item.disclosed_at or item.created_at,
                    "event_sort_dt": dt,
                    "source_type": "disclosure",
                    "title": item.disclosure_title,
                    "summary": summary_text,
                    "risk_level": risk_level,
                    "sentiment": None,
                    "event_type": item.ai_event_type,
                    "score": item.ai_importance_score if item.ai_importance_score is not None else item.importance_score,
                    "gpt_note_ko": note,
                }
            )

        combined = {k: news_counts[k] + disclosure_counts[k] for k in ("high", "medium", "low", "unknown")}
        if combined["high"] > 0:
            highest, summary_ko = "high", "최근 30일 기준 high Risk 이벤트가 확인되어 보수적 검토가 필요합니다."
        elif combined["medium"] > 0:
            highest, summary_ko = "medium", "최근 30일 기준 medium Risk 이벤트가 일부 확인되어 변동성 확대 가능성 검토가 필요합니다."
        elif combined["low"] > 0:
            highest, summary_ko = "low", "명확한 high Risk는 없지만 수집 누락 가능성을 함께 확인해 주세요."
        else:
            highest, summary_ko = "unknown", "최근 뉴스·공시 데이터 부족 또는 Risk 정보 부족으로 신뢰도가 낮습니다."

        timeline.sort(key=lambda x: x["event_sort_dt"], reverse=True)
        timeline_items = [{k: v for k, v in item.items() if k != "event_sort_dt"} for item in timeline]
        return {
            "news_summary_block": {"included": True, "lookback_days": lookback_days, "max_items": max_items, "total_found": len(news_rows), "items": news_items},
            "disclosure_summary_block": {"included": True, "lookback_days": lookback_days, "max_items": max_items, "total_found": len(disclosure_rows), "items": disclosure_items},
            "risk_summary_block": {
                "included": True,
                "lookback_days": lookback_days,
                "news_risk_counts": news_counts,
                "disclosure_risk_counts": disclosure_counts,
                "combined_risk_counts": combined,
                "highest_risk_level": highest,
                "risk_summary_ko": summary_ko,
                "caution_notes_ko": [
                    "뉴스·공시·Risk는 투자 판단 보조 참고 자료입니다.",
                    "자동 매수/매도 판단에 사용하지 마세요.",
                ],
            },
            "recent_event_timeline": timeline_items,
            "missing_ai_summary_count": missing_ai_summary_count,
            "unknown_risk_count": unknown_risk_count,
        }

    @staticmethod
    def _sma(values: list[float], period: int) -> list[float | None]:
        out: list[float | None] = []
        for i in range(len(values)):
            if i + 1 < period:
                out.append(None)
            else:
                window = values[i + 1 - period : i + 1]
                out.append(sum(window) / period)
        return out

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float]:
        if not values:
            return []
        k = 2 / (period + 1)
        ema_vals = [values[0]]
        for v in values[1:]:
            ema_vals.append(v * k + ema_vals[-1] * (1 - k))
        return ema_vals

    def _build_technical_indicators_block(self, rows_desc: list, include: bool, lookback_days: int) -> dict:
        block = {
            "included": include,
            "source": None,
            "calculation_version": "v1",
            "as_of_date": rows_desc[0].trade_date if rows_desc else None,
            "lookback_days": lookback_days,
            "indicators": {},
            "interpretation_notes_ko": [
                "기술적 지표는 가격 위치, 추세, 변동성, 거래량 변화를 참고하기 위한 보조 정보입니다.",
                "각 지표는 단독으로 투자 판단을 내리기 위한 근거가 아닙니다.",
                "뉴스·공시·Risk, 시장지표와 함께 종합적으로 검토해야 합니다.",
            ],
            "data_quality_notes": [],
        }
        if not include:
            return block
        if len(rows_desc) < 20:
            block["data_quality_notes"].append("기술적 지표 계산에 필요한 가격 데이터가 부족합니다.")
            return block

        rows = list(reversed(rows_desc))
        closes = [float(r.close_price) for r in rows if r.close_price is not None]
        highs = [float(r.high_price) for r in rows if r.high_price is not None]
        lows = [float(r.low_price) for r in rows if r.low_price is not None]
        vols = [float(r.volume) for r in rows if r.volume is not None]
        if not (len(closes) == len(rows) and len(highs) == len(rows) and len(lows) == len(rows)):
            block["data_quality_notes"].append("high/low/close 누락 구간이 있어 일부 지표는 계산이 제한됩니다.")

        # RSI(14)
        rsi_value = None
        if len(closes) >= 15:
            gains: list[float] = []
            losses: list[float] = []
            for i in range(1, len(closes)):
                diff = closes[i] - closes[i - 1]
                gains.append(max(diff, 0.0))
                losses.append(max(-diff, 0.0))
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            if avg_loss == 0:
                rsi_value = 100.0 if avg_gain > 0 else 50.0
            else:
                rs = avg_gain / avg_loss
                rsi_value = 100 - (100 / (1 + rs))
        else:
            block["data_quality_notes"].append("RSI 계산에 필요한 가격 데이터가 부족합니다.")
        rsi_status = "데이터 부족으로 계산 불가"
        if rsi_value is not None:
            if rsi_value >= 70:
                rsi_status = "상대적으로 강한 구간"
            elif rsi_value <= 30:
                rsi_status = "상대적으로 약한 구간"
            else:
                rsi_status = "중립에 가까운 구간"

        # MACD(12,26,9)
        macd = signal = hist = None
        macd_status = "데이터 부족으로 계산 불가"
        if len(closes) >= 26:
            ema12 = self._ema(closes, 12)
            ema26 = self._ema(closes, 26)
            macd_series = [a - b for a, b in zip(ema12, ema26)]
            signal_series = self._ema(macd_series, 9)
            macd = macd_series[-1]
            signal = signal_series[-1]
            hist = macd - signal
            if macd > signal:
                macd_status = "단기 평균이 장기 평균보다 높은 구간"
            elif macd < signal:
                macd_status = "단기 평균이 장기 평균보다 낮은 구간"
            else:
                macd_status = "MACD와 signal 간 차이가 크지 않은 구간"
        else:
            block["data_quality_notes"].append("MACD 계산에 필요한 장기 가격 데이터가 부족합니다.")

        # Bollinger(20,2)
        bb = {"upper_band": None, "middle_band": None, "lower_band": None, "band_width": None, "close_position": None}
        if len(closes) >= 20:
            win = closes[-20:]
            mid = sum(win) / 20
            var = sum((x - mid) ** 2 for x in win) / 20
            std = var ** 0.5
            upper = mid + 2 * std
            lower = mid - 2 * std
            last_close = closes[-1]
            band_width = None if mid == 0 else (upper - lower) / mid
            if last_close > upper or last_close < lower:
                pos = "밴드 밖 위치"
            elif last_close >= mid + (upper - mid) * 0.5:
                pos = "상단에 가까움"
            elif last_close <= mid - (mid - lower) * 0.5:
                pos = "하단에 가까움"
            else:
                pos = "중심선 부근"
            bb = {
                "upper_band": round(upper, 2),
                "middle_band": round(mid, 2),
                "lower_band": round(lower, 2),
                "band_width": None if band_width is None else round(band_width, 4),
                "close_position": pos,
            }
        else:
            block["data_quality_notes"].append("볼린저밴드 계산에 필요한 가격 데이터가 부족합니다.")

        # ATR(14)
        atr_val = atr_ratio = None
        if len(closes) >= 15 and len(highs) == len(rows) and len(lows) == len(rows):
            tr_list: list[float] = []
            for i in range(1, len(rows)):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
                tr_list.append(tr)
            atr_slice = tr_list[-14:]
            atr_val = sum(atr_slice) / len(atr_slice) if atr_slice else None
            atr_ratio = None if (atr_val is None or closes[-1] == 0) else (atr_val / closes[-1]) * 100
        else:
            block["data_quality_notes"].append("ATR 계산에 필요한 가격 데이터가 부족합니다.")

        # MA gap
        latest = rows[-1]
        close = latest.close_price
        def gap(ma: float | None) -> float | None:
            if close in (None,) or ma in (None, 0):
                return None
            return round(((float(close) - float(ma)) / float(ma)) * 100, 2)
        ma_gap = {
            "close": close,
            "ma5_gap_pct": gap(latest.ma5),
            "ma10_gap_pct": gap(latest.ma10),
            "ma20_gap_pct": gap(latest.ma20),
            "ma60_gap_pct": gap(latest.ma60),
            "ma120_gap_pct": gap(latest.ma120),
            "ma240_gap_pct": gap(latest.ma240),
            "note_ko": "이동평균선 대비 현재 가격 위치 참고값입니다.",
        }
        if any(ma_gap[k] is None for k in ("ma120_gap_pct", "ma240_gap_pct")):
            block["data_quality_notes"].append("일부 장기 이동평균선 값이 없어 이격도 계산에서 제외되었습니다.")

        # Volume ratio
        vol_ratio = {"volume": latest.volume, "volume_ma5": None, "volume_ma20": None, "volume_5_20_ratio": None, "note_ko": "최근 거래량 변화 참고 지표입니다."}
        if len(vols) >= 20 and len(vols) == len(rows):
            ma5 = sum(vols[-5:]) / 5
            ma20 = sum(vols[-20:]) / 20
            ratio = None if ma20 == 0 else ma5 / ma20
            vol_ratio["volume_ma5"] = round(ma5, 2)
            vol_ratio["volume_ma20"] = round(ma20, 2)
            vol_ratio["volume_5_20_ratio"] = None if ratio is None else round(ratio, 4)
        else:
            block["data_quality_notes"].append("거래량 데이터가 부족해 5일/20일 비율 계산이 제한됩니다.")

        block["indicators"] = {
            "rsi": {
                "period": 14,
                "value": None if rsi_value is None else round(rsi_value, 2),
                "status_ko": rsi_status,
                "note_ko": "RSI는 상대적 강약 상태를 보는 참고 지표입니다.",
            },
            "macd": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "macd": None if macd is None else round(macd, 4),
                "signal": None if signal is None else round(signal, 4),
                "histogram": None if hist is None else round(hist, 4),
                "status_ko": macd_status,
                "note_ko": "MACD는 단기·장기 평균 간 상대 위치 참고값입니다.",
            },
            "bollinger_bands": {
                "period": 20,
                "stddev_multiplier": 2,
                **bb,
                "note_ko": "볼린저밴드는 현재 가격 위치와 변동 폭 참고 지표입니다.",
            },
            "atr": {
                "period": 14,
                "value": None if atr_val is None else round(atr_val, 4),
                "atr_ratio_to_close": None if atr_ratio is None else round(atr_ratio, 2),
                "note_ko": "ATR은 변동성 크기를 참고하기 위한 지표입니다.",
            },
            "moving_average_gap": ma_gap,
            "volume_ratio": vol_ratio,
        }
        return block

    def _build_technical_indicators_block_from_stored(self, stored_row, include: bool, lookback_days: int) -> dict:
        block = {
            "included": include,
            "source": "stored",
            "calculation_version": getattr(stored_row, "calculation_version", "v1"),
            "as_of_date": getattr(stored_row, "trade_date", None),
            "lookback_days": lookback_days,
            "indicators": {},
            "interpretation_notes_ko": [
                "기술적 지표는 가격 위치, 추세, 변동성, 거래량 변화를 참고하기 위한 보조 정보입니다.",
                "각 지표는 단독으로 투자 판단을 내리기 위한 근거가 아닙니다.",
                "뉴스·공시·Risk, 시장지표와 함께 종합적으로 검토해야 합니다.",
            ],
            "data_quality_notes": [],
        }
        if not include:
            return block
        rsi_value = stored_row.rsi14
        if rsi_value is None:
            rsi_status = "데이터 부족으로 계산 불가"
        elif rsi_value >= 70:
            rsi_status = "상대적으로 강한 구간"
        elif rsi_value <= 30:
            rsi_status = "상대적으로 약한 구간"
        else:
            rsi_status = "중립에 가까운 구간"

        macd_status = "데이터 부족으로 계산 불가"
        if stored_row.macd is not None and stored_row.macd_signal is not None:
            if stored_row.macd > stored_row.macd_signal:
                macd_status = "단기 평균이 장기 평균보다 높은 구간"
            elif stored_row.macd < stored_row.macd_signal:
                macd_status = "단기 평균이 장기 평균보다 낮은 구간"
            else:
                macd_status = "MACD와 signal 간 차이가 크지 않은 구간"

        block["indicators"] = {
            "rsi": {"period": 14, "value": rsi_value, "status_ko": rsi_status, "note_ko": "RSI는 상대적 강약 상태를 보는 참고 지표입니다."},
            "macd": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "macd": stored_row.macd,
                "signal": stored_row.macd_signal,
                "histogram": stored_row.macd_histogram,
                "status_ko": macd_status,
                "note_ko": "MACD는 단기·장기 평균 간 상대 위치 참고값입니다.",
            },
            "bollinger_bands": {
                "period": 20,
                "stddev_multiplier": 2,
                "upper_band": stored_row.bb_upper,
                "middle_band": stored_row.bb_middle,
                "lower_band": stored_row.bb_lower,
                "band_width": stored_row.bb_width,
                "close_position": stored_row.bb_close_position,
                "note_ko": "볼린저밴드는 현재 가격 위치와 변동 폭 참고 지표입니다.",
            },
            "atr": {
                "period": 14,
                "value": stored_row.atr14,
                "atr_ratio_to_close": stored_row.atr14_ratio_to_close,
                "note_ko": "ATR은 변동성 크기를 참고하기 위한 지표입니다.",
            },
            "moving_average_gap": {
                "close": None,
                "ma5_gap_pct": stored_row.ma5_gap_pct,
                "ma10_gap_pct": stored_row.ma10_gap_pct,
                "ma20_gap_pct": stored_row.ma20_gap_pct,
                "ma60_gap_pct": stored_row.ma60_gap_pct,
                "ma120_gap_pct": stored_row.ma120_gap_pct,
                "ma240_gap_pct": stored_row.ma240_gap_pct,
                "note_ko": "이동평균선 대비 현재 가격 위치 참고값입니다.",
            },
            "volume_ratio": {
                "volume": None,
                "volume_ma5": stored_row.volume_ma5,
                "volume_ma20": stored_row.volume_ma20,
                "volume_5_20_ratio": stored_row.volume_5_20_ratio,
                "note_ko": "최근 거래량 변화 참고 지표입니다.",
            },
        }
        return block

    @staticmethod
    def _build_data_freshness_block(
        *,
        generated_at: str,
        price_summary: dict,
        market_metrics_summary: dict | None,
        technical_indicators_block: dict,
        news_blocks: dict,
    ) -> dict:
        price_date = price_summary.get("latest_trade_date")
        price_source = price_summary.get("source")
        market_date = None if market_metrics_summary is None else market_metrics_summary.get("latest_market_metrics_date")
        market_source = None if market_metrics_summary is None else market_metrics_summary.get("source")
        market_stale = bool(market_metrics_summary.get("is_stale")) if market_metrics_summary else None
        tech_date = technical_indicators_block.get("as_of_date")
        tech_source = technical_indicators_block.get("source")
        tech_version = technical_indicators_block.get("calculation_version")
        news_lookback_days = news_blocks.get("news_summary_block", {}).get("lookback_days", 30)
        news_count = news_blocks.get("news_summary_block", {}).get("total_found", 0)
        disclosure_count = news_blocks.get("disclosure_summary_block", {}).get("total_found", 0)

        if price_date and tech_date and market_date and not market_stale:
            confidence_level = "high"
            confidence_summary = "가격, 시장지표, 기술적 지표 기준일이 비교적 정렬되어 데이터 품질 신뢰도가 높습니다."
        elif price_date and tech_date:
            confidence_level = "medium"
            confidence_summary = "가격과 기술적 지표는 확인되지만 시장지표 최신성은 별도 확인이 필요합니다."
        else:
            confidence_level = "low"
            confidence_summary = "핵심 기준일 데이터가 일부 부족하여 데이터 품질 신뢰도가 낮을 수 있습니다."

        return {
            "package_generated_at": generated_at,
            "price": {
                "source": price_source,
                "latest_trade_date": price_date,
                "status_ko": "가격 데이터가 확인되었습니다." if price_date else "가격 기준일 데이터가 부족합니다.",
            },
            "market_metrics": {
                "source": market_source,
                "latest_trade_date": market_date,
                "price_trade_date": None if market_metrics_summary is None else market_metrics_summary.get("latest_price_trade_date"),
                "date_gap_days": None if market_metrics_summary is None else market_metrics_summary.get("date_gap_days"),
                "date_gap_label": None if market_metrics_summary is None else market_metrics_summary.get("date_gap_label"),
                "stale": market_stale,
                "freshness_status": None if market_metrics_summary is None else market_metrics_summary.get("freshness_status"),
                "freshness_label": None if market_metrics_summary is None else market_metrics_summary.get("freshness_label"),
                "status_ko": (
                    "시장지표 기준일이 가격 기준일보다 오래되었습니다."
                    if market_stale
                    else ("시장지표 데이터가 확인되었습니다." if market_date else "시장지표 데이터가 없습니다.")
                ),
            },
            "technical_indicators": {
                "source": tech_source,
                "latest_trade_date": tech_date,
                "calculation_version": tech_version,
                "status_ko": (
                    "저장된 기술적 지표를 사용했습니다."
                    if tech_source == "stored"
                    else ("저장값이 없어 실시간 계산값을 사용했습니다." if tech_source else "기술적 지표가 비활성화되었습니다.")
                ),
            },
            "news_disclosures": {
                "lookback_days": news_lookback_days,
                "news_count": news_count,
                "disclosure_count": disclosure_count,
                "status_ko": "최근 뉴스·공시 데이터가 확인되었습니다." if (news_count + disclosure_count) > 0 else "최근 뉴스·공시 데이터가 부족할 수 있습니다.",
            },
            "overall_data_confidence": {"level": confidence_level, "summary_ko": confidence_summary},
            "notes_ko": [
                "시장지표는 source와 기준일을 함께 확인해야 합니다.",
                "KRX Open API 승인 전까지 거래대금 최신성은 제한될 수 있습니다.",
            ],
        }

    @staticmethod
    def _build_executive_summary_for_gpt(
        *,
        candle_reference: dict | None,
        technical_indicators_block: dict,
        news_blocks: dict,
        data_freshness_block: dict,
    ) -> dict:
        confidence = (data_freshness_block.get("overall_data_confidence") or {}).get("level", "unknown")
        generated_basis = {
            "price": True,
            "market_metrics": bool(data_freshness_block.get("market_metrics", {}).get("latest_trade_date")),
            "technical_indicators": bool(technical_indicators_block.get("included")),
            "news_disclosures_risk": bool(news_blocks.get("news_summary_block", {}).get("included")),
            "similar_patterns": bool((candle_reference or {}).get("similar_pattern_cases", {}).get("included")),
        }
        return {
            "summary_ko": "이 패키지는 가격, 기술적 지표, 뉴스·공시·Risk, 유사 패턴을 함께 검토하기 위한 GPT 분석용 근거 자료입니다. 데이터 기준일과 품질 상태를 먼저 확인한 뒤 단기와 중장기 관점을 분리해 해석해야 합니다.",
            "key_points": [
                "가격과 기술적 지표의 기준일을 먼저 확인해 주세요.",
                "시장지표는 source와 stale 여부를 함께 확인해 주세요.",
                "뉴스·공시 데이터가 부족하면 이벤트 해석 신뢰도는 낮아질 수 있습니다.",
                "과거 유사 패턴은 예측이 아니라 참고 사례입니다.",
            ],
            "analyst_focus_points": [
                "단기 관점에서 거래량 변화와 MA20 위치를 함께 검토해 주세요.",
                "기술적 지표와 실제 가격 흐름 방향이 같은지 확인해 주세요.",
                "뉴스·공시·Risk 이벤트가 가격 변화와 연결되는지 검토해 주세요.",
                "시장지표 기준일이 오래된 경우 거래대금 해석을 보수적으로 진행해 주세요.",
                "유사 패턴 후속 수익률은 과거 참고값으로만 해석해 주세요.",
            ],
            "caution_points": [
                "이 패키지는 자동 매수/매도 판단을 제공하지 않습니다.",
                "목표가나 확정 수익률을 제시하지 않습니다.",
                "데이터가 부족한 블록은 낮은 신뢰도로 해석해야 합니다.",
                "최종 투자 판단은 사용자가 수행해야 합니다.",
            ],
            "data_confidence_level": confidence,
            "generated_basis": generated_basis,
        }

    def get_evidence_package(self, stock_id: int, options: EvidencePackageOptions | None = None) -> AdvisoryEvidencePackageResponse:
        generated_at = now_kst()
        resolved = self._normalize_options(options or EvidencePackageOptions())
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        price_summary = self.price_service.get_summary(stock_id=stock_id, source=resolved.price_source)
        data_quality_notes: list[str] = []

        market_metrics_summary = None
        try:
            market_metrics_summary = self.market_metrics_service.get_summary(stock_id=stock_id, source=resolved.market_metrics_source)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND or exc.detail != "market metrics not found":
                raise
            data_quality_notes.append(f"시장지표 요약 데이터가 없습니다. source={resolved.market_metrics_source} 데이터 확인이 필요합니다.")
        if market_metrics_summary and market_metrics_summary.get("is_stale"):
            data_quality_notes.append("시장지표 기준일이 최신 가격 기준일보다 오래되어 해석 시 주의가 필요합니다.")
        if market_metrics_summary and market_metrics_summary.get("data_note"):
            data_quality_notes.append(str(self._localize_market_metrics_note(market_metrics_summary["data_note"])))

        candle_reference = self._build_candle_reference(stock_id=stock_id, source=resolved.price_source, options=resolved)
        if candle_reference and candle_reference["similar_pattern_cases"]["included"]:
            data_quality_notes.extend(candle_reference["similar_pattern_cases"]["data_quality_notes"])
        recent_price_rows = self.price_repo.list_recent_rows(stock_id=stock_id, source=resolved.price_source, limit=252)
        stored_indicator = self.technical_indicator_service.get_latest_indicator(stock_id=stock_id)
        if resolved.include_technical_indicators and stored_indicator is not None:
            technical_indicators_block = self._build_technical_indicators_block_from_stored(
                stored_row=stored_indicator,
                include=True,
                lookback_days=252,
            )
        else:
            technical_indicators_block = self._build_technical_indicators_block(
                rows_desc=recent_price_rows,
                include=resolved.include_technical_indicators,
                lookback_days=252,
            )
            if resolved.include_technical_indicators:
                technical_indicators_block["source"] = "calculated_fallback"
                technical_indicators_block["calculation_version"] = "v1"
                if stored_indicator is None:
                    technical_indicators_block["data_quality_notes"].append(
                        "저장된 기술적 지표가 없어 실시간 계산값을 사용했습니다."
                    )
        data_quality_notes.extend(technical_indicators_block.get("data_quality_notes", []))

        strategy_horizon_context, analysis_horizon_weights = self._build_strategy_horizon_context(resolved.strategy_horizon)
        scenario_questions = self._build_scenario_questions(resolved)

        if resolved.include_news_disclosures_risk:
            news_blocks = self._build_news_disclosure_blocks(stock_id=stock_id, lookback_days=30, max_items=5)
            if news_blocks["news_summary_block"]["total_found"] == 0:
                data_quality_notes.append("최근 30일 뉴스 데이터가 부족합니다.")
            if news_blocks["disclosure_summary_block"]["total_found"] == 0:
                data_quality_notes.append("최근 30일 공시 데이터가 부족합니다.")
        else:
            news_blocks = {
                "news_summary_block": {"included": False, "lookback_days": 30, "max_items": 5, "total_found": 0, "items": []},
                "disclosure_summary_block": {"included": False, "lookback_days": 30, "max_items": 5, "total_found": 0, "items": []},
                "risk_summary_block": {
                    "included": False,
                    "lookback_days": 30,
                    "news_risk_counts": self._empty_risk_counts(),
                    "disclosure_risk_counts": self._empty_risk_counts(),
                    "combined_risk_counts": self._empty_risk_counts(),
                    "highest_risk_level": "unknown",
                    "risk_summary_ko": "옵션이 비활성화되어 뉴스·공시·Risk 블록을 포함하지 않았습니다.",
                    "caution_notes_ko": ["필요 시 include_news_disclosures_risk=true로 다시 조회해 주세요."],
                },
                "recent_event_timeline": [],
            }

        instruction_guardrails = [
            "이 패키지는 자동 투자 판단을 위한 자료가 아니라 근거 정리 참고 자료입니다.",
            "자동 매수/매도, 목표가 단정, 확정 수익률 표현을 생성하지 않습니다.",
            "과거 유사 패턴은 미래 예측이 아니라 과거 참고 사례로만 해석해야 합니다.",
            "최종 투자 판단은 사용자가 수행해야 합니다.",
        ]

        instruction_guardrails = instruction_guardrails + ["기술적 지표는 보조 참고 정보이며 자동 매수/매도 판단 신호가 아닙니다."]

        data_freshness_block = self._build_data_freshness_block(
            generated_at=generated_at,
            price_summary=price_summary,
            market_metrics_summary=market_metrics_summary,
            technical_indicators_block=technical_indicators_block,
            news_blocks=news_blocks,
        )
        executive_summary_for_gpt = self._build_executive_summary_for_gpt(
            candle_reference=candle_reference,
            technical_indicators_block=technical_indicators_block,
            news_blocks=news_blocks,
            data_freshness_block=data_freshness_block,
        )

        return AdvisoryEvidencePackageResponse(
            stock={"stock_id": stock.id, "stock_code": stock.stock_code, "stock_name": stock.stock_name},
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
                    "date_gap_days": market_metrics_summary.get("date_gap_days"),
                    "date_gap_label": market_metrics_summary.get("date_gap_label"),
                    "freshness_status": market_metrics_summary.get("freshness_status"),
                    "freshness_label": market_metrics_summary.get("freshness_label"),
                    "freshness_message": market_metrics_summary.get("freshness_message"),
                    "is_stale": market_metrics_summary["is_stale"],
                    "stale_days": market_metrics_summary.get("stale_days"),
                    "staleness_level": market_metrics_summary["staleness_level"],
                    "market": market_metrics_summary.get("market"),
                    "trading_value": market_metrics_summary.get("trading_value"),
                    "trading_value_display": market_metrics_summary.get("trading_value_display"),
                    "market_cap": market_metrics_summary.get("market_cap"),
                    "market_cap_display": market_metrics_summary.get("market_cap_display"),
                    "listed_shares": market_metrics_summary.get("listed_shares"),
                    "trading_volume": market_metrics_summary.get("trading_volume"),
                    "trading_value_rank": market_metrics_summary.get("trading_value_rank"),
                    "market_trading_value_rank": market_metrics_summary.get("market_trading_value_rank"),
                    "trading_value_percentile": market_metrics_summary.get("trading_value_percentile"),
                    "market_trading_value_percentile": market_metrics_summary.get("market_trading_value_percentile"),
                    "source": market_metrics_summary["source"],
                    "unit_notes": market_metrics_summary.get("unit_notes"),
                    "data_note": self._localize_market_metrics_note(market_metrics_summary["data_note"]),
                }
            ),
            price_candle_reference=candle_reference,
            strategy_horizon_context=strategy_horizon_context,
            analysis_horizon_weights=analysis_horizon_weights,
            scenario_questions_for_gpt=scenario_questions,
            news_summary_block=news_blocks["news_summary_block"],
            disclosure_summary_block=news_blocks["disclosure_summary_block"],
            risk_summary_block=news_blocks["risk_summary_block"],
            recent_event_timeline=news_blocks["recent_event_timeline"],
            technical_indicators_block=technical_indicators_block,
            data_freshness_block=data_freshness_block,
            executive_summary_for_gpt=executive_summary_for_gpt,
            news_summary=None,
            disclosure_summary=None,
            risk_summary=None,
            theme_summary=None,
            telegram_theme_summary=None,
            data_quality_notes=data_quality_notes,
            instruction_guardrails=instruction_guardrails,
            generated_at=generated_at,
        )
