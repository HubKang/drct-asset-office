from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.providers.market_data.kiwoom_rest_investor_flow_provider import KiwoomRestInvestorFlowProvider
from backend.app.repositories.stock_investor_flow_repository import StockInvestorFlowRepository
from backend.app.schemas.external_kiwoom_schema import MarketThemeReturnRefreshRequest
from backend.app.services.external_kiwoom_service import ExternalKiwoomService
from backend.app.services.stock_investor_flow_service import StockInvestorFlowService
from backend.app.services.market_theme_price_flow_collection_service import (
    MarketThemePriceFlowCollectionService,
    MarketThemePriceFlowJobManager,
)
from backend.app.services.stock_price_service import StockPriceService


def test_ka10059_maps_individual_foreign_and_institution_by_trade_side() -> None:
    raw = {
        "dt": "20260801",
        "ind_invsr": "1,200",
        "frgnr_invsr": "-300",
        "orgn": "-900",
        "fnnc_invt": "-100",
    }

    net = KiwoomRestInvestorFlowProvider._map_ka10059_qty_row(raw, trade_side="net")
    buy = KiwoomRestInvestorFlowProvider._map_ka10059_qty_row(raw, trade_side="buy")

    assert net is not None
    assert net.individual_net_qty == 1200
    assert net.foreign_net_qty == -300
    assert net.institution_net_qty == -900
    assert net.financial_investment_net_qty == -100
    assert buy is not None
    assert buy.individual_buy_qty == 1200
    assert buy.foreign_buy_qty == -300
    assert buy.institution_buy_qty == -900
    assert buy.financial_investment_net_qty is None


def test_ka10059_amount_is_converted_from_million_won_to_won() -> None:
    row = KiwoomRestInvestorFlowProvider._map_ka10059_amount_row(
        {"dt": "20260801", "ind_invsr": "12", "frgnr_invsr": "3", "orgn": "9"},
        trade_side="sell",
    )

    assert row is not None
    assert row.individual_sell_amount == 12_000_000
    assert row.foreign_sell_amount == 3_000_000
    assert row.institution_sell_amount == 9_000_000


def test_ka90013_parses_signed_values_and_converts_amount_to_won() -> None:
    row = KiwoomRestInvestorFlowProvider._map_ka90013_row({
        "dt": "20260801",
        "prm_buy_qty": "+1,200",
        "prm_sell_qty": "300",
        "prm_netprps_qty": "+900",
        "prm_buy_amt": "12",
        "prm_sell_amt": "3",
        "prm_netprps_amt": "9",
    })
    assert row is not None
    assert row.program_buy_qty == 1200
    assert row.program_net_qty == 900
    assert row.program_buy_amount == 12_000_000
    assert row.program_net_amount == 9_000_000


def test_real_flow_is_complete_only_when_all_investors_and_program_exist() -> None:
    complete = {
        "individual_net_qty": 1,
        "foreign_net_qty": 2,
        "institution_net_qty": 3,
        "program_net_qty": 4,
    }
    missing_individual = {key: value for key, value in complete.items() if key != "individual_net_qty"}

    assert StockInvestorFlowService._collection_status(complete) == "SUCCESS"
    assert StockInvestorFlowService._collection_status(missing_individual) == "PARTIAL"


def test_six_month_initial_window_uses_calendar_months() -> None:
    assert StockPriceService._subtract_calendar_months(date(2026, 8, 31), 6) == date(2026, 2, 28)
    assert StockPriceService._subtract_calendar_months(date(2026, 8, 2), 6) == date(2026, 2, 2)


def test_expected_trade_date_rolls_weekend_back_to_friday() -> None:
    assert StockPriceService._latest_expected_weekday(date(2026, 8, 2)) == date(2026, 7, 31)


def test_price_latest_on_expected_trade_date_is_up_to_date() -> None:
    service = object.__new__(StockPriceService)
    stock = SimpleNamespace(id=1, stock_code="034020", stock_name="두산에너빌리티", market="KOSPI")
    service.stock_repo = SimpleNamespace(get_by_ids=lambda ids: [stock])
    service.price_repo = SimpleNamespace(get_latest_trade_dates=lambda ids: {1: "2026-07-31"})
    service._collect_and_upsert_with_stats = lambda *args, **kwargs: pytest.fail("provider must not be called")
    result = service.refresh_theme_stock_price_ranges(stock_ids=[1], end_date=date(2026, 8, 2))
    assert result[0]["status"] == "UP_TO_DATE"
    assert result[0]["attempted"] is False


