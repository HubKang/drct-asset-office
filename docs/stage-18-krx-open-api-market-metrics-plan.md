# Stage 18 KRX Open API Market Metrics Plan

## Why KRX Open API
- `marcap` collection works, but the upstream 2026 parquet snapshot available during this stage only reaches `2026-02-20`.
- Daily operating market metrics need a fresher source for trading value, market cap, and listed shares.
- KRX Open API is the candidate source for the latest market snapshot.

## Official Service References
- KRX Open API service list:
  - `유가증권 일별매매정보`
  - `코스닥 일별매매정보`
- Official service pages confirm:
  - authentication key is sent in request header `AUTH_KEY`
  - the services are under the KRX Open API stock category
  - service approval is required per API

## Endpoint Plan
- KOSPI daily trade:
  - `https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd`
- KOSDAQ daily trade:
  - `https://data-dbg.krx.co.kr/svc/apis/sto/ksq_bydd_trd`

## Request Shape
- Method: `GET`
- Header:
  - `AUTH_KEY: <KRX_OPEN_API_AUTH_KEY>`
- Query:
  - `basDd=YYYYMMDD`

## Response Shape
- Expected JSON envelope:
  - `OutBlock_1`: row list
- Expected field candidates from prior community examples and current implementation:
  - `ISU_SRT_CD` or `ISU_CD`
  - `ISU_NM`
  - `TDD_CLSPRC`
  - `ACC_TRDVOL`
  - `ACC_TRDVAL`
  - `MKTCAP`
  - `LIST_SHRS`
  - `MKT_NM`

## Environment Variables
- `KRX_OPEN_API_AUTH_KEY`
- `KRX_OPEN_API_BASE_URL`
- `KRX_OPEN_API_TIMEOUT_SECONDS`
- `DATA_API_SERVICE_KEY`

## Key Naming Policy
- `KRX_OPEN_API_AUTH_KEY`
  - KRX Open API only
  - send in request header `AUTH_KEY`
- `DATA_API_SERVICE_KEY`
  - data.go.kr public data portal only
  - send in request query parameter `serviceKey`
- `KRX_API_SERVICE_KEY`
  - deprecated
  - no longer used in operating code

## Storage Policy
- Save to `stock_daily_market_metrics`
- Use `source='krx_open_api'`
- Keep `source='marcap'` data alongside it
- Unique key remains `(stock_id, trade_date, source)`
- Until KRX approval is completed, the UI should keep using `source='marcap'` for market metrics summary display.

## Role Split
- `marcap`
  - fallback and historical batch-friendly source
- `krx_open_api`
  - latest operating market metrics source

## Security Notes
- Do not commit the actual auth key
- Keep the real key only in `.env`
- Do not print the auth key in logs or probe output

## Test Notes
- Without key:
  - probe script should print `KRX_OPEN_API_AUTH_KEY is not configured.`
  - API should return a clear `503`
- With key:
  - verify both KOSPI and KOSDAQ responses for `2026-05-12`
  - verify `000020` and `454910`
  - if response is `401 Unauthorized API Call`, the key is loaded but the target KRX service is likely not approved for that auth key yet

## Current Authorization Diagnosis
- `KRX_OPEN_API_AUTH_KEY` loading is successful in the local environment.
- Current KRX response is `401 Unauthorized API Call`.
- This indicates that the code path and environment variable path are working, but the key likely does not have service approval for:
  - `유가증권 일별매매정보`
  - `코스닥 일별매매정보`
- Current API error mapping returns a project-friendly message:
  - `KRX Open API authorization failed. Check whether this API key is approved for the requested KRX daily trading information services.`
- Re-test after approval:
  - `.venv\Scripts\python.exe scripts\prototypes\krx_open_api_auth_probe.py`
  - `.venv\Scripts\python.exe scripts\prototypes\krx_open_api_market_metrics_probe.py`
  - `POST /market-metrics/collect/daily` with `{"trade_date":"2026-05-12","source":"krx_open_api"}`
