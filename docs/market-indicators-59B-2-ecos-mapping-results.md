# 59-B-2 ECOS mapping results

## Scope

Confirmed BOK ECOS mappings for the first seven general market indicators and ran the first collection window.

Collection window used for the first run:

```text
2026-04-01 ~ 2026-07-01
```

## Confirmed Mappings

| DrCT indicator | ECOS stat_code | ECOS stat_name | cycle | item_code1 | item_name1 | unit | test | activate | collect |
|---|---:|---|---|---:|---|---|---|---|---|
| USD_KRW | 731Y001 | 3.1.1.1. Major currency KRW exchange rates | D | 0000001 | KRW/USD base rate | KRW | SUCCESS | YES | SUCCESS |
| JPY_KRW | 731Y001 | 3.1.1.1. Major currency KRW exchange rates | D | 0000002 | KRW/JPY (100 yen) | KRW | SUCCESS | YES | SUCCESS |
| CNY_KRW | 731Y001 | 3.1.1.1. Major currency KRW exchange rates | D | 0000053 | KRW/CNY base rate | KRW | SUCCESS | YES | SUCCESS |
| BASE_RATE | 722Y001 | 1.3.1. BOK base rate and lending/deposit rates | D | 0101000 | BOK base rate | annual % | SUCCESS | YES | SUCCESS |
| CALL_RATE | 817Y002 | 1.3.2.1. Market rates, daily | D | 010101000 | Call rate, 1 day, all transactions | annual % | SUCCESS | YES | SUCCESS |
| KTB_3Y | 817Y002 | 1.3.2.1. Market rates, daily | D | 010200000 | Korea Treasury Bond, 3Y | annual % | SUCCESS | YES | SUCCESS |
| KTB_10Y | 817Y002 | 1.3.2.1. Market rates, daily | D | 010210000 | Korea Treasury Bond, 10Y | annual % | SUCCESS | YES | SUCCESS |

Provider mapping storage format:

```json
{
  "provider": "BOK_ECOS",
  "api_type": "STATISTIC_SEARCH",
  "api_id": "ECOS_STATISTIC_SEARCH",
  "endpoint_url": "/api/StatisticSearch",
  "provider_symbol": "{stat_code}:{item_code1}",
  "request_params_json": {
    "stat_code": "...",
    "cycle": "D",
    "item_code1": "...",
    "item_name1": "...",
    "value_field": "DATA_VALUE",
    "scale": 1,
    "source_unit": "...",
    "date_format": "ECOS_TIME"
  }
}
```

## Test Results

| Indicator | sample_count |
|---|---:|
| USD_KRW | 62 |
| JPY_KRW | 62 |
| CNY_KRW | 62 |
| BASE_RATE | 89 |
| CALL_RATE | 61 |
| KTB_3Y | 61 |
| KTB_10Y | 61 |

All seven mappings were verified and activated.

## Collection Results

| Indicator | saved_count | first_date | latest_date | latest_value |
|---|---:|---|---|---:|
| USD_KRW | 62 | 2026-04-01 | 2026-07-01 | 1548.4 |
| JPY_KRW | 62 | 2026-04-01 | 2026-07-01 | 952.25 |
| CNY_KRW | 62 | 2026-04-01 | 2026-07-01 | 227.81 |
| BASE_RATE | 89 | 2026-04-01 | 2026-06-28 | 2.5 |
| CALL_RATE | 61 | 2026-04-01 | 2026-06-30 | 2.65 |
| KTB_3Y | 61 | 2026-04-01 | 2026-06-30 | 3.703 |
| KTB_10Y | 61 | 2026-04-01 | 2026-06-30 | 4.091 |

`market_indicators.latest_value` and `latest_value_date` were updated for all seven indicators.

## Unit Notes

- JPY_KRW uses ECOS item `KRW/JPY (100 yen)`. The value is intentionally stored as provided by ECOS; no `/100` conversion is applied in this step.
- BASE_RATE is available from ECOS with daily cycle `D`; the DrCT seed/default frequency was adjusted to `DAILY`.

## API Key Safety

Checked collected `raw_payload_json` rows for the seven indicators. No `BOK_ECOS_API_KEY`, ECOS URL, or `StatisticSearch` URL text was found.

## Remaining Work

- 59-B-3 can expose these general indicators in the main market indicator list/chart.
- A longer historical backfill can be run after verifying the 3-month collection in the UI.
