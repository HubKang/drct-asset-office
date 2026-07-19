# Market Indicator Data Readiness

This document records the readiness model used for market indicator collection, charting, compare, signal rules, and GPT-assisted rule design.

## Readiness Levels

| Level | Meaning |
| --- | --- |
| `MASTER_ONLY` | Indicator master exists, but an enabled and verified provider mapping is missing. |
| `MAPPING_READY` | Provider mapping is enabled and verified, but no numeric values are stored yet. |
| `DATA_READY` | Numeric values exist in the DB. |
| `CHART_READY` | Numeric values can be rendered by the line chart API/UI. |
| `COMPARE_READY` | Numeric values can be normalized and used in the compare chart. |
| `SIGNAL_READY` | Data count is sufficient for the default signal transform catalog. |
| `ERROR` | Current collection status or readiness calculation indicates an error. |

The current API collapses data/chart/compare readiness into a single computed item with explicit booleans:
`data_ready`, `chart_ready`, `compare_ready`, and `signal_ready`.

## API

- `GET /market-indicators-data/readiness`
- `GET /market-indicators-data/readiness?indicator_codes=WTI&indicator_codes=US_CORE_PCE`
- `GET /market-indicators-data/{indicator_code}/readiness`

Each item includes provider, provider symbol, frequency, unit, value count, first/latest value date, latest collected time, readiness reason, and supported signal transforms.

## Signal Minimums

Default signal-ready minimums:

| Frequency | Minimum rows |
| --- | ---: |
| DAILY | 60 |
| WEEKLY | 26 |
| MONTHLY | 24 |

Transform availability is data-count based:

- `RAW_VALUE`: 1 row
- `CHANGE`, `CHANGE_RATE`, `MOM`: 2 rows
- moving/turn/slope/distance/persistence transforms: 20 rows
- `Z_SCORE`, `PERCENTILE`, `N_PERIOD_HIGH`, `N_PERIOD_LOW`, `YOY`: 60 rows

## Current Completion Notes

- FRED 9 indicators are mapped, enabled, collected, and DB-backed.
- Monthly FRED price indexes (`US_CPI`, `US_CORE_PCE`) store `period_label`, MoM, and YoY values.
- Weekly FRED indicators (`US_NFCI`, `US_INITIAL_CLAIMS`) store only actual weekly observations returned by FRED.
- Derived indicators use existing source values and do not create future-dated rows.
- `US_REAL_POLICY_RATE` aligns monthly inflation observations with the latest policy-rate value on or before the inflation observation date.

## UI

The market indicator admin drawer includes a `수집 준비도` tab. It displays summary counts and per-indicator readiness rows using the same API that GPT rule design uses.
