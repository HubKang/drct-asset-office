from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from backend.app.core.database import Base
from backend.app.schemas.drct_stock_signal_schema import DrctRuleVersionCreate, DrctStructuredRule, DrctSignalSearchCreate
from backend.app.services.drct_rule_engine import BooleanExpression, DrctRuleEvaluator, DrctRuleValidator
from backend.app.services.drct_rule_scan_service import DrctRuleScanService, DrctRuleUniverseService
from backend.app.services.drct_rule_service import DrctRuleService
from backend.app.services.drct_stock_signal_service import DrctStockSignalService


def _condition(code: str, kind: str, **params):
    return {"code": code, "type": kind, "label": code, "configured": True, "params": params}


def _rule(*conditions, expression: str | None = None):
    return {"schema_version": 1, "conditions": list(conditions), "expression": expression or " AND ".join(item["code"] for item in conditions)}


def _rows(count: int = 30):
    rows = []
    for offset in range(count):
        close = 110 - offset
        rows.append({
            "trade_date": (date(2026, 8, 31) - timedelta(days=offset)).isoformat(),
            "open_price": close - 1, "high_price": close + 2, "low_price": close - 2, "close_price": close,
            "volume": 1000 + offset, "trading_value": 1_000_000 + offset,
            "ma5": 105 - offset, "ma10": 104 - offset, "ma20": 103 - offset,
            "ma60": 102 - offset, "ma120": 101 - offset, "ma240": 100 - offset,
        })
    return rows


def test_validation_normal_duplicate_unknown_parentheses_unconfigured_and_ma() -> None:
    valid = _rule(_condition("A", "PRICE_COMPARE_VALUE", price_field="CLOSE", offset=0, operator="GTE", value=1000))
    assert DrctRuleValidator.validate(valid).status == "VALID"

    duplicate = _rule(valid["conditions"][0], valid["conditions"][0], expression="A")
    assert "DUPLICATE_CODE" in {item["code"] for item in DrctRuleValidator.validate(duplicate).errors}

    unknown = {**valid, "expression": "A AND X"}
    assert "UNKNOWN_CODE" in {item["code"] for item in DrctRuleValidator.validate(unknown).errors}

    broken = {**valid, "expression": "(A AND A"}
    assert "EXPRESSION" in {item["code"] for item in DrctRuleValidator.validate(broken).errors}

    unsupported = _rule(_condition("A", "PRICE_COMPARE_VALUE", price_field="CLOSE", offset=0, operator="NE", value=1))
    assert DrctRuleValidator.validate(unsupported).status == "INVALID"

    unconfigured = _rule({"code": "C", "type": "PRICE_COMPARE_VALUE", "configured": False, "params": {}})
    assert "구성되지" in DrctRuleValidator.validate(unconfigured).errors[0]["message"]

    bad_ma = _rule(_condition("A", "MA_COMPARE", lhs_period=30, lhs_offset=0, rhs_period=60, rhs_offset=0, operator="GT"))
    assert DrctRuleValidator.validate(bad_ma).status == "INVALID"


def test_safe_boolean_and_or_nested() -> None:
    values = {"A": True, "B": False, "C": True}
    assert BooleanExpression.evaluate("A AND C", values) is True
    assert BooleanExpression.evaluate("A OR B", values) is True
    assert BooleanExpression.evaluate("(A AND B) OR (C AND A)", values) is True
    with pytest.raises(ValueError):
        BooleanExpression.evaluate("A __import__", values)


@pytest.mark.parametrize("condition,expected", [
    (_condition("A", "MARKET_CAP_COMPARE", operator="GTE", value=200_000_000_000), "PASS"),
    (_condition("A", "PRICE_COMPARE_VALUE", price_field="CLOSE", offset=0, operator="GTE", value=100), "PASS"),
    (_condition("A", "PRICE_COMPARE_PRICE", lhs={"kind":"PRICE","field":"LOW","offset":0}, rhs={"kind":"PRICE","field":"LOW","offset":5}, operator="GT"), "PASS"),
    (_condition("A", "MA_COMPARE", lhs_period=20, lhs_offset=0, rhs_period=60, rhs_offset=0, operator="GT"), "PASS"),
    (_condition("A", "PRICE_MA_COMPARE", price_field="CLOSE", price_offset=0, ma_period=20, ma_offset=0, operator="GT"), "PASS"),
    (_condition("A", "MA_TREND", ma_period=60, direction="UP", count=2, offset=0), "PASS"),
    (_condition("A", "PCT_CHANGE", lhs={"kind":"PRICE","field":"LOW","offset":10}, rhs={"kind":"PRICE","field":"HIGH","offset":0}, operator="GTE", value=10), "PASS"),
    (_condition("A", "DISTANCE_PCT", lhs={"kind":"PRICE","field":"CLOSE","offset":0}, rhs={"kind":"MA","period":5,"offset":0}, operator="LTE", value=5), "PASS"),
    (_condition("A", "PERIOD_EXISTS_PRICE_CHANGE", price_field="CLOSE", lookback=5, operator="GTE", value=0.5), "PASS"),
    (_condition("A", "PERIOD_VALUE_COMPARE", value_field="TRADING_VALUE", lookback=5, operator="GTE", value=1_000_000), "PASS"),
])
def test_condition_types(condition, expected) -> None:
    assert DrctRuleEvaluator.evaluate_condition(condition, _rows(), 300_000_000_000)["status"] == expected


