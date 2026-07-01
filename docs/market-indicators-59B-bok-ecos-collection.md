# 59-B BOK ECOS collection

## Scope

59-B adds the first collection path for general market indicators that can be sourced from the Bank of Korea ECOS API.

Initial target indicators:

- USD_KRW
- JPY_KRW
- CNY_KRW
- BASE_RATE
- CALL_RATE
- KTB_3Y
- KTB_10Y

The implementation does not hard-code or auto-enable unverified ECOS stat/item codes. A mapping must be tested successfully before it can be activated for collection.

## Environment

`.env.example` includes:

```env
BOK_ECOS_API_KEY=
BOK_ECOS_BASE_URL=https://ecos.bok.or.kr/api
BOK_ECOS_TIMEOUT_SECONDS=15
```

The API key is never returned by backend responses, saved in provider mappings, or included in raw payload JSON.

## Mapping flow

1. Search ECOS item candidates.

```http
GET /market-indicators-data/ecos/item-list?stat_code=731Y001
```

2. Save a candidate mapping.

```http
PUT /market-indicators-data/USD_KRW/provider-mapping
Content-Type: application/json

{
  "provider": "BOK_ECOS",
  "api_type": "ECONOMIC_STAT",
  "api_id": "731Y001",
  "provider_symbol": "0000001",
  "request_params_json": {
    "stat_code": "731Y001",
    "cycle": "D",
    "item_code1": "0000001"
  }
}
```

3. Test the mapping against ECOS.

```http
POST /market-indicators-data/USD_KRW/provider-mapping/test
Content-Type: application/json

{
  "start_date": "2026-01-01",
  "end_date": "2026-06-30"
}
```

4. Activate only after test success.

```http
POST /market-indicators-data/USD_KRW/provider-mapping/activate
```

5. Collect enabled and verified mappings.

```http
POST /market-indicators-data/collect
Content-Type: application/json

{
  "indicator_codes": ["USD_KRW", "BASE_RATE"],
  "start_date": "2025-07-01",
  "end_date": "2026-06-30"
}
```

## Storage behavior

- Collected rows are upserted into `market_indicator_values` by `(indicator_code, value_date)`.
- The latest collected row updates `market_indicators.latest_value`, `latest_value_date`, `latest_change_value`, and `latest_change_pct`.
- Indicators without enabled and verified BOK_ECOS mappings remain `WAITING`.
- Per-indicator collection failures are isolated in the collect response.

## Frontend

The market indicator admin drawer now has a `General Mapping` tab that shows mapping status for general indicators, including provider, stat code, item code, verification, activation, and last test message.
