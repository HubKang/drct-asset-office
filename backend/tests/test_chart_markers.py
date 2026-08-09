from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.schemas.chart_marker_schema import MarkerEventWrite, MarkerGroupWrite, MarkerWrite
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
          marker_date DATE NOT NULL,memo TEXT,created_at DATETIME,updated_at DATETIME,UNIQUE(stock_id,marker_id,marker_date))""")
        conn.exec_driver_sql("INSERT INTO stocks VALUES(1,'005930','삼성전자')")
        for day in range(1, 31):
            conn.exec_driver_sql("INSERT INTO stock_daily_prices VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (day,1,f'2026-07-{day:02d}',100+day,105+day,95+day,102+day,1000+day,100,100,100,100,100))
    return Session(engine)


def test_marker_event_upsert_updates_memo_without_duplicate() -> None:
    db=_db(); service=ChartMarkerService(db)
    group=service.create_group(MarkerGroupWrite(name="저점확인",color="#2563eb"))
    marker=service.create_marker(MarkerWrite(marker_group_id=group["id"],name="긴 아랫꼬리"))
    first=service.upsert_event(MarkerEventWrite(stock_id=1,marker_id=marker["id"],marker_date=date(2026,7,15),memo="처음"))
    second=service.upsert_event(MarkerEventWrite(stock_id=1,marker_id=marker["id"],marker_date=date(2026,7,15),memo="수정"))
    assert first["created"] is True and second["created"] is False and first["id"]==second["id"]
    assert service.review_events(marker["id"])["items"][0]["memo"]=="수정"
    db.close()


def test_review_chart_returns_existing_trading_days_only() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,7,20),5,20)
    assert len(result["candles"])==16
    assert result["before_trading_days"]==5 and result["after_trading_days"]==10
    assert result["candles"][5]["trade_date"]=="2026-07-20"
    db.close()
