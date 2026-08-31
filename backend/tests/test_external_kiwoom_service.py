from backend.app.services.external_kiwoom_service import ExternalKiwoomService

from backend.app.providers.market_data.kiwoom_rest_condition_provider import KiwoomRestConditionProvider


def test_kiwoom_condition_change_rate_hundredths_are_percent_points() -> None:
    assert ExternalKiwoomService._normalize_change_rate(981) == 9.81
    assert ExternalKiwoomService._normalize_change_rate("-1234") == -12.34


def test_kiwoom_condition_change_rate_percent_values_are_kept() -> None:
    assert ExternalKiwoomService._normalize_change_rate(8.85) == 8.85
    assert ExternalKiwoomService._normalize_change_rate("0.85") == 0.85


def test_condition_provider_normalizes_integer_encoded_realtime_rates() -> None:
    provider = object.__new__(KiwoomRestConditionProvider)
    items, _, _ = provider._normalize_condition_results(
        {
            "data": [
                {"9001": "A007340", "302": "DN오토모티브", "10": "+000047500", "12": "+000000064", "13": "64417"},
                {"9001": "A446540", "302": "메가터치", "10": "+000006940", "flu_rt": "1.31", "13": "81843"},
            ]
        },
        condition_seq="3",
        condition_name="03. 이평조정_5,10,20,60",
    )

    assert items[0]["change_rate"] == 0.64
    assert items[1]["change_rate"] == 1.31


def test_condition_provider_keeps_zero_rate_instead_of_falling_through() -> None:
    assert KiwoomRestConditionProvider._get_condition_rate({"flu_rt": "0", "12": "+000000123"}, ("flu_rt", "12")) == 0.0
