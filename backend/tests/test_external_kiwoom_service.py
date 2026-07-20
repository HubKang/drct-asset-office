from backend.app.services.external_kiwoom_service import ExternalKiwoomService


def test_kiwoom_condition_change_rate_hundredths_are_percent_points() -> None:
    assert ExternalKiwoomService._normalize_change_rate(981) == 9.81
    assert ExternalKiwoomService._normalize_change_rate("-1234") == -12.34


def test_kiwoom_condition_change_rate_percent_values_are_kept() -> None:
    assert ExternalKiwoomService._normalize_change_rate(8.85) == 8.85
    assert ExternalKiwoomService._normalize_change_rate("0.85") == 0.85