def test_price_current_trade_date_is_refreshed_when_requested() -> None:
    service = object.__new__(StockPriceService)
    stock = SimpleNamespace(id=1, stock_code="034020", stock_name="두산에너빌리티", market="KOSPI")
    service.stock_repo = SimpleNamespace(get_by_ids=lambda ids: [stock])
    service.price_repo = SimpleNamespace(
        get_latest_trade_dates=lambda ids: {1: "2026-08-03"},
        get_latest_trade_date=lambda stock_id: "2026-08-03",
    )
    calls: list[tuple[date, date]] = []

    def collect(stock, source, start_date, end_date, **kwargs):
        calls.append((start_date, end_date))
        return {
            "collected_count": 1,
            "saved_count": 1,
            "inserted_count": 0,
            "updated_count": 1,
        }

    service._collect_and_upsert_with_stats = collect
    result = service.refresh_theme_stock_price_ranges(
        stock_ids=[1],
        end_date=date(2026, 8, 3),
        refresh_current_trade_date=True,
    )

    assert calls == [(date(2026, 8, 3), date(2026, 8, 3))]
    assert result[0]["status"] == "SUCCESS"
    assert result[0]["attempted"] is True
    assert result[0]["updated_count"] == 1


def test_empty_price_response_is_no_data_not_failed() -> None:
    service = object.__new__(StockPriceService)
    stock = SimpleNamespace(id=1, stock_code="454910", stock_name="두산로보틱스", market="KOSPI")
    service.stock_repo = SimpleNamespace(get_by_ids=lambda ids: [stock])
    service.price_repo = SimpleNamespace(
        get_latest_trade_dates=lambda ids: {},
        get_latest_trade_date=lambda stock_id: None,
    )
    service._collect_and_upsert_with_stats = lambda *args, **kwargs: {
        "collected_count": 0, "saved_count": 0, "inserted_count": 0, "updated_count": 0,
    }
    result = service.refresh_theme_stock_price_ranges(stock_ids=[1], end_date=date(2026, 8, 1))
    assert result[0]["status"] == "NO_DATA"
    assert result[0]["attempted"] is True


def test_common_price_provider_error_stops_repeated_calls() -> None:
    service = object.__new__(StockPriceService)
    stocks = [
        SimpleNamespace(id=1, stock_code="000001", stock_name="A", market="KOSPI"),
        SimpleNamespace(id=2, stock_code="000002", stock_name="B", market="KOSPI"),
    ]
    service.db = SimpleNamespace(rollback=lambda: None)
    service.stock_repo = SimpleNamespace(get_by_ids=lambda ids: stocks)
    service.price_repo = SimpleNamespace(get_latest_trade_dates=lambda ids: {})
    calls: list[int] = []
    def fail_once(stock, *args, **kwargs):
        calls.append(stock.id)
        raise ConnectionError("/oauth2/token WinError 10013")
    service._collect_and_upsert_with_stats = fail_once
    result = service.refresh_theme_stock_price_ranges(stock_ids=[1, 2], end_date=date(2026, 8, 1))
    assert calls == [1]
    assert [item["status"] for item in result] == ["FAILED", "FAILED"]
    assert result[1]["attempted"] is False


def test_stage_summary_distinguishes_success_latest_no_data_skip_and_failure() -> None:
    summary = MarketThemePriceFlowCollectionService._stage_summary(
        [
            {"status": "SUCCESS", "attempted": True, "inserted_count": 2, "updated_count": 1},
            {"status": "UP_TO_DATE", "attempted": False},
            {"status": "NO_DATA", "attempted": True},
            {"status": "SKIPPED", "attempted": False},
            {"status": "FAILED", "attempted": True},
        ],
        inserted_key="inserted_count",
        updated_key="updated_count",
    )
    assert summary.target_count == 5
    assert summary.attempted_count == 3
    assert summary.success_count == 1
    assert summary.up_to_date_count == 1
    assert summary.no_data_count == 1
    assert summary.skipped_count == 1
    assert summary.failed_count == 1
    assert summary.inserted_rows == 2


def test_theme_stock_links_are_deduplicated_by_stock_id() -> None:
    links = [
        {"theme_id": 1, "stock_id": 10, "stock_code": "000010", "stock_name": "A"},
        {"theme_id": 2, "stock_id": 10, "stock_code": "000010", "stock_name": "A"},
        {"theme_id": 2, "stock_id": 20, "stock_code": "000020", "stock_name": "B"},
    ]

    targets = MarketThemePriceFlowCollectionService._deduplicate_stock_links(links)

    assert list(targets) == [10, 20]


