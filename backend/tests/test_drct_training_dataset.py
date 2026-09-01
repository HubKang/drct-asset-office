from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from backend.app.core.database import Base
from backend.app.schemas.drct_stock_signal_schema import DrctRuleVersionCreate, DrctSignalMarkerLinksPut, DrctSignalSearchCreate, DrctStructuredRule
from backend.app.services.drct_future_outcome_service import FutureOutcomeService
from backend.app.services.drct_pattern_baseline_service import PatternBaselineService
from backend.app.services.drct_pattern_feature_service import CORE_FEATURE_NAMES, ENRICHED_FEATURE_NAMES, PatternFeatureService
from backend.app.services.drct_rule_service import DrctRuleService
from backend.app.services.drct_stock_signal_service import DrctStockSignalService
from backend.app.services.drct_training_case_service import TrainingCaseService
from backend.app.services.drct_training_dataset_service import DrctTrainingDatasetService
from backend.app.services.drct_signal_validation_service import DrctSignalValidationService


def _price_rows(count: int = 81, future_jump: float | None = None):
    d0 = date(2026, 5, 1)
    chronological = []
    for index in range(count):
        offset = index - 60
        close = 100 + offset
        if future_jump is not None and offset > 0: close = future_jump
        chronological.append({
            "trade_date": (d0 + timedelta(days=offset)).isoformat(),
            "open_price": close - 1, "high_price": close + 2, "low_price": close - 2, "close_price": close,
            "volume": 1000 + index, "trading_value": 1_000_000,
            "ma5": close - 1, "ma10": close - 2, "ma20": close - 3, "ma60": close - 4,
            "ma120": close - 5, "ma240": close - 6,
        })
    return chronological


def test_core_features_use_only_d0_and_prior_and_normalized_slope() -> None:
    rows = _price_rows(future_jump=9999)
    d0_index = 60
    status, features, missing = PatternFeatureService.core(list(reversed(rows[:d0_index + 1])))
    assert status == "READY" and not missing and features is not None
    assert set(features) == set(CORE_FEATURE_NAMES)
    assert features["price_return_5"] == pytest.approx((100 / 95 - 1) * 100)
    assert features["price_slope_20"] > 0
    assert max(abs(value) for value in features.values()) < 1000


def test_core_requires_61_bars_and_never_imputes() -> None:
    status, features, missing = PatternFeatureService.core(list(reversed(_price_rows(60))))
    assert status == "CORE_DATA_INCOMPLETE" and features is None and missing


def test_enriched_feature_macd_normalization_and_missing_indicator() -> None:
    rows = list(reversed(_price_rows()[:61]))
    _, core, _ = PatternFeatureService.core(rows)
    status, enriched, missing = PatternFeatureService.enriched(core, {"rsi14": 55, "macd_histogram": 2, "bb_width": 10, "atr14_ratio_to_close": 3}, 100)
    assert status == "READY" and not missing and enriched is not None
    assert set(enriched) == set(ENRICHED_FEATURE_NAMES)
    assert enriched["macd_histogram_pct"] == pytest.approx(2.0)
    assert PatternFeatureService.enriched(core, None, 100)[0] == "ENRICHED_DATA_INCOMPLETE"


def test_future_outcomes_d5_d10_d20_mfe_mae_and_coverage() -> None:
    future = [{"close_price": 100 + index, "high_price": 102 + index, "low_price": 98 + index} for index in range(1, 21)]
    result = FutureOutcomeService.calculate(100, future)
    assert result["d5_return"] == pytest.approx(5)
    assert result["d10_return"] == pytest.approx(10)
    assert result["d20_return"] == pytest.approx(20)
    assert result["mfe_20"] == pytest.approx(22)
    assert result["mae_20"] == pytest.approx(-1)
    partial = FutureOutcomeService.calculate(100, future[:7])
    assert partial["d5_return"] is not None and partial["d10_return"] is None and partial["mfe_20"] is None


def _event(event_id: int, stock: int, label: str | None, marker: str):
    return {"event_id": event_id, "stock_id": stock, "marker_date": "2026-05-01", "review_result": label, "stock_code": f"00000{stock}", "stock_name": f"종목{stock}", "marker_name": marker}


