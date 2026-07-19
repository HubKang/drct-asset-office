from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_market_signal_seed_and_detail_api() -> None:
    response = client.get("/market-signals")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 4
    assert {item["status"] for item in items} >= {"DRAFT"}

    detail = client.get(f"/market-signals/{items[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["conditions"]


def test_market_signal_evaluate_and_gpt_prompt_api() -> None:
    evaluate = client.post("/market-signals/evaluate", json={"signal_ids": [1], "active_only": False, "save": False})
    assert evaluate.status_code == 200
    body = evaluate.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["state"] in {"INACTIVE", "WATCH", "ACTIVE", "STRENGTHENING", "WEAKENING", "DATA_INSUFFICIENT"}

    prompt = client.post("/market-signals/gpt-rule-draft", json={"goal_text": "위험선호가 위험회피로 전환되는 지점을 찾고 싶다."})
    assert prompt.status_code == 200
    assert prompt.json()["validation_status"] == "PROMPT_READY"
    assert "Supported transforms" in prompt.json()["prompt"]


def test_market_signal_catalog_and_condition_preview_api() -> None:
    catalog = client.get("/market-signals/indicator-catalog")
    assert catalog.status_code == 200
    items = catalog.json()["items"]
    assert any(item["code"] == "WTI" and item["classification"] in {"AVAILABLE", "DATA_INSUFFICIENT"} for item in items)

    preview = client.post(
        "/market-signals/condition-preview",
        json={
            "condition": {
                "condition_group": "A",
                "condition_role": "REQUIRED",
                "item_type": "INDICATOR",
                "item_code": "WTI",
                "transform_type": "RAW_VALUE",
                "window_size": 20,
                "comparison_operator": ">",
                "threshold_type": "ABSOLUTE",
                "threshold_value": 0,
                "weight": 10,
                "is_required": True,
                "sort_order": 1,
            }
        },
    )
    assert preview.status_code == 200
    assert "passed" in preview.json()["preview"]


def test_market_signal_layered_single_composite_phenomenon_api() -> None:
    single = client.get("/market-signals/single-indicator")
    assert single.status_code == 200
    single_items = single.json()["items"]
    assert single_items
    assert {"evaluation_status", "trend_state", "diagnostic"} <= set(single_items[0])

    single_eval = client.post(f"/market-signals/single-indicator/{single_items[0]['id']}/evaluate", json={"save": False})
    assert single_eval.status_code == 200
    assert single_eval.json()["item"]["signal_level"] == "SINGLE_INDICATOR"

    trend_chart = client.get(f"/market-signals/single-indicator/{single_items[0]['id']}/trend-chart")
    assert trend_chart.status_code == 200
    assert "series" in trend_chart.json()

    composite = client.get("/market-signals/composite")
    assert composite.status_code == 200
    composite_items = composite.json()["items"]
    assert len(composite_items) >= 4

    composite_eval = client.post(f"/market-signals/composite/{composite_items[0]['id']}/evaluate", json={"save": False})
    assert composite_eval.status_code == 200
    assert "relation_diagnostic" in composite_eval.json()["item"]

    phenomena = client.get("/market-signals/phenomena")
    assert phenomena.status_code == 200
    phenomenon_items = phenomena.json()["items"]
    assert len(phenomenon_items) >= 4

    phenomenon_eval = client.post(f"/market-signals/phenomena/{phenomenon_items[0]['id']}/evaluate", json={"save": False})
    assert phenomenon_eval.status_code == 200
    assert phenomenon_eval.json()["item"]["signal_level"] == "PHENOMENON"


def test_market_signal_gpt_auxiliary_diagnosis_does_not_change_rule_status() -> None:
    before = client.get("/market-signals/1")
    assert before.status_code == 200
    before_status = before.json()["status"]

    diagnosis = client.post("/market-signals/phenomena/1/gpt-diagnosis", json={"payload": {"goal_text": "보조 진단"}})
    assert diagnosis.status_code == 200
    body = diagnosis.json()["item"]
    assert body["drct_state_locked"] is True
    assert "Do not change DrCT state" in body["prompt"]

    after = client.get("/market-signals/1")
    assert after.status_code == 200
    assert after.json()["status"] == before_status


def test_market_signal_learning_and_today_api() -> None:
    today = client.get("/market-signals/events/today")
    assert today.status_code == 200
    assert "items" in today.json()["item"]

    sources = client.get("/market-signals/evidence-sources")
    assert sources.status_code == 200
    assert sources.json()["items"]

    experiments = client.post(
        "/market-signals/rule-experiments",
        json={"payload": {"signal_definition_id": 1, "experiment_code": "TEST_CHALLENGER_LAYER", "experiment_name": "Layer test", "hypothesis": "test"}},
    )
    assert experiments.status_code == 200
    assert any(item["experiment_code"] == "TEST_CHALLENGER_LAYER" for item in experiments.json()["items"])


def test_market_signal_overview_and_lazy_templates_gpt_design_api() -> None:
    overview = client.get("/market-signals/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["single_indicator_signals"]
    assert body["composite_indicator_signals"]
    assert body["objective_phenomena"]
    assert body["templates"] == []
    assert "sparkline" in body["single_indicator_signals"][0]
    assert "number_label" in body["single_indicator_signals"][0]

    templates = client.get("/market-signals/rule-templates")
    assert templates.status_code == 200
    assert len(templates.json()["items"]) >= 15
    first_template = templates.json()["items"][0]
    assert first_template["status"] in {"DRAFT", "REVIEWED", "APPROVED", "DEPRECATED"}
    assert first_template["readiness_label"]

    copied = client.post(f"/market-signals/rule-templates/{first_template['id']}/copy")
    assert copied.status_code == 200
    assert copied.json()["status"] == "DRAFT"

    design = client.post("/market-signals/gpt-rule-design", json={"goal_text": "금리 상승 후 성장주 약화 신호"})
    assert design.status_code == 200
    assert design.json()["item"]["drct_save_policy"] == "DRAFT_ONLY"


def test_market_signal_all_indicator_catalog_and_profiles_api() -> None:
    catalog = client.get("/market-signals/catalog")
    assert catalog.status_code == 200
    body = catalog.json()
    items = body["items"]
    assert body["total_count"] == len(items)
    assert any(item["item_type"] == "INDEX" and item["item_code"] == "KOSPI" for item in items)
    assert any(item["item_type"] == "INDICATOR" and item["item_code"] in {"USD_KRW", "WTI"} for item in items)
    assert all("recommended_profile_code" in item for item in items)

    domestic = client.get("/market-signals/catalog?category=DOMESTIC_STOCK_MARKET")
    assert domestic.status_code == 200
    domestic_codes = {item["item_code"] for item in domestic.json()["items"]}
    assert {"KOSPI", "KOSDAQ"} <= domestic_codes

    profiles = client.get("/market-signals/model-profiles")
    assert profiles.status_code == 200
    profile_codes = {item["profile_code"] for item in profiles.json()["items"]}
    assert len(profile_codes) >= 10
    assert {"MARKET_PRICE_TREND", "FX_TREND", "YIELD_TREND", "MACRO_MOM_YOY_TREND"} <= profile_codes

    summary = client.get("/market-signals/single-indicator/coverage-summary")
    assert summary.status_code == 200
    assert summary.json()["item"]["total_count"] == body["total_count"]


def test_market_signal_single_indicator_preview_and_draft_creation_api() -> None:
    preview = client.post(
        "/market-signals/single-indicator/preview",
        json={"payload": {"item_type": "INDEX", "item_code": "KOSPI", "profile_code": "MARKET_PRICE_TREND"}},
    )
    assert preview.status_code == 200
    preview_item = preview.json()["item"]
    assert preview_item["catalog"]["item_code"] == "KOSPI"
    assert preview_item["profile"]["profile_code"] == "MARKET_PRICE_TREND"
    assert "current_trend" in preview_item

    created = client.post(
        "/market-signals/single-indicator/create-draft",
        json={"payload": {"item_type": "INDEX", "item_code": "KOSPI", "profile_code": "MARKET_PRICE_TREND"}},
    )
    assert created.status_code == 200
    body = created.json()["item"]
    assert body["created"] in {True, False}
    if body["created"]:
        assert body["signal"]["status"] == "DRAFT"
    else:
        assert body["reason"] in {"DUPLICATE_DRAFT_OR_SIGNAL", "DATA_INSUFFICIENT"}

    duplicated = client.post(
        "/market-signals/single-indicator/create-draft",
        json={"payload": {"item_type": "INDEX", "item_code": "KOSPI", "profile_code": "MARKET_PRICE_TREND"}},
    )
    assert duplicated.status_code == 200
    assert duplicated.json()["item"]["created"] is False

    bulk = client.post(
        "/market-signals/single-indicator/create-drafts",
        json={
            "payload": {
                "items": [
                    {"item_type": "INDEX", "item_code": "KOSDAQ", "profile_code": "MARKET_PRICE_TREND"},
                    {"item_type": "INDICATOR", "item_code": "USD_KRW", "profile_code": "FX_TREND"},
                ]
            }
        },
    )
    assert bulk.status_code == 200
    assert bulk.json()["created_count"] >= 0
    assert bulk.json()["skipped_count"] >= 0


def test_market_signal_domestic_composite_template_readiness_api() -> None:
    templates = client.get("/market-signals/rule-templates")
    assert templates.status_code == 200
    domestic = next(item for item in templates.json()["items"] if item["template_code"] == "KR_STOCK_RISK_OFF_TURN")
    readiness = client.post(f"/market-signals/composite/templates/{domestic['id']}/validate-readiness")
    assert readiness.status_code == 200
    body = readiness.json()["item"]
    assert body["template"]["template_code"] == "KR_STOCK_RISK_OFF_TURN"
    assert {"ready_codes", "data_insufficient_codes", "missing_codes"} <= set(body)


def test_market_signal_stage_preview_validation_and_activation_guard_api() -> None:
    before = client.get("/market-signals").json()["items"]
    before_count = len(before)

    preview = client.post(
        "/market-signals/single-indicator/preview",
        json={
            "payload": {
                "item_type": "INDEX",
                "item_code": "KRX100",
                "profile_code": "MARKET_PRICE_TREND",
                "period": "3M",
                "configuration": {"short_window": 10, "medium_window": 20, "trend_window": 30, "channel_multiplier": 1.8, "minimum_break_persistence": 2, "false_break_window": 5, "reversal_persistence": 3},
            }
        },
    )
    assert preview.status_code == 200
    preview_item = preview.json()["item"]
    assert preview_item["chart"]
    assert preview_item["period"]["requested_period"] == "3M"
    assert preview_item["period"]["actual_period_type"] == "CALENDAR"
    assert preview_item["period"]["observation_count"] == len(preview_item["chart"])
    assert preview_item["period"]["display_observation_count"] == len(preview_item["price_points"])
    assert preview_item["period"]["display_range_start"] == preview_item["chart"][0]["date"]
    assert preview_item["period"]["display_range_end"] == preview_item["chart"][-1]["date"]
    assert preview_item["period"]["trend_analysis_observation_count"] == 30
    assert preview_item["period"]["trend_analysis_start"] == preview_item["chart"][-30]["date"]
    assert len(preview_item["regression_points"]) == 30
    assert len(preview_item["upper_channel_points"]) == 30
    assert len(preview_item["lower_channel_points"]) == 30
    assert preview_item["chart"][-30]["is_trend_analysis_start"] is True
    if len(preview_item["chart"]) > 30:
        assert preview_item["chart"][0].get("center") is None
    assert preview_item["applied_configuration"]["trend_window"] == 30
    assert preview_item["plain_explanation"]["judgement"]

    after_preview = client.get("/market-signals").json()["items"]
    assert len(after_preview) == before_count

    invalid = client.post(
        "/market-signals/single-indicator/preview",
        json={"payload": {"item_type": "INDEX", "item_code": "KRX100", "profile_code": "MARKET_PRICE_TREND", "configuration": {"short_window": 60, "medium_window": 20}}},
    )
    assert invalid.status_code == 400

    draft = client.post(
        "/market-signals/single-indicator/create-draft",
        json={"payload": {"item_type": "INDEX", "item_code": "KRX100", "profile_code": "MARKET_PRICE_TREND"}},
    )
    assert draft.status_code == 200
    draft_body = draft.json()["item"]
    signal_id = draft_body.get("signal", draft_body.get("existing_signal", {})).get("id")
    assert signal_id

    blocked = client.post(f"/market-signals/{signal_id}/activate-with-approval", json={"payload": {"reason": "test"}})
    assert blocked.status_code in {200, 409}
    if blocked.status_code == 409:
        assert "validation" in blocked.json()["detail"]

    validation = client.post(f"/market-signals/{signal_id}/mark-validation-complete", json={"payload": {"validation_period_years": 3, "validation_summary": {"test": True}}})
    assert validation.status_code == 200
    assert validation.json()["item"]["validation_status"] == "VALIDATED"