def test_pilot_targets_only_select_active_linked_stocks() -> None:
    targets = {
        10: {"stock_id": 10, "stock_code": "005930", "stock_name": "삼성전자"},
        20: {"stock_id": 20, "stock_code": "000660", "stock_name": "SK하이닉스"},
    }
    selected = MarketThemePriceFlowCollectionService._select_collection_targets(
        targets,
        MarketThemeReturnRefreshRequest(mode="PILOT", pilot_stock_codes=["005930"]),
    )
    assert list(selected) == [10]

    with pytest.raises(HTTPException) as exc_info:
        MarketThemePriceFlowCollectionService._select_collection_targets(
            targets,
            MarketThemeReturnRefreshRequest(mode="PILOT", pilot_stock_codes=["999999"]),
        )
    assert exc_info.value.status_code == 422


def test_full_mode_keeps_all_unique_stocks_and_ignores_pilot_limit() -> None:
    targets = {
        10: {"stock_id": 10, "stock_code": "005930", "stock_name": "삼성전자"},
        20: {"stock_id": 20, "stock_code": "000660", "stock_name": "SK하이닉스"},
    }
    selected = MarketThemePriceFlowCollectionService._select_collection_targets(
        targets,
        MarketThemeReturnRefreshRequest(mode="FULL", max_stocks=1),
    )
    assert list(selected) == [10, 20]


def test_flow_window_uses_initial_six_months_if_either_subject_is_missing() -> None:
    start = MarketThemePriceFlowCollectionService._resolve_flow_start(
        end_date=date(2026, 8, 2),
        initial_start=date(2026, 2, 2),
        investor_latest="2026-07-31",
        program_latest=None,
    )
    assert start == date(2026, 2, 2)


def test_flow_window_uses_oldest_subject_latest_date_with_overlap() -> None:
    start = MarketThemePriceFlowCollectionService._resolve_flow_start(
        end_date=date(2026, 8, 2),
        initial_start=date(2026, 2, 2),
        investor_latest="2026-07-31",
        program_latest="2026-07-29",
    )
    assert start == date(2026, 7, 22)


def test_program_failure_does_not_discard_ka10059_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = KiwoomRestInvestorFlowProvider()

    def fake_fetch_pages(**kwargs):
        if kwargs["api_id"] == provider.PROGRAM_API_ID:
            raise RuntimeError("program unavailable")
        if kwargs["api_id"] == provider.FOREIGN_HOLDING_API_ID:
            return {"rows": [], "pages": 1}
        return {
            "rows": [{"dt": "20260801", "ind_invsr": "10", "frgnr_invsr": "20", "orgn": "30"}],
            "pages": 1,
        }

    monkeypatch.setattr(provider, "_fetch_pages", fake_fetch_pages)
    result = provider.get_investor_flows(
        stock_code="005930", start_date="2026-07-01", end_date="2026-08-01", max_rows=30
    )

    assert result["items"]
    assert result["items"][0]["individual_net_qty"] == 10
    assert result["items"][0]["program_net_qty"] is None
    assert "ka90013" in result["collection_errors"]

def test_theme_lightweight_flow_profile_uses_only_three_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = KiwoomRestInvestorFlowProvider()
    calls: list[tuple[str, str | None, str | None]] = []

    def fake_fetch_pages(**kwargs):
        body = kwargs["body"]
        calls.append((kwargs["api_id"], body.get("amt_qty_tp"), body.get("trde_tp")))
        if kwargs["api_id"] == provider.PROGRAM_API_ID:
            return {
                "rows": [{"dt": "20260801", "prm_netprps_qty": "40", "prm_netprps_amt": "4"}],
                "pages": 1,
            }
        return {
            "rows": [{"dt": "20260801", "ind_invsr": "10", "frgnr_invsr": "20", "orgn": "30"}],
            "pages": 1,
        }

    monkeypatch.setattr(provider, "_fetch_pages", fake_fetch_pages)
    result = provider.get_investor_flows(
        stock_code="005930",
        start_date="2026-07-01",
        end_date="2026-08-01",
        max_rows=30,
        include_trade_breakdown=False,
        include_foreign_holding=False,
    )

    assert calls == [
        (provider.INVESTOR_API_ID, "2", "0"),
        (provider.INVESTOR_API_ID, "1", "0"),
        (provider.PROGRAM_API_ID, None, None),
    ]
    assert result["items"][0]["individual_net_qty"] == 10
    assert result["items"][0]["foreign_net_amount"] == 20_000_000
    assert result["items"][0]["institution_net_amount"] == 30_000_000
    assert result["items"][0]["program_net_qty"] == 40
    assert result["items"][0]["program_net_amount"] == 4_000_000
    assert result["source_methods"] == ["kiwoom_rest_ka10059", "kiwoom_rest_ka90013"]
    assert result["ka10008_count"] == 0


