# 59-B-1 ECOS discovery

## Purpose

59-B-1 adds discovery APIs for BOK ECOS statistic tables so DrCT can find exchange-rate and interest-rate mappings without guessing stat/item codes.

Target indicators:

- USD_KRW
- JPY_KRW
- CNY_KRW
- BASE_RATE
- CALL_RATE
- KTB_3Y
- KTB_10Y

## ECOS API Added

### StatisticTableList

Pattern:

```text
https://ecos.bok.or.kr/api/StatisticTableList/{api_key}/json/kr/{start_index}/{end_index}
https://ecos.bok.or.kr/api/StatisticTableList/{api_key}/json/kr/{start_index}/{end_index}/{parent_stat_code}
```

Returned fields are normalized as:

- `P_STAT_CODE` -> `p_stat_code`
- `STAT_CODE` -> `stat_code`
- `STAT_NAME` -> `stat_name`
- `CYCLE` -> `cycle`
- `SRCH_YN` -> `srch_yn`
- `ORG_NAME` -> `org_name`

API keys are only used inside the provider request path and are never included in responses, DB payloads, UI, or logs.

## Backend APIs

```http
GET /market-indicators-data/ecos/table-list?start_index=1&end_index=100
GET /market-indicators-data/ecos/table-list?parent_stat_code=102Y004&start_index=1&end_index=100
GET /market-indicators-data/ecos/table-search?keyword=??&max_depth=2
POST /market-indicators-data/ecos/discover-candidates
GET /market-indicators-data/ecos/item-list?stat_code=...
```

`discover-candidates` is advisory only. It does not create, verify, activate, or collect provider mappings.

## Candidate Scoring

Rules are intentionally simple and transparent:

- Keyword in `stat_name`: +50
- `srch_yn = Y`: +20
- Preferred cycle match: +15
- `org_name` contains Bank of Korea: +10
- Indicator-specific terms in `stat_name`: +20
- Not searchable: -30
- Cycle mismatch: -10
- Broad parent table: -10

Score is for sorting only, not automatic confirmation.

## Frontend

The Market Indicator admin drawer `General Mapping` tab now includes:

- ECOS keyword search input
- ECOS table-search result table
- Candidate discovery button for the seven FX/rate targets
- Existing general provider mapping status list

## Next Step

Use table-search results to inspect candidate `stat_code`s with `item-list`, then test concrete `stat_code + item_code` pairs through the existing provider-mapping test endpoint. Only successful tests should be activated and collected.


## Verification Notes

2026-07-01 local verification:

- `StatisticTableList` live call succeeded with the configured `BOK_ECOS_API_KEY`.
- Sample call returned `status=SUCCESS`, `message=OK`, `total_count=834`.
- Normalized sample rows included top-level monetary/financial statistic tables.
- An early recursive search implementation exceeded ECOS rate limits. ECOS returned the documented excessive-call message: calls are restricted after more than 300 calls within 3 minutes and should be retried after 30 minutes.
- The implementation was changed after that to use one full `StatisticTableList` fetch plus a 10-minute in-process cache for table-search and candidate discovery.

Because ECOS rate limiting was active after the early recursive test, live candidate discovery for the seven indicators was not completed in this run. Retry after the ECOS limit window resets.
