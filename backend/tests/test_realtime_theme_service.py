from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services import realtime_theme_service as module
from backend.app.services.realtime_theme_service import RealtimeThemeService, calculate_theme_strength, calculate_trimmed_mean


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.exec_driver_sql("CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT, theme_level TEXT, is_supply_theme INTEGER, sort_order INTEGER, is_active INTEGER)")
        conn.exec_driver_sql("CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT, is_active INTEGER)")
        conn.exec_driver_sql("CREATE TABLE market_theme_stocks (id INTEGER PRIMARY KEY, theme_id INTEGER, stock_id INTEGER, is_primary INTEGER, is_active INTEGER, stock_memo TEXT)")
        conn.exec_driver_sql("CREATE TABLE market_theme_realtime_returns (id INTEGER PRIMARY KEY AUTOINCREMENT, trade_date TEXT NOT NULL, theme_id INTEGER NOT NULL, stock_id INTEGER NOT NULL, change_rate REAL NOT NULL, trading_value INTEGER, collected_at TEXT NOT NULL, UNIQUE(trade_date, theme_id, stock_id))")
        conn.exec_driver_sql("INSERT INTO market_themes VALUES (1, 'AI', 'THEME', 0, 1, 1), (2, '반도체', 'THEME', 0, 2, 1)")
        conn.exec_driver_sql("INSERT INTO stocks VALUES (10, '005930', '삼성전자', 1), (20, '000660', 'SK하이닉스', 1)")
        conn.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (1, 1, 10, 1, 1, '대표 AI 종목'), (2, 2, 10, 1, 1, NULL), (3, 2, 20, 0, 1, 'HBM')")
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class FakeProvider:
    calls: list[str] = []
    fail_codes: set[str] = set()

    def __init__(self) -> None:
        pass

    def get_stock_basic_info(self, *, stock_code: str) -> dict[str, object]:
        self.calls.append(stock_code)
        if stock_code in self.fail_codes:
            raise RuntimeError("provider failed")
        if stock_code == "005930":
            return {"change_rate": 2.5, "trading_value": 120_000_000_000}
        return {"change_rate": -1.0, "trading_value": 80_000_000_000}


@pytest.fixture(autouse=True)
def fixed_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeProvider.calls = []
    FakeProvider.fail_codes = set()
    monkeypatch.setattr(module, "KiwoomRestMarketIndicatorProvider", FakeProvider)
    monkeypatch.setattr(module, "now_kst", lambda: "2026-08-13 11:05:03")


def test_refresh_fetches_each_unique_stock_once_and_persists_only_change_rate(db: Session) -> None:
    result = RealtimeThemeService(db).refresh()

    assert FakeProvider.calls == ["005930", "000660"]
    assert result.price_api_call_count == 2
    assert result.linked_stock_count == 3
    assert result.unique_stock_count == 2
    assert result.valid_stock_count == 2
    assert result.failed_stock_count == 0
    assert [(item.theme_name, item.avg_change_rate) for item in result.themes] == [("AI", 2.5), ("반도체", 0.75)]
    # The market median is based on two unique stocks (2.5, -1.0), not the
    # three theme links in which Samsung Electronics appears twice.
    assert next(item.theme_strength for item in result.themes if item.theme_name == "AI") == pytest.approx(1.4583)
    rows = db.execute(text("SELECT theme_id, stock_id, change_rate, trading_value FROM market_theme_realtime_returns ORDER BY theme_id, stock_id")).all()
    assert rows == [(1, 10, 2.5, None), (2, 10, 2.5, None), (2, 20, -1.0, None)]
    dumped = result.model_dump()
    assert "total_trading_value" not in dumped["themes"][0]


def test_theme_stocks_uses_current_snapshot_memo_and_never_calls_provider(db: Session) -> None:
    RealtimeThemeService(db).refresh()
    calls_before_detail = list(FakeProvider.calls)

    detail = RealtimeThemeService(db).get_theme_stocks(2)

    assert FakeProvider.calls == calls_before_detail
    assert detail.theme_name == "반도체"
    assert detail.theme_rank == 2
    assert detail.theme_change_rate == 0.75
    assert [(item.stock_code, item.change_rate, item.memo) for item in detail.stocks] == [
        ("005930", 2.5, None),
        ("000660", -1.0, "HBM"),
    ]
    assert "trading_value" not in detail.stocks[0].model_dump()


def test_partial_failure_excludes_failed_stock_and_does_not_reuse_stale_value(db: Session) -> None:
    RealtimeThemeService(db).refresh()
    FakeProvider.fail_codes = {"000660"}

    result = RealtimeThemeService(db).refresh()

    assert result.valid_stock_count == 1
    assert result.failed_stock_count == 1
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_realtime_returns WHERE stock_id=20")).scalar_one() == 0
    semiconductor = next(item for item in result.themes if item.theme_name == "반도체")
    assert semiconductor.linked_stock_count == 2
    assert semiconductor.valid_stock_count == 1
    assert semiconductor.avg_change_rate == 2.5


def test_refresh_reconciles_removed_links_and_clears_previous_date(db: Session) -> None:
    db.execute(text("INSERT INTO market_theme_realtime_returns (trade_date, theme_id, stock_id, change_rate, trading_value, collected_at) VALUES ('2026-08-12', 2, 20, 9.9, 1, '2026-08-12 15:00:00')"))
    db.execute(text("UPDATE market_theme_stocks SET is_active=0 WHERE id=3"))
    db.commit()

    result = RealtimeThemeService(db).refresh()

    assert result.linked_stock_count == 2
    assert result.unique_stock_count == 1
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_realtime_returns WHERE trade_date='2026-08-12'")).scalar_one() == 0
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_realtime_returns WHERE stock_id=20")).scalar_one() == 0


def test_total_provider_failure_preserves_existing_snapshot(db: Session) -> None:
    RealtimeThemeService(db).refresh()
    before = db.execute(text("SELECT COUNT(*) FROM market_theme_realtime_returns")).scalar_one()
    FakeProvider.fail_codes = {"005930", "000660"}

    with pytest.raises(HTTPException) as error:
        RealtimeThemeService(db).refresh()

    assert error.value.status_code == 502
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_realtime_returns")).scalar_one() == before


def test_theme_strength_reduces_single_outlier_distortion() -> None:
    values = [15, 1, 0.5, -0.2, -0.3]
    assert calculate_theme_strength(values, market_median=0.5) < sum(values) / len(values)


def test_theme_strength_reflects_broad_rise_and_fall() -> None:
    rising = [4, 3.5, 3, 2.5, 2]
    falling = [-4, -3.5, -3, -2.5, -2]
    assert calculate_theme_strength(rising, market_median=3) > 3
    assert calculate_theme_strength(falling, market_median=-3) < -3


def test_single_stock_strength_is_shrunk_toward_market_median() -> None:
    strength = calculate_theme_strength([15], market_median=0.5)
    assert strength is not None
    assert 0.5 < strength < 15


def test_twenty_percent_trim_and_empty_values() -> None:
    assert calculate_trimmed_mean(list(range(1, 11))) == pytest.approx(5.5)
    assert calculate_theme_strength([], market_median=0) is None