@pytest.mark.parametrize("labels,expected", [
    (("SUCCESS", "SUCCESS"), "SUCCESS"),
    (("FAILURE", "FAILURE"), "FAILURE"),
    (("SUCCESS", "FAILURE"), "CONFLICT"),
    (("SUCCESS", None), "SUCCESS"),
    (("FAILURE", None), "FAILURE"),
    ((None, None), "UNDECIDED"),
])
def test_case_dedup_and_label_policy(labels, expected) -> None:
    rows = [_event(index + 1, 1, label, f"M{index}") for index, label in enumerate(labels)]
    cases = TrainingCaseService._deduplicate(rows)
    assert len(cases) == 1 and cases[0]["label"] == expected
    assert len(cases[0]["source_marker_event_ids"]) == 2


def _features(seed: float) -> dict[str, float]:
    return {name: seed + index * 0.01 for index, name in enumerate(CORE_FEATURE_NAMES)}


def _baseline_cases(success: int, failure: int, same_date_batch: bool = False):
    rows = []
    for index in range(success + failure):
        label = "SUCCESS" if index < success else "FAILURE"
        d0_index = index // 2 if same_date_batch else index
        core = _features(1.0 + (0.1 if label == "SUCCESS" else -0.1) + index * 0.001)
        enriched = {**core, "rsi14": 60 if label == "SUCCESS" else 40, "macd_histogram_pct": 1 if label == "SUCCESS" else -1, "bb_width": 10, "atr14_ratio_to_close": 2}
        rows.append({"stock_id": index + 1, "d0": (date(2025, 1, 1) + timedelta(days=d0_index)).isoformat(), "label": label, "rule_status": "RULE_MATCH", "core_status": "READY", "enriched_status": "READY", "core_features": core, "enriched_features": enriched, "outcomes": {"d20_return": 5 if label == "SUCCESS" else -2, "mfe_20": 8, "mae_20": -3}})
    return sorted(rows, key=lambda item: item["d0"])


def test_prototype_minimum_median_iqr_zero_deterministic_and_contrast() -> None:
    assert PatternBaselineService.prototype(_baseline_cases(4, 5), "CORE")["status"] == "INSUFFICIENT_DATA"
    cases = _baseline_cases(8, 7)
    first = PatternBaselineService.prototype(cases, "CORE")
    second = PatternBaselineService.prototype(cases, "CORE")
    assert first["status"] == "READY" and first["failure_contrast"] is True
    assert first["case_scores"] == second["case_scores"]
    constant = _baseline_cases(5, 0)
    for case in constant: case["core_features"] = _features(1)
    assert PatternBaselineService.prototype(constant, "CORE")["zero_iqr_feature_count"] == len(CORE_FEATURE_NAMES)


def test_logistic_minimum_expanding_window_same_date_batch_and_metrics() -> None:
    assert PatternBaselineService.logistic_shadow(_baseline_cases(5, 5), "CORE")["status"] == "INSUFFICIENT_DATA"
    result = PatternBaselineService.logistic_shadow(_baseline_cases(10, 10, same_date_batch=True), "CORE")
    assert result["status"] == "SHADOW_EVALUATED"
    assert result["initial_training_window_count"] >= 10
    assert result["evaluated_case_count"] > 0
    assert set(result["metrics"]) == {"accuracy", "precision", "recall", "roc_auc", "brier_score"}


def test_logistic_scaling_is_fitted_per_window(monkeypatch) -> None:
    seen_sizes = []
    original = PatternBaselineService._fit_logistic
    def wrapped(x, y):
        seen_sizes.append(len(x))
        return original(x, y)
    monkeypatch.setattr(PatternBaselineService, "_fit_logistic", staticmethod(wrapped))
    result = PatternBaselineService.logistic_shadow(_baseline_cases(10, 10), "CORE")
    assert result["status"] == "SHADOW_EVALUATED"
    assert min(seen_sizes) < 20 and max(seen_sizes) == 20


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _create_search(db: Session, name: str):
    return DrctStockSignalService(db).create_search(DrctSignalSearchCreate(name=name, description=None, hts_reference_conditions="A", hts_condition_expression="A", change_note="seed"))


