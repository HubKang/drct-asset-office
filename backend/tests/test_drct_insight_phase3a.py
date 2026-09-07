from types import SimpleNamespace

from backend.app.services.drct_insight_service import DrctInsightService
from backend.app.services.us_kr_theme_link_service import UsKrThemeLinkService


def test_preliminary_requires_strong_success_pattern_and_keeps_final_strict() -> None:
    assert DrctInsightService._pattern_status("NOT_READY", "VERY_SIMILAR", 4) == "PROMISING"
    assert DrctInsightService._pattern_status("NOT_READY", "HIGH_SIMILARITY", 0) == "PROMISING"
    assert DrctInsightService._pattern_status("NOT_READY", "SIMILAR", 4) == "NOT_READY"
    assert DrctInsightService._is_preliminary_candidate("PASS", "PASS", "PROMISING")
    assert DrctInsightService._is_preliminary_candidate("PASS", "WATCH", "PROMISING")
    assert not DrctInsightService._is_preliminary_candidate("WATCH", "PASS", "PROMISING")
    assert DrctInsightService._pattern_status("PASS", "VERY_SIMILAR", 5) == "VERIFIED"
    assert DrctInsightService._is_final_candidate("PASS", "WATCH", "PASS")


def test_us_lead_reuses_relation_identifiers_and_handles_missing_mapping() -> None:
    source = SimpleNamespace(
        link_id=17, us_theme_id=3, us_theme_name="AI 반도체", latest_value=4.7,
        breadth_ratio=0.8, available=True, response_rate=65.0, sample_count=40,
        latest_us_date="2026-09-04", kr_target_date="2026-09-07",
    )
    lead = DrctInsightService._us_lead(source)
    assert lead["link_id"] == 17
    assert lead["us_theme_id"] == 3
    assert lead["direction"] == "UP"
    assert lead["strength"] == "STRONG"
    assert lead["kr_response_date"] == "2026-09-07"
    assert DrctInsightService._us_lead(None) == {"linked": False, "relation_status": "MISSING"}


def test_existing_us_kr_pair_policy_uses_first_later_kr_trading_day() -> None:
    us_rows = [{"trade_date": "2026-09-04", "us_value": 2.5}]
    kr_rows = [
        {"return_date": "2026-09-04", "kr_return": -1.0},
        {"return_date": "2026-09-07", "kr_return": 1.2},
    ]
    pairs, candidate_count, excluded_count = UsKrThemeLinkService._build_pairs_from_rows(us_rows, kr_rows, 120, 7)
    assert pairs[0]["us_trade_date"] == "2026-09-04"
    assert pairs[0]["kr_trade_date"] == "2026-09-07"
    assert pairs[0]["calendar_gap_days"] == 3
    assert candidate_count == 1
    assert excluded_count == 0


def test_readiness_stale_and_not_ready_are_distinct() -> None:
    assert DrctInsightService._source_status(None, "2026-09-07", available=False) == "NOT_READY"
    assert DrctInsightService._source_status("2026-09-04", "2026-09-07", available=True) == "READY"
    assert DrctInsightService._source_status("2026-08-28", "2026-09-07", available=True) == "STALE"
