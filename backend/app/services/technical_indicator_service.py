from __future__ import annotations

from backend.app.entities.stock_daily_price import StockDailyPrice
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.technical_indicator_repository import TechnicalIndicatorRepository


class TechnicalIndicatorService:
    def __init__(self, db) -> None:
        self.db = db
        self.price_repo = StockPriceRepository(db)
        self.repo = TechnicalIndicatorRepository(db)

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float]:
        if not values:
            return []
        k = 2 / (period + 1)
        out = [values[0]]
        for value in values[1:]:
            out.append(value * k + out[-1] * (1 - k))
        return out

    @staticmethod
    def _round_or_none(value: float | None, digits: int) -> float | None:
        return None if value is None else round(value, digits)

    def calculate_for_price_rows(self, rows_asc: list[StockDailyPrice]) -> list[dict]:
        if not rows_asc:
            return []

        closes: list[float | None] = [None if r.close_price is None else float(r.close_price) for r in rows_asc]
        highs: list[float | None] = [None if r.high_price is None else float(r.high_price) for r in rows_asc]
        lows: list[float | None] = [None if r.low_price is None else float(r.low_price) for r in rows_asc]
        volumes: list[float | None] = [None if r.volume is None else float(r.volume) for r in rows_asc]

        close_clean = [c if c is not None else 0.0 for c in closes]
        ema12 = self._ema(close_clean, 12)
        ema26 = self._ema(close_clean, 26)
        macd_series = [a - b for a, b in zip(ema12, ema26)]
        signal_series = self._ema(macd_series, 9)

        out: list[dict] = []
        for idx, row in enumerate(rows_asc):
            close = closes[idx]
            high = highs[idx]
            low = lows[idx]

            rsi14 = None
            if idx >= 14:
                gains: list[float] = []
                losses: list[float] = []
                valid = True
                for j in range(idx - 13, idx + 1):
                    if closes[j] is None or closes[j - 1] is None:
                        valid = False
                        break
                    diff = float(closes[j]) - float(closes[j - 1])
                    gains.append(max(diff, 0.0))
                    losses.append(max(-diff, 0.0))
                if valid:
                    avg_gain = sum(gains) / 14
                    avg_loss = sum(losses) / 14
                    if avg_loss == 0:
                        rsi14 = 100.0 if avg_gain > 0 else 50.0
                    else:
                        rs = avg_gain / avg_loss
                        rsi14 = 100 - (100 / (1 + rs))

            macd = signal = histogram = None
            if idx >= 25 and close is not None:
                macd = macd_series[idx]
                signal = signal_series[idx]
                histogram = macd - signal

            bb_upper = bb_middle = bb_lower = bb_width = None
            bb_close_position = None
            if idx >= 19:
                window = closes[idx - 19 : idx + 1]
                if all(v is not None for v in window):
                    vals = [float(v) for v in window]  # type: ignore[arg-type]
                    mid = sum(vals) / 20
                    var = sum((v - mid) ** 2 for v in vals) / 20
                    std = var ** 0.5
                    upper = mid + 2 * std
                    lower = mid - 2 * std
                    bb_middle = mid
                    bb_upper = upper
                    bb_lower = lower
                    bb_width = None if mid == 0 else (upper - lower) / mid
                    if close is not None:
                        if close > upper or close < lower:
                            bb_close_position = "밴드 밖 위치"
                        elif close >= mid + (upper - mid) * 0.5:
                            bb_close_position = "상단에 가까움"
                        elif close <= mid - (mid - lower) * 0.5:
                            bb_close_position = "하단에 가까움"
                        else:
                            bb_close_position = "중심선 부근"

            atr14 = atr14_ratio_to_close = None
            if idx >= 14 and close not in (None, 0):
                tr_values: list[float] = []
                valid = True
                for j in range(idx - 13, idx + 1):
                    if j == 0 or highs[j] is None or lows[j] is None or closes[j - 1] is None:
                        valid = False
                        break
                    tr_values.append(
                        max(
                            float(highs[j]) - float(lows[j]),
                            abs(float(highs[j]) - float(closes[j - 1])),
                            abs(float(lows[j]) - float(closes[j - 1])),
                        )
                    )
                if valid and tr_values:
                    atr14 = sum(tr_values) / len(tr_values)
                    atr14_ratio_to_close = (atr14 / float(close)) * 100

            def ma_gap(ma_value: float | None) -> float | None:
                if close in (None,) or ma_value in (None, 0):
                    return None
                return ((float(close) - float(ma_value)) / float(ma_value)) * 100

            volume_ma5 = volume_ma20 = volume_5_20_ratio = None
            if idx >= 19:
                window20 = volumes[idx - 19 : idx + 1]
                if all(v is not None for v in window20):
                    vals20 = [float(v) for v in window20]  # type: ignore[arg-type]
                    ma20 = sum(vals20) / 20
                    vals5 = vals20[-5:]
                    ma5 = sum(vals5) / 5
                    volume_ma5 = ma5
                    volume_ma20 = ma20
                    volume_5_20_ratio = None if ma20 == 0 else ma5 / ma20

            out.append(
                {
                    "trade_date": row.trade_date,
                    "rsi14": self._round_or_none(rsi14, 2),
                    "macd": self._round_or_none(macd, 4),
                    "macd_signal": self._round_or_none(signal, 4),
                    "macd_histogram": self._round_or_none(histogram, 4),
                    "bb_upper": self._round_or_none(bb_upper, 2),
                    "bb_middle": self._round_or_none(bb_middle, 2),
                    "bb_lower": self._round_or_none(bb_lower, 2),
                    "bb_width": self._round_or_none(bb_width, 4),
                    "bb_close_position": bb_close_position,
                    "atr14": self._round_or_none(atr14, 4),
                    "atr14_ratio_to_close": self._round_or_none(atr14_ratio_to_close, 2),
                    "ma5_gap_pct": self._round_or_none(ma_gap(row.ma5), 2),
                    "ma10_gap_pct": self._round_or_none(ma_gap(row.ma10), 2),
                    "ma20_gap_pct": self._round_or_none(ma_gap(row.ma20), 2),
                    "ma60_gap_pct": self._round_or_none(ma_gap(row.ma60), 2),
                    "ma120_gap_pct": self._round_or_none(ma_gap(row.ma120), 2),
                    "ma240_gap_pct": self._round_or_none(ma_gap(row.ma240), 2),
                    "volume_ma5": self._round_or_none(volume_ma5, 2),
                    "volume_ma20": self._round_or_none(volume_ma20, 2),
                    "volume_5_20_ratio": self._round_or_none(volume_5_20_ratio, 4),
                    "source": "calculated_from_pykrx_prices",
                    "calculation_version": "v1",
                }
            )
        return out

    def calculate_and_save_for_stock(self, stock_id: int) -> dict:
        rows = self.price_repo.list_by_stock_asc(stock_id=stock_id)
        calculated = self.calculate_for_price_rows(rows)
        saved_count = self.repo.upsert_daily_rows(stock_id=stock_id, rows=calculated) if calculated else 0
        latest_trade_date = calculated[-1]["trade_date"] if calculated else None
        return {
            "stock_id": stock_id,
            "calculated_count": len(calculated),
            "saved_count": saved_count,
            "latest_trade_date": latest_trade_date,
            "message": "기술적 지표 계산 및 저장이 완료되었습니다.",
        }

    def get_latest_indicator(self, stock_id: int):
        return self.repo.get_latest(stock_id=stock_id)

