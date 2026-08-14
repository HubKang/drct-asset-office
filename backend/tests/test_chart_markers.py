from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.schemas.chart_marker_schema import MarkerEventPatch, MarkerEventWrite, MarkerGroupWrite, MarkerWrite
from backend.app.services.chart_marker_service import ChartMarkerService


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.exec_driver_sql("CREATE TABLE stocks(id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT)")
        conn.exec_driver_sql("""CREATE TABLE stock_daily_prices(id INTEGER PRIMARY KEY, stock_id INTEGER, trade_date TEXT,
          open_price REAL, high_price REAL, low_price REAL, close_price REAL, volume INTEGER,
          ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL, ma120 REAL)""")
        conn.exec_driver_sql("""CREATE TABLE chart_marker_groups(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,
          description TEXT,color TEXT NOT NULL,sort_order INTEGER NOT NULL,is_active INTEGER NOT NULL,created_at DATETIME,updated_at DATETIME)""")
        conn.exec_driver_sql("""CREATE TABLE chart_markers(id INTEGER PRIMARY KEY AUTOINCREMENT,marker_group_id INTEGER NOT NULL,name TEXT NOT NULL,
          description TEXT,symbol TEXT NOT NULL,sort_order INTEGER NOT NULL,is_active INTEGER NOT NULL,created_at DATETIME,updated_at DATETIME,
          UNIQUE(marker_group_id,name))""")
        conn.exec_driver_sql("""CREATE TABLE chart_marker_events(id INTEGER PRIMARY KEY AUTOINCREMENT,stock_id INTEGER NOT NULL,marker_id INTEGER NOT NULL,
          marker_date DATE NOT NULL,memo TEXT,review_result TEXT,reviewed_at DATETIME,created_at DATETIME,updated_at DATETIME,
          CHECK(review_result IS NULL OR review_result IN ('SUCCESS','FAILURE')),UNIQUE(stock_id,marker_id,marker_date))""")
        conn.exec_driver_sql("INSERT INTO stocks VALUES(1,'005930','삼성전자')")
        start = date(2026, 5, 1)
        for index in range(120):
            trade_date = start + timedelta(days=index)
            conn.exec_driver_sql("INSERT INTO stock_daily_prices VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (index + 1,1,trade_date.isoformat(),101+index,106+index,96+index,103+index,1001+index,100,100,100,100,100))
    return Session(engine)


def test_marker_event_upsert_updates_memo_without_duplicate() -> None:
    db=_db(); service=ChartMarkerService(db)
    group=service.create_group(MarkerGroupWrite(name="저점확인",color="#2563eb"))
    marker=service.create_marker(MarkerWrite(marker_group_id=group["id"],name="긴 아랫꼬리"))
    first=service.upsert_event(MarkerEventWrite(stock_id=1,marker_id=marker["id"],marker_date=date(2026,7,15),memo="처음"))
    second=service.upsert_event(MarkerEventWrite(stock_id=1,marker_id=marker["id"],marker_date=date(2026,7,15),memo="수정"))
    service.upsert_event(MarkerEventWrite(stock_id=1,marker_id=marker["id"],marker_date=date(2026,7,16),memo=None))
    assert first["created"] is True and second["created"] is False and first["id"]==second["id"]
    events=service.review_events(marker["id"])["items"]
    assert next(item for item in events if item["marker_date"] == "2026-07-15")["memo"]=="수정"
    catalog_marker=service.list_catalog()["items"][0]["markers"][0]
    assert catalog_marker["stock_count"] == 1 and catalog_marker["marker_count"] == 2
    assert catalog_marker["success_count"] == 0 and catalog_marker["failure_count"] == 0
    db.close()


def test_review_chart_centers_marker_between_forty_candles_on_each_side() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,7,10),81)
    assert result["total_candles"] == 81
    assert result["marker_index"] == 40
    assert result["available_before"] == 40 and result["available_after"] == 40
    assert result["candles"][40]["trade_date"] == "2026-07-10"
    assert [row["trade_date"] for row in result["candles"]] == sorted(row["trade_date"] for row in result["candles"])
    db.close()


def test_marker_event_review_result_updates_existing_event_and_can_be_cleared() -> None:
    db = _db(); service = ChartMarkerService(db)
    group = service.create_group(MarkerGroupWrite(name="반등", color="#2563eb"))
    marker = service.create_marker(MarkerWrite(marker_group_id=group["id"], name="거래량 장대양봉"))
    created = service.upsert_event(MarkerEventWrite(stock_id=1, marker_id=marker["id"], marker_date=date(2026, 7, 15), memo=None))

    success = service.update_event(created["id"], MarkerEventPatch(review_result="SUCCESS"))
    assert success["review_result"] == "SUCCESS"
    assert success["reviewed_at"] is not None
    assert service.review_events(marker["id"])["items"][0]["review_result"] == "SUCCESS"
    reviewed_marker = service.list_catalog()["items"][0]["markers"][0]
    assert reviewed_marker["success_count"] == 1 and reviewed_marker["failure_count"] == 0

    cleared = service.update_event(created["id"], MarkerEventPatch(review_result=None))
    assert cleared["review_result"] is None
    assert cleared["reviewed_at"] is None
    assert len(service.review_events(marker["id"])["items"]) == 1
    db.close()


def test_review_chart_keeps_future_side_at_forty_when_past_is_short() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,5,16),81)
    assert (result["available_before"], result["marker_index"], result["available_after"], result["total_candles"]) == (15,15,40,56)
    db.close()


def test_review_chart_keeps_past_side_at_forty_when_future_is_short() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,8,21),81)
    assert (result["available_before"], result["marker_index"], result["available_after"], result["total_candles"]) == (40,40,7,48)
    db.close()


def test_review_chart_returns_all_existing_rows_when_stock_has_fewer_than_eighty_one() -> None:
    db=_db()
    db.execute(text("INSERT INTO stocks VALUES(2,'000002','short history')"))
    start = date(2026, 1, 1)
    for index in range(53):
        trade_date = (start + timedelta(days=index)).isoformat()
        db.execute(text("""INSERT INTO stock_daily_prices
            (id,stock_id,trade_date,open_price,high_price,low_price,close_price,volume,ma5,ma10,ma20,ma60,ma120)
            VALUES(:id,2,:trade_date,100,105,95,102,1000,100,100,100,100,100)"""), {"id": 1000 + index, "trade_date": trade_date})
    db.commit()
    result=ChartMarkerService(db).review_chart(2,date(2026,1,21),81)
    assert result["total_candles"] == 53
    assert result["marker_index"] == 20
    assert result["available_after"] == 32
    assert len({row["trade_date"] for row in result["candles"]}) == 53
    db.close()


def test_review_chart_does_not_replace_a_missing_marker_date() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,4,30),81)
    assert result["marker_index"] is None
    assert result["total_candles"] == 0
    assert result["candles"] == []
    db.close()


def test_review_chart_api_uses_candle_count_contract() -> None:
    from backend.app.main import app

    parameters = app.openapi()["paths"]["/chart-markers/review/chart"]["get"]["parameters"]
    by_name = {parameter["name"]: parameter for parameter in parameters}
    assert by_name["candle_count"]["schema"]["default"] == 81
    assert "before_trading_days" not in by_name
    assert "after_trading_days" not in by_name