def _seed_catalog(db: Session):
    db.execute(text("INSERT INTO chart_marker_groups(id,name,color,sort_order,is_active,created_at,updated_at) VALUES (1,'G','#000',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.execute(text("INSERT INTO chart_markers(id,marker_group_id,name,symbol,sort_order,is_active,created_at,updated_at) VALUES (1,1,'M1','A',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,1,'M2','B',2,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.execute(text("INSERT INTO stocks(id,stock_code,stock_name,is_active,created_at,updated_at) VALUES (1,'000001','종목1',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,'000002','종목2',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(3,'000003','종목3',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.commit()


def _seed_dataset(db: Session) -> int:
    _seed_catalog(db)
    search = _create_search(db, "Dataset")
    rule = DrctStructuredRule(schema_version=1, conditions=[{"code":"A","type":"PRICE_COMPARE_VALUE","label":"종가","configured":True,"params":{"price_field":"CLOSE","offset":0,"operator":"GTE","value":90}}], expression="A")
    DrctRuleService(db).create_rule_version(search["id"], DrctRuleVersionCreate(rule=rule, change_note="rule"))
    DrctStockSignalService(db).replace_marker_links(search["id"], DrctSignalMarkerLinksPut(marker_definition_ids=[1, 2]))
    d0 = date(2026, 5, 1)
    events = [(1,1,1,"SUCCESS"),(2,1,2,None),(3,2,1,"FAILURE"),(4,2,2,"FAILURE"),(5,3,1,"SUCCESS"),(6,3,2,"FAILURE")]
    for event_id, stock_id, marker_id, label in events:
        db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES (:i,:s,:m,:d,:r,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"i":event_id,"s":stock_id,"m":marker_id,"d":d0.isoformat(),"r":label})
    for stock_id, d0_close in ((1,100),(2,80),(3,110)):
        for offset in range(-60, 21):
            day = d0 + timedelta(days=offset)
            close = d0_close + offset * 0.1
            db.execute(text("INSERT INTO stock_daily_prices(stock_id,trade_date,open_price,high_price,low_price,close_price,volume,trading_value,ma5,ma10,ma20,ma60,ma120,ma240,created_at,updated_at) VALUES (:s,:d,:c,:h,:l,:c,1000,1000000,:m5,:m10,:m20,:m60,:m120,:m240,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"s":stock_id,"d":day.isoformat(),"c":close,"h":close+2,"l":close-2,"m5":close-1,"m10":close-2,"m20":close-3,"m60":close-4,"m120":close-5,"m240":close-6})
        db.execute(text("INSERT INTO stock_daily_technical_indicators(stock_id,trade_date,rsi14,macd,macd_signal,macd_histogram,bb_width,atr14_ratio_to_close,created_at,updated_at) VALUES (:s,:d,55,1,.5,.5,10,2,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"s":stock_id,"d":d0.isoformat()})
    db.commit()
    return search["id"]


def test_readiness_no_marker_and_no_rule() -> None:
    db = _db(); search = _create_search(db, "Empty")
    result = DrctTrainingDatasetService(db).readiness(search["id"], None)
    assert result["summary"]["blocking_reasons"] == ["RULE_NOT_CONFIGURED", "NO_MARKER_LINK"]


def test_dataset_events_dedup_rule_d0_feature_and_conflict() -> None:
    db = _db(); search_id = _seed_dataset(db)
    build = TrainingCaseService(db).build(search_id)
    assert build.summary["linked_event_count"] == 6
    assert build.summary["reviewed_event_count"] == 5
    assert build.summary["dedup_case_count"] == 3
    assert build.summary["label_conflict_count"] == 1
    labels = {case["stock_id"]: case["label"] for case in build.cases}
    assert labels == {1:"SUCCESS",2:"FAILURE",3:"CONFLICT"}
    statuses = {case["stock_id"]: case["rule_status"] for case in build.cases}
    assert statuses[1] == "RULE_MATCH" and statuses[2] == "RULE_NO_MATCH"
    case = next(item for item in build.cases if item["stock_id"] == 1)
    assert case["core_status"] == "READY" and case["enriched_status"] == "READY"
    assert case["outcomes"]["d20_return"] is not None


def test_dataset_runtime_storage_unchanged_and_query_count_bulk() -> None:
    db = _db(); search_id = _seed_dataset(db)
    before = {table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in ("drct_signal_search_rules","chart_marker_events","stock_daily_prices")}
    count = 0
    def track(*_args):
        nonlocal count
        count += 1
    event.listen(db.get_bind(), "before_cursor_execute", track)
    preview = DrctTrainingDatasetService(db).preview(search_id, None)
    event.remove(db.get_bind(), "before_cursor_execute", track)
    after = {table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in before}
    assert before == after and preview["summary"]["dedup_case_count"] == 3
    assert count <= 7


def test_training_case_list_and_detail_separate_outcomes() -> None:
    db = _db(); search_id = _seed_dataset(db)
    service = DrctTrainingDatasetService(db)
    rows = service.cases(search_id, None, 1, 25, True)
    assert rows["total"] == 3 and "core_features" not in rows["items"][0]
    detail = service.case_detail(search_id, 1, "2026-05-01", None)
    assert detail["core_features"] and detail["outcomes"]
    assert "학습 입력에 사용하지 않습니다" in detail["outcome_notice"]


def test_rule_data_incomplete_is_kept_as_exclusion() -> None:
    db = _db(); search_id = _seed_dataset(db)
    db.execute(text("DELETE FROM stock_daily_prices WHERE stock_id=1 AND trade_date='2026-05-01'")); db.commit()
    build = TrainingCaseService(db).build(search_id)
    case = next(item for item in build.cases if item["stock_id"] == 1)
    assert case["rule_status"] == "RULE_DATA_INCOMPLETE"
    assert build.summary["rule_data_incomplete_count"] == 1


def test_metric_unavailable_is_null_not_zero() -> None:
    assert PatternBaselineService._roc_auc(np.asarray([1, 1]), np.asarray([0.2, 0.8])) is None
    assert PatternBaselineService._roc_auc(np.asarray([0, 0]), np.asarray([0.2, 0.8])) is None


def test_auto_profile_and_model_preview_are_runtime_only() -> None:
    cases = _baseline_cases(10, 10)
    assert PatternBaselineService.choose_profile(cases, "AUTO") == "ENRICHED"
    db = _db(); search_id = _seed_dataset(db)
    tables_before = set(db.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).scalars())
    DrctTrainingDatasetService(db).baseline(search_id, None, "AUTO")
    tables_after = set(db.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).scalars())
    assert tables_before == tables_after
    assert not any("model" in name or "feature_matrix" in name for name in tables_after)


def test_phase5_overview_keeps_unconfigured_search_not_ready() -> None:
    db = _db(); _create_search(db, "Not ready")
    result = DrctSignalValidationService(db).overview()
    assert result["registered_search_count"] == 1
    assert result["rule_valid_count"] == result["marker_linked_count"] == result["dataset_ready_count"] == 0
    assert result["items"][0]["research_status"] == "NOT_READY"


def test_phase5_dataset_ready_checklist_and_reproducibility_metadata() -> None:
    db = _db(); search_id = _seed_dataset(db)
    report = DrctSignalValidationService(db).report(search_id, None, "AUTO")
    assert report["checklist"]["rule_valid"] and report["checklist"]["marker_linked"]
    assert report["checklist"]["reviewed_case_exists"] and report["checklist"]["rule_match_exists"]
    assert report["metadata"]["search_id"] == search_id and report["metadata"]["rule_schema_version"] == 1
    assert report["metadata"]["feature_schema_version"] == 1 and report["metadata"]["data_cutoff"] == "2026-05-01"
    assert report["research_status"] == "RULE_REVIEW_NEEDED"


def test_phase5_quality_gate_values_and_warning_thresholds() -> None:
    db = _db(); search_id = _seed_dataset(db)
    gate = DrctSignalValidationService(db).report(search_id, None, "CORE")["quality_gate"]
    assert gate["reviewed_coverage"] == {"value": 100.0, "numerator": 3, "denominator": 3}
    assert gate["rule_match_rate"]["value"] == pytest.approx(200 / 3)
    assert gate["core_coverage"]["value"] == 50.0 and gate["enriched_coverage"]["value"] == 50.0
    assert gate["d20_coverage"]["value"] == 100.0
    assert {warning["code"] for warning in gate["warnings"]} >= {"LOW_RULE_MATCH_RATE", "LOW_CORE_COVERAGE", "LOW_ENRICHED_COVERAGE"}


def test_phase5_quality_gate_zero_denominators_are_null() -> None:
    db = _db(); search = _create_search(db, "Empty gate")
    report = DrctSignalValidationService(db).report(search["id"], None, "AUTO")
    for name in ("reviewed_coverage", "rule_match_rate", "core_coverage", "enriched_coverage", "d20_coverage"):
        assert report["quality_gate"][name]["value"] is None


def test_phase5_rule_mismatch_returns_failed_conditions() -> None:
    db = _db(); search_id = _seed_dataset(db)
    rows = DrctSignalValidationService(db).report(search_id, None, "CORE")["rule_mismatch_cases"]
    assert len(rows) == 1 and rows[0]["stock_id"] == 2
    assert rows[0]["failed_conditions"] and rows[0]["failed_conditions"][0]["status"] == "FAIL"


def test_phase5_data_incomplete_is_separate_from_rule_mismatch() -> None:
    db = _db(); search_id = _seed_dataset(db)
    db.execute(text("DELETE FROM stock_daily_prices WHERE stock_id=1 AND trade_date='2026-05-01'")); db.commit()
    report = DrctSignalValidationService(db).report(search_id, None, "CORE")
    assert any(row["stock_id"] == 1 and row["rule_status"] == "RULE_DATA_INCOMPLETE" for row in report["data_incomplete_cases"])
    assert all(row["stock_id"] != 1 for row in report["rule_mismatch_cases"])


def test_phase5_outcome_mean_median_difference_coverage_and_recent_null() -> None:
    success = [{"label":"SUCCESS","rule_status":"RULE_MATCH","outcomes":{"d5_return":1,"d10_return":2,"d20_return":3,"mfe_20":5,"mae_20":-2}}, {"label":"SUCCESS","rule_status":"RULE_MATCH","outcomes":{"d5_return":3,"d10_return":4,"d20_return":None,"mfe_20":None,"mae_20":None}}]
    failure = [{"label":"FAILURE","rule_status":"RULE_MATCH","outcomes":{"d5_return":-1,"d10_return":0,"d20_return":-2,"mfe_20":1,"mae_20":-5}}]
    s = DrctSignalValidationService._outcome(success + failure, "SUCCESS")
    f = DrctSignalValidationService._outcome(success + failure, "FAILURE")
    delta = DrctSignalValidationService._difference(s, f)
    assert s["d5_return"] == {"mean": 2.0, "median": 2.0, "n": 2}
    assert s["d20_return"] == {"mean": 3.0, "median": 3.0, "n": 1}
    assert delta["d20_return"] == 5.0


def test_phase5_prototype_oos_is_time_ordered_same_date_and_future_independent() -> None:
    cases = _baseline_cases(10, 10, same_date_batch=True)
    first = PatternBaselineService.prototype_shadow(cases, "CORE")
    for case in cases: case["outcomes"]["d20_return"] = 999999
    second = PatternBaselineService.prototype_shadow(cases, "CORE")
    assert first == second and first["status"] == "OOS_EVALUATED"
    evaluated_dates = {item["d0"] for item in first["case_scores"]}
    assert all(sum(case["d0"] == d0 for case in cases) == sum(item["d0"] == d0 for item in first["case_scores"]) for d0 in evaluated_dates)


def test_phase5_prototype_small_sample_and_score_bucket() -> None:
    assert PatternBaselineService.prototype_shadow(_baseline_cases(4, 4), "CORE")["status"] == "INSUFFICIENT_EVALUATION"
    cases = _baseline_cases(10, 10)
    scores = PatternBaselineService.prototype_shadow(cases, "CORE")["case_scores"]
    buckets = DrctSignalValidationService._buckets(scores, "prototype_score", cases)
    assert sum(bucket["n"] for bucket in buckets) == len(scores)
    assert all("observed_success_ratio" in bucket and "d20_median" in bucket for bucket in buckets)


def test_phase5_score_relationship_matches_same_oos_cases() -> None:
    prototype = [{"stock_id":1,"d0":"2026-01-01","prototype_score":60}, {"stock_id":2,"d0":"2026-01-02","prototype_score":80}]
    logistic = [{"stock_id":2,"d0":"2026-01-02","shadow_score":90}, {"stock_id":1,"d0":"2026-01-01","shadow_score":70}, {"stock_id":3,"d0":"2026-01-03","shadow_score":50}]
    result = DrctSignalValidationService._score_relationship(prototype, logistic)
    assert result["matched_case_count"] == 2 and result["pearson"] == pytest.approx(1) and result["spearman"] == pytest.approx(1)


def test_phase5_feature_distribution_iqr_and_high_correlation_without_matrix() -> None:
    cases = _baseline_cases(10, 10)
    distribution, pairs = DrctSignalValidationService._feature_research(cases, "CORE")
    assert len(distribution) == len(CORE_FEATURE_NAMES)
    assert {"success_median", "failure_median", "difference", "success_iqr", "failure_iqr"} <= set(distribution[0])
    assert pairs and abs(pairs[0]["correlation"]) >= .9
    db = _db(); search_id = _seed_dataset(db)
    report = DrctSignalValidationService(db).report(search_id, None, "CORE")
    assert "core_features" not in str(report) and "enriched_features" not in str(report)


def test_phase5_validation_report_is_runtime_and_does_not_change_database() -> None:
    db = _db(); search_id = _seed_dataset(db)
    before = db.execute(text("SELECT total_changes()" )).scalar_one()
    tables_before = set(db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
    DrctSignalValidationService(db).report(search_id, None, "AUTO")
    after = db.execute(text("SELECT total_changes()" )).scalar_one()
    tables_after = set(db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
    assert before == after and tables_before == tables_after


def test_phase5_overview_api_uses_static_route_before_search_id(isolated_api_client) -> None:
    created = isolated_api_client.post("/drct-stock-signals/searches", json={"name":"API 준비","description":None,"hts_reference_conditions":"A","hts_condition_expression":"A","change_note":"seed"})
    assert created.status_code == 201
    response = isolated_api_client.get("/drct-stock-signals/searches/training-overview")
    assert response.status_code == 200 and response.json()["registered_search_count"] == 1
    assert response.json()["items"][0]["research_status"] == "NOT_READY"


def test_phase5_validation_report_api_does_not_expose_feature_matrix(isolated_api_client) -> None:
    search = isolated_api_client.post("/drct-stock-signals/searches", json={"name":"API 보고서","description":None,"hts_reference_conditions":"A","hts_condition_expression":"A","change_note":"seed"}).json()
    response = isolated_api_client.post(f"/drct-stock-signals/searches/{search['id']}/validation-report", json={"search_version_id":search["current_version"]["id"],"feature_profile":"AUTO"})
    assert response.status_code == 200 and response.json()["research_status"] == "NOT_READY"
    assert "core_features" not in response.text and "enriched_features" not in response.text


def test_phase5_logistic_coefficient_stability_is_window_based() -> None:
    result = PatternBaselineService.logistic_shadow(_baseline_cases(12, 12, same_date_batch=True), "CORE")
    assert result["status"] == "SHADOW_EVALUATED"
    assert len(result["coefficient_stability"]) == len(CORE_FEATURE_NAMES)
    assert all(item["window_count"] > 0 and item["direction_flip_count"] >= 0 for item in result["coefficient_stability"])
