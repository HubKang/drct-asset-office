from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from backend.app.services.marker_current_pattern_scan_service import MarkerCurrentPatternScanService
from backend.tests.test_drct_marker_learning_phase6a import _db


def _seed_scan(db):  # type: ignore[no-untyped-def]
    db.execute(text("INSERT INTO chart_marker_groups(id,name,color,sort_order,is_active,created_at,updated_at) VALUES(1,'지지/저항','#16a34a',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.execute(text("INSERT INTO chart_markers(id,marker_group_id,name,symbol,sort_order,is_active,created_at,updated_at) VALUES(1,1,'지지 - 테스트 Marker','T',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    for theme_id, name, active, level in ((1,"테마A",1,"THEME"),(2,"테마B",1,"THEME"),(3,"비활성",0,"THEME"),(4,"그룹",1,"THEME_GROUP")):
        db.execute(text("""INSERT INTO market_themes(id,theme_name,theme_code,theme_type,theme_level,keywords,is_supply_theme,is_active,sort_order,created_at,updated_at)
            VALUES(:id,:name,:code,'MANUAL',:level,'[]',0,:active,:id,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),{"id":theme_id,"name":name,"code":f"T{theme_id}","level":level,"active":active})
    start=date(2026,2,1); end=date(2026,6,30); d0=date(2026,5,1)
    event_id=1
    for stock_id in range(1,8):
        db.execute(text("INSERT INTO stocks(id,stock_code,stock_name,is_active,created_at,updated_at) VALUES(:id,:code,:name,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"id":stock_id,"code":f"00000{stock_id}","name":f"종목{stock_id}"})
        db.execute(text("INSERT INTO market_theme_stocks(theme_id,stock_id,mapping_source,is_primary,is_active,created_at,updated_at) VALUES(1,:stock,'test',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"stock":stock_id})
        if stock_id==7:
            db.execute(text("INSERT INTO market_theme_stocks(theme_id,stock_id,mapping_source,is_primary,is_active,created_at,updated_at) VALUES(2,7,'test',0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            db.execute(text("INSERT INTO market_theme_stocks(theme_id,stock_id,mapping_source,is_primary,is_active,created_at,updated_at) VALUES(3,7,'test',0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            db.execute(text("INSERT INTO market_theme_stocks(theme_id,stock_id,mapping_source,is_primary,is_active,created_at,updated_at) VALUES(4,7,'test',0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        day=start
        offset=0
        while day<=end:
            close=100+stock_id*.7+offset*.18+((offset%9)-4)*.05*stock_id
            db.execute(text("""INSERT INTO stock_daily_prices(stock_id,trade_date,open_price,high_price,low_price,close_price,volume,trading_value,ma5,ma10,ma20,ma60,ma120,ma240,created_at,updated_at)
                VALUES(:stock,:day,:open,:high,:low,:close,:volume,1000000,:ma5,:ma10,:ma20,:ma60,:ma120,:ma240,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),{
                "stock":stock_id,"day":day.isoformat(),"open":close-.1,"high":close+1,"low":close-1,"close":close,"volume":1000+offset*3+stock_id*11,
                "ma5":close-.3-stock_id*.01,"ma10":close-.6-stock_id*.02,"ma20":close-1.0-stock_id*.03,"ma60":close-2.0-stock_id*.04,"ma120":close-3,"ma240":close-4})
            day+=timedelta(days=1); offset+=1
        if stock_id<=6:
            db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(:id,:stock,1,:d0,'S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"id":event_id,"stock":stock_id,"d0":d0.isoformat()})
            event_id+=1
    db.execute(text("INSERT INTO chart_marker_learning_decisions(chart_marker_event_id,decision,decision_reason,pattern_algorithm_version,created_at,updated_at) VALUES(6,'EXCLUDE','test',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.commit()


@pytest.mark.parametrize("similarity,expected",[(39.9,None),(40.0,"SIMILAR"),(60.0,"HIGH_SIMILARITY"),(80.0,"VERY_SIMILAR")])
def test_candidate_band_boundaries(similarity:float,expected:str|None)->None:
    assert MarkerCurrentPatternScanService._band(similarity,{"p25":40.0,"median":60.0,"p75":80.0})==expected


def test_scan_uses_active_theme_universe_dedupes_and_keeps_theme_names() -> None:
    db=_db(); _seed_scan(db)
    result=MarkerCurrentPatternScanService(db).scan()
    assert result["analysis_date"]=="2026-06-30"
    assert result["universe_count"]==7 and result["evaluable_stock_count"]==7
    assert result["eligible_marker_count"]==1 and result["timings"]["sql_query_count"]==4
    stock7=next((row for row in result["stocks"] if row["stock_id"]==7),None)
    if stock7 is not None:
        assert stock7["theme_names"]==["테마A","테마B"]
    assert result["storage_policy"]=="RUNTIME_ONLY"


def test_scan_is_s_only_honors_exclude_and_does_not_persist() -> None:
    db=_db(); _seed_scan(db)
    tables=("chart_marker_events","chart_marker_learning_decisions","drct_signal_searches")
    before={table:db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in tables}
    first=MarkerCurrentPatternScanService(db).scan(date(2026,6,30))
    assert first["marker_summaries"][0]["training_case_count"]==5
    db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(20,7,1,'2026-05-15','F',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")); db.commit()
    second=MarkerCurrentPatternScanService(db).scan(date(2026,6,30))
    assert [(row["stock_id"],[(signal["marker_id"],signal["current_pattern_similarity"]) for signal in row["signals"]]) for row in first["stocks"]]==[(row["stock_id"],[(signal["marker_id"],signal["current_pattern_similarity"]) for signal in row["signals"]]) for row in second["stocks"]]
    assert before|{"chart_marker_events":before["chart_marker_events"]+1}=={table:db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in tables}


def test_historical_scan_excludes_future_prices_and_training_events() -> None:
    db=_db(); _seed_scan(db); service=MarkerCurrentPatternScanService(db)
    before=service.scan(date(2026,6,1))
    db.execute(text("UPDATE stock_daily_prices SET close_price=99999,high_price=100000,low_price=99998 WHERE trade_date>'2026-06-01'"))
    db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(30,7,1,'2026-06-15','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")); db.commit()
    after=MarkerCurrentPatternScanService(db).scan(date(2026,6,1))
    assert before["marker_summaries"]==after["marker_summaries"]
    assert before["stocks"]==after["stocks"]


def test_multiple_marker_hits_are_preserved_per_stock() -> None:
    db=_db(); _seed_scan(db)
    db.execute(text("INSERT INTO chart_markers(id,marker_group_id,name,symbol,sort_order,is_active,created_at,updated_at) VALUES(2,1,'지지 - 두 번째 Marker','2',2,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    for stock_id in range(1,6):
        db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(:id,:stock,2,'2026-05-01','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"id":100+stock_id,"stock":stock_id})
    db.commit()
    result=MarkerCurrentPatternScanService(db).scan(date(2026,5,1))
    assert result["eligible_marker_count"]==2
    assert any(len(stock["signals"])==2 for stock in result["stocks"])


def test_empty_eligible_markers_and_zero_candidates_are_normal_results() -> None:
    db=_db(); _seed_scan(db)
    db.execute(text("UPDATE chart_marker_events SET review_result='F'")); db.commit()
    empty=MarkerCurrentPatternScanService(db).scan(date(2026,6,30))
    assert empty["eligible_marker_count"]==0 and empty["candidate_stock_count"]==0
    db.rollback(); db.close()

    db=_db(); _seed_scan(db)
    db.execute(text("UPDATE stock_daily_prices SET close_price=99999,high_price=100000,low_price=99998 WHERE trade_date='2026-06-30'")); db.commit()
    no_candidates=MarkerCurrentPatternScanService(db).scan(date(2026,6,30))
    assert no_candidates["candidate_pair_count"]==0 and no_candidates["stocks"]==[]



def test_incomplete_stock_is_counted_without_partial_similarity() -> None:
    db=_db(); _seed_scan(db)
    db.execute(text("DELETE FROM stock_daily_prices WHERE stock_id=7")); db.commit()
    result=MarkerCurrentPatternScanService(db).scan(date(2026,6,30))
    assert result["universe_count"]==7
    assert result["evaluable_stock_count"]==6 and result["incomplete_stock_count"]==1
    assert all(stock["stock_id"]!=7 for stock in result["stocks"])


def test_detail_calculates_only_selected_stock_and_marker_without_full_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    db=_db(); _seed_scan(db)
    scan=MarkerCurrentPatternScanService(db).scan(date(2026,5,1))
    stock=scan["stocks"][0]; expected=stock["signals"][0]
    service=MarkerCurrentPatternScanService(db)
    monkeypatch.setattr(service,"_run",lambda _date: pytest.fail("detail must not rerun the universe scan"))
    detail=service.detail(stock["stock_id"],expected["marker_id"],date(2026,5,1))
    assert service.query_count==3
    assert detail["stock_id"]==stock["stock_id"]
    assert detail["signal"]==expected
    assert len(detail["top_feature_differences"])==5


def test_detail_is_s_only_future_safe_and_runtime_only() -> None:
    db=_db(); _seed_scan(db)
    stock=MarkerCurrentPatternScanService(db).scan(date(2026,6,1))["stocks"][0]
    service=MarkerCurrentPatternScanService(db)
    before=service.detail(stock["stock_id"],1,date(2026,6,1))
    counts={table:db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in ("chart_marker_events","chart_marker_learning_decisions","drct_signal_searches")}
    db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(90,7,1,'2026-05-15','F',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.execute(text("UPDATE stock_daily_prices SET close_price=99999,high_price=100000,low_price=99998 WHERE trade_date>'2026-06-01'")); db.commit()
    after=MarkerCurrentPatternScanService(db).detail(stock["stock_id"],1,date(2026,6,1))
    assert before==after
    assert after["storage_policy"]=="RUNTIME_ONLY"
    assert {table:db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in counts}==counts|{"chart_marker_events":counts["chart_marker_events"]+1}


def test_multiple_marker_detail_keeps_each_marker_independent() -> None:
    db=_db(); _seed_scan(db)
    db.execute(text("INSERT INTO chart_markers(id,marker_group_id,name,symbol,sort_order,is_active,created_at,updated_at) VALUES(2,1,'지지 - 두 번째 Marker','2',2,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    for stock_id in range(1,6):
        db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(:id,:stock,2,'2026-05-01','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"id":100+stock_id,"stock":stock_id})
    db.commit()
    stock=next(row for row in MarkerCurrentPatternScanService(db).scan(date(2026,5,1))["stocks"] if len(row["signals"])==2)
    details=[MarkerCurrentPatternScanService(db).detail(stock["stock_id"],signal["marker_id"],date(2026,5,1)) for signal in stock["signals"]]
    assert {detail["signal"]["marker_id"] for detail in details}=={1,2}
    assert all(detail["stock_id"]==stock["stock_id"] for detail in details)
