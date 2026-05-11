from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class MockPriceRow:
    trade_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    change_price: float
    change_rate: float
    volume: int
    trading_value: int


class MockPriceCollector:
    @property
    def name(self) -> str:
        return "mock_price_collector"

    def _business_days(self, start_date: date, end_date: date) -> list[date]:
        rows: list[date] = []
        cur = start_date
        while cur <= end_date:
            if cur.weekday() < 5:
                rows.append(cur)
            cur += timedelta(days=1)
        return rows

    def collect_daily(
        self,
        stock_id: int,
        stock_code: str,
        start_date: date,
        end_date: date,
    ) -> list[MockPriceRow]:
        business_days = self._business_days(start_date, end_date)
        seed = abs(hash(f"{stock_id}:{stock_code}:{start_date}:{end_date}")) % (2**32)
        rng = random.Random(seed)

        base_price = 10000 + (stock_id % 1000) * 20
        prev_close = float(base_price)
        rows: list[MockPriceRow] = []
        for d in business_days:
            drift = rng.uniform(-0.03, 0.03)
            open_price = prev_close * (1 + rng.uniform(-0.01, 0.01))
            close_price = max(100.0, open_price * (1 + drift))
            high_price = max(open_price, close_price) * (1 + rng.uniform(0.0, 0.015))
            low_price = min(open_price, close_price) * (1 - rng.uniform(0.0, 0.015))
            change_price = close_price - prev_close
            change_rate = 0.0 if prev_close == 0 else (change_price / prev_close) * 100
            volume = int(rng.uniform(100_000, 2_500_000))
            trading_value = int(close_price * volume)
            rows.append(
                MockPriceRow(
                    trade_date=d.strftime("%Y-%m-%d"),
                    open_price=round(open_price, 2),
                    high_price=round(high_price, 2),
                    low_price=round(low_price, 2),
                    close_price=round(close_price, 2),
                    change_price=round(change_price, 2),
                    change_rate=round(change_rate, 4),
                    volume=volume,
                    trading_value=trading_value,
                )
            )
            prev_close = close_price
        return rows
