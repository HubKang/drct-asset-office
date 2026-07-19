# Market Indicators Collection Enhancement

## Scope

This update improves the DrCT Asset market indicator management feature in three areas:

- collection foundation: incremental windows, per-item failure isolation, collection policies, run history, raw payload cleanup, and revision metadata
- minimal UI: selected refresh, all incremental refresh, admin/history tools, and basic provider/frequency/status filters
- indicator coverage: additional FRED indicators, derived indicators, and a generic KOSIS provider path without unverified KOSIS code seeding

## Storage Policy

The application no longer stores external API raw JSON payloads in `market_indicator_values.raw_payload_json`.

Before applying schema changes, the SQLite database was backed up to:

`db/drct_asset.sqlite3.backup-20260718-115937`

After backup, existing `market_indicator_values.raw_payload_json` values were cleared. Future FRED, BOK ECOS, KOSIS, and derived writes bind `raw_payload_json` as `NULL`.

## Schema Changes

The runtime schema guard now adds:

- `market_index_daily_prices.collected_at`
- `market_index_daily_prices.revised_at`
- `market_indicator_values.collected_at`
- `market_indicator_values.revised_at`
- `market_data_collection_policies`
- `market_data_collection_runs`
- `market_data_collection_run_items`
- `market_indicator_derivations`

Policies are seeded for existing active market indexes and indicators. The run tables record per-run and per-item collection outcomes.

## Collection Behavior

The common API endpoint is:

`POST /market-data/collect`

Supported modes:

- `SELECTED`: refreshes explicitly selected items and can retry items currently marked `ERROR`
- `INCREMENTAL_ALL`: refreshes active indexes and indicators while excluding items already marked `ERROR` or intentionally excluded/custom/no-official

Indicator collection now resolves its window from the latest stored observation date plus a provider policy overlap. If there is no stored data, it falls back to the policy initial lookback period. This avoids the previous broad repeated re-fetch pattern for normal incremental runs.

Each target item is collected in isolation. One provider or item failure is recorded in `market_data_collection_run_items` and does not stop the remaining items.

Batch upsert now reports:

- received
- inserted
- updated
- unchanged

Changed existing values get `revised_at`; all writes get `collected_at`.

Market index moving-average recalculation is limited to the earliest changed date with a lookback buffer instead of recalculating the full series on every save.

## New Indicators

The following FRED indicators are registered with verified FRED series IDs:

- `US_VIX`: `VIXCLS`
- `US_REAL_10Y`: `DFII10`
- `US_BREAKEVEN_10Y`: `T10YIE`
- `US_NFCI`: `NFCI`
- `US_BROAD_DOLLAR`: `DTWEXBGS`
- `WTI`: `DCOILWTICO`
- `US_CPI`: `CPIAUCSL`
- `US_CORE_PCE`: `PCEPILFE`
- `US_INITIAL_CLAIMS`: `ICSA`

The following derived indicators are registered:

- `US_10Y_2Y_SPREAD`
- `KR_10Y_3Y_SPREAD`
- `KR_REAL_POLICY_RATE`
- `US_REAL_POLICY_RATE`
- `USD_KRW_VOLATILITY`
- `NASDAQ_SP500_RELATIVE`
- `SOX_SP500_RELATIVE`

KOSIS provider support is implemented as a generic mapping-driven provider. No KOSIS indicator mapping was seeded without a verified real KOSIS API response and code set.

## UI Changes

The market indicator page header now exposes:

- `선택 지표 갱신`
- `전체 증분 갱신`
- `관리 도구`

The compact indicator list supports provider, frequency, and collection status filters. A refresh checkbox can select multiple visible metrics for the selected refresh action. The admin drawer includes a collection history tab backed by `/market-data/collection-runs`.

### Selector Card Catalog Alignment

The Market Indicators page uses a shared US-market display catalog for the compare group and the left selector list. The US-market selector includes the same 15 active indicators as the compare group:

- `US_NASDAQ`
- `US_SP500`
- `US_DOW`
- `US_SOX`
- `US_10Y`
- `US_2Y`
- `US_FED_FUNDS`
- `US_VIX`
- `US_REAL_10Y`
- `US_BREAKEVEN_10Y`
- `US_NFCI`
- `US_BROAD_DOLLAR`
- `US_CPI`
- `US_CORE_PCE`
- `US_INITIAL_CLAIMS`

`WTI` remains outside the US-market group and is shown in the energy/commodity category.

Selector cards keep the existing fixed size. The title is a single-line ellipsis with the full name available through the browser tooltip. The right-side card badge is always a collection status badge such as latest, release waiting, data insufficient, collection needed, error, or unsupported. Provider/category badges are not shown on the card; provider information remains available in chart detail context, hover title, admin tools, and provider mapping views.

Selector items are deduplicated by item type and item code, and chart loading still branches by item type: market indexes use the existing index chart path, while market indicators use the indicator value API and line chart path.

### UI Regression Stabilization

The filter toolbar was stabilized after adding provider/frequency/status filters:

- category pills occupy the first row and wrap naturally to at most two compact rows at narrow widths
- search/provider/frequency/status controls use a scoped grid under `.market-index-page .market-index-toolbar`
- desktop widths keep the four controls on one row
- tablet widths allow a 2x2 control grid
- mobile/narrow widths stack without overlap
- indicator refresh checkboxes are offset from the card title so chart selection and refresh selection remain visually distinct

## Verification Notes

Backend compile check:

`python -m compileall backend\app`

Frontend type check:

`npm.cmd exec -- tsc -p tsconfig.app.json --noEmit`

The full frontend build reached TypeScript output but could not write `frontend/tsconfig.app.tsbuildinfo` in this environment due an `EPERM` filesystem error. The no-emit type check passed.

Backend collection smoke tests were run through FastAPI `TestClient` using the derived `US_10Y_2Y_SPREAD` indicator. The second overlapping run returned only the recent overlap window and reported unchanged rows, confirming incremental behavior.
