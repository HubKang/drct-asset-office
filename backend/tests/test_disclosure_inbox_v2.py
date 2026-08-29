from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.core.database import Base
from backend.app.entities.disclosure import Disclosure, DisclosureItemExclusion, StockDisclosureCollectionState
from backend.app.entities.stock import Stock
from backend.app.repositories.disclosure_repository import DisclosureRepository
from backend.app.services.collector_service import CollectorService


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def add_stock(db: Session, code: str = "010170", name: str = "대한광통신") -> Stock:
    stock = Stock(
        stock_code=code, stock_name=name, market="KOSDAQ", sector=None, industry=None,
        isin_code=None, corp_name=None, corp_reg_no=None, last_synced_at=None,
        source=None, security_type="보통주", is_active=1,
        created_at="2026-08-29 09:00:00", updated_at="2026-08-29 09:00:00",
    )
    db.add(stock); db.commit(); db.refresh(stock)
    return stock


def disclosure_item(index: int) -> dict:
    return {
        "rcept_no": f"2026082900{index:04d}",
        "report_nm": f"테스트 공시 {index}",
        "pblntf_ty": "A",
        "rcept_dt": "20260829",
    }


def test_initial_collection_expands_until_ten_and_persists_only_durable_fields(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db)

    class Collector:
        name = "dart_disclosure_collector"
        calls: list[str] = []

        def ensure_corp_code_file(self): return None
        def find_corp_code_by_stock_code(self, _code): return "00123456"
        def collect_by_corp_code(self, **kwargs):
            self.calls.append(kwargs["bgn_de"])
            count = [4, 8, 12][len(self.calls) - 1]
            return {"list": [disclosure_item(index) for index in range(count)]}

    collector = Collector()
    monkeypatch.setattr("backend.app.services.collector_service.DartDisclosureCollector", lambda: collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 29))

    result = CollectorService(db).collect_disclosures_for_stock(stock.id)
    rows = list(db.scalars(select(Disclosure).order_by(Disclosure.dart_receipt_no)).all())
    state = db.get(StockDisclosureCollectionState, stock.id)

    assert result["mode"] == "INITIAL"
    assert result["initial_window"] == "1Y"
    assert result["saved_count"] == 10
    assert len(collector.calls) == 3
    assert len(rows) == 10
    assert all(row.raw_text_path is None and row.summary is None for row in rows)
    assert state is not None and state.last_successful_collection_date == "2026-08-29"
    db.close()


def test_same_day_deleted_receipt_is_excluded_then_allowed_next_day(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db)

    class Collector:
        name = "dart_disclosure_collector"
        def ensure_corp_code_file(self): return None
        def find_corp_code_by_stock_code(self, _code): return "00123456"
        def collect_by_corp_code(self, **_kwargs): return {"list": [disclosure_item(1)]}

    monkeypatch.setattr("backend.app.services.collector_service.DartDisclosureCollector", Collector)
    current_day = {"value": date(2026, 8, 29)}
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: current_day["value"])

    first = CollectorService(db).collect_disclosures_for_stock(stock.id)
    saved = db.scalar(select(Disclosure))
    assert first["saved_count"] == 1 and saved is not None

    assert DisclosureRepository(db).delete_by_ids_with_exclusion([saved.id], "2026-08-29") == 1
    assert db.scalar(select(func.count(DisclosureItemExclusion.rcept_no))) == 1

    same_day = CollectorService(db).collect_disclosures_for_stock(stock.id)
    assert same_day["mode"] == "SAME_DAY_REFRESH"
    assert same_day["saved_count"] == 0 and same_day["excluded_skipped"] == 1

    current_day["value"] = date(2026, 8, 30)
    next_day = CollectorService(db).collect_disclosures_for_stock(stock.id)
    assert next_day["mode"] == "INCREMENTAL"
    assert next_day["saved_count"] == 1
    assert db.scalar(select(func.count(DisclosureItemExclusion.rcept_no))) == 0
    db.close()


def test_provider_failure_does_not_move_cursor_or_partially_store(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db)

    class Collector:
        name = "dart_disclosure_collector"
        calls = 0
        def ensure_corp_code_file(self): return None
        def find_corp_code_by_stock_code(self, _code): return "00123456"
        def collect_by_corp_code(self, **_kwargs):
            self.calls += 1
            if self.calls == 2:
                raise ValueError("provider stage failed")
            return {"list": [disclosure_item(index) for index in range(4)]}

    monkeypatch.setattr("backend.app.services.collector_service.DartDisclosureCollector", Collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 29))

    with pytest.raises(HTTPException):
        CollectorService(db).collect_disclosures_for_stock(stock.id)

    assert db.get(StockDisclosureCollectionState, stock.id) is None
    assert db.scalar(select(func.count(Disclosure.id))) == 0
    db.close()


def test_zero_result_searches_all_initial_windows_and_still_advances_cursor(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db)

    class Collector:
        name = "dart_disclosure_collector"
        calls = 0
        def ensure_corp_code_file(self): return None
        def find_corp_code_by_stock_code(self, _code): return "00123456"
        def collect_by_corp_code(self, **_kwargs):
            self.calls += 1
            return {"list": []}

    collector = Collector()
    monkeypatch.setattr("backend.app.services.collector_service.DartDisclosureCollector", lambda: collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 29))

    result = CollectorService(db).collect_disclosures_for_stock(stock.id)

    assert collector.calls == 4
    assert result["initial_window"] == "2Y"
    assert result["saved_count"] == 0
    assert db.get(StockDisclosureCollectionState, stock.id).last_successful_collection_date == "2026-08-29"
    db.close()


def test_incremental_range_uses_cursor_plus_one_and_distinct_receipt_is_correction(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db)
    db.add(StockDisclosureCollectionState(
        stock_id=stock.id,
        last_successful_collection_date="2026-08-27",
        last_successful_at="2026-08-27 18:00:00",
    ))
    db.add(Disclosure(
        stock_id=stock.id, dart_receipt_no="20260827000001", disclosure_title="기존 공시",
        disclosure_type="A", disclosed_at="2026-08-27 00:00:00", url=None,
        raw_text_path=None, summary=None, importance_score=0, created_at="2026-08-27 18:00:00",
    ))
    db.commit()

    class Collector:
        name = "dart_disclosure_collector"
        requested: tuple[str, str] | None = None
        def ensure_corp_code_file(self): return None
        def find_corp_code_by_stock_code(self, _code): return "00123456"
        def collect_by_corp_code(self, **kwargs):
            self.requested = (kwargs["bgn_de"], kwargs["end_de"])
            corrected = disclosure_item(99)
            corrected["report_nm"] = "기존 공시 정정"
            return {"list": [corrected]}

    collector = Collector()
    monkeypatch.setattr("backend.app.services.collector_service.DartDisclosureCollector", lambda: collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 29))

    result = CollectorService(db).collect_disclosures_for_stock(stock.id)

    assert result["mode"] == "INCREMENTAL"
    assert collector.requested == ("20260828", "20260829")
    assert result["saved_count"] == 1
    assert db.scalar(select(func.count(Disclosure.id))) == 2
    db.close()