def test_theme_flow_probe_skips_only_when_both_sources_are_stale() -> None:
    service = object.__new__(MarketThemePriceFlowCollectionService)
    service.flow_service = SimpleNamespace(kiwoom_provider=SimpleNamespace(
        get_investor_flows=lambda **kwargs: {
            "items": [{
                "flow_date": "2026-07-31",
                "individual_net_qty": 1,
                "foreign_net_qty": 2,
                "institution_net_qty": 3,
                "program_net_qty": 4,
            }],
            "collection_errors": {},
        }
    ))

    result = service._probe_theme_flow_availability(
        stock={"stock_code": "005930"},
        expected_trade_date=date(2026, 8, 3),
    )

    assert result["should_skip"] is True
    assert result["investor_latest_date"] == "2026-07-31"
    assert result["program_latest_date"] == "2026-07-31"


def test_theme_flow_probe_failure_never_suppresses_collection() -> None:
    service = object.__new__(MarketThemePriceFlowCollectionService)
    service.flow_service = SimpleNamespace(kiwoom_provider=SimpleNamespace(
        get_investor_flows=lambda **kwargs: {
            "items": [],
            "collection_errors": {"ka10059_qty_net": "temporary error"},
        }
    ))

    result = service._probe_theme_flow_availability(
        stock={"stock_code": "005930"},
        expected_trade_date=date(2026, 8, 3),
    )

    assert result["should_skip"] is False


def test_saved_theme_stock_returns_are_loaded_in_one_query_with_unit_conversion() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE stock_daily_prices (
                stock_id INTEGER,
                trade_date TEXT,
                change_rate REAL,
                trading_value INTEGER,
                close_price REAL
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO stock_daily_prices VALUES (1, '2026-08-03', 2.5, 12300, 1500)"
        )
    session = sessionmaker(bind=engine)()
    try:
        service = ExternalKiwoomService(session)
        result = service._load_saved_theme_stock_returns(
            {
                1: {"stock_id": 1, "stock_code": "000001", "stock_name": "A"},
                2: {"stock_id": 2, "stock_code": "000002", "stock_name": "B"},
            },
            "2026-08-03",
        )
    finally:
        session.close()

    assert result[1]["data_status"] == "success"
    assert result[1]["change_rate"] == 2.5
    assert result[1]["trading_value"] == 12_300_000_000
    assert result[1]["trading_value_100m"] == 123.0
    assert result[1]["current_price"] == 1500
    assert result[2]["data_status"] == "missing"


def test_job_manager_rejects_duplicate_pending_job() -> None:
    with MarketThemePriceFlowJobManager._lock:
        MarketThemePriceFlowJobManager._jobs.clear()
    try:
        job_id = MarketThemePriceFlowJobManager.start(MarketThemeReturnRefreshRequest())
        assert MarketThemePriceFlowJobManager.get(job_id)["status"] == "PENDING"
        with pytest.raises(HTTPException) as exc_info:
            MarketThemePriceFlowJobManager.start(MarketThemeReturnRefreshRequest())
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["job_id"] == job_id
    finally:
        with MarketThemePriceFlowJobManager._lock:
            MarketThemePriceFlowJobManager._jobs.clear()


def test_job_routes_are_registered_on_main_app() -> None:
    paths = app.openapi()["paths"]
    assert "post" in paths["/external/kiwoom/market-themes/returns-and-flows/jobs"]
    assert "get" in paths["/external/kiwoom/market-themes/returns-and-flows/jobs/{job_id}"]
    assert "post" in paths["/external/kiwoom/market-themes/returns-and-flows/refresh"]


