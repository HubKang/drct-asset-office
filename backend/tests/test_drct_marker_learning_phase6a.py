from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.core.database import Base, _ensure_marker_review_result_codes
from backend.app.schemas.chart_marker_schema import MarkerEventPatch
from backend.app.schemas.drct_stock_signal_schema import DrctSignalMarkerLinksPut, DrctSignalSearchCreate
from backend.app.services.drct_stock_signal_service import DrctStockSignalService
from backend.app.services.marker_review_result import normalize_marker_review_result
from backend.app.services.marker_training_case_service import MarkerTrainingCaseService


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed(db: Session) -> int:
    db.execute(text("INSERT INTO chart_marker_groups(id,name,color,sort_order,is_active,created_at,updated_at) VALUES (1,'지지','#22c55e',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.execute(text("INSERT INTO chart_markers(id,marker_group_id,name,symbol,sort_order,is_active,created_at,updated_at) VALUES (1,1,'이평조정 10선','↝',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    for stock_id, code, name, label in ((1,"000001","S종목","S"),(2,"000002","F종목","F"),(3,"000003","미판정",None)):
        db.execute(text("INSERT INTO stocks(id,stock_code,stock_name,is_active,created_at,updated_at) VALUES (:id,:code,:name,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"id":stock_id,"code":code,"name":name})
        d0=date(2026,5,1)
        db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES (:id,:id,1,:d0,:label,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"id":stock_id,"d0":d0.isoformat(),"label":label})
        for offset in range(-60,21):
            day=d0+timedelta(days=offset); close=100+stock_id+offset*.1
            db.execute(text("""INSERT INTO stock_daily_prices(stock_id,trade_date,open_price,high_price,low_price,close_price,volume,trading_value,ma5,ma10,ma20,ma60,ma120,ma240,created_at,updated_at)
                VALUES(:stock,:day,:close,:high,:low,:close,1000,1000000,:ma5,:ma10,:ma20,:ma60,:ma120,:ma240,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),
                {"stock":stock_id,"day":day.isoformat(),"close":close,"high":close+2,"low":close-2,"ma5":close-1,"ma10":close-2,"ma20":close-3,"ma60":close-4,"ma120":close-5,"ma240":close-6})
        db.execute(text("""INSERT INTO stock_daily_technical_indicators(stock_id,trade_date,rsi14,macd,macd_signal,macd_histogram,bb_width,atr14_ratio_to_close,created_at,updated_at)
            VALUES(:stock,:d0,55,1,.5,.5,10,2,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""), {"stock":stock_id,"d0":d0.isoformat()})
    db.commit(); return 1


def test_review_code_normalize_and_new_write_validation() -> None:
    assert normalize_marker_review_result("SUCCESS") == "S"
    assert normalize_marker_review_result("FAILURE") == "F"
    assert normalize_marker_review_result("S") == "S"
    assert normalize_marker_review_result("F") == "F"
    assert normalize_marker_review_result(None) is None
    MarkerEventPatch(review_result="S"); MarkerEventPatch(review_result="F"); MarkerEventPatch(review_result=None)
    with pytest.raises(ValidationError): MarkerEventPatch(review_result="SUCCESS")  # type: ignore[arg-type]
    with pytest.raises(ValidationError): MarkerEventPatch(review_result="FAILURE")  # type: ignore[arg-type]
    with pytest.raises(ValidationError): MarkerEventPatch(review_result="X")  # type: ignore[arg-type]


def test_legacy_migration_preserves_ids_counts_and_null() -> None:
    engine=create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE stocks(id INTEGER PRIMARY KEY)"); conn.exec_driver_sql("CREATE TABLE chart_markers(id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO stocks VALUES(1)"); conn.exec_driver_sql("INSERT INTO chart_markers VALUES(1)")
        conn.exec_driver_sql("CREATE TABLE chart_marker_events(id INTEGER PRIMARY KEY AUTOINCREMENT,stock_id INTEGER,marker_id INTEGER,marker_date TEXT,memo TEXT,review_result TEXT,reviewed_at TEXT,created_at TEXT,updated_at TEXT,UNIQUE(stock_id,marker_id,marker_date),CHECK(review_result IS NULL OR review_result IN ('SUCCESS','FAILURE'))) ")
        conn.exec_driver_sql("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(1,1,1,'2026-01-01','SUCCESS','x','x'),(2,1,1,'2026-01-02','FAILURE','x','x'),(3,1,1,'2026-01-03',NULL,'x','x')")
        _ensure_marker_review_result_codes(conn)
        assert conn.exec_driver_sql("SELECT id,review_result FROM chart_marker_events ORDER BY id").fetchall() == [(1,"S"),(2,"F"),(3,None)]


def test_marker_id_only_builds_pattern_quality_features_and_outcomes_without_search() -> None:
    db=_db(); marker_id=_seed(db); service=MarkerTrainingCaseService(db)
    before={table:db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in ("chart_marker_events","stock_daily_prices","drct_signal_searches")}
    result=service.readiness(marker_id); summary=result["summary"]
    assert summary["total_event_count"] == 3 and summary["pattern_case_count"] == 3
    assert summary["quality_case_count"] == 2 and summary["review_counts"] == {"S":1,"F":1,"undecided":1}
    assert summary["core_ready_count"] == 3 and summary["enriched_ready_count"] == 3
    assert summary["outcome_coverage"]["d20_return"] == 3 and summary["related_search_count"] == 0
    assert before == {table:db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in before}


def test_search_reference_invalid_or_false_is_not_a_marker_dataset_gate() -> None:
    db=_db(); marker_id=_seed(db); service=MarkerTrainingCaseService(db)
    baseline=service.readiness(marker_id)["summary"]
    search=DrctStockSignalService(db).create_search(DrctSignalSearchCreate(name="참고 검색식",description=None,hts_reference_conditions="A",hts_condition_expression="A",change_note="참고"))
    DrctStockSignalService(db).replace_marker_links(search["id"],DrctSignalMarkerLinksPut(marker_definition_ids=[marker_id]))
    linked=service.readiness(marker_id)["summary"]
    assert linked["related_search_count"] == 1
    assert (linked["pattern_case_count"],linked["quality_case_count"],linked["core_ready_count"]) == (baseline["pattern_case_count"],baseline["quality_case_count"],baseline["core_ready_count"])


def test_case_filters_detail_outcomes_and_d0_future_leakage() -> None:
    db=_db(); marker_id=_seed(db); service=MarkerTrainingCaseService(db)
    assert service.cases(marker_id,"ALL",1,100)["total"] == 3
    assert service.cases(marker_id,"S",1,100)["total"] == 1
    assert service.cases(marker_id,"F",1,100)["total"] == 1
    assert service.cases(marker_id,"UNDECIDED",1,100)["total"] == 1
    before=service.case_detail(marker_id,1); core_before=before["core_features"]
    db.execute(text("UPDATE stock_daily_prices SET close_price=99999,high_price=100000,low_price=99998 WHERE stock_id=1 AND trade_date>'2026-05-01'")); db.commit()
    after=service.case_detail(marker_id,1)
    assert after["core_features"] == core_before
    assert after["outcomes"] != before["outcomes"]
    outcome=service.outcomes(marker_id)
    assert outcome["quality_case_count"] == 2 and outcome["labels"] == {"S":1,"F":1}

