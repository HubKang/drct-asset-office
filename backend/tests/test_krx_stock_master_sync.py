from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.collectors.stocks.krx_stock_collector import KrxStockCollector
from backend.app.core.database import Base
from backend.app.entities.stock import Stock
from backend.app.services.stock_sync_service import StockSyncService


class _FakeKiwoomClient:
    def __init__(self, rows_by_market: dict[str, list[dict[str, str]]]) -> None:
        self.rows_by_market = rows_by_market
        self.calls: list[str] = []

    def post_json(self, _path: str, *, api_id: str, body: dict[str, str], **_kwargs: object) -> SimpleNamespace:
        assert api_id == "ka10099"
        market_type = body["mrkt_tp"]
        self.calls.append(market_type)
        return SimpleNamespace(
            json_body={"return_code": 0, "list": self.rows_by_market.get(market_type, [])},
            cont_yn="N",
            next_key="",
        )


def test_ka10099_uses_official_product_fields_before_stock_name() -> None:
    collector = KrxStockCollector(_FakeKiwoomClient({}))  # type: ignore[arg-type]
    rows = collector._normalize_items([
        {"code": "069500", "name": "KODEX 200", "marketCode": "8", "marketName": "ETF"},
        {"code": "037270", "name": "YG PLUS", "marketCode": "0", "marketName": "거래소"},
        {"code": "500061", "name": "신한 인버스 코스피 200 선물 ETN", "marketCode": "60", "marketName": "ETN"},
        {"code": "088260", "name": "이리츠코크렙", "marketCode": "6", "marketName": "리츠"},
        {"code": "0004Y0", "name": "디비금융제14호스팩", "marketCode": "10", "marketName": "코스닥", "companyClassName": "스팩"},
        {"code": "005935", "name": "삼성전자우", "marketCode": "0", "marketName": "거래소"},
    ])
    assert {row["stock_code"]: row["security_type"] for row in rows} == {
        "069500": "etf",
        "037270": "common_stock",
        "500061": "etn",
        "088260": "reit",
        "0004Y0": "spac",
        "005935": "preferred_stock",
    }


def test_collect_all_deduplicates_overlapping_product_market_calls(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake = _FakeKiwoomClient({
        "0": [
            {"code": "005930", "name": "삼성전자", "marketCode": "0", "marketName": "거래소"},
            {"code": "069500", "name": "KODEX 200", "marketCode": "8", "marketName": "ETF"},
        ],
        "8": [{"code": "069500", "name": "KODEX 200", "marketCode": "8", "marketName": "ETF"}],
    })
    collector = KrxStockCollector(fake)  # type: ignore[arg-type]
    monkeypatch.setattr(type(collector), "is_configured", property(lambda _self: True))
    rows = collector.collect_all()
    assert [row["stock_code"] for row in rows] == ["005930", "069500"]
    assert fake.calls == list(KrxStockCollector.MARKET_TYPES)


def test_rebuild_only_deactivates_selected_security_types() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Stock(stock_code="005930", stock_name="삼성전자", market="KOSPI", security_type="common_stock", is_active=1, created_at="2026-01-01", updated_at="2026-01-01"),
            Stock(stock_code="069500", stock_name="KODEX 200 old", market="KOSPI", security_type="etf", is_active=1, created_at="2026-01-01", updated_at="2026-01-01"),
        ])
        db.commit()
        service = StockSyncService(db)
        service.collector = SimpleNamespace(
            is_configured=True,
            collect_all=lambda: [{
                "stock_code": "069500", "stock_name": "KODEX 200", "market": "KOSPI",
                "security_type": "etf", "isin_code": None, "corp_name": "KODEX 200",
                "corp_reg_no": None, "source": "KIWOOM_REST_KA10099",
            }],
        )
        service.sync_stocks(["KOSPI"], include_security_types=["etf"], mode="rebuild")
        common = service.stock_repo.get_by_code("005930")
        etf = service.stock_repo.get_by_code("069500")
        assert common is not None and common.is_active == 1
        assert etf is not None and etf.is_active == 1 and etf.stock_name == "KODEX 200"
    engine.dispose()