def test_job_post_get_not_found_and_duplicate_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    with MarketThemePriceFlowJobManager._lock:
        MarketThemePriceFlowJobManager._jobs.clear()
    monkeypatch.setattr(MarketThemePriceFlowJobManager, "run", lambda job_id: None)
    try:
        created = client.post(
            "/external/kiwoom/market-themes/returns-and-flows/jobs",
            json={"scope": "all_active", "mode": "PILOT", "max_stocks": 1},
        )
        assert created.status_code == 200
        created_body = created.json()
        assert created_body["job_id"]
        assert created_body["status"] == "PENDING"
        assert created_body["requested_at"]

        status_response = client.get(
            f"/external/kiwoom/market-themes/returns-and-flows/jobs/{created_body['job_id']}"
        )
        assert status_response.status_code == 200
        status_body = status_response.json()
        assert status_body["current_stage"] == "PENDING"
        assert status_body["current_stage_label"] == "작업 준비"

        duplicate = client.post(
            "/external/kiwoom/market-themes/returns-and-flows/jobs",
            json={"scope": "all_active"},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["job_id"] == created_body["job_id"]

        missing = client.get("/external/kiwoom/market-themes/returns-and-flows/jobs/not-a-job")
        assert missing.status_code == 404
        assert missing.json()["detail"]["code"] == "MARKET_THEME_FLOW_JOB_NOT_FOUND"
    finally:
        with MarketThemePriceFlowJobManager._lock:
            MarketThemePriceFlowJobManager._jobs.clear()


FLOW_COLUMNS = (
    "individual_buy_qty", "individual_sell_qty", "individual_net_qty",
    "individual_buy_amount", "individual_sell_amount", "individual_net_amount",
    "foreign_buy_qty", "foreign_sell_qty", "foreign_net_qty",
    "foreign_buy_amount", "foreign_sell_amount", "foreign_net_amount",
    "foreign_holding_qty", "foreign_holding_ratio",
    "institution_buy_qty", "institution_sell_qty", "institution_net_qty",
    "institution_buy_amount", "institution_sell_amount", "institution_net_amount",
    "financial_investment_net_qty", "insurance_net_qty", "investment_trust_net_qty",
    "bank_net_qty", "other_finance_net_qty", "pension_fund_net_qty",
    "private_fund_net_qty", "other_corporation_net_qty",
    "program_buy_qty", "program_sell_qty", "program_net_qty",
    "program_buy_amount", "program_sell_amount", "program_net_amount",
    "program_arbitrage_net_qty", "program_non_arbitrage_net_qty",
)


def _flow_payload(**values: int | float | str | None) -> dict[str, object]:
    row: dict[str, object] = {column: None for column in FLOW_COLUMNS}
    row.update({
        "stock_id": 1,
        "stock_code": "005930",
        "flow_date": "2026-08-01",
        "source": "kiwoom",
        "data_source_type": "KIWOOM_REAL",
        "source_method": "test_partial_flow",
        "is_real_investor_flow": 1,
        "collection_status": "PARTIAL",
        "created_at": "2026-08-02 00:00:00",
        "updated_at": "2026-08-02 00:00:00",
    })
    row.update(values)
    return row


@pytest.mark.parametrize("investor_first", [True, False])
def test_partial_flow_upsert_preserves_investor_and_program_fields(investor_first: bool) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    column_sql = ",\n".join(f"{column} REAL" for column in FLOW_COLUMNS)
    with engine.begin() as connection:
        connection.exec_driver_sql(f"""
            CREATE TABLE stock_investor_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                flow_date TEXT NOT NULL,
                {column_sql},
                source TEXT NOT NULL,
                data_source_type TEXT NOT NULL,
                source_method TEXT NOT NULL,
                is_real_investor_flow INTEGER NOT NULL,
                collection_status TEXT NOT NULL,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(stock_id, flow_date)
            )
        """)
    session = sessionmaker(bind=engine)()
    repo = StockInvestorFlowRepository(session)
    investor = _flow_payload(
        individual_buy_qty=100, individual_sell_qty=40, individual_net_qty=60,
        individual_buy_amount=1_000_000, individual_sell_amount=400_000, individual_net_amount=600_000,
        foreign_buy_qty=20, foreign_net_amount=200_000,
        institution_sell_qty=30, institution_net_amount=-300_000,
    )
    program = _flow_payload(
        program_buy_qty=70, program_sell_qty=10, program_net_qty=60,
        program_buy_amount=700_000, program_sell_amount=100_000, program_net_amount=600_000,
    )
    try:
        for payload in ([investor, program] if investor_first else [program, investor]):
            repo.upsert_flow(payload)
            session.commit()
        row = session.execute(text("SELECT * FROM stock_investor_flows")).mappings().one()
        assert row["individual_buy_qty"] == 100
        assert row["individual_net_amount"] == 600_000
        assert row["foreign_buy_qty"] == 20
        assert row["institution_net_amount"] == -300_000
        assert row["program_buy_qty"] == 70
        assert row["program_net_amount"] == 600_000
        assert session.execute(text("SELECT COUNT(*) FROM stock_investor_flows")).scalar_one() == 1
    finally:
        session.close()
        engine.dispose()
