# Market Indicators 59-A Design

## Purpose

`market_indexes` remains dedicated to OHLCV-style market/sector indexes such as KOSPI, KOSDAQ, sector indexes, and KRX gold spot. The new `market_indicators` model is for general macro and market environment indicators such as FX, rates, inflation, and economy indicators.

## New Tables

- `market_indicators`: indicator master data, category, chart type, unit, latest value summary, collection status.
- `market_indicator_values`: dated values and optional derived metrics such as MoM/YoY/normalized value.
- `market_indicator_provider_mappings`: external provider mapping and verification state.

## Categories

- `FX`
- `RATE`
- `INFLATION`
- `ECONOMY`
- `COMMODITY`
- `GLOBAL_INDEX`
- `GLOBAL_RATE`
- `CUSTOM`

## Seed Indicators

- FX: `USD_KRW`, `JPY_KRW`, `CNY_KRW`
- RATE: `BASE_RATE`, `CALL_RATE`, `KTB_3Y`, `KTB_10Y`
- INFLATION: `CPI`, `PPI`
- ECONOMY: `CSI`, `BSI_MANUFACTURING`

All provider mappings are initially `is_enabled = 0`, `is_verified = 0`, and `last_test_status = WAITING`.

## Provider Priority

For 59-A, no live collection is enabled. For 59-B/59-C:

- BOK ECOS is the preferred first candidate for FX, rates, CSI, BSI, and many macro time series because it offers structured economic statistics.
- KOSIS is a candidate for inflation and survey/statistical datasets.
- DATA_GO_KR is a fallback or service-specific candidate when a public endpoint offers the most direct dataset.
- KRX Open API remains more suitable for exchange/market data than macro indicators.
- Kiwoom REST remains for existing market index and sector index flows.

## API Key Safety

The provider status API returns only:

- `configured`
- `masked_key`
- `status`
- `message`

Raw API keys must not be logged, persisted, returned in API responses, or rendered in the frontend.

## Added API Endpoints

- `GET /market-indicators-data`
- `GET /market-indicators-data/{indicator_code}`
- `GET /market-indicators-data/{indicator_code}/values`
- `GET /market-indicators-data/provider-mappings`
- `GET /market-indicators-data/providers/status`
- `POST /market-indicators-data/collect`

## Next Steps

- 59-B: investigate and verify ECOS/Fallback provider codes for FX and rates.
- 59-C: connect inflation and economy providers.
- 59-D: connect market environment interpretation rules.
