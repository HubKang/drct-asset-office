from __future__ import annotations

import pytest

from backend.app.services.drct_hts_import_service import DrctHtsImportService
from backend.app.services.drct_rule_engine import BooleanExpression, DrctRuleEvaluator, DrctRuleValidator
from backend.app.services.drct_stock_signal_defaults import INITIAL_DRCT_SIGNAL_SEARCHES


PARSER = DrctHtsImportService()


def parse(line: str, expression: str = "A", resolutions=None):
    return PARSER.parse(line, expression, resolutions or {})


@pytest.mark.parametrize(("source", "expected"), [
    ("Ａ　시가총액：현재가기준 200십억원 이상", "A 시가총액:현재가기준 200십억원 이상"),
    ("A   조건:   값", "A 조건: 값"),
    ("A 조건: 값\r\n\r\n\r\nB 조건: 값", "A 조건: 값\n\nB 조건: 값"),
    ("  A 조건: 값  ", "A 조건: 값"),
    ("A\t조건:\t값", "A 조건: 값"),
])
def test_normalization(source, expected):
    assert PARSER.normalize(source) == expected


@pytest.mark.parametrize("line", [
    "A 시가총액:현재가기준 200십억원 이상",
    "A 주가범위:0일전 종가가 1000 이상 99999999 이하",
    "A 주가이평배열(3):[일]0봉전 20이평 > 60이평 > 120이평",
    "A 주가이평추세:[일]0봉전 (종가 60)이평 상승추세유지 2회 이상",
    "A 주가비교:[일]20봉전 저가 < 10봉전 저가 < 2봉전 저가",
    "A 주가등락률:[일]20봉전(종) 저가대비 14봉전 고가등락률 8%이상",
    "A 주가이평비교:[일]0봉전 (종가 5)이평 > (종가 20)이평 1회이상",
    "A 가격-이동평균 비교:[일]0봉전 (종가 20)이평 < 종가",
    "A 이평이격도:[일]0봉전(종가 1, 종가 20) 5%이내 근접 1회이상",
    "A 기간내 등락률:[일]0봉전 20봉이내에서 전일종가대비종가 10% 이상",
    "A 기간내 거래대금:[일]0봉전 20봉이내 거래대금 100억원 이상",
    "A 주가이평돌파:[일]0봉전 (종가 1)이평 (종가 10)이평 골든크로스",
])
def test_supported_templates_auto_convert_and_validate(line):
    result = parse(line)
    assert result["status"] == "READY"
    assert result["conditions"][0]["status"] == "AUTO_CONVERTED"
    assert DrctRuleValidator.validate(result["rule"]).status == "VALID"


@pytest.mark.parametrize(("line", "kind", "resolution"), [
    ("A 주가비교:[일]20봉전 저가 < 14봉전 고가 > 5봉전", "PRICE_FIELD", {"price_field": "LOW"}),
    ("A 상세이평돌파:[일]0봉전 단순(종가 5)이평이 단순(종가 20)이평을", "RELATION", {"relation": "CROSS_UP"}),
    ("A 상세이평비교:[일]0봉전 단순(종가 1)이평이 단순(종가 10)이평을", "RELATION", {"relation": "LT"}),
    ("A 기간내 거래대금:[일]0봉전 20봉이내 거래대금(일/주:백만, 분:천", "THRESHOLD", {"threshold": 10_000_000_000}),
])
def test_incomplete_supported_condition_requires_explicit_resolution(line, kind, resolution):
    pending = parse(line)
    assert pending["status"] == "NEEDS_REVIEW"
    assert pending["conditions"][0]["resolution_kind"] == kind
    ready = parse(line, resolutions={"A": resolution})
    assert ready["status"] == "READY"
    assert DrctRuleValidator.validate(ready["rule"]).status == "VALID"


@pytest.mark.parametrize(("text", "expression", "status"), [
    ("아무 텍스트", "A", "INVALID"),
    ("A 알 수 없는 조건:무언가", "A", "NEEDS_REVIEW"),
    ("A 시가총액:현재가기준 200십억원 이상", "A AND", "INVALID"),
    ("A 시가총액:현재가기준 200십억원 이상", "B", "INVALID"),
    ("A 시가총액:현재가기준", "A", "NEEDS_REVIEW"),
    ("A 기간내 등락률:[일]2봉전 20봉이내에서 전일종가대비종가 10% 이상", "A", "NEEDS_REVIEW"),
])
def test_invalid_unsupported_and_incomplete_are_never_guessed(text, expression, status):
    assert parse(text, expression)["status"] == status


