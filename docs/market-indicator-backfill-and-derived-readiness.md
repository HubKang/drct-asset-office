# Market Indicator Backfill And Derived Readiness

## Scope

This work preserved the existing SQLite database and backfilled only the source indicators needed to promote three derived indicators from `COMPARE_READY` to `SIGNAL_READY`.

Backup:

- `db/drct_asset.sqlite3.backup-20260718-1640-signal-readiness-tuning`

## Source Backfill

Backfill run:

- `run_type`: `BACKFILL`
- `run_id`: 4
- requested range: `2014-01-01` to `2026-07-18`
- target indicators: `BASE_RATE`, `CPI`, `USD_KRW`, `US_FED_FUNDS`, `US_CORE_PCE`

Result:

| Indicator | Provider | Received | Inserted | Updated | Unchanged |
| --- | --- | ---: | ---: | ---: | ---: |
| BASE_RATE | BOK_ECOS | 4,579 | 4,490 | 1 | 88 |
| CPI | BOK_ECOS | 150 | 85 | 12 | 53 |
| USD_KRW | BOK_ECOS | 3,089 | 3,027 | 1 | 61 |
| US_FED_FUNDS | FRED | 4,580 | 3,850 | 1 | 729 |
| US_CORE_PCE | FRED | 149 | 90 | 12 | 47 |

BOK ECOS collection now pages through 1,000-row chunks, so long daily ranges are not truncated.

## Derived Recalculation

Backfill run:

- `run_type`: `BACKFILL`
- `run_id`: 5
- requested range: `2014-01-01` to `2026-07-18`
- target indicators: `KR_REAL_POLICY_RATE`, `US_REAL_POLICY_RATE`, `USD_KRW_VOLATILITY`

Result:

| Derived indicator | Formula | Count | First | Latest | Readiness |
| --- | --- | ---: | --- | --- | --- |
| KR_REAL_POLICY_RATE | `BASE_RATE - CPI YoY` | 138 | 2015-01-01 | 2026-06-01 | SIGNAL_READY |
| US_REAL_POLICY_RATE | `US_FED_FUNDS - US_CORE_PCE YoY` | 137 | 2015-01-01 | 2026-05-01 | SIGNAL_READY |
| USD_KRW_VOLATILITY | 20-observation rolling std dev of USD/KRW returns | 3,069 | 2014-02-03 | 2026-07-16 | SIGNAL_READY |

Date alignment:

- Monthly real policy rates use the inflation observation month as the derived observation date.
- The policy rate value is the latest valid policy-rate observation on or before the inflation observation date.
- No future policy-rate values are applied to prior months.
- USD/KRW volatility uses the latest valid prior FX observation for return calculation and stores no weekend/holiday duplication.

## Readiness Criteria

General indicator readiness:

- Daily: 60 rows
- Weekly: 26 rows
- Monthly: 24 rows

Special derived readiness:

- `KR_REAL_POLICY_RATE`: 60 monthly rows recommended
- `US_REAL_POLICY_RATE`: 60 monthly rows recommended
- `USD_KRW_VOLATILITY`: 252 daily rows recommended

All three special derived indicators now exceed the recommended minimum.

## Remaining Notes

Five-year simulations may still show `DATA_INSUFFICIENT_PERIODS` for signals that depend on indicators whose own history starts later than five years ago. Three-year simulations are available for the initial rules after this backfill.
