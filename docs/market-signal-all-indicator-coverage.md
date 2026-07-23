# Market Signal All Indicator Coverage

## Scope

This change expands the Market Signal Management screen and backend signal engine from a US/FRED-centered set of trend cards to a common catalog built from both `market_indexes` and `market_indicators`.

Economic Flow Management and scenario diagnosis remain out of scope. The supported user-facing layers remain:

- 단일 지표 시그널
- 복합 지표 시그널
- 객관적 현상

## Backup

Before implementation, the working SQLite database was backed up to:

`db/drct_asset.sqlite3.backup-20260718-1949-all-indicator-signals`

No existing market data or signal definitions were reset or deleted.

## Common Catalog

The new signal catalog API is:

`GET /market-signals/catalog`

It merges:

- `market_indexes` as `item_type = INDEX`, `source_kind = MARKET_INDEX`
- `market_indicators` as `item_type = INDICATOR`, `source_kind = MARKET_INDICATOR`
- derived indicator rows as `item_type = INDICATOR`, `source_kind = DERIVED_INDICATOR`

The stable base key is:

`item_type + item_code`

The model-specific key is:

`item_type + item_code + model_profile_code`

Duplicate cards are suppressed at selector/service level. Existing duplicate DB rows are not physically deleted.

## Catalog Fields

Catalog rows include item identity, display metadata, data coverage, registration coverage, recommended model profile, supported transforms, and exclusion/readiness information:

- `item_type`
- `item_code`
- `item_name`
- `category`
- `category_group`
- `country`
- `provider`
- `frequency`
- `unit`
- `data_count`
- `first_observation_date`
- `latest_observation_date`
- `readiness`
- `signal_readiness`
- `registered_signal_count`
- `active_signal_count`
- `trend_model_count`
- `recommended_profile_code`
- `recommended_profile_reason`
- `supported_transforms`
- `exclusion_reason`

## Signal Readiness

The current screen and API use these readiness states:

- `DATA_INSUFFICIENT`
- `SIGNAL_AVAILABLE`
- `SIGNAL_NOT_REGISTERED`
- `SIGNAL_DRAFT`
- `SIGNAL_ACTIVE`
- `REVIEW_REQUIRED`
- `EXCLUDED`

Draft creation never activates a signal automatically. Created single-indicator signals are saved as `DRAFT`.

## Model Profiles

The model profile table is:

`market_signal_model_profiles`

Seeded active profiles:

- `MARKET_PRICE_TREND`
- `FX_TREND`
- `YIELD_TREND`
- `POLICY_RATE_REGIME`
- `MACRO_MOM_YOY_TREND`
- `SENTIMENT_TREND`
- `RELATIVE_STRENGTH`
- `VOLATILITY_REGIME`
- `SPREAD_REGIME`
- `COMMODITY_TREND`

The catalog recommends a profile by `item_type`, category, frequency, country, and item code.

## Draft APIs

New APIs:

- `GET /market-signals/model-profiles`
- `POST /market-signals/single-indicator/preview`
- `POST /market-signals/single-indicator/create-draft`
- `POST /market-signals/single-indicator/create-drafts`
- `GET /market-signals/single-indicator/coverage-summary`
- `POST /market-signals/composite/templates/{id}/validate-readiness`

Duplicate DRAFT creation is blocked by `item_type + item_code + profile_code`.

## UI

The `MarketSignalsPage` single-indicator tab now displays the common catalog, not only already registered trend models.

The card grid can show:

- registered single-indicator cards with existing sparkline and trend diagnostics
- unregistered catalog cards with data count, latest observation date, recommended profile, preview, and DRAFT creation actions

Filters are available for category, signal readiness, model profile, and text search.

The card title remains one line with ellipsis and a `title` tooltip for full indicator names. Card sizing and grid structure remain aligned with the existing screen.

## Stage-Based Operation UX

Single-indicator cards now separate operation status from current trend judgement:

- 미등록: 추세를 확인할 지표
- 초안: 룰을 검증할 시그널
- 운영: 자동 평가 중인 시그널
- 중지: 이력은 유지하되 운영하지 않는 시그널
- 데이터 부족: 관측값 보강 필요

Details are documented in [market-signal-stage-based-operation-ux.md](market-signal-stage-based-operation-ux.md).

## GPT Catalog

The GPT rule design prompt now receives the full signal catalog from `market_indexes + market_indicators`, including domestic, US, commodity, and derived indicators. GPT remains an auxiliary rule-design helper and cannot change DrCT rule state.

## Domestic Composite Templates

Additional domestic composite templates were seeded:

- `KR_STOCK_RISK_OFF_TURN`
- `USD_KRW_UP_PRESSURE`
- `KR_LONG_RATE_PRESSURE`
- `KR_SENTIMENT_WEAKENING`
- `KR_SEMICONDUCTOR_CONTEXT_WEAKENING`
- `KR_REAL_TIGHTENING_ENVIRONMENT`

Templates are stored as `DRAFT` templates and can be readiness-validated before copying.

## Verification

Verified:

- backend compileall
- market signal API tests
- TypeScript noEmit
- production frontend build

Visual viewport checks were not automated in this pass.


## 운영 평가 이력

운영 활성화 이후 BASELINE·PERIODIC·MANUAL 평가와 상태 전환 이벤트 정책은 [운영 시그널 평가 이력](./market-signal-evaluation-history.md)을 따른다. 사용자 표시는 FALSE_BREAK를 ‘일시 이탈 후 복귀’로 통일한다.
