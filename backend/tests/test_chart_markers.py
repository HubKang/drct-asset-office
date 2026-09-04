from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from backend.app.schemas.chart_marker_schema import MarkerEventPatch, MarkerEventWrite, MarkerGroupPatch, MarkerGroupWrite, MarkerWrite
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
          CHECK(review_result IS NULL OR review_result IN ('S','F')),UNIQUE(stock_id,marker_id,marker_date))""")
        conn.exec_driver_sql("""CREATE TABLE kms_setting_items(id INTEGER PRIMARY KEY,item_name TEXT,is_active INTEGER NOT NULL)""")
        conn.exec_driver_sql("""CREATE TABLE kms_knowledge_items(id INTEGER PRIMARY KEY,title TEXT NOT NULL,summary TEXT,
          para_type_id INTEGER,category_id INTEGER,is_active INTEGER NOT NULL)""")
        conn.exec_driver_sql("""CREATE TABLE chart_marker_group_knowledge_links(id INTEGER PRIMARY KEY AUTOINCREMENT,
          marker_group_id INTEGER NOT NULL,knowledge_item_id INTEGER NOT NULL,sort_order INTEGER NOT NULL DEFAULT 0,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,UNIQUE(marker_group_id,knowledge_item_id))""")
        conn.exec_driver_sql("INSERT INTO stocks VALUES(1,'005930','삼성전자')")
        start = date(2026, 5, 1)
        for index in range(120):
            trade_date = start + timedelta(days=index)
            conn.exec_driver_sql("INSERT INTO stock_daily_prices VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (index + 1,1,trade_date.isoformat(),101+index,106+index,96+index,103+index,1001+index,100,100,100,100,100))
    return Session(engine)


def _seed_knowledge(db: Session) -> None:
    db.execute(text("INSERT INTO kms_setting_items VALUES (10, '차트패턴', 1), (20, '기술분석', 1)"))
    db.execute(text("""INSERT INTO kms_knowledge_items
        (id,title,summary,para_type_id,category_id,is_active) VALUES
        (1,'거래량 돌파 확인','거래량을 동반한 돌파를 확인합니다.',20,10,1),
        (2,'지지선 반등','지지선 부근 반응을 확인합니다.',20,10,1),
        (3,'과거 비활성 지식','기존 연결 보존 확인용입니다.',20,10,0)"""))
    db.commit()


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


def test_marker_can_be_deleted_only_when_event_count_is_zero() -> None:
    db = _db(); service = ChartMarkerService(db)
    group = service.create_group(MarkerGroupWrite(name="삭제 검증", color="#2563eb"))
    unused = service.create_marker(MarkerWrite(marker_group_id=group["id"], name="미사용 마커"))
    used = service.create_marker(MarkerWrite(marker_group_id=group["id"], name="사용 중 마커"))
    service.upsert_event(MarkerEventWrite(stock_id=1, marker_id=used["id"], marker_date=date(2026, 7, 15), memo=None))

    assert service.delete_marker(unused["id"]) == {"deleted": True, "id": unused["id"]}
    assert db.execute(text("SELECT COUNT(*) FROM chart_markers WHERE id = :id"), {"id": unused["id"]}).scalar_one() == 0
    try:
        service.delete_marker(used["id"])
        raise AssertionError("used marker should not be deleted")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    assert db.execute(text("SELECT COUNT(*) FROM chart_markers WHERE id = :id"), {"id": used["id"]}).scalar_one() == 1
    db.close()


def test_group_knowledge_links_create_update_deduplicate_and_keep_existing_inactive() -> None:
    db = _db(); _seed_knowledge(db); service = ChartMarkerService(db)
    group = service.create_group(MarkerGroupWrite(name="돌파", color="#2563eb", knowledge_item_ids=[1, 1, 2]))
    assert [item["id"] for item in group["knowledge_items"]] == [1, 2]
    assert group["knowledge_items"][0]["category_name"] == "차트패턴"

    db.execute(text("UPDATE kms_knowledge_items SET is_active=0 WHERE id=1")); db.commit()
    updated = service.update_group(group["id"], MarkerGroupPatch(description="설명 변경", knowledge_item_ids=[1, 2]))
    assert updated["knowledge_items"][0]["is_active"] is False

    removed = service.update_group(group["id"], MarkerGroupPatch(knowledge_item_ids=[2]))
    assert [item["id"] for item in removed["knowledge_items"]] == [2]
    db.close()


def test_group_knowledge_links_reject_new_inactive_item() -> None:
    db = _db(); _seed_knowledge(db); service = ChartMarkerService(db)
    try:
        service.create_group(MarkerGroupWrite(name="저점", color="#2563eb", knowledge_item_ids=[3]))
        raise AssertionError("inactive knowledge link should be rejected")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    assert db.execute(text("SELECT COUNT(*) FROM chart_marker_groups")).scalar() == 0
    db.close()


def test_catalog_loads_all_group_knowledge_links_with_one_query() -> None:
    db = _db(); _seed_knowledge(db); service = ChartMarkerService(db)
    service.create_group(MarkerGroupWrite(name="돌파", color="#2563eb", knowledge_item_ids=[1]))
    service.create_group(MarkerGroupWrite(name="반등", color="#16a34a", knowledge_item_ids=[2]))
    knowledge_selects: list[str] = []

    def count_knowledge_query(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:  # type: ignore[no-untyped-def]
        if "FROM chart_marker_group_knowledge_links link" in statement:
            knowledge_selects.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", count_knowledge_query)
    catalog = service.list_catalog()
    event.remove(db.get_bind(), "before_cursor_execute", count_knowledge_query)
    assert len(catalog["items"]) == 2
    assert len(knowledge_selects) == 1
    db.close()


def test_review_chart_uses_forty_before_and_after() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,7,10),40,40)
    assert result["total_candles"] == 81
    assert result["marker_index"] == 40
    assert result["available_before"] == 40 and result["available_after"] == 40
    assert result["requested_before"] == 40 and result["requested_after"] == 40
    assert result["candles"][40]["trade_date"] == "2026-07-10"
    assert [row["trade_date"] for row in result["candles"]] == sorted(row["trade_date"] for row in result["candles"])
    db.close()


def test_marker_event_review_result_updates_existing_event_and_can_be_cleared() -> None:
    db = _db(); service = ChartMarkerService(db)
    group = service.create_group(MarkerGroupWrite(name="반등", color="#2563eb"))
    marker = service.create_marker(MarkerWrite(marker_group_id=group["id"], name="거래량 장대양봉"))
    created = service.upsert_event(MarkerEventWrite(stock_id=1, marker_id=marker["id"], marker_date=date(2026, 7, 15), memo=None))

    success = service.update_event(created["id"], MarkerEventPatch(review_result="S"))
    assert success["review_result"] == "S"
    assert success["reviewed_at"] is not None
    assert service.review_events(marker["id"])["items"][0]["review_result"] == "S"
    reviewed_marker = service.list_catalog()["items"][0]["markers"][0]
    assert reviewed_marker["success_count"] == 1 and reviewed_marker["failure_count"] == 0

    cleared = service.update_event(created["id"], MarkerEventPatch(review_result=None))
    assert cleared["review_result"] is None
    assert cleared["reviewed_at"] is None
    assert len(service.review_events(marker["id"])["items"]) == 1
    db.close()


def test_marker_event_type_can_change_without_resetting_review_result() -> None:
    db = _db(); service = ChartMarkerService(db)
    group = service.create_group(MarkerGroupWrite(name="반등", color="#2563eb"))
    marker_a = service.create_marker(MarkerWrite(marker_group_id=group["id"], name="A"))
    marker_b = service.create_marker(MarkerWrite(marker_group_id=group["id"], name="B"))
    created = service.upsert_event(MarkerEventWrite(stock_id=1, marker_id=marker_a["id"], marker_date=date(2026, 7, 15), memo="기존"))
    reviewed = service.update_event(created["id"], MarkerEventPatch(review_result="S"))

    changed = service.update_event(reviewed["id"], MarkerEventPatch(marker_id=marker_b["id"], memo="수정"))

    assert changed["marker_id"] == marker_b["id"]
    assert changed["memo"] == "수정"
    assert changed["review_result"] == "S"
    assert changed["reviewed_at"] == reviewed["reviewed_at"]
    db.close()


def test_marker_event_type_change_rejects_unique_collision() -> None:
    db = _db(); service = ChartMarkerService(db)
    group = service.create_group(MarkerGroupWrite(name="충돌", color="#2563eb"))
    marker_a = service.create_marker(MarkerWrite(marker_group_id=group["id"], name="A"))
    marker_b = service.create_marker(MarkerWrite(marker_group_id=group["id"], name="B"))
    event_a = service.upsert_event(MarkerEventWrite(stock_id=1, marker_id=marker_a["id"], marker_date=date(2026, 7, 15), memo=None))
    service.upsert_event(MarkerEventWrite(stock_id=1, marker_id=marker_b["id"], marker_date=date(2026, 7, 15), memo=None))

    try:
        service.update_event(event_a["id"], MarkerEventPatch(marker_id=marker_b["id"]))
        raise AssertionError("duplicate marker change should fail")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    db.close()


def test_review_chart_keeps_future_side_at_forty_when_past_is_short() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,5,16),40,40)
    assert (result["available_before"], result["marker_index"], result["available_after"], result["total_candles"]) == (15,15,40,56)
    db.close()


def test_review_chart_keeps_past_side_at_forty_when_future_is_short() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,8,21),40,40)
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
    result=ChartMarkerService(db).review_chart(2,date(2026,1,21),60,20)
    assert result["total_candles"] == 41
    assert result["marker_index"] == 20
    assert result["available_after"] == 20
    assert len({row["trade_date"] for row in result["candles"]}) == 41
    db.close()


def test_review_chart_does_not_replace_a_missing_marker_date() -> None:
    db=_db(); result=ChartMarkerService(db).review_chart(1,date(2026,4,30),81)
    assert result["marker_index"] is None
    assert result["total_candles"] == 0
    assert result["candles"] == []
    db.close()


def test_review_chart_api_uses_before_after_contract() -> None:
    from backend.app.main import app

    parameters = app.openapi()["paths"]["/chart-markers/review/chart"]["get"]["parameters"]
    by_name = {parameter["name"]: parameter for parameter in parameters}
    assert by_name["before_candles"]["schema"]["default"] == 60
    assert by_name["after_candles"]["schema"]["default"] == 20
    assert "candle_count" not in by_name


def test_review_chart_modes_keep_requested_d0_index() -> None:
    db = _db(); service = ChartMarkerService(db)
    marker_date = date(2026, 7, 19)
    for before, after in ((40, 40), (60, 20), (70, 10)):
        result = service.review_chart(1, marker_date, before, after)
        assert result["total_candles"] == 81
        assert result["marker_index"] == before
        assert result["available_before"] == before
        assert result["available_after"] == after
    db.close()


def test_review_chart_does_not_backfill_missing_side() -> None:
    db = _db(); service = ChartMarkerService(db)
    result = service.review_chart(1, date(2026, 5, 26), 60, 20)
    assert result["available_before"] == 25
    assert result["available_after"] == 20
    assert result["total_candles"] == 46
    db.close()