def test_unreferenced_incomplete_condition_does_not_block_ready():
    result = parse("A 시가총액:현재가기준 200십억원 이상\nB 상세이평돌파:[일]0봉전 단순(종가 5)이평이 단순(종가 20)이평을", "A")
    assert result["status"] == "READY"
    assert result["conditions"][1]["used_label"] == "미사용 조건"
    assert [item["code"] for item in result["rule"]["conditions"]] == ["A"]


@pytest.mark.parametrize("default", INITIAL_DRCT_SIGNAL_SEARCHES)
def test_real_reference_acceptance_is_deterministic(default):
    first = PARSER.parse(default["hts_reference_conditions"], default["hts_condition_expression"], {})
    second = PARSER.parse(default["hts_reference_conditions"], default["hts_condition_expression"], {})
    assert first == second
    assert first["summary"]["unsupported"] == 0
    assert first["status"] == "NEEDS_REVIEW"


def group(code: str, join: str, predicates: list[dict]):
    return {"code": code, "label": f"조건 {code}", "source_text": "원본", "join": join, "configured": True, "predicates": predicates}


def predicate(kind="PRICE_COMPARE_VALUE", **params):
    return {"type": kind, "label": "한국어 조건", "configured": True, "params": params or {"price_field": "CLOSE", "offset": 0, "operator": "GTE", "value": 100}}


@pytest.mark.parametrize("join", ["AND", "OR"])
def test_schema_v2_group_validation(join):
    rule = {"schema_version": 2, "conditions": [group("A", join, [predicate(), predicate(value=90, price_field="CLOSE", offset=0, operator="GTE")])], "expression": "A"}
    assert DrctRuleValidator.validate(rule).status == "VALID"


@pytest.mark.parametrize(("join", "expected"), [("AND", "NO_MATCH"), ("OR", "MATCH")])
def test_schema_v2_group_boolean_evaluation(join, expected):
    rows = [{"close_price": 100, "open_price": 100, "high_price": 100, "low_price": 100}]
    yes = predicate(value=90, price_field="CLOSE", offset=0, operator="GTE")
    no = predicate(value=110, price_field="CLOSE", offset=0, operator="GTE")
    rule = {"schema_version": 2, "conditions": [group("A", join, [yes, no])], "expression": "A"}
    assert DrctRuleEvaluator.evaluate(rule, rows, None)["status"] == expected


@pytest.mark.parametrize(("expression", "values", "expected"), [
    ("A AND B", {"A": "FAIL", "B": "DATA_INCOMPLETE"}, "FAIL"),
    ("A AND B", {"A": "PASS", "B": "DATA_INCOMPLETE"}, "DATA_INCOMPLETE"),
    ("A OR B", {"A": "PASS", "B": "DATA_INCOMPLETE"}, "PASS"),
    ("A OR B", {"A": "FAIL", "B": "DATA_INCOMPLETE"}, "DATA_INCOMPLETE"),
    ("(A OR B) AND C", {"A": "FAIL", "B": "PASS", "C": "PASS"}, "PASS"),
])
def test_three_state_boolean_logic(expression, values, expected):
    assert BooleanExpression.evaluate_status(expression, values) == expected


def test_v1_meaning_is_unchanged():
    rule = {"schema_version": 1, "conditions": [{"code": "A", **predicate()}], "expression": "A"}
    rows = [{"close_price": 100, "open_price": 100, "high_price": 100, "low_price": 100}]
    assert DrctRuleValidator.validate(rule).status == "VALID"
    assert DrctRuleEvaluator.evaluate(rule, rows, None)["status"] == "MATCH"


def test_durable_v2_rule_uses_explicit_allow_list():
    source = {"schema_version": 2, "expression": "A", "private": "drop", "conditions": [{**group("A", "AND", [{**predicate(), "debug": "drop"}]), "parse_status": "drop"}]}
    durable = DrctRuleValidator.durable_rule(source)
    assert "private" not in durable and "parse_status" not in durable["conditions"][0]
    assert "debug" not in durable["conditions"][0]["predicates"][0]


@pytest.mark.parametrize("relation", ["CROSS_UP", "CROSS_DOWN", "GT", "LT"])
def test_all_korean_relation_choices_create_valid_rules(relation):
    line = "A 상세이평돌파:[일]0봉전 단순(종가 5)이평이 단순(종가 20)이평을"
    result = parse(line, resolutions={"A": {"relation": relation}})
    assert result["status"] == "READY"
    assert DrctRuleValidator.validate(result["rule"]).status == "VALID"