def test_cross_up_and_cross_down() -> None:
    rows = _rows()
    rows[0]["close_price"], rows[0]["ma20"] = 105, 100
    rows[1]["close_price"], rows[1]["ma20"] = 95, 100
    up = _condition("A", "CROSS_UP", lhs={"kind":"PRICE","field":"CLOSE","offset":0}, rhs={"kind":"MA","period":20,"offset":0})
    assert DrctRuleEvaluator.evaluate_condition(up, rows, None)["status"] == "PASS"
    rows[0]["close_price"], rows[1]["close_price"] = 95, 105
    down = {**up, "type": "CROSS_DOWN"}
    assert DrctRuleEvaluator.evaluate_condition(down, rows, None)["status"] == "PASS"


def test_offset_is_trading_bar_and_incomplete_is_not_no_match() -> None:
    rows = _rows(2)
    condition = _condition("A", "PRICE_COMPARE_VALUE", price_field="CLOSE", offset=1, operator="EQ", value=109)
    assert DrctRuleEvaluator.evaluate_condition(condition, rows, None)["status"] == "PASS"
    condition["params"]["offset"] = 2
    result = DrctRuleEvaluator.evaluate(_rule(condition), rows, None)
    assert result["status"] == "DATA_INCOMPLETE"


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_scan(db: Session) -> int:
    db.execute(text("INSERT INTO market_themes(id,theme_name,theme_code,theme_type,keywords,is_active,is_supply_theme,sort_order,created_at,updated_at,theme_level) VALUES (1,'활성테마','T1','MANUAL','[]',1,0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'THEME'),(2,'비활성테마','T2','MANUAL','[]',0,0,2,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'THEME'),(3,'그룹','T3','MANUAL','[]',1,0,3,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'GROUP')"))
    db.execute(text("INSERT INTO stocks(id,stock_code,stock_name,is_active,created_at,updated_at) VALUES (1,'000001','종목1',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,'000002','종목2',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(3,'000003','종목3',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.execute(text("INSERT INTO market_theme_stocks(theme_id,stock_id,mapping_source,is_primary,is_active,created_at,updated_at) VALUES (1,1,'test',0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(1,2,'test',0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,3,'test',0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(3,3,'test',0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    for stock_id, close in ((1, 120), (2, 80)):
        for offset in range(3):
            day = date(2026, 8, 31) - timedelta(days=offset)
            db.execute(text("INSERT INTO stock_daily_prices(stock_id,trade_date,open_price,high_price,low_price,close_price,volume,trading_value,ma5,ma10,ma20,ma60,ma120,ma240,created_at,updated_at) VALUES (:s,:d,:c,:c,:c,:c,100,1000,:c,:c,:c,:c,:c,:c,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"s":stock_id,"d":day.isoformat(),"c":close-offset})
    db.commit()
    search = DrctStockSignalService(db).create_search(DrctSignalSearchCreate(name="실행 테스트", description=None, hts_reference_conditions="A", hts_condition_expression="A", change_note="seed"))
    rule = DrctStructuredRule(**_rule(_condition("A", "PRICE_COMPARE_VALUE", price_field="CLOSE", offset=0, operator="GTE", value=100)))
    DrctRuleService(db).create_rule_version(search["id"], DrctRuleVersionCreate(rule=rule, change_note="Rule 구성"))
    return search["id"]


def test_universe_filters_deduplicates_scan_cutoff_and_does_not_persist_results() -> None:
    db = _db(); search_id = _seed_scan(db)
    db.execute(text("INSERT INTO market_theme_stocks(theme_id,stock_id,mapping_source,is_primary,is_active,created_at,updated_at) VALUES (2,1,'test',0,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.commit()
    universe = DrctRuleUniverseService(db).load()
    assert [row["stock_id"] for row in universe] == [1, 2]
    before = db.execute(text("SELECT COUNT(*) FROM drct_signal_search_rules")).scalar_one()
    preview = DrctRuleScanService(db).preview(search_id, date(2026, 8, 31), True)
    assert preview["universe_count"] == 2 and preview["matched_count"] == 1
    assert {row["status"] for row in preview["items"]} == {"MATCH", "NO_MATCH"}
    assert db.execute(text("SELECT COUNT(*) FROM drct_signal_search_rules")).scalar_one() == before

    earlier = DrctRuleScanService(db).preview(search_id, date(2026, 8, 30), True)
    assert earlier["analysis_date"] == "2026-08-30"
    assert all(row["close"] in {119.0, 79.0} for row in earlier["items"])


def test_rule_change_creates_version_and_preserves_old() -> None:
    db = _db(); search_id = _seed_scan(db)
    versions = DrctStockSignalService(db).list_versions(search_id)
    assert [row["version_no"] for row in versions] == [2, 1]
    assert versions[0]["structured_rule"]["validation_status"] == "VALID"
    assert versions[1]["structured_rule"] is None


def test_identical_rule_save_is_idempotent() -> None:
    db = _db(); search_id = _seed_scan(db)
    current = DrctStockSignalService(db).get_search(search_id)["current_version"]
    payload = DrctRuleVersionCreate(
        rule=DrctStructuredRule(**current["structured_rule"]["rule"]),
        change_note="같은 조건 재검토",
        hts_reference_conditions=current["hts_reference_conditions"],
        hts_condition_expression=current["hts_condition_expression"],
    )
    saved = DrctRuleService(db).create_rule_version(search_id, payload)
    assert saved["id"] == current["id"]
    assert saved["version_no"] == current["version_no"]
    assert len(DrctStockSignalService(db).list_versions(search_id)) == 2


def test_market_cap_missing_becomes_data_incomplete_and_diagnose() -> None:
    db = _db(); search_id = _seed_scan(db)
    current = db.execute(text("SELECT id FROM drct_signal_search_versions WHERE search_id=:id AND is_current=1"), {"id":search_id}).scalar_one()
    db.execute(text("UPDATE drct_signal_search_versions SET is_current=0 WHERE id=:id"), {"id":current})
    source = db.execute(text("SELECT * FROM drct_signal_search_versions WHERE id=:id"), {"id":current}).mappings().one()
    db.execute(text("INSERT INTO drct_signal_search_versions(search_id,version_no,hts_reference_conditions,hts_condition_expression,change_note,is_current,created_at) VALUES (:s,3,:h,:e,'시장가치',1,CURRENT_TIMESTAMP)"), {"s":search_id,"h":source["hts_reference_conditions"],"e":source["hts_condition_expression"]})
    version_id = db.execute(text("SELECT last_insert_rowid()")).scalar_one()
    rule = _rule(_condition("A", "MARKET_CAP_COMPARE", operator="GTE", value=1))
    import json
    db.execute(text("INSERT INTO drct_signal_search_rules(search_version_id,schema_version,rule_json,validation_status,created_at) VALUES (:v,1,:r,'VALID',CURRENT_TIMESTAMP)"), {"v":version_id,"r":json.dumps(rule)})
    db.commit()
    preview = DrctRuleScanService(db).preview(search_id, date(2026, 8, 31), True)
    assert preview["data_incomplete_count"] == 2 and preview["evaluable_count"] == 0
    diagnose = DrctRuleScanService(db).diagnose(search_id, 1, date(2026, 8, 31))
    assert diagnose["status"] == "DATA_INCOMPLETE"


def test_preview_query_count_is_constant_bulk_shape() -> None:
    db = _db(); search_id = _seed_scan(db)
    count = 0
    def track(*_args):
        nonlocal count
        count += 1
    event.listen(db.get_bind(), "before_cursor_execute", track)
    DrctRuleScanService(db).preview(search_id, None, True)
    event.remove(db.get_bind(), "before_cursor_execute", track)
    assert count <= 8


def test_unconfigured_rule_blocks_preview() -> None:
    db = _db()
    search = DrctStockSignalService(db).create_search(DrctSignalSearchCreate(name="미구성", hts_reference_conditions="A", hts_condition_expression="A", description=None, change_note=None))
    with pytest.raises(HTTPException) as exc:
        DrctRuleScanService(db).preview(search["id"], None)
    assert exc.value.status_code == 409
