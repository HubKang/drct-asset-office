from __future__ import annotations

from sqlalchemy import text

from backend.app.services.drct_training_dataset_service import DrctTrainingDatasetService
from backend.app.services.drct_training_case_service import TrainingCaseService, TrainingDatasetBuild
from backend.tests.test_drct_training_dataset import _db, _seed_dataset


def test_mismatch_summary_counts_match_no_match_and_condition_values() -> None:
    db = _db(); search_id = _seed_dataset(db)
    result = DrctTrainingDatasetService(db).mismatch_summary(search_id, None)
    assert result["case_count"] == 1
    assert result["conditions"] == [{"code":"A", "label":"종가", "evaluated_count":1, "pass_count":0, "fail_count":1, "incomplete_count":0, "fail_rate":100.0}]


def test_mismatch_summary_zero_denominator_and_empty_conditions() -> None:
    db = _db(); search_id = _seed_dataset(db)
    db.execute(text("UPDATE stock_daily_prices SET close_price=120 WHERE stock_id=2 AND trade_date='2026-05-01'")); db.commit()
    result = DrctTrainingDatasetService(db).mismatch_summary(search_id, None)
    assert result["case_count"] == 0 and result["conditions"] == []


def test_rule_match_filter_returns_only_matching_cases() -> None:
    db = _db(); search_id = _seed_dataset(db)
    result = DrctTrainingDatasetService(db).cases(search_id, None, 1, 100, True, "RULE_MATCH")
    assert result["total"] == 2 and {item["stock_id"] for item in result["items"]} == {1, 3}


def test_rule_no_match_filter_and_failed_condition_payload() -> None:
    db = _db(); search_id = _seed_dataset(db)
    result = DrctTrainingDatasetService(db).cases(search_id, None, 1, 100, True, "RULE_NO_MATCH")
    assert result["total"] == 1 and result["items"][0]["failed_conditions"][0]["code"] == "A"


def test_condition_filter_returns_only_condition_failures() -> None:
    db = _db(); search_id = _seed_dataset(db)
    yes = DrctTrainingDatasetService(db).cases(search_id, None, 1, 100, True, "RULE_NO_MATCH", "A")
    no = DrctTrainingDatasetService(db).cases(search_id, None, 1, 100, True, "RULE_NO_MATCH", "B")
    assert yes["total"] == 1 and no["total"] == 0


def test_data_incomplete_filter_uses_marker_d0() -> None:
    db = _db(); search_id = _seed_dataset(db)
    db.execute(text("DELETE FROM stock_daily_prices WHERE stock_id=1 AND trade_date='2026-05-01'")); db.commit()
    result = DrctTrainingDatasetService(db).cases(search_id, None, 1, 100, True, "RULE_DATA_INCOMPLETE")
    assert result["total"] == 1 and result["items"][0]["d0"] == "2026-05-01"


def test_label_filter_returns_undecided_without_changing_review() -> None:
    db = _db(); search_id = _seed_dataset(db)
    db.execute(text("UPDATE chart_marker_events SET review_result=NULL WHERE stock_id=1")); db.commit()
    before = db.execute(text("SELECT COUNT(*) FROM chart_marker_events WHERE review_result IS NULL")).scalar_one()
    result = DrctTrainingDatasetService(db).cases(search_id, None, 1, 100, True, None, None, "UNDECIDED")
    after = db.execute(text("SELECT COUNT(*) FROM chart_marker_events WHERE review_result IS NULL")).scalar_one()
    assert result["total"] == 1 and before == after


def test_summary_and_filters_do_not_persist_analysis() -> None:
    db = _db(); search_id = _seed_dataset(db); service = DrctTrainingDatasetService(db)
    tables = ("drct_signal_search_rules", "chart_marker_events", "stock_daily_prices")
    before = {name: db.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one() for name in tables}
    service.mismatch_summary(search_id, None); service.cases(search_id, None, 1, 100, True, "RULE_NO_MATCH", "A")
    after = {name: db.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one() for name in tables}
    assert before == after


def test_explicit_and_current_version_return_same_current_result() -> None:
    db = _db(); search_id = _seed_dataset(db); service = DrctTrainingDatasetService(db)
    current = db.execute(text("SELECT id FROM drct_signal_search_versions WHERE search_id=:id AND is_current=1"), {"id":search_id}).scalar_one()
    implicit, explicit = service.mismatch_summary(search_id, None), service.mismatch_summary(search_id, current)
    assert implicit["search_version_id"] == explicit["search_version_id"]
    assert implicit["conditions"] == explicit["conditions"] and implicit["case_count"] == explicit["case_count"]


def test_future_prices_do_not_change_d0_rule_summary() -> None:
    db = _db(); search_id = _seed_dataset(db); service = DrctTrainingDatasetService(db)
    before = service.mismatch_summary(search_id, None)
    db.execute(text("UPDATE stock_daily_prices SET close_price=99999, ma5=99999 WHERE trade_date>'2026-05-01'")); db.commit()
    after = service.mismatch_summary(search_id, None)
    assert before["conditions"] == after["conditions"] and before["case_count"] == after["case_count"]


def test_condition_rows_are_sorted_by_fail_rate_descending() -> None:
    db = _db(); search_id = _seed_dataset(db)
    rates = [item["fail_rate"] for item in DrctTrainingDatasetService(db).mismatch_summary(search_id, None)["conditions"]]
    assert rates == sorted(rates, reverse=True)


def test_case_detail_reuses_d0_diagnostics_and_hides_internal_storage() -> None:
    db = _db(); search_id = _seed_dataset(db); service = DrctTrainingDatasetService(db)
    detail = service.case_detail(search_id, 2, "2026-05-01", None)
    assert detail["rule_status"] == "RULE_NO_MATCH" and detail["rule_diagnostics"][0]["status"] == "FAIL"
    assert "rule_json" not in detail and "price_rows" not in detail


def test_nested_or_branch_statistics_are_evaluated_independently(monkeypatch) -> None:
    db = _db(); service = DrctTrainingDatasetService(db)
    cases = [
        {"rule_status":"RULE_NO_MATCH", "rule_diagnostics":[{"code":"E","label":"E","status":"PASS"},{"code":"F","label":"F","status":"PASS"},{"code":"H","label":"H","status":"FAIL"},{"code":"I","label":"I","status":"PASS"}]},
        {"rule_status":"RULE_NO_MATCH", "rule_diagnostics":[{"code":"E","label":"E","status":"PASS"},{"code":"F","label":"F","status":"FAIL"},{"code":"H","label":"H","status":"PASS"},{"code":"I","label":"I","status":"PASS"}]},
    ]
    build = TrainingDatasetBuild(1, 2, 3, "VALID", 2, 1, cases, {}, 1)
    monkeypatch.setattr(service, "_build", lambda *_args: build)
    monkeypatch.setattr(TrainingCaseService, "_version_rule", lambda *_args: ({"id":2}, {"expression":"(E AND F) OR (H AND I)"}, "VALID"))
    result = service.mismatch_summary(1, 2)
    branches = {row["expression"]: row for row in result["branches"]}
    assert branches["E AND F"]["pass_count"] == 1
    assert branches["H AND I"]["pass_count"] == 1